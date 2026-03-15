"""
浏览器自动化 API 封装模块

基于 Playwright 提供浏览器自动化功能：
- 页面导航
- 元素交互
- 表单填写
- 用户登录
- 截图
- 文件下载
- 数据提取

参考: https://playwright.dev/python/
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nanobot.agent.tools.common import api_error_handler, format_datetime

logger = logging.getLogger(__name__)

_PLAYWRIGHT_INSTALL_HINT = "playwright 未安装，请运行: pip install playwright && playwright install chromium"

# ==================== 网站策略配置 ====================

# 不同类型网站的等待策略
# networkidle: 等待网络空闲（适合静态页面）
# domcontentloaded: DOM 加载完成（适合动态资源多的网站）
# load: 页面加载完成（折中方案）

SITE_STRATEGIES: dict[str, dict[str, Any]] = {
    # 金融类网站 - 动态资源多，使用 domcontentloaded
    "eastmoney.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "10jqka.com.cn": {"wait_until": "domcontentloaded", "timeout": 30000},
    "sina.com.cn": {"wait_until": "domcontentloaded", "timeout": 30000},
    "163.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "qq.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "ifeng.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "hexun.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "cnstock.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "stockstar.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "jrj.com.cn": {"wait_until": "domcontentloaded", "timeout": 30000},
    "xueqiu.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    # 电商类 - 动态资源多
    "taobao.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "jd.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "tmall.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    # 社交媒体 - SPA 应用
    "weibo.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "zhihu.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "bilibili.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    "douyin.com": {"wait_until": "domcontentloaded", "timeout": 30000},
    # 默认策略
    "_default": {"wait_until": "networkidle", "timeout": 30000},
}


def get_site_strategy(url: str) -> dict[str, Any]:
    """
    根据 URL 获取对应的网站策略。

    参数：
        url: 目标 URL

    返回：
        网站策略配置 (wait_until, timeout)
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 移除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]

        # 精确匹配
        if domain in SITE_STRATEGIES:
            return SITE_STRATEGIES[domain]

        # 匹配主域名（如 finance.eastmoney.com -> eastmoney.com）
        for site_domain, strategy in SITE_STRATEGIES.items():
            if site_domain != "_default" and domain.endswith(site_domain):
                return strategy

        return SITE_STRATEGIES["_default"]
    except Exception:
        return SITE_STRATEGIES["_default"]


def smart_goto(
    page,
    url: str,
    wait_until: str | None = None,
    timeout: int | None = None,
    fallback: bool = True,
) -> dict[str, Any]:
    """
    智能页面导航，支持自动回退策略。

    参数：
        page: Playwright page 对象
        url: 目标 URL
        wait_until: 等待条件（可选，为 None 时自动选择）
        timeout: 超时时间（可选，为 None 时使用默认值）
        fallback: 是否在超时时自动回退到更宽松的策略

    返回：
        导航结果信息
    """
    strategy = get_site_strategy(url)
    actual_wait = wait_until or strategy["wait_until"]
    actual_timeout = timeout or strategy["timeout"]

    result = {
        "url": url,
        "strategy_used": actual_wait,
        "timeout_used": actual_timeout,
        "fallback_used": False,
    }

    try:
        page.goto(url, wait_until=actual_wait, timeout=actual_timeout)
        return result
    except Exception as e:
        error_msg = str(e)
        # 如果是超时错误且启用了回退
        if fallback and "Timeout" in error_msg and actual_wait == "networkidle":
            logger.warning(f"networkidle 超时，回退到 domcontentloaded: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=actual_timeout)
                result["strategy_used"] = "domcontentloaded"
                result["fallback_used"] = True
                return result
            except Exception as e2:
                raise e2
        raise e


def _get_download_dir() -> Path:
    """获取下载目录。"""
    download_dir = Path.home() / ".nanobot" / "workspace" / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    return download_dir


def _get_screenshot_dir() -> Path:
    """获取截图目录。"""
    screenshot_dir = Path.home() / ".nanobot" / "workspace" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    return screenshot_dir


def _get_cookies_dir() -> Path:
    """获取 cookies 存储目录。"""
    cookies_dir = Path.home() / ".nanobot" / "workspace" / "browser_cookies"
    cookies_dir.mkdir(parents=True, exist_ok=True)
    return cookies_dir


def sync_cookies_to_gstack(cookies: list[dict], session_name: str) -> str | None:
    """
    将 nanobot 的 cookies 同步到 gstack 可导入的 JSON 文件。

    在 login() 保存会话 cookies 后调用，使 gstack browse 可以通过
    `$B cookie-import` 导入这些 cookies。

    参数：
        cookies: Playwright context.cookies() 返回的 cookie 列表
        session_name: 会话名称（用于日志记录）

    返回：
        写入的文件路径，或 None（如果失败）
    """
    try:
        cookies_dir = _get_cookies_dir()
        gstack_path = cookies_dir / "_for_gstack.json"
        with open(gstack_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookies synced to gstack: {gstack_path} (session: {session_name})")
        return str(gstack_path)
    except Exception as e:
        logger.warning(f"Failed to sync cookies to gstack: {e}")
        return None


def load_gstack_cookies(context) -> int:
    """
    从 gstack 导出的 cookies 文件加载 cookies 到 Playwright context。

    检查 gstack 导出的 cookies 文件（~/.nanobot/workspace/browser_cookies/_gstack.json），
    如果存在则添加到 Playwright context。

    参数：
        context: Playwright BrowserContext 对象

    返回：
        加载的 cookie 数量
    """
    gstack_cookies_path = _get_cookies_dir() / "_gstack.json"
    if not gstack_cookies_path.exists():
        return 0

    try:
        with open(gstack_cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if cookies and isinstance(cookies, list):
            context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} gstack cookies")
            return len(cookies)
    except Exception as e:
        logger.warning(f"Failed to load gstack cookies: {e}")
    return 0


def _import_playwright():
    """延迟导入 playwright。"""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError as e:
        raise ImportError(_PLAYWRIGHT_INSTALL_HINT) from e


# ==================== 页面导航 ====================


@api_error_handler("打开页面失败")
def open_url(
    url: str,
    wait_until: str | None = None,
    timeout: int | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """
    打开 URL 并获取页面内容。

    参数：
        url: 要打开的 URL
        wait_until: 等待条件 (load/domcontentloaded/networkidle)，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值
        headless: 是否无头模式

    返回：
        包含页面信息的字典
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        load_gstack_cookies(context)
        page = context.new_page()

        nav_result = smart_goto(page, url, wait_until=wait_until, timeout=timeout)

        title = page.title()
        current_url = page.url

        try:
            body_text = page.locator("body").text_content()
            body_text = re.sub(r'\s+', ' ', body_text or "").strip()[:5000]
        except Exception:
            body_text = ""

        try:
            headings = []
            for h in page.locator("h1, h2, h3").all()[:10]:
                text = h.text_content()
                if text:
                    headings.append(text.strip()[:100])
        except Exception:
            headings = []

        browser.close()

    return {
        "url": current_url,
        "title": title,
        "headings": headings,
        "content_preview": body_text[:2000] if body_text else "",
        "strategy_used": nav_result.get("strategy_used"),
        "update_time": format_datetime(),
    }


# ==================== 截图功能 ====================


@api_error_handler("截图失败")
def take_screenshot(
    url: str,
    full_page: bool = True,
    selector: str | None = None,
    filename: str | None = None,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    对页面进行截图。

    参数：
        url: 要截图的 URL
        full_page: 是否截取整个页面
        selector: 特定元素的选择器（可选）
        filename: 保存的文件名（可选）
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        包含截图路径的字典
    """
    sync_playwright = _import_playwright()
    screenshot_dir = _get_screenshot_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        nav_result = smart_goto(page, url, wait_until=wait_until, timeout=timeout)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        save_path = screenshot_dir / filename

        if selector:
            element = page.locator(selector)
            element.screenshot(path=str(save_path))
        else:
            page.screenshot(path=str(save_path), full_page=full_page)

        browser.close()

    return {
        "path": str(save_path),
        "url": url,
        "full_page": full_page,
        "selector": selector,
        "strategy_used": nav_result.get("strategy_used"),
        "update_time": format_datetime(),
    }


# ==================== 元素交互 ====================


@api_error_handler("点击元素失败")
def click_element(
    url: str,
    selector: str,
    wait_after: int = 2000,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    点击页面元素。

    参数：
        url: 页面 URL
        selector: 元素选择器
        wait_after: 点击后等待时间（毫秒）
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        操作结果
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        smart_goto(page, url, wait_until=wait_until, timeout=timeout)
        page.locator(selector).click()
        page.wait_for_timeout(wait_after)

        new_url = page.url
        new_title = page.title()

        browser.close()

    return {
        "success": True,
        "selector": selector,
        "original_url": url,
        "new_url": new_url,
        "new_title": new_title,
        "update_time": format_datetime(),
    }


@api_error_handler("填写表单失败")
def fill_form(
    url: str,
    fields: dict[str, str],
    submit_selector: str | None = None,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    填写表单字段。

    参数：
        url: 页面 URL
        fields: 字段映射 {选择器: 值}
        submit_selector: 提交按钮选择器（可选）
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        操作结果
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        smart_goto(page, url, wait_until=wait_until, timeout=timeout)

        filled_fields = []
        for selector, value in fields.items():
            try:
                page.fill(selector, value)
                filled_fields.append(selector)
            except Exception as e:
                logger.warning(f"填写字段 {selector} 失败: {e}")

        submitted = False
        if submit_selector:
            try:
                page.click(submit_selector)
                # 提交后使用 domcontentloaded，避免超时
                page.wait_for_load_state("domcontentloaded")
                submitted = True
            except Exception as e:
                logger.warning(f"提交表单失败: {e}")

        new_url = page.url
        new_title = page.title()

        browser.close()

    return {
        "success": True,
        "filled_fields": filled_fields,
        "submitted": submitted,
        "new_url": new_url,
        "new_title": new_title,
        "update_time": format_datetime(),
    }


# ==================== 用户登录 ====================


@api_error_handler("登录失败")
def login(
    url: str,
    username_selector: str,
    password_selector: str,
    username: str,
    password: str,
    submit_selector: str,
    success_indicator: str | None = None,
    save_session: str | None = None,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    执行用户登录。

    参数：
        url: 登录页面 URL
        username_selector: 用户名输入框选择器
        password_selector: 密码输入框选择器
        username: 用户名
        password: 密码
        submit_selector: 提交按钮选择器
        success_indicator: 登录成功标识选择器（可选）
        save_session: 保存会话的名称（可选）
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        登录结果
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = context.new_page()

        smart_goto(page, url, wait_until=wait_until, timeout=timeout)
        page.fill(username_selector, username)
        page.fill(password_selector, password)
        page.click(submit_selector)
        # 登录后使用 domcontentloaded，避免超时
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        login_success = False
        if success_indicator:
            try:
                page.wait_for_selector(success_indicator, timeout=10000)
                login_success = True
            except Exception:
                login_success = False
        else:
            login_success = page.url != url

        cookies_path = None
        gstack_path = None
        if save_session and login_success:
            cookies = context.cookies()
            cookies_path = _get_cookies_dir() / f"{save_session}.json"
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            gstack_path = sync_cookies_to_gstack(cookies, save_session)

        new_url = page.url
        new_title = page.title()

        browser.close()

    return {
        "success": login_success,
        "url": new_url,
        "title": new_title,
        "cookies_saved": str(cookies_path) if cookies_path else None,
        "gstack_cookies_synced": gstack_path,
        "update_time": format_datetime(),
    }


@api_error_handler("加载会话失败")
def load_session(
    url: str,
    session_name: str,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    加载已保存的会话（cookies）并访问页面。

    参数：
        url: 要访问的 URL
        session_name: 会话名称
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        页面信息
    """
    sync_playwright = _import_playwright()
    cookies_path = _get_cookies_dir() / f"{session_name}.json"

    if not cookies_path.exists():
        return {"error": f"未找到会话 {session_name}"}

    with open(cookies_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        load_gstack_cookies(context)

        page = context.new_page()
        smart_goto(page, url, wait_until=wait_until, timeout=timeout)

        title = page.title()
        current_url = page.url
        logged_in = url != current_url or "login" not in current_url.lower()

        browser.close()

    return {
        "session_name": session_name,
        "url": current_url,
        "title": title,
        "logged_in": logged_in,
        "update_time": format_datetime(),
    }


# ==================== 数据提取 ====================


@api_error_handler("数据提取失败")
def extract_data(
    url: str,
    selectors: dict[str, str],
    list_selector: str | None = None,
    limit: int = 50,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    从页面提取数据。

    参数：
        url: 页面 URL
        selectors: 数据选择器映射 {字段名: 选择器}
        list_selector: 列表容器选择器（可选，用于提取列表数据）
        limit: 最大提取数量
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        提取的数据
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        smart_goto(page, url, wait_until=wait_until, timeout=timeout)

        extracted_data = []

        if list_selector:
            items = page.locator(list_selector).all()[:limit]
            for item in items:
                item_data = {}
                for field_name, selector in selectors.items():
                    try:
                        element = item.locator(selector)
                        if element.count() > 0:
                            item_data[field_name] = element.first.text_content().strip()
                    except Exception:
                        continue
                if item_data:
                    extracted_data.append(item_data)
        else:
            single_data = {}
            for field_name, selector in selectors.items():
                try:
                    element = page.locator(selector)
                    if element.count() > 0:
                        single_data[field_name] = element.first.text_content().strip()
                except Exception:
                    continue
            if single_data:
                extracted_data.append(single_data)

        browser.close()

    return {
        "url": url,
        "count": len(extracted_data),
        "data": extracted_data,
        "update_time": format_datetime(),
    }


# ==================== 文件下载 ====================


@api_error_handler("文件下载失败")
def download_file(
    url: str,
    click_selector: str | None = None,
    filename: str | None = None,
    session_name: str | None = None,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    下载文件。

    参数：
        url: 下载页面 URL 或直接文件 URL
        click_selector: 触发下载的元素选择器（可选）
        filename: 保存的文件名（可选）
        session_name: 使用的会话名称（可选，用于需要登录的下载）
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        下载结果
    """
    sync_playwright = _import_playwright()
    download_dir = _get_download_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)

        if session_name:
            cookies_path = _get_cookies_dir() / f"{session_name}.json"
            if cookies_path.exists():
                with open(cookies_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                context.add_cookies(cookies)

        page = context.new_page()

        if click_selector:
            smart_goto(page, url, wait_until=wait_until, timeout=timeout)
            with page.expect_download(timeout=60000) as download_info:
                page.click(click_selector)
        else:
            with page.expect_download(timeout=60000) as download_info:
                page.goto(url)

        download = download_info.value

        if filename:
            save_path = download_dir / filename
        else:
            save_path = download_dir / download.suggested_filename

        download.save_as(str(save_path))

        browser.close()

    return {
        "success": True,
        "path": str(save_path),
        "filename": save_path.name,
        "size": save_path.stat().st_size if save_path.exists() else 0,
        "update_time": format_datetime(),
    }


# ==================== JavaScript 执行 ====================


@api_error_handler("执行 JavaScript 失败")
def execute_javascript(
    url: str,
    script: str,
    wait_until: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    在页面中执行 JavaScript。

    参数：
        url: 页面 URL
        script: 要执行的 JavaScript 代码
        wait_until: 等待条件，为 None 时自动选择
        timeout: 超时时间（毫秒），为 None 时使用默认值

    返回：
        执行结果
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        smart_goto(page, url, wait_until=wait_until, timeout=timeout)
        result = page.evaluate(script)

        browser.close()

    return {
        "url": url,
        "script": script[:200] + "..." if len(script) > 200 else script,
        "result": result,
        "update_time": format_datetime(),
    }


# ==================== 页面等待 ====================


@api_error_handler("等待元素失败")
def wait_for_element(
    url: str,
    selector: str,
    state: str = "visible",
    timeout: int = 30000,
) -> dict[str, Any]:
    """
    等待页面元素出现。

    参数：
        url: 页面 URL
        selector: 元素选择器
        state: 等待状态 (attached/detached/visible/hidden)
        timeout: 超时时间（毫秒）

    返回：
        等待结果
    """
    sync_playwright = _import_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(url, wait_until="domcontentloaded")

        start_time = time.time()
        try:
            page.locator(selector).wait_for(state=state, timeout=timeout)
            found = True
            wait_time = time.time() - start_time
        except Exception:
            found = False
            wait_time = timeout / 1000

        element_text = None
        if found:
            try:
                element_text = page.locator(selector).first.text_content()
            except Exception:
                pass

        browser.close()

    return {
        "url": url,
        "selector": selector,
        "found": found,
        "wait_time_seconds": round(wait_time, 2),
        "element_text": element_text[:500] if element_text else None,
        "update_time": format_datetime(),
    }


__all__ = [
    "open_url",
    "take_screenshot",
    "click_element",
    "fill_form",
    "login",
    "load_session",
    "extract_data",
    "download_file",
    "execute_javascript",
    "wait_for_element",
    "sync_cookies_to_gstack",
    "load_gstack_cookies",
]
