#!/usr/bin/env python3
"""智能心跳 — 定期自主醒来，检查 focus.md 并执行到期任务。

借鉴 Clawith 的 Heartbeat 设计：
- 读取 focus.md 检查待办事项
- 检查所有 poll 触发器
- 生成心跳报告
- 可选推送飞书通知

用法：
  # 执行一次心跳
  python3 heartbeat.py

  # 心跳 + 推送飞书
  python3 heartbeat.py --notify

  # 心跳 + 运行 poll 触发器
  python3 heartbeat.py --check-triggers

  # 全部（推荐配合 cron 使用）
  python3 heartbeat.py --notify --check-triggers
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 路径
MEMORY_DIR = Path("/Users/momo/.nanobot/workspace/memory")
FOCUS_FILE = MEMORY_DIR / "focus.md"
TASK_HISTORY_FILE = MEMORY_DIR / "task_history.md"
HEARTBEAT_LOG = Path(__file__).parent.parent / "state" / "heartbeat.log"

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/4a70789f-f9ae-4e7b-bcde-95811b96a3c9"


def read_focus() -> dict:
    """读取 focus.md，解析 checklist 项。"""
    if not FOCUS_FILE.exists():
        return {"pending": [], "in_progress": [], "completed": []}
    
    content = FOCUS_FILE.read_text(encoding="utf-8")
    
    pending = []
    in_progress = []
    completed = []
    
    for line in content.split("\n"):
        line = line.strip()
        # 解析 checklist 格式
        match = re.match(r'^- \[(.)\] (.+)$', line)
        if match:
            status = match.group(1)
            item = match.group(2).strip()
            if status == ' ':
                pending.append(item)
            elif status == '/':
                in_progress.append(item)
            elif status == 'x':
                completed.append(item)
    
    return {
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
    }


def check_poll_triggers() -> list:
    """运行所有 poll 触发器。"""
    try:
        from poll_trigger import run_all_triggers
        return run_all_triggers() or []
    except Exception as e:
        print(f"⚠️ Poll 触发器检查失败: {e}")
        return []


def generate_report(focus: dict, trigger_results: list = None) -> str:
    """生成心跳报告。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    lines = [f"💓 心跳报告 — {now}", ""]
    
    # Focus 状态
    lines.append("📋 Focus 状态:")
    if focus["in_progress"]:
        lines.append(f"  🔄 进行中: {len(focus['in_progress'])} 项")
        for item in focus["in_progress"]:
            lines.append(f"    - {item}")
    
    if focus["pending"]:
        lines.append(f"  📝 待办: {len(focus['pending'])} 项")
        for item in focus["pending"]:
            lines.append(f"    - {item}")
    
    if focus["completed"]:
        lines.append(f"  ✅ 已完成: {len(focus['completed'])} 项")
    
    if not focus["in_progress"] and not focus["pending"]:
        lines.append("  ✨ 无待办事项")
    
    # 触发器结果
    if trigger_results:
        lines.append("")
        lines.append(f"🔔 触发器事件: {len(trigger_results)} 个")
        for r in trigger_results:
            lines.append(f"  - [{r['name']}] 值变化: {r['current_value'][:100]}")
    
    # 建议
    lines.append("")
    if len(focus.get("completed", [])) >= 5:
        lines.append("💡 建议: 已完成项较多，考虑归档到 task_history.md")
    
    return "\n".join(lines)


def send_feishu(message: str):
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except Exception as e:
        print(f"❌ 飞书通知失败: {e}")
        return False


def archive_completed(focus: dict):
    """将已完成项归档到 task_history.md（当超过 5 个时）。"""
    if len(focus["completed"]) < 5:
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 追加到 task_history.md
    archive_lines = [f"\n## {today} (自动归档)\n"]
    for item in focus["completed"]:
        archive_lines.append(f"- ✅ {item}")
    archive_lines.append("")
    
    with open(TASK_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(archive_lines))
    
    # 从 focus.md 中移除已完成项
    if FOCUS_FILE.exists():
        content = FOCUS_FILE.read_text(encoding="utf-8")
        new_lines = []
        for line in content.split("\n"):
            if not re.match(r'^- \[x\] ', line.strip()):
                new_lines.append(line)
        FOCUS_FILE.write_text("\n".join(new_lines), encoding="utf-8")
    
    print(f"📦 已归档 {len(focus['completed'])} 个已完成项到 task_history.md")


def save_heartbeat_log(report: str):
    """保存心跳日志。"""
    HEARTBEAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    # 只保留最近 50 条
    existing = []
    if HEARTBEAT_LOG.exists():
        existing = HEARTBEAT_LOG.read_text(encoding="utf-8").split("\n---\n")
        existing = existing[-49:]  # 保留最近 49 条
    
    existing.append(report)
    HEARTBEAT_LOG.write_text("\n---\n".join(existing), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="智能心跳")
    parser.add_argument("--notify", action="store_true", help="推送飞书通知")
    parser.add_argument("--check-triggers", action="store_true", help="检查 poll 触发器")
    parser.add_argument("--auto-archive", action="store_true", help="自动归档已完成项")
    args = parser.parse_args()
    
    print("💓 心跳开始...")
    
    # 1. 读取 focus
    focus = read_focus()
    print(f"📋 Focus: {len(focus['in_progress'])} 进行中, {len(focus['pending'])} 待办, {len(focus['completed'])} 已完成")
    
    # 2. 检查触发器
    trigger_results = []
    if args.check_triggers:
        trigger_results = check_poll_triggers()
    
    # 3. 生成报告
    report = generate_report(focus, trigger_results)
    print(report)
    
    # 4. 保存日志
    save_heartbeat_log(report)
    
    # 5. 自动归档
    if args.auto_archive:
        archive_completed(focus)
    
    # 6. 推送通知
    if args.notify:
        # 只在有待办事项或触发器事件时通知
        if focus["in_progress"] or focus["pending"] or trigger_results:
            send_feishu(report)
            print("📤 已推送飞书通知")
        else:
            print("✨ 无待办事项，跳过通知")
    
    print("💓 心跳完成")


if __name__ == "__main__":
    main()
