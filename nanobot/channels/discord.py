"""Discord channel implementation using Discord Gateway websocket."""

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp
import httpx
from aiohttp_socks import ProxyConnector
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import DiscordConfig

DISCORD_API_BASE = "https://discord.com/api/v10"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20MB


class DiscordChannel(BaseChannel):
    """Discord channel using Gateway websocket."""

    name = "discord"

    def __init__(self, config: DiscordConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: DiscordConfig = config
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._seq: int | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Start the Discord gateway connection."""
        if not self.config.token:
            logger.error("Discord bot token not configured")
            return

        self._running = True
        max_retries = 3
        retry_count = 0

        # Set up HTTP client — bypass env proxy unless explicitly configured
        http_kwargs: dict[str, Any] = {"timeout": 30.0}
        if self.config.proxy:
            http_kwargs["proxy"] = self.config.proxy
        else:
            http_kwargs["proxy"] = None
        self._http = httpx.AsyncClient(**http_kwargs)

        while self._running:
            try:
                logger.info("Connecting to Discord gateway...")
                # Create aiohttp session — bypass env proxy unless explicitly configured
                connector = None
                if self.config.proxy:
                    connector = ProxyConnector.from_url(self.config.proxy)
                else:
                    connector = aiohttp.TCPConnector()
                self._session = aiohttp.ClientSession(
                    connector=connector, trust_env=bool(self.config.proxy)
                )

                async with self._session.ws_connect(self.config.gateway_url) as ws:
                    self._ws = ws
                    retry_count = 0  # reset on successful connection
                    await self._gateway_loop()
                # Gateway loop exited normally (reconnect requested or session invalid)
                if self._running:
                    logger.info("Reconnecting to Discord gateway in 5 seconds...")
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Discord gateway error: {e}")
                if retry_count >= max_retries:
                    logger.error(
                        f"Discord failed to connect after {max_retries} attempts, giving up"
                    )
                    self._running = False
                    break
                if self._running:
                    logger.info(
                        f"Reconnecting to Discord gateway in 5 seconds "
                        f"(attempt {retry_count}/{max_retries})..."
                    )
                    await asyncio.sleep(5)
            finally:
                if self._session:
                    await self._session.close()
                    self._session = None

    async def stop(self) -> None:
        """Stop the Discord channel."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None
        if self._http:
            await self._http.aclose()
            self._http = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Discord REST API.

        Automatically splits messages that exceed Discord's 2000-character limit.
        """
        if not self._http:
            logger.warning("Discord HTTP client not initialized")
            return

        try:
            chunks = self._split_message(msg.content)
            for i, chunk in enumerate(chunks):
                payload: dict[str, Any] = {"content": chunk}

                # Only set reply reference on the first chunk
                if i == 0 and msg.reply_to:
                    payload["message_reference"] = {"message_id": msg.reply_to}
                    payload["allowed_mentions"] = {"replied_user": False}

                await self._send_payload(msg.chat_id, payload)
        finally:
            await self._stop_typing(msg.chat_id)

    async def _send_payload(self, channel_id: str, payload: dict[str, Any]) -> None:
        """Send a single payload to Discord with retry logic."""
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {self.config.token}"}

        for attempt in range(3):
            try:
                response = await self._http.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    logger.warning(f"Discord rate limited, retrying in {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Error sending Discord message: {e}")
                else:
                    await asyncio.sleep(1)

    @staticmethod
    def _split_message(content: str, limit: int = 2000) -> list[str]:
        """Split a message into chunks that fit within Discord's character limit.

        Tries to split at newlines, then spaces, then hard-cuts as a last resort.
        """
        if len(content) <= limit:
            return [content]

        chunks: list[str] = []
        while content:
            if len(content) <= limit:
                chunks.append(content)
                break

            # Try to split at last newline within limit
            split_at = content.rfind("\n", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                # Try to split at last space within limit
                split_at = content.rfind(" ", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                # Hard cut
                split_at = limit

            chunks.append(content[:split_at])
            content = content[split_at:].lstrip("\n")

        return chunks

    async def _gateway_loop(self) -> None:
        """Main gateway loop: identify, heartbeat, dispatch events."""
        if not self._ws:
            return

        async for msg in self._ws:
            logger.trace(f"Discord WS message type: {msg.type}")
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Discord gateway: {msg.data[:100]}")
                    continue

                op = data.get("op")
                event_type = data.get("t")
                seq = data.get("s")
                payload = data.get("d")

                if seq is not None:
                    self._seq = seq

                if op == 10:
                    # HELLO: start heartbeat and identify
                    logger.debug("Discord gateway HELLO received")
                    interval_ms = payload.get("heartbeat_interval", 45000)
                    await self._start_heartbeat(interval_ms / 1000)
                    await self._identify()
                    logger.debug("Discord IDENTIFY sent")
                elif op == 0 and event_type == "READY":
                    logger.info("Discord gateway READY")
                elif op == 0 and event_type == "MESSAGE_CREATE":
                    await self._handle_message_create(payload)
                elif op == 7:
                    # RECONNECT: exit loop to reconnect
                    logger.info("Discord gateway requested reconnect")
                    break
                elif op == 9:
                    # INVALID_SESSION: reconnect
                    logger.warning("Discord gateway invalid session")
                    break
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                close_code = self._ws.close_code if self._ws else None
                logger.warning(f"Discord WebSocket closed: {msg.type}, code={close_code}")
                if close_code == 4014:
                    logger.error("Discord error 4014: Disallowed intents - enable MESSAGE_CONTENT in Developer Portal")
                elif close_code == 4004:
                    logger.error("Discord error 4004: Authentication failed - check your bot token")
                break

        # Log when loop exits without hitting a break
        logger.debug(f"Discord gateway loop exited, ws close_code={self._ws.close_code if self._ws else 'N/A'}")

    async def _identify(self) -> None:
        """Send IDENTIFY payload."""
        if not self._ws:
            return

        identify = {
            "op": 2,
            "d": {
                "token": self.config.token,
                "intents": self.config.intents,
                "properties": {
                    "os": "nanobot",
                    "browser": "nanobot",
                    "device": "nanobot",
                },
            },
        }
        await self._ws.send_str(json.dumps(identify))

    async def _start_heartbeat(self, interval_s: float) -> None:
        """Start or restart the heartbeat loop."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        async def heartbeat_loop() -> None:
            while self._running and self._ws:
                payload = {"op": 1, "d": self._seq}
                try:
                    await self._ws.send_str(json.dumps(payload))
                except Exception as e:
                    logger.warning(f"Discord heartbeat failed: {e}")
                    break
                await asyncio.sleep(interval_s)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        """Handle incoming Discord messages."""
        author = payload.get("author") or {}
        if author.get("bot"):
            return

        sender_id = str(author.get("id", ""))
        channel_id = str(payload.get("channel_id", ""))
        content = payload.get("content") or ""

        if not sender_id or not channel_id:
            return

        if not self.is_allowed(sender_id):
            return

        content_parts = [content] if content else []
        media_paths: list[str] = []
        media_dir = Path.home() / ".nanobot" / "media"

        for attachment in payload.get("attachments") or []:
            url = attachment.get("url")
            filename = attachment.get("filename") or "attachment"
            size = attachment.get("size") or 0
            if not url or not self._http:
                continue
            if size and size > MAX_ATTACHMENT_BYTES:
                content_parts.append(f"[attachment: {filename} - too large]")
                continue
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
                file_path = media_dir / f"{attachment.get('id', 'file')}_{filename.replace('/', '_')}"
                resp = await self._http.get(url)
                resp.raise_for_status()
                file_path.write_bytes(resp.content)
                media_paths.append(str(file_path))
                content_parts.append(f"[attachment: {file_path}]")
            except Exception as e:
                logger.warning(f"Failed to download Discord attachment: {e}")
                content_parts.append(f"[attachment: {filename} - download failed]")

        reply_to = (payload.get("referenced_message") or {}).get("id")

        await self._start_typing(channel_id)

        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content="\n".join(p for p in content_parts if p) or "[empty message]",
            media=media_paths,
            metadata={
                "message_id": str(payload.get("id", "")),
                "guild_id": payload.get("guild_id"),
                "reply_to": reply_to,
            },
        )

    async def _start_typing(self, channel_id: str) -> None:
        """Start periodic typing indicator for a channel."""
        await self._stop_typing(channel_id)

        async def typing_loop() -> None:
            url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
            headers = {"Authorization": f"Bot {self.config.token}"}
            while self._running:
                try:
                    await self._http.post(url, headers=headers)
                except Exception:
                    pass
                await asyncio.sleep(8)

        self._typing_tasks[channel_id] = asyncio.create_task(typing_loop())

    async def _stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator for a channel."""
        task = self._typing_tasks.pop(channel_id, None)
        if task:
            task.cancel()
