"""WeChat channel implementation using bridge or wechaty."""

import asyncio
import json
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import WeChatConfig


class WeChatChannel(BaseChannel):
    """
    WeChat channel that connects to a WeChat bridge service.

    Supports multiple bridge implementations:
    - WebSocket bridge (default): connects to a custom WebSocket server
    - Wechaty: connects to a Wechaty Puppet Service via gRPC

    For WebSocket bridge mode, the bridge service handles:
    - WeChat Web/Desktop protocol
    - Message forwarding via WebSocket

    Bridge message format (WebSocket):
    - Inbound: {"type": "message", "sender": "wxid_xxx", "content": "hello", ...}
    - Outbound: {"type": "send", "to": "wxid_xxx", "text": "hello"}
    """

    name = "wechat"

    def __init__(self, config: WeChatConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WeChatConfig = config
        self._ws = None
        self._connected = False
        self._wechaty = None

    async def start(self) -> None:
        """Start the WeChat channel."""
        self._running = True

        if self.config.mode == "wechaty":
            await self._start_wechaty()
        else:
            await self._start_websocket()

    async def _start_websocket(self) -> None:
        """Start WebSocket bridge connection."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets 未安装，请运行: pip install websockets")
            return

        bridge_url = self.config.bridge_url
        logger.info(f"连接微信 bridge: {bridge_url}...")

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("微信 bridge 已连接")

                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error(f"处理 bridge 消息出错: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"微信 bridge 连接错误: {e}")

                if self._running:
                    logger.info("5 秒后重连...")
                    await asyncio.sleep(5)

    async def _start_wechaty(self) -> None:
        """Start Wechaty Puppet Service connection."""
        try:
            from wechaty import Wechaty, WechatyOptions
            from wechaty_puppet import PuppetOptions
        except ImportError:
            logger.error(
                "wechaty 未安装，请运行: pip install wechaty wechaty-puppet"
            )
            return

        logger.info("启动 Wechaty...")

        options = WechatyOptions(
            puppet="wechaty-puppet-service",
            puppet_options=PuppetOptions(
                token=self.config.wechaty_token,
                endpoint=self.config.wechaty_endpoint,
            )
        )

        self._wechaty = Wechaty(options)

        # Register event handlers
        self._wechaty.on("scan", self._on_wechaty_scan)
        self._wechaty.on("login", self._on_wechaty_login)
        self._wechaty.on("logout", self._on_wechaty_logout)
        self._wechaty.on("message", self._on_wechaty_message)

        try:
            await self._wechaty.start()
            self._connected = True

            while self._running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Wechaty 错误: {e}")
            self._connected = False

    async def stop(self) -> None:
        """Stop the WeChat channel."""
        self._running = False
        self._connected = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._wechaty:
            await self._wechaty.stop()
            self._wechaty = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WeChat."""
        if self.config.mode == "wechaty":
            await self._send_wechaty(msg)
        else:
            await self._send_websocket(msg)

    async def _send_websocket(self, msg: OutboundMessage) -> None:
        """Send message via WebSocket bridge."""
        if not self._ws or not self._connected:
            logger.warning("微信 bridge 未连接")
            return

        try:
            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content
            }
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")

    async def _send_wechaty(self, msg: OutboundMessage) -> None:
        """Send message via Wechaty."""
        if not self._wechaty or not self._connected:
            logger.warning("Wechaty 未连接")
            return

        try:
            contact = await self._wechaty.Contact.find(msg.chat_id)
            if contact:
                await contact.say(msg.content)
            else:
                # Try as room
                room = await self._wechaty.Room.find(msg.chat_id)
                if room:
                    await room.say(msg.content)
                else:
                    logger.warning(f"未找到联系人或群聊: {msg.chat_id}")
        except Exception as e:
            logger.error(f"发送微信消息失败: {e}")

    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the WebSocket bridge."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"无效的 JSON: {raw[:100]}")
            return

        msg_type = data.get("type")

        if msg_type == "message":
            sender = data.get("sender", "")
            content = data.get("content", "")
            room_id = data.get("room", "")

            # Extract wxid
            sender_id = sender.split("@")[0] if "@" in sender else sender

            # Use room_id for group messages, sender for private messages
            chat_id = room_id if room_id else sender

            # Skip self messages
            if data.get("is_self", False):
                return

            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": bool(room_id),
                    "room_id": room_id,
                    "sender_name": data.get("sender_name", ""),
                    "room_name": data.get("room_name", ""),
                }
            )

        elif msg_type == "status":
            status = data.get("status")
            logger.info(f"微信状态: {status}")

            if status == "connected" or status == "logged_in":
                self._connected = True
            elif status == "disconnected" or status == "logged_out":
                self._connected = False

        elif msg_type == "qr":
            qr_url = data.get("url", "")
            logger.info(f"请扫描二维码登录微信: {qr_url}")
            if data.get("qr_terminal"):
                logger.info(f"\n{data.get('qr_terminal')}")

        elif msg_type == "login":
            user_name = data.get("user_name", "")
            logger.info(f"微信已登录: {user_name}")
            self._connected = True

        elif msg_type == "logout":
            logger.info("微信已登出")
            self._connected = False

        elif msg_type == "error":
            logger.error(f"微信 bridge 错误: {data.get('error')}")

    # Wechaty event handlers
    async def _on_wechaty_scan(self, qr_code: str, status: int) -> None:
        """Handle Wechaty scan event."""
        logger.info(f"请扫描二维码登录 (status={status})")
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(qr_code)
            qr.make(fit=True)
            qr.print_ascii()
        except ImportError:
            logger.info(f"二维码 URL: {qr_code}")

    async def _on_wechaty_login(self, contact: Any) -> None:
        """Handle Wechaty login event."""
        logger.info(f"微信已登录: {contact.name}")
        self._connected = True

    async def _on_wechaty_logout(self, contact: Any) -> None:
        """Handle Wechaty logout event."""
        logger.info(f"微信已登出: {contact.name}")
        self._connected = False

    async def _on_wechaty_message(self, message: Any) -> None:
        """Handle Wechaty message event."""
        try:
            # Skip self messages
            if message.is_self():
                return

            talker = message.talker()
            room = message.room()
            content = message.text()

            sender_id = talker.id if talker else ""
            chat_id = room.id if room else sender_id

            # Check if we need @mention in group
            if room and self.config.require_mention_in_group:
                mention_self = await message.mention_self()
                if not mention_self:
                    return

            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "message_id": message.id,
                    "timestamp": message.date(),
                    "is_group": room is not None,
                    "room_id": room.id if room else "",
                    "sender_name": talker.name() if talker else "",
                    "room_name": await room.topic() if room else "",
                }
            )
        except Exception as e:
            logger.error(f"处理 Wechaty 消息出错: {e}")
