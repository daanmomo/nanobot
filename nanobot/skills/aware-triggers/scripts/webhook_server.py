#!/usr/bin/env python3
"""Webhook 接收器 — 接收外部 HTTP POST 并触发动作。

借鉴 Clawith 的 webhook trigger 设计：
- 自动生成唯一 token 的 URL
- 支持多个 webhook 端点
- 接收到请求后执行配置的动作（飞书通知/执行脚本）

用法：
  # 启动 webhook 服务器
  python3 webhook_server.py --port 8765

  # 注册一个 webhook
  python3 webhook_server.py --register --name "github_ci" --action "notify" --message "CI 构建完成"

  # 外部系统 POST 到：http://localhost:8765/hook/<token>
"""

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# 配置文件
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
WEBHOOKS_FILE = CONFIG_DIR / "webhooks.json"

# 飞书 Webhook
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/4a70789f-f9ae-4e7b-bcde-95811b96a3c9"


def load_webhooks() -> dict:
    if WEBHOOKS_FILE.exists():
        return json.loads(WEBHOOKS_FILE.read_text())
    return {"webhooks": {}}


def save_webhooks(data: dict):
    WEBHOOKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def register_webhook(name: str, action: str = "notify", message: str = "", script: str = "") -> str:
    """注册一个新的 webhook，返回 token。"""
    data = load_webhooks()
    
    # 复用已有 token（和 Clawith 一样，重新启用时保持 URL 稳定）
    existing = data["webhooks"].get(name)
    if existing:
        token = existing["token"]
        print(f"♻️ 复用已有 webhook: {name} (token: {token})")
    else:
        token = secrets.token_urlsafe(16)
    
    data["webhooks"][name] = {
        "token": token,
        "action": action,  # notify | script
        "message": message,
        "script": script,
        "is_enabled": True,
        "fire_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_fired_at": None,
    }
    save_webhooks(data)
    print(f"✅ Webhook 注册成功:")
    print(f"   名称: {name}")
    print(f"   Token: {token}")
    print(f"   URL: http://localhost:8765/hook/{token}")
    return token


def send_feishu(message: str):
    """发送飞书通知。"""
    import urllib.request
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
            return resp.read().decode()
    except Exception as e:
        print(f"❌ 飞书通知失败: {e}")


class WebhookHandler(BaseHTTPRequestHandler):
    """处理 webhook 请求。"""
    
    def do_POST(self):
        # 解析路径
        path = self.path.strip("/")
        if not path.startswith("hook/"):
            self.send_error(404, "Not Found")
            return
        
        token = path[5:]  # 去掉 "hook/"
        
        # 查找对应的 webhook
        data = load_webhooks()
        target = None
        target_name = None
        for name, wh in data["webhooks"].items():
            if wh["token"] == token and wh.get("is_enabled", True):
                target = wh
                target_name = name
                break
        
        if not target:
            self.send_error(404, "Webhook not found or disabled")
            return
        
        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else ""
        
        # 解析 JSON body
        body_data = {}
        try:
            if body:
                body_data = json.loads(body)
        except json.JSONDecodeError:
            body_data = {"raw": body}
        
        print(f"🔔 Webhook [{target_name}] 触发！Body: {body[:200]}")
        
        # 执行动作
        action = target.get("action", "notify")
        if action == "notify":
            message = target.get("message", f"Webhook [{target_name}] 触发")
            if body_data:
                message += f"\n\n📦 Payload:\n{json.dumps(body_data, ensure_ascii=False, indent=2)[:500]}"
            send_feishu(message)
        
        elif action == "script":
            script = target.get("script", "")
            if script:
                try:
                    env_vars = {**dict(__import__('os').environ), "WEBHOOK_BODY": body[:10000]}
                    result = subprocess.run(
                        script, shell=True, capture_output=True, text=True,
                        timeout=60, env=env_vars
                    )
                    print(f"📜 脚本输出: {result.stdout[:500]}")
                    if result.returncode != 0:
                        print(f"⚠️ 脚本错误: {result.stderr[:500]}")
                except Exception as e:
                    print(f"❌ 脚本执行失败: {e}")
        
        # 更新状态
        target["fire_count"] = target.get("fire_count", 0) + 1
        target["last_fired_at"] = datetime.now(timezone.utc).isoformat()
        save_webhooks(data)
        
        # 返回成功
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps({"ok": True, "name": target_name, "fire_count": target["fire_count"]})
        self.wfile.write(response.encode())
    
    def do_GET(self):
        """健康检查 + 列出 webhooks。"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        
        if self.path == "/list":
            data = load_webhooks()
            summary = {}
            for name, wh in data["webhooks"].items():
                summary[name] = {
                    "url": f"http://localhost:8765/hook/{wh['token']}",
                    "action": wh.get("action"),
                    "is_enabled": wh.get("is_enabled", True),
                    "fire_count": wh.get("fire_count", 0),
                    "last_fired_at": wh.get("last_fired_at"),
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(summary, ensure_ascii=False, indent=2).encode())
            return
        
        self.send_error(404)
    
    def log_message(self, format, *args):
        """自定义日志格式。"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def run_server(port: int = 8765):
    """启动 webhook 服务器。"""
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"🚀 Webhook 服务器启动: http://localhost:{port}")
    print(f"   健康检查: http://localhost:{port}/health")
    print(f"   列出 webhooks: http://localhost:{port}/list")
    print(f"   接收 POST: http://localhost:{port}/hook/<token>")
    print("   Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webhook 接收器")
    parser.add_argument("--port", type=int, default=8765, help="服务器端口")
    parser.add_argument("--register", action="store_true", help="注册新 webhook")
    parser.add_argument("--name", default="", help="Webhook 名称")
    parser.add_argument("--action", default="notify", choices=["notify", "script"], help="触发动作")
    parser.add_argument("--message", default="", help="通知消息")
    parser.add_argument("--script", default="", help="要执行的脚本")
    
    args = parser.parse_args()
    
    if args.register:
        if not args.name:
            print("❌ 请提供 --name")
            sys.exit(1)
        register_webhook(args.name, args.action, args.message, args.script)
    else:
        run_server(args.port)
