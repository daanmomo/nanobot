"""企业微信 (WeCom/WeChat Work) channel implementation."""

import asyncio
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import WeComConfig


class WeComChannel(BaseChannel):
    """
    企业微信 (WeCom) channel.

    使用企业微信 API 接收和发送消息。

    配置说明:
    - corpid: 企业ID
    - corpsecret: 应用Secret
    - agent_id: 应用AgentId
    - token: 用于验证消息签名
    - encoding_aes_key: 用于消息加解密 (可选)

    接收消息方式:
    - 回调模式: 配置企业微信后台回调URL，需要外网可访问
    - 主动轮询: 定期拉取消息 (不推荐)
    """

    name = "wecom"

    def __init__(self, config: WeComConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config = config
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._http_client: httpx.AsyncClient | None = None
        self._server = None

    async def start(self) -> None:
        """Start the WeCom channel."""
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30)

        logger.info(f"企业微信渠道启动 (corpid: {self.config.corpid[:8]}...)")

        # 刷新 access_token
        await self._refresh_access_token()

        if self.config.callback_enabled:
            # 启动回调服务器
            await self._start_callback_server()
        else:
            logger.info("企业微信回调模式未启用，仅支持发送消息")

        # 保持运行
        while self._running:
            # 定期刷新 token
            if time.time() > self._token_expires_at - 300:
                await self._refresh_access_token()
            await asyncio.sleep(60)

    async def stop(self) -> None:
        """Stop the WeCom channel."""
        self._running = False

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info("企业微信渠道已停止")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WeCom."""
        if not self._access_token:
            await self._refresh_access_token()

        if not self._access_token:
            logger.error("无法获取企业微信 access_token")
            return

        # 判断是发送给用户还是群聊
        chat_id = msg.chat_id
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self._access_token}"

        # 构建消息体
        if chat_id.startswith("@chatid:"):
            # 群聊消息
            chatid = chat_id.replace("@chatid:", "")
            payload = {
                "chatid": chatid,
                "msgtype": "text",
                "text": {"content": msg.content},
            }
            url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={self._access_token}"
        else:
            # 用户消息
            payload = {
                "touser": chat_id,
                "msgtype": "text",
                "agentid": self.config.agent_id,
                "text": {"content": msg.content},
            }

        try:
            resp = await self._http_client.post(url, json=payload)
            result = resp.json()

            if result.get("errcode") != 0:
                logger.error(f"企业微信发送消息失败: {result}")
            else:
                logger.debug(f"企业微信消息已发送: {chat_id}")
        except Exception as e:
            logger.error(f"企业微信发送消息异常: {e}")

    async def _refresh_access_token(self) -> None:
        """刷新 access_token."""
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.config.corpid,
            "corpsecret": self.config.corpsecret,
        }

        try:
            resp = await self._http_client.get(url, params=params)
            result = resp.json()

            if result.get("errcode") == 0:
                self._access_token = result["access_token"]
                self._token_expires_at = time.time() + result.get("expires_in", 7200)
                logger.debug("企业微信 access_token 已刷新")
            else:
                logger.error(f"获取企业微信 access_token 失败: {result}")
        except Exception as e:
            logger.error(f"获取企业微信 access_token 异常: {e}")

    async def _start_callback_server(self) -> None:
        """启动回调服务器接收消息."""
        from aiohttp import web

        app = web.Application()
        app.router.add_get(self.config.callback_path, self._handle_verify)
        app.router.add_post(self.config.callback_path, self._handle_callback)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.config.callback_host, self.config.callback_port)
        await site.start()

        logger.info(
            f"企业微信回调服务器启动: "
            f"http://{self.config.callback_host}:{self.config.callback_port}{self.config.callback_path}"
        )

    async def _handle_verify(self, request) -> Any:
        """处理企业微信 URL 验证请求."""
        from aiohttp import web

        msg_signature = request.query.get("msg_signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")
        echostr = request.query.get("echostr", "")

        # 验证签名
        if self._verify_signature(msg_signature, timestamp, nonce, echostr):
            # 解密 echostr
            if self.config.encoding_aes_key:
                echostr = self._decrypt_msg(echostr)
            return web.Response(text=echostr)
        else:
            logger.warning("企业微信验证签名失败")
            return web.Response(status=403)

    async def _handle_callback(self, request) -> Any:
        """处理企业微信消息回调."""
        from aiohttp import web

        msg_signature = request.query.get("msg_signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")

        body = await request.text()

        try:
            # 解析 XML
            root = ET.fromstring(body)
            encrypt = root.find("Encrypt")

            if encrypt is not None:
                encrypted_msg = encrypt.text
                # 验证签名
                if not self._verify_signature(msg_signature, timestamp, nonce, encrypted_msg):
                    logger.warning("企业微信消息签名验证失败")
                    return web.Response(status=403)

                # 解密消息
                if self.config.encoding_aes_key:
                    decrypted = self._decrypt_msg(encrypted_msg)
                    root = ET.fromstring(decrypted)

            # 解析消息
            msg_type = root.find("MsgType")
            if msg_type is not None and msg_type.text == "text":
                from_user = root.find("FromUserName")
                content = root.find("Content")
                agent_id = root.find("AgentID")

                if from_user is not None and content is not None:
                    sender_id = from_user.text
                    text = content.text

                    await self._handle_message(
                        sender_id=sender_id,
                        chat_id=sender_id,
                        content=text,
                        metadata={
                            "agent_id": agent_id.text if agent_id is not None else "",
                            "msg_type": "text",
                        }
                    )

            return web.Response(text="success")

        except Exception as e:
            logger.error(f"处理企业微信回调异常: {e}")
            return web.Response(status=500)

    def _verify_signature(self, signature: str, timestamp: str, nonce: str, data: str = "") -> bool:
        """验证消息签名."""
        token = self.config.token
        items = sorted([token, timestamp, nonce, data])
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        logger.debug(f"签名验证: token={token[:8]}..., timestamp={timestamp}, nonce={nonce}, data_len={len(data)}")
        logger.debug(f"计算签名: {sha1}, 收到签名: {signature}, 匹配: {sha1 == signature}")
        return sha1 == signature

    def _decrypt_msg(self, encrypted: str) -> str:
        """解密消息 (需要实现 AES 解密)."""
        # TODO: 实现 AES-256-CBC 解密
        # 需要使用 encoding_aes_key 解密
        logger.warning("消息解密未实现，返回原始内容")
        return encrypted
