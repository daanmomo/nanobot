"""飞书 (Feishu) 渠道实现，使用 lark-oapi SDK 的 WebSocket 长连接。"""

import asyncio
import json
import re
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import FeishuConfig

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        Emoji,
        GetImageRequest,
        P2ImMessageReceiveV1,
        PatchMessageRequest,
        PatchMessageRequestBody,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None
    Emoji = None

# Message type display mapping
MSG_TYPE_MAP = {
    "image": "[image]",
    "audio": "[audio]",
    "file": "[file]",
    "sticker": "[sticker]",
}


class FeishuChannel(BaseChannel):
    """
    飞书 (Feishu) 渠道，使用 WebSocket 长连接。

    通过 WebSocket 接收事件，无需公网 IP 或 webhook。

    需要：
    - 飞书开放平台的 App ID 和 App Secret
    - 启用机器人能力
    - 启用事件订阅 (im.message.receive_v1)
    """

    name = "feishu"

    # 流式更新配置
    STREAM_UPDATE_INTERVAL = 0.5  # 最小更新间隔（秒）
    STREAM_PLACEHOLDER = "思考中..."  # 初始占位文本

    def __init__(self, config: FeishuConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client: Any = None
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()  # Ordered dedup cache
        self._loop: asyncio.AbstractEventLoop | None = None
        # 流式消息状态: {chat_id: {"message_id": str, "content": str, "last_update": float}}
        self._stream_states: dict[str, dict] = {}

    async def start(self) -> None:
        """Start the Feishu bot with WebSocket long connection."""
        if not FEISHU_AVAILABLE:
            logger.error("Feishu SDK not installed. Run: pip install lark-oapi")
            return

        if not self.config.app_id or not self.config.app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return

        # 解析域名：feishu（飞书国内）或 lark（飞书国际版）
        domain_url = (
            lark.LARK_DOMAIN
            if self.config.domain.lower() == "lark"
            else lark.FEISHU_DOMAIN
        )

        self._running = True
        self._loop = asyncio.get_running_loop()

        # 创建飞书客户端用于发送消息
        self._client = lark.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .domain(domain_url) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # Create event handler (only register message receive, ignore other events)
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key or "",
            self.config.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).build()

        # Create WebSocket client for long connection (CRITICAL to suppress 401/reconnect/error noise)
        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.CRITICAL,
            domain=domain_url,
        )

        # Start WebSocket client in a separate thread with reconnect loop
        def run_ws():
            while self._running:
                try:
                    self._ws_client.start()
                except Exception as e:
                    logger.warning(f"Feishu WebSocket error: {e}")
                if self._running:
                    import time; time.sleep(5)

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        logger.info("Feishu bot started with WebSocket long connection")
        logger.info("No public IP required - using WebSocket to receive events")

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Feishu bot."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception as e:
                logger.warning(f"Error stopping WebSocket client: {e}")
        logger.info("Feishu bot stopped")

    def _add_reaction_sync(self, message_id: str, emoji_type: str) -> None:
        """Sync helper for adding reaction (runs in thread pool)."""
        try:
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()

            response = self._client.im.v1.message_reaction.create(request)

            if not response.success():
                logger.warning(f"Failed to add reaction: code={response.code}, msg={response.msg}")
            else:
                logger.debug(f"Added {emoji_type} reaction to message {message_id}")
        except Exception as e:
            logger.warning(f"Error adding reaction: {e}")

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """
        Add a reaction emoji to a message (non-blocking).
        
        Common emoji types: THUMBSUP, OK, EYES, DONE, OnIt, HEART
        """
        if not self._client or not Emoji:
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_reaction_sync, message_id, emoji_type)

    # Regex to match markdown tables (header + separator + data rows)
    _TABLE_RE = re.compile(
        r"((?:^[ \t]*\|.+\|[ \t]*\n)(?:^[ \t]*\|[-:\s|]+\|[ \t]*\n)(?:^[ \t]*\|.+\|[ \t]*\n?)+)",
        re.MULTILINE,
    )

    @staticmethod
    def _parse_md_table(table_text: str) -> dict | None:
        """Parse a markdown table into a Feishu table element."""
        lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            return None
        split = lambda l: [c.strip() for c in l.strip("|").split("|")]
        headers = split(lines[0])
        rows = [split(l) for l in lines[2:]]
        columns = [{"tag": "column", "name": f"c{i}", "display_name": h, "width": "auto"}
                   for i, h in enumerate(headers)]
        return {
            "tag": "table",
            "page_size": len(rows) + 1,
            "columns": columns,
            "rows": [{f"c{i}": r[i] if i < len(r) else "" for i in range(len(headers))} for r in rows],
        }

    _MAX_TABLES = 8  # Feishu card table limit is ~10, use 8 to be safe

    def _build_card_elements(self, content: str) -> list[dict]:
        """Split content into markdown + table elements for Feishu card."""
        elements, last_end, table_count = [], 0, 0
        for m in self._TABLE_RE.finditer(content):
            before = content[last_end:m.start()].strip()
            if before:
                elements.append({"tag": "markdown", "content": before})
            # Convert to native table only if under limit, else keep as markdown
            if table_count < self._MAX_TABLES:
                parsed = self._parse_md_table(m.group(1))
                if parsed:
                    elements.append(parsed)
                    table_count += 1
                else:
                    elements.append({"tag": "markdown", "content": m.group(1)})
            else:
                elements.append({"tag": "markdown", "content": m.group(1)})
            last_end = m.end()
        remaining = content[last_end:].strip()
        if remaining:
            elements.append({"tag": "markdown", "content": remaining})
        return elements or [{"tag": "markdown", "content": content}]

    # Maximum characters per card (Feishu card limit ~30KB, ~4000 chars to be safe with tables/JSON overhead)
    _MAX_CARD_CHARS = 4000

    @staticmethod
    def _split_content(content: str, max_chars: int) -> list[str]:
        """Split long content into chunks, preferring to break at section boundaries.

        Tries to split at '---' (horizontal rule), then '## ' (heading), then '\n\n' (paragraph).
        """
        if len(content) <= max_chars:
            return [content]

        chunks = []
        remaining = content

        while remaining:
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            # Find the best split point within max_chars
            segment = remaining[:max_chars]
            split_point = -1

            # Priority 1: split at '---' (section divider)
            idx = segment.rfind("\n---\n")
            if idx > max_chars // 4:  # Don't split too early
                split_point = idx + 1  # Keep the --- on the previous chunk's end

            # Priority 2: split at '## ' (heading)
            if split_point == -1:
                idx = segment.rfind("\n## ")
                if idx > max_chars // 4:
                    split_point = idx + 1  # Start new chunk with the heading

            # Priority 3: split at '\n\n' (paragraph)
            if split_point == -1:
                idx = segment.rfind("\n\n")
                if idx > max_chars // 4:
                    split_point = idx + 1

            # Priority 4: split at '\n' (any newline)
            if split_point == -1:
                idx = segment.rfind("\n")
                if idx > max_chars // 4:
                    split_point = idx + 1

            # Fallback: hard cut
            if split_point == -1:
                split_point = max_chars

            chunks.append(remaining[:split_point].rstrip())
            remaining = remaining[split_point:].lstrip()

        return chunks

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Feishu. Auto-splits long messages into multiple cards."""
        if not self._client:
            logger.warning("Feishu client not initialized")
            return

        # Determine receive_id_type based on chat_id format
        # open_id starts with "ou_", chat_id starts with "oc_"
        if msg.chat_id.startswith("oc_"):
            receive_id_type = "chat_id"
        else:
            receive_id_type = "open_id"

        # Split long content into chunks
        chunks = self._split_content(msg.content, self._MAX_CARD_CHARS)
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            # Add part indicator for multi-part messages
            if total > 1:
                chunk = f"**({i + 1}/{total})**\n\n{chunk}"

            # Try sending as interactive card first
            success = await self._send_card(msg.chat_id, receive_id_type, chunk)
            if not success:
                # Fallback: send as plain text
                logger.info(f"Card failed for part {i + 1}/{total}, falling back to plain text")
                await self._send_text(msg.chat_id, receive_id_type, chunk)

            # Small delay between multi-part messages to maintain order
            if total > 1 and i < total - 1:
                await asyncio.sleep(0.5)

    async def _send_card(self, chat_id: str, receive_id_type: str, content: str) -> bool:
        """Send message as interactive card. Returns True on success."""
        try:
            elements = self._build_card_elements(content)
            card = {
                "config": {"wide_screen_mode": True},
                "elements": elements,
            }
            card_json = json.dumps(card, ensure_ascii=False)

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(card_json)
                    .build()
                ).build()

            response = self._client.im.v1.message.create(request)

            if response.success():
                logger.debug(f"Feishu card sent to {chat_id}")
                return True

            # Check for table limit error (code=230099, ErrCode=11310)
            error_info = f"code={response.code}, msg={response.msg}"
            if response.code == 230099 or "table" in str(response.msg).lower():
                logger.warning(f"Feishu card table limit exceeded: {error_info}")
                return False

            logger.error(f"Failed to send Feishu card: {error_info}")
            return False
        except Exception as e:
            logger.error(f"Error sending Feishu card: {e}")
            return False

    async def _send_text(self, chat_id: str, receive_id_type: str, content: str) -> bool:
        """Send message as plain text. Returns True on success."""
        try:
            text_content = json.dumps({"text": content}, ensure_ascii=False)

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(text_content)
                    .build()
                ).build()

            response = self._client.im.v1.message.create(request)

            if response.success():
                logger.debug(f"Feishu text sent to {chat_id}")
                return True

            logger.error(
                f"Failed to send Feishu text: code={response.code}, "
                f"msg={response.msg}, log_id={response.get_log_id()}"
            )
            return False
        except Exception as e:
            logger.error(f"Error sending Feishu text: {e}")
            return False

    # ==================== 流式卡片支持 ====================

    async def stream_start(self, chat_id: str) -> str | None:
        """
        开始流式输出：创建占位卡片，返回 message_id。

        Args:
            chat_id: 会话 ID

        Returns:
            message_id 或 None（失败时）
        """
        if not self._client:
            return None

        receive_id_type = "chat_id" if chat_id.startswith("oc_") else "open_id"

        # 创建初始卡片
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [{"tag": "markdown", "content": self.STREAM_PLACEHOLDER}],
        }
        card_json = json.dumps(card, ensure_ascii=False)

        try:
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(card_json)
                    .build()
                ).build()

            response = self._client.im.v1.message.create(request)

            if response.success():
                message_id = response.data.message_id
                import time
                self._stream_states[chat_id] = {
                    "message_id": message_id,
                    "content": "",
                    "last_update": time.time(),
                }
                logger.debug(f"Feishu stream started: {message_id}")
                return message_id
            else:
                logger.error(f"Failed to create stream card: {response.code} {response.msg}")
                return None
        except Exception as e:
            logger.error(f"Error creating stream card: {e}")
            return None

    async def stream_update(self, chat_id: str, content: str, force: bool = False) -> bool:
        """
        更新流式卡片内容。

        Args:
            chat_id: 会话 ID
            content: 当前累积的完整内容
            force: 是否强制更新（忽略时间间隔）

        Returns:
            是否更新成功
        """
        state = self._stream_states.get(chat_id)
        if not state:
            return False

        import time
        now = time.time()

        # 限制更新频率
        if not force and (now - state["last_update"]) < self.STREAM_UPDATE_INTERVAL:
            return True  # 跳过但不算失败

        # 内容没变化则跳过
        if content == state["content"]:
            return True

        message_id = state["message_id"]
        state["content"] = content
        state["last_update"] = now

        # 构建更新卡片
        elements = self._build_card_elements(content) if content.strip() else [
            {"tag": "markdown", "content": self.STREAM_PLACEHOLDER}
        ]
        card = {
            "config": {"wide_screen_mode": True},
            "elements": elements,
        }
        card_json = json.dumps(card, ensure_ascii=False)

        try:
            request = PatchMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    PatchMessageRequestBody.builder()
                    .content(card_json)
                    .build()
                ).build()

            response = self._client.im.v1.message.patch(request)

            if response.success():
                logger.debug(f"Feishu stream updated: {len(content)} chars")
                return True
            else:
                logger.warning(f"Failed to update stream: {response.code} {response.msg}")
                return False
        except Exception as e:
            logger.warning(f"Error updating stream: {e}")
            return False

    async def stream_end(self, chat_id: str, final_content: str) -> bool:
        """
        结束流式输出：发送最终内容并清理状态。

        Args:
            chat_id: 会话 ID
            final_content: 最终完整内容

        Returns:
            是否成功
        """
        state = self._stream_states.get(chat_id)
        if not state:
            # 没有流式状态，直接发送完整消息
            return await self._send_card(
                chat_id,
                "chat_id" if chat_id.startswith("oc_") else "open_id",
                final_content
            )

        # 最后一次强制更新
        success = await self.stream_update(chat_id, final_content, force=True)

        # 清理状态
        del self._stream_states[chat_id]
        logger.debug(f"Feishu stream ended for {chat_id}")

        return success

    # ==================== 图片下载支持 ====================

    _IMAGE_CACHE_DIR = Path(tempfile.gettempdir()) / "nanobot_feishu_images"

    def _download_image_sync(self, image_key: str) -> str | None:
        """
        Download image from Feishu by image_key. Returns local file path or None.
        
        Uses GET /open-apis/im/v1/images/{image_key} via lark-oapi SDK.
        """
        if not self._client or not FEISHU_AVAILABLE:
            return None

        try:
            # Ensure cache directory exists
            self._IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Check cache first
            cached = self._IMAGE_CACHE_DIR / f"{image_key}.png"
            if cached.exists() and cached.stat().st_size > 0:
                logger.debug(f"Feishu image cache hit: {image_key}")
                return str(cached)

            # Download via SDK
            request = GetImageRequest.builder().image_key(image_key).build()
            response = self._client.im.v1.image.get(request)

            if not response.success():
                logger.warning(f"Failed to download image {image_key}: code={response.code}, msg={response.msg}")
                return None

            # Write to file
            image_data = response.file.read() if hasattr(response.file, 'read') else response.file
            if not image_data:
                logger.warning(f"Empty image data for {image_key}")
                return None

            cached.write_bytes(image_data)
            logger.info(f"Feishu image downloaded: {image_key} ({len(image_data)} bytes)")
            return str(cached)

        except Exception as e:
            logger.error(f"Error downloading Feishu image {image_key}: {e}")
            return None

    async def _download_image(self, image_key: str) -> str | None:
        """Async wrapper for image download."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._download_image_sync, image_key)

    def _on_message_sync(self, data: "P2ImMessageReceiveV1") -> None:
        """
        Sync handler for incoming messages (called from WebSocket thread).
        Schedules async handling in the main event loop.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)

    async def _on_message(self, data: "P2ImMessageReceiveV1") -> None:
        """Handle incoming message from Feishu."""
        try:
            event = data.event
            message = event.message
            sender = event.sender

            # Deduplication check
            message_id = message.message_id
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None

            # Trim cache: keep most recent 500 when exceeds 1000
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

            # Skip bot messages
            sender_type = sender.sender_type
            if sender_type == "bot":
                return

            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = message.chat_id
            chat_type = message.chat_type  # "p2p" or "group"
            msg_type = message.message_type

            # Add reaction to indicate "seen"
            await self._add_reaction(message_id, "THUMBSUP")

            # Parse message content and handle media
            media: list[str] = []

            if msg_type == "text":
                try:
                    content = json.loads(message.content).get("text", "")
                except json.JSONDecodeError:
                    content = message.content or ""
            elif msg_type == "image":
                # Extract image_key and download the image
                content = "[image]"
                try:
                    image_key = json.loads(message.content).get("image_key", "")
                    if image_key:
                        local_path = await self._download_image(image_key)
                        if local_path:
                            media.append(local_path)
                            content = "用户发送了一张图片，请查看并描述/分析图片内容。"
                        else:
                            content = "[image] (图片下载失败)"
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to parse image content: {e}")
                    content = "[image] (图片解析失败)"
            elif msg_type == "post":
                # Rich text (post) may contain images inline
                try:
                    post_data = json.loads(message.content)
                    # Extract text from post content
                    parts = []
                    for lang_content in post_data.values():
                        if not isinstance(lang_content, dict):
                            # Some post formats have string values (e.g. "title" at top level)
                            if isinstance(lang_content, str) and lang_content:
                                parts.append(lang_content)
                            continue
                        title = lang_content.get("title", "")
                        if title:
                            parts.append(title)
                        for line in lang_content.get("content", []):
                            for element in line:
                                tag = element.get("tag", "")
                                if tag == "text":
                                    parts.append(element.get("text", ""))
                                elif tag == "a":
                                    parts.append(element.get("text", "") + " " + element.get("href", ""))
                                elif tag == "img":
                                    img_key = element.get("image_key", "")
                                    if img_key:
                                        local_path = await self._download_image(img_key)
                                        if local_path:
                                            media.append(local_path)
                    content = "\n".join(parts) if parts else "[post]"
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to parse post content: {e}")
                    content = "[post]"
            else:
                content = MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]")

            if not content and not media:
                return

            # Forward to message bus
            reply_to = chat_id if chat_type == "group" else sender_id
            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
                media=media if media else None,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                }
            )

        except Exception as e:
            logger.error(f"Error processing Feishu message: {e}")
