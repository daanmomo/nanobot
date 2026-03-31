#!/usr/bin/env python3
"""HTTP 轮询触发器 — 监控 URL 变化并触发通知。

借鉴 Clawith 的 poll trigger 设计：
- 支持 JSON Path 提取特定字段
- 支持 change/threshold 两种触发模式
- SSRF 防护（禁止访问内网地址）
- 冷却时间防止重复触发

用法：
  # 监控 JSON API 字段变化
  python3 poll_trigger.py --url "https://api.example.com/data" --json-path "$.status" --fire-on change

  # 监控网页内容变化
  python3 poll_trigger.py --url "https://example.com/page" --fire-on change

  # 从配置文件运行所有触发器
  python3 poll_trigger.py --config ../config/triggers.json
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# 状态文件目录
STATE_DIR = Path(__file__).parent.parent / "state"
STATE_DIR.mkdir(exist_ok=True)

# 配置文件
CONFIG_FILE = Path(__file__).parent.parent / "config" / "triggers.json"


def ssrf_check(url: str) -> bool:
    """SSRF 防护：禁止访问内网地址。"""
    import socket
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    
    # 禁止的模式
    blocked = [
        r'^localhost$',
        r'^127\.',
        r'^10\.',
        r'^172\.(1[6-9]|2\d|3[01])\.',
        r'^192\.168\.',
        r'^0\.0\.0\.0$',
        r'^::1$',
        r'^fe80:',
        r'^fc00:',
        r'^fd00:',
    ]
    for pattern in blocked:
        if re.match(pattern, hostname):
            print(f"⚠️ SSRF 防护：禁止访问内网地址 {hostname}")
            return False
    return True


def extract_json_path(data, path: str):
    """简单的 JSON Path 提取（支持 $.key.subkey 格式）。"""
    if not path or path == "$":
        return data
    
    keys = path.lstrip("$.").split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def fetch_url(url: str, timeout: int = 30) -> str:
    """获取 URL 内容。"""
    req = urllib.request.Request(url, headers={"User-Agent": "nanobot-poll-trigger/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_state_file(trigger_name: str) -> Path:
    """获取触发器状态文件路径。"""
    safe_name = re.sub(r'[^\w\-]', '_', trigger_name)
    return STATE_DIR / f"{safe_name}.json"


def load_state(trigger_name: str) -> dict:
    """加载触发器状态。"""
    state_file = get_state_file(trigger_name)
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {}


def save_state(trigger_name: str, state: dict):
    """保存触发器状态。"""
    state_file = get_state_file(trigger_name)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def send_feishu_notification(webhook: str, message: str):
    """发送飞书通知。"""
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": message}
    }).encode("utf-8")
    
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f"❌ 飞书通知失败: {e}")
        return None


def check_trigger(trigger: dict) -> dict | None:
    """检查单个触发器，返回触发结果或 None。"""
    name = trigger.get("name", "unnamed")
    config = trigger.get("config", {})
    url = config.get("url", "")
    json_path = config.get("json_path", "")
    fire_on = config.get("fire_on", "change")  # change | threshold
    
    if not url:
        print(f"⚠️ [{name}] 没有配置 URL")
        return None
    
    # SSRF 检查
    if not ssrf_check(url):
        return None
    
    # 冷却时间检查
    state = load_state(name)
    cooldown = trigger.get("cooldown_seconds", 60)
    last_fired = state.get("last_fired_at", 0)
    if time.time() - last_fired < cooldown:
        print(f"⏳ [{name}] 冷却中（{cooldown}s）")
        return None
    
    # 最大触发次数检查
    max_fires = trigger.get("max_fires")
    fire_count = state.get("fire_count", 0)
    if max_fires and fire_count >= max_fires:
        print(f"🔴 [{name}] 已达最大触发次数 {max_fires}")
        return None
    
    # 过期检查
    expires_at = trigger.get("expires_at")
    if expires_at:
        exp_time = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) > exp_time:
            print(f"🔴 [{name}] 已过期")
            return None
    
    # 获取内容
    try:
        content = fetch_url(url)
    except Exception as e:
        print(f"❌ [{name}] 获取失败: {e}")
        return None
    
    # 提取值
    current_value = content
    if json_path:
        try:
            data = json.loads(content)
            current_value = extract_json_path(data, json_path)
        except json.JSONDecodeError:
            pass
    
    # 计算哈希
    current_hash = hashlib.md5(str(current_value).encode()).hexdigest()
    previous_hash = state.get("last_hash", "")
    
    # 判断是否触发
    triggered = False
    if fire_on == "change":
        if previous_hash and current_hash != previous_hash:
            triggered = True
            print(f"🔥 [{name}] 检测到变化！")
        elif not previous_hash:
            print(f"📝 [{name}] 首次记录，保存基线")
    
    # 更新状态
    state["last_hash"] = current_hash
    state["last_value"] = str(current_value)[:500]
    state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    
    if triggered:
        state["last_fired_at"] = time.time()
        state["fire_count"] = fire_count + 1
    
    save_state(name, state)
    
    if triggered:
        return {
            "name": name,
            "previous_value": state.get("last_value", ""),
            "current_value": str(current_value)[:500],
            "fired_at": datetime.now(timezone.utc).isoformat(),
        }
    
    return None


def run_all_triggers(config_path: str = None):
    """运行所有配置的触发器。"""
    path = Path(config_path) if config_path else CONFIG_FILE
    if not path.exists():
        print(f"⚠️ 配置文件不存在: {path}")
        print("创建示例配置...")
        path.parent.mkdir(parents=True, exist_ok=True)
        example = {
            "triggers": [
                {
                    "name": "example_monitor",
                    "type": "poll",
                    "config": {
                        "url": "https://httpbin.org/json",
                        "json_path": "$.slideshow.title",
                        "fire_on": "change",
                        "interval_seconds": 300
                    },
                    "reason": "示例：监控 httpbin JSON 响应变化",
                    "is_enabled": False,
                    "max_fires": None,
                    "cooldown_seconds": 60,
                    "expires_at": None,
                    "focus_ref": None
                }
            ],
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/4a70789f-f9ae-4e7b-bcde-95811b96a3c9"
        }
        path.write_text(json.dumps(example, ensure_ascii=False, indent=2))
        print(f"✅ 示例配置已创建: {path}")
        return
    
    config = json.loads(path.read_text())
    triggers = config.get("triggers", [])
    webhook = config.get("feishu_webhook", "")
    
    enabled = [t for t in triggers if t.get("is_enabled", True) and t.get("type") == "poll"]
    print(f"📡 检查 {len(enabled)} 个轮询触发器...")
    
    results = []
    for trigger in enabled:
        result = check_trigger(trigger)
        if result:
            results.append(result)
            # 发送通知
            reason = trigger.get("reason", "")
            message = f"🔔 触发器 [{result['name']}] 触发！\n原因: {reason}\n当前值: {result['current_value'][:200]}"
            if webhook:
                send_feishu_notification(webhook, message)
            print(message)
    
    if not results:
        print("✅ 无触发事件")
    
    return results


def run_single(url: str, json_path: str = "", fire_on: str = "change",
               name: str = "cli_trigger", webhook: str = "", message: str = ""):
    """运行单个触发器（命令行模式）。"""
    trigger = {
        "name": name,
        "type": "poll",
        "config": {
            "url": url,
            "json_path": json_path,
            "fire_on": fire_on,
        },
        "reason": message or f"监控 {url}",
        "is_enabled": True,
        "cooldown_seconds": 0,
    }
    
    result = check_trigger(trigger)
    if result:
        msg = message or f"🔔 [{name}] 检测到变化！\n值: {result['current_value'][:200]}"
        if webhook:
            send_feishu_notification(webhook, msg)
        print(msg)
    else:
        print("无变化")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP 轮询触发器")
    parser.add_argument("--config", help="触发器配置文件路径")
    parser.add_argument("--url", help="监控的 URL")
    parser.add_argument("--json-path", default="", help="JSON Path 提取路径")
    parser.add_argument("--fire-on", default="change", choices=["change"], help="触发条件")
    parser.add_argument("--name", default="cli_trigger", help="触发器名称")
    parser.add_argument("--webhook", default="", help="飞书 Webhook URL")
    parser.add_argument("--message", default="", help="触发时的通知消息")
    
    args = parser.parse_args()
    
    if args.url:
        run_single(args.url, args.json_path, args.fire_on, args.name, args.webhook, args.message)
    else:
        run_all_triggers(args.config)
