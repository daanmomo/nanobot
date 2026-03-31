#!/usr/bin/env python3
"""智能心跳 v2 — 学自 OpenClaw/Clawith 的增强版心跳系统。

新增能力（相比 v1）：
- 智能调度：不同检查项有不同频率，跳过最近已检查的
- 安静时间：23:00-08:00 不主动打扰（除非紧急）
- 状态追踪：heartbeat_state.json 记录上次检查时间
- 记忆维护：定期回顾 daily notes → 提炼到 MEMORY.md
- 自动归档：已完成项超过 5 个自动迁移到 task_history.md
- HEARTBEAT.md：支持用户自定义心跳 checklist

用法：
  python3 heartbeat_v2.py                    # 标准心跳
  python3 heartbeat_v2.py --force            # 忽略安静时间
  python3 heartbeat_v2.py --notify           # 有事时推送飞书
  python3 heartbeat_v2.py --full             # 全量检查（忽略间隔）
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================================
# Paths
# ============================================================================
WORKSPACE = Path("/Users/momo/.nanobot/workspace")
MEMORY_DIR = WORKSPACE / "memory"
FOCUS_FILE = MEMORY_DIR / "focus.md"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"
TASK_HISTORY = MEMORY_DIR / "task_history.md"
HEARTBEAT_MD = WORKSPACE / "HEARTBEAT.md"

SKILL_DIR = Path(__file__).parent.parent
STATE_DIR = SKILL_DIR / "state"
CONFIG_DIR = SKILL_DIR / "config"
HEARTBEAT_STATE = CONFIG_DIR / "heartbeat_state.json"
HEARTBEAT_LOG = STATE_DIR / "heartbeat_v2.log"

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/4a70789f-f9ae-4e7b-bcde-95811b96a3c9"

# ============================================================================
# State Management
# ============================================================================

def load_state() -> dict:
    """加载心跳状态。"""
    if HEARTBEAT_STATE.exists():
        try:
            return json.loads(HEARTBEAT_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "lastChecks": {},
        "quietHours": {"start": 23, "end": 8},
        "checkIntervals": {
            "focus": 1800,           # 30 min
            "memory_maintenance": 86400,  # 24h
            "triggers": 3600,        # 1h
            "news": 14400,           # 4h
        },
        "stats": {
            "totalBeats": 0,
            "lastBeatAt": None,
            "silentBeats": 0,
            "activeBeats": 0,
        }
    }


def save_state(state: dict):
    """保存心跳状态。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def is_quiet_hours(state: dict) -> bool:
    """判断当前是否在安静时间。"""
    now_hour = datetime.now().hour
    start = state.get("quietHours", {}).get("start", 23)
    end = state.get("quietHours", {}).get("end", 8)
    if start > end:  # 跨午夜 (e.g. 23-8)
        return now_hour >= start or now_hour < end
    else:
        return start <= now_hour < end


def should_check(state: dict, check_name: str, force_full: bool = False) -> bool:
    """判断某个检查项是否需要执行。"""
    if force_full:
        return True
    last = state.get("lastChecks", {}).get(check_name)
    if last is None:
        return True
    interval = state.get("checkIntervals", {}).get(check_name, 3600)
    return (time.time() - last) >= interval


def mark_checked(state: dict, check_name: str):
    """标记某个检查项已执行。"""
    if "lastChecks" not in state:
        state["lastChecks"] = {}
    state["lastChecks"][check_name] = time.time()


# ============================================================================
# Check: Focus
# ============================================================================

def check_focus() -> dict:
    """读取 focus.md，解析 checklist 项。"""
    if not FOCUS_FILE.exists():
        return {"pending": [], "in_progress": [], "completed": []}

    content = FOCUS_FILE.read_text(encoding="utf-8")
    result = {"pending": [], "in_progress": [], "completed": []}

    for line in content.split("\n"):
        line = line.strip()
        match = re.match(r'^- \[(.)\] (.+)$', line)
        if match:
            status, item = match.group(1), match.group(2).strip()
            if status == ' ':
                result["pending"].append(item)
            elif status == '/':
                result["in_progress"].append(item)
            elif status == 'x':
                result["completed"].append(item)

    return result


# ============================================================================
# Check: HEARTBEAT.md (user-defined checklist)
# ============================================================================

def check_heartbeat_md() -> list:
    """读取 HEARTBEAT.md 中用户自定义的心跳任务。"""
    if not HEARTBEAT_MD.exists():
        return []

    content = HEARTBEAT_MD.read_text(encoding="utf-8").strip()
    # 忽略纯注释文件
    lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
    return lines


# ============================================================================
# Check: Memory Maintenance
# ============================================================================

def check_memory_maintenance() -> dict:
    """检查记忆维护状态。"""
    result = {
        "daily_notes_count": 0,
        "memory_size_kb": 0,
        "oldest_unreviewed": None,
        "needs_maintenance": False,
    }

    # 统计 daily notes
    if MEMORY_DIR.exists():
        daily_files = sorted(MEMORY_DIR.glob("20??-??-??.md"))
        result["daily_notes_count"] = len(daily_files)

        # 找最旧的未回顾的（超过 7 天的 daily note）
        cutoff = datetime.now() - timedelta(days=7)
        for f in daily_files:
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    result["oldest_unreviewed"] = f.stem
                    result["needs_maintenance"] = True
                    break
            except ValueError:
                continue

    # MEMORY.md 大小
    if MEMORY_FILE.exists():
        result["memory_size_kb"] = round(MEMORY_FILE.stat().st_size / 1024, 1)

    return result


# ============================================================================
# Auto Archive
# ============================================================================

def auto_archive(focus: dict) -> int:
    """将已完成项归档到 task_history.md。返回归档数量。"""
    if len(focus["completed"]) < 5:
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    archive_lines = [f"\n## {today} (自动归档)\n"]
    for item in focus["completed"]:
        archive_lines.append(f"- ✅ {item}")
    archive_lines.append("")

    TASK_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(TASK_HISTORY, "a", encoding="utf-8") as f:
        f.write("\n".join(archive_lines))

    # 从 focus.md 移除已完成项
    if FOCUS_FILE.exists():
        content = FOCUS_FILE.read_text(encoding="utf-8")
        new_lines = [l for l in content.split("\n")
                     if not re.match(r'^- \[x\] ', l.strip())]
        FOCUS_FILE.write_text("\n".join(new_lines), encoding="utf-8")

    return len(focus["completed"])


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    focus: dict,
    heartbeat_tasks: list,
    memory_status: dict,
    archived_count: int,
    checks_run: list,
    quiet: bool,
) -> str:
    """生成心跳报告。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    lines = [f"💓 心跳报告 v2 — {now}"]

    if quiet:
        lines.append("🌙 安静时间模式")

    lines.append("")

    # Focus
    lines.append("📋 **Focus 状态**")
    if focus["in_progress"]:
        for item in focus["in_progress"]:
            lines.append(f"  🔄 {item}")
    if focus["pending"]:
        for item in focus["pending"]:
            lines.append(f"  📝 {item}")
    if not focus["in_progress"] and not focus["pending"]:
        lines.append("  ✨ 无待办事项")
    if focus["completed"]:
        lines.append(f"  ✅ 已完成: {len(focus['completed'])} 项")

    # HEARTBEAT.md tasks
    if heartbeat_tasks:
        lines.append("")
        lines.append("📌 **HEARTBEAT.md 任务**")
        for task in heartbeat_tasks:
            lines.append(f"  → {task}")

    # Memory maintenance
    if memory_status.get("needs_maintenance"):
        lines.append("")
        lines.append("🧠 **记忆维护提醒**")
        lines.append(f"  📝 Daily notes: {memory_status['daily_notes_count']} 个")
        lines.append(f"  💾 MEMORY.md: {memory_status['memory_size_kb']} KB")
        if memory_status["oldest_unreviewed"]:
            lines.append(f"  ⚠️ 最旧未回顾: {memory_status['oldest_unreviewed']}")

    # Archive
    if archived_count > 0:
        lines.append("")
        lines.append(f"📦 已归档 {archived_count} 个已完成项")

    # Checks run
    lines.append("")
    lines.append(f"🔍 本次检查: {', '.join(checks_run)}")

    return "\n".join(lines)


# ============================================================================
# Notification
# ============================================================================

def send_feishu(message: str) -> bool:
    """发送飞书通知。"""
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": message}
    }).encode("utf-8")

    req = urllib.request.Request(
        FEISHU_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception as e:
        print(f"❌ 飞书通知失败: {e}")
        return False


# ============================================================================
# Logging
# ============================================================================

def save_log(report: str):
    """保存心跳日志（保留最近 100 条）。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    existing = []
    if HEARTBEAT_LOG.exists():
        existing = HEARTBEAT_LOG.read_text(encoding="utf-8").split("\n===\n")
        existing = existing[-99:]
    existing.append(report)
    HEARTBEAT_LOG.write_text("\n===\n".join(existing), encoding="utf-8")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="智能心跳 v2")
    parser.add_argument("--force", action="store_true", help="忽略安静时间")
    parser.add_argument("--full", action="store_true", help="全量检查（忽略间隔）")
    parser.add_argument("--notify", action="store_true", help="有事时推送飞书")
    args = parser.parse_args()

    state = load_state()
    quiet = is_quiet_hours(state)
    checks_run = []
    has_actionable = False

    # 安静时间：除非 --force，否则只做最小检查
    if quiet and not args.force:
        print("🌙 安静时间，最小检查模式")

    # 1. Focus（总是检查）
    focus = check_focus()
    checks_run.append("focus")
    mark_checked(state, "focus")
    if focus["in_progress"] or focus["pending"]:
        has_actionable = True

    # 2. HEARTBEAT.md
    heartbeat_tasks = check_heartbeat_md()
    if heartbeat_tasks:
        has_actionable = True

    # 3. Memory maintenance（按间隔）
    memory_status = {}
    if should_check(state, "memory_maintenance", args.full):
        memory_status = check_memory_maintenance()
        checks_run.append("memory")
        mark_checked(state, "memory_maintenance")
        if memory_status.get("needs_maintenance"):
            has_actionable = True

    # 4. Auto archive
    archived_count = auto_archive(focus)

    # 5. Generate report
    report = generate_report(
        focus, heartbeat_tasks, memory_status,
        archived_count, checks_run, quiet
    )
    print(report)

    # 6. Update stats
    stats = state.setdefault("stats", {})
    stats["totalBeats"] = stats.get("totalBeats", 0) + 1
    stats["lastBeatAt"] = time.time()
    if has_actionable:
        stats["activeBeats"] = stats.get("activeBeats", 0) + 1
    else:
        stats["silentBeats"] = stats.get("silentBeats", 0) + 1

    save_state(state)
    save_log(report)

    # 7. Notify（安静时间不通知，除非 --force）
    if args.notify and has_actionable:
        if not quiet or args.force:
            send_feishu(report)
            print("📤 已推送飞书")
        else:
            print("🌙 安静时间，跳过通知")

    print(f"💓 心跳完成 (#{stats['totalBeats']})")


if __name__ == "__main__":
    main()
