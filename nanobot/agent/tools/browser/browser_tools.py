"""
浏览器自动化工具

基于 Playwright 提供浏览器自动化所需的工具类，包括：
- 页面导航与内容获取
- 截图
- 元素交互
- 表单填写
- 用户登录
- 数据提取
- 文件下载
"""

import asyncio
import json
from typing import Any

from nanobot.agent.tools.base import Tool


def _run_sync(func, *args, **kwargs):
    """Helper to run sync Playwright functions in a thread."""
    return func(*args, **kwargs)


class BrowserOpenTool(Tool):
    """打开页面并获取内容工具。"""

    @property
    def name(self) -> str:
        return "browser_open"

    @property
    def description(self) -> str:
        return "使用浏览器打开 URL 并获取页面内容，适用于 JavaScript 渲染的页面。系统会根据网站自动选择最佳等待策略"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要打开的 URL",
                },
                "wait_until": {
                    "type": "string",
                    "description": "等待条件（可选，留空自动选择）：load/domcontentloaded/networkidle",
                    "enum": ["load", "domcontentloaded", "networkidle"],
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（毫秒，可选，默认 30000）",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        wait_until = kwargs.get("wait_until")  # None 时自动选择
        timeout = kwargs.get("timeout")
        result = await asyncio.to_thread(
            _run_sync, browser_api.open_url, url, wait_until=wait_until, timeout=timeout
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserScreenshotTool(Tool):
    """页面截图工具。"""

    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return "对网页进行截图，可截取整个页面或特定元素。系统会根据网站自动选择最佳等待策略"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要截图的 URL",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "是否截取整个页面（默认 true）",
                },
                "selector": {
                    "type": "string",
                    "description": "特定元素的 CSS 选择器（可选）",
                },
                "filename": {
                    "type": "string",
                    "description": "保存的文件名（可选）",
                },
                "wait_until": {
                    "type": "string",
                    "description": "等待条件（可选，留空自动选择）",
                    "enum": ["load", "domcontentloaded", "networkidle"],
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（毫秒，可选）",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        full_page = kwargs.get("full_page", True)
        selector = kwargs.get("selector")
        filename = kwargs.get("filename")
        wait_until = kwargs.get("wait_until")
        timeout = kwargs.get("timeout")
        result = await asyncio.to_thread(
            _run_sync,
            browser_api.take_screenshot,
            url,
            full_page,
            selector,
            filename,
            wait_until,
            timeout,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserClickTool(Tool):
    """点击元素工具。"""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "点击页面上的元素，如按钮、链接等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "页面 URL",
                },
                "selector": {
                    "type": "string",
                    "description": "要点击元素的 CSS 选择器",
                },
                "wait_after": {
                    "type": "integer",
                    "description": "点击后等待时间（毫秒，默认 2000）",
                },
            },
            "required": ["url", "selector"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        selector = kwargs.get("selector", "")
        wait_after = kwargs.get("wait_after", 2000)
        result = await asyncio.to_thread(
            _run_sync, browser_api.click_element, url, selector, wait_after
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserFillFormTool(Tool):
    """填写表单工具。"""

    @property
    def name(self) -> str:
        return "browser_fill_form"

    @property
    def description(self) -> str:
        return "填写网页表单字段"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "页面 URL",
                },
                "fields": {
                    "type": "object",
                    "description": "字段映射，格式为 {CSS选择器: 值}",
                    "additionalProperties": {"type": "string"},
                },
                "submit_selector": {
                    "type": "string",
                    "description": "提交按钮的 CSS 选择器（可选）",
                },
            },
            "required": ["url", "fields"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        fields = kwargs.get("fields", {})
        submit_selector = kwargs.get("submit_selector")
        result = await asyncio.to_thread(
            _run_sync, browser_api.fill_form, url, fields, submit_selector
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserLoginTool(Tool):
    """用户登录工具。"""

    @property
    def name(self) -> str:
        return "browser_login"

    @property
    def description(self) -> str:
        return "执行网站登录操作，支持保存会话以便后续使用"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "登录页面 URL",
                },
                "username_selector": {
                    "type": "string",
                    "description": "用户名输入框的 CSS 选择器",
                },
                "password_selector": {
                    "type": "string",
                    "description": "密码输入框的 CSS 选择器",
                },
                "username": {
                    "type": "string",
                    "description": "用户名",
                },
                "password": {
                    "type": "string",
                    "description": "密码",
                },
                "submit_selector": {
                    "type": "string",
                    "description": "登录按钮的 CSS 选择器",
                },
                "success_indicator": {
                    "type": "string",
                    "description": "登录成功后出现的元素选择器（可选）",
                },
                "save_session": {
                    "type": "string",
                    "description": "保存会话的名称（可选，用于后续免登录访问）",
                },
            },
            "required": ["url", "username_selector", "password_selector",
                         "username", "password", "submit_selector"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        result = await asyncio.to_thread(
            _run_sync,
            browser_api.login,
            url=kwargs.get("url", ""),
            username_selector=kwargs.get("username_selector", ""),
            password_selector=kwargs.get("password_selector", ""),
            username=kwargs.get("username", ""),
            password=kwargs.get("password", ""),
            submit_selector=kwargs.get("submit_selector", ""),
            success_indicator=kwargs.get("success_indicator"),
            save_session=kwargs.get("save_session"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserLoadSessionTool(Tool):
    """加载会话工具。"""

    @property
    def name(self) -> str:
        return "browser_load_session"

    @property
    def description(self) -> str:
        return "加载已保存的登录会话，访问需要登录的页面"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要访问的 URL",
                },
                "session_name": {
                    "type": "string",
                    "description": "会话名称（之前 browser_login 时保存的名称）",
                },
            },
            "required": ["url", "session_name"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        session_name = kwargs.get("session_name", "")
        result = await asyncio.to_thread(_run_sync, browser_api.load_session, url, session_name)
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserExtractTool(Tool):
    """数据提取工具。"""

    @property
    def name(self) -> str:
        return "browser_extract"

    @property
    def description(self) -> str:
        return "从网页中提取结构化数据"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "页面 URL",
                },
                "selectors": {
                    "type": "object",
                    "description": "数据选择器映射，格式为 {字段名: CSS选择器}",
                    "additionalProperties": {"type": "string"},
                },
                "list_selector": {
                    "type": "string",
                    "description": "列表容器的 CSS 选择器（用于提取多条数据）",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大提取数量（默认 50）",
                },
            },
            "required": ["url", "selectors"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        selectors = kwargs.get("selectors", {})
        list_selector = kwargs.get("list_selector")
        limit = kwargs.get("limit", 50)
        result = await asyncio.to_thread(
            _run_sync, browser_api.extract_data, url, selectors, list_selector, limit
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserDownloadTool(Tool):
    """文件下载工具。"""

    @property
    def name(self) -> str:
        return "browser_download"

    @property
    def description(self) -> str:
        return "从网页下载文件，支持需要登录的下载"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "下载页面 URL 或直接文件 URL",
                },
                "click_selector": {
                    "type": "string",
                    "description": "触发下载的元素选择器（可选）",
                },
                "filename": {
                    "type": "string",
                    "description": "保存的文件名（可选）",
                },
                "session_name": {
                    "type": "string",
                    "description": "使用的会话名称（用于需要登录的下载）",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        click_selector = kwargs.get("click_selector")
        filename = kwargs.get("filename")
        session_name = kwargs.get("session_name")
        result = await asyncio.to_thread(
            _run_sync, browser_api.download_file, url, click_selector, filename, session_name
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserExecuteJSTool(Tool):
    """执行 JavaScript 工具。"""

    @property
    def name(self) -> str:
        return "browser_execute_js"

    @property
    def description(self) -> str:
        return "在网页中执行 JavaScript 代码并返回结果"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "页面 URL",
                },
                "script": {
                    "type": "string",
                    "description": "要执行的 JavaScript 代码",
                },
            },
            "required": ["url", "script"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        script = kwargs.get("script", "")
        result = await asyncio.to_thread(_run_sync, browser_api.execute_javascript, url, script)
        return json.dumps(result, ensure_ascii=False, indent=2)


class BrowserWaitTool(Tool):
    """等待元素工具。"""

    @property
    def name(self) -> str:
        return "browser_wait"

    @property
    def description(self) -> str:
        return "等待页面元素出现或消失"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "页面 URL",
                },
                "selector": {
                    "type": "string",
                    "description": "要等待的元素 CSS 选择器",
                },
                "state": {
                    "type": "string",
                    "description": "等待状态：visible/hidden/attached/detached",
                    "enum": ["visible", "hidden", "attached", "detached"],
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（毫秒，默认 30000）",
                },
            },
            "required": ["url", "selector"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.browser import browser_api

        url = kwargs.get("url", "")
        selector = kwargs.get("selector", "")
        state = kwargs.get("state", "visible")
        timeout = kwargs.get("timeout", 30000)
        result = await asyncio.to_thread(
            _run_sync, browser_api.wait_for_element, url, selector, state, timeout
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
