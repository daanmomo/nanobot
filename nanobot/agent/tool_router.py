"""Tool router: dynamically select tools based on message content.

Inspired by Pi's minimal-tools philosophy — only load what's needed.
Core tools (file, shell, web, message, think, spawn, cron) are always available.
Extension tools (stock, usstock, fund, forex, news, browser, openbb, screenshot)
are loaded on-demand based on message intent.

This saves ~3000+ tokens per turn when the user doesn't need domain tools.
"""

from __future__ import annotations

import re
from typing import Sequence

# ── Tool groups ──
# Core tools are ALWAYS included (these are the "Pi 4 tools" equivalent)
CORE_TOOLS = frozenset({
    "read_file", "write_file", "edit_file", "list_dir",
    "exec",
    "web_search", "ddg_search", "tencent_search", "web_fetch",
    "think",
    "message",
    "spawn",
    "cron",
})

# Extension groups: name → set of tool name prefixes
EXTENSIONS: dict[str, frozenset[str]] = {
    "stock": frozenset({
        "stock_",
    }),
    "usstock": frozenset({
        "usstock_",
    }),
    "fund": frozenset({
        "fund_",
    }),
    "forex": frozenset({
        "forex_",
    }),
    "news": frozenset({
        "news_",
    }),
    "browser": frozenset({
        "browser_",
    }),
    "openbb": frozenset({
        "openbb_",
    }),
    "screenshot": frozenset({
        "screenshot",
    }),
}

# ── Intent detection patterns ──
# Each extension has keyword patterns that trigger loading
_INTENT_PATTERNS: dict[str, re.Pattern] = {
    "stock": re.compile(
        r"(股票|A股|行情|大盘|涨停|跌停|板块|龙头|K线|均线|MACD|KDJ|RSI|"
        r"回测|策略|信号|筛选|stock_|关注列表|日报|成交|换手|市盈率|"
        r"主力|资金流|北向|沪深|创业板|科创板|涨跌|收盘|开盘|"
        r"两融|融资|融券|st\b|退市|打板|龙虎榜|大宗交易)",
        re.IGNORECASE,
    ),
    "usstock": re.compile(
        r"(美股|港股|纳斯达克|标普|道琼斯|恒生|AAPL|MSFT|TSLA|GOOG|NVDA|META|AMZN|"
        r"usstock|us\s*stock|\.HK\b|nasdaq|s&p|dow\s*jones|hang\s*seng|"
        r"苹果.*股|特斯拉.*股|英伟达.*股|腾讯.*股|阿里.*股|美元.*股)",
        re.IGNORECASE,
    ),
    "fund": re.compile(
        r"(基金|净值|持仓|基金经理|指数基金|ETF|QDII|混合型|股票型|债券型|"
        r"fund_|申购|赎回|定投|天天基金|晨星)",
        re.IGNORECASE,
    ),
    "forex": re.compile(
        r"(汇率|外汇|换汇|forex|美元|欧元|英镑|日元|港币|"
        r"USD|EUR|GBP|JPY|HKD|CNY|货币兑换|forex_)",
        re.IGNORECASE,
    ),
    "news": re.compile(
        r"(新闻|快讯|财经|要闻|公告|研报|资讯|news_|热点新闻|"
        r"市场消息|利好|利空|政策|央行|证监会)",
        re.IGNORECASE,
    ),
    "browser": re.compile(
        r"(浏览器|打开网页|截图|登录|网页|browser_|playwright|"
        r"填写表单|点击|下载文件|爬取|抓取网页|自动化)",
        re.IGNORECASE,
    ),
    "openbb": re.compile(
        r"(openbb|加密货币|比特币|以太坊|BTC|ETH|crypto|"
        r"经济日历|CPI|GDP|非农|宏观经济|openbb_)",
        re.IGNORECASE,
    ),
    "screenshot": re.compile(
        r"(截屏|屏幕截图|screenshot|看看屏幕|桌面截图|电脑屏幕|"
        r"screen\s*capture)",
        re.IGNORECASE,
    ),
}

# Extensions that are commonly used together
_CO_ACTIVATE: dict[str, list[str]] = {
    "stock": ["news"],           # 看股票通常也需要新闻
    "usstock": ["news", "openbb"],  # 看美股通常也需要新闻和 openbb
    "fund": ["news"],            # 看基金通常也需要新闻
}

# ── Special patterns that force ALL tools ──
_FORCE_ALL_PATTERN = re.compile(
    r"(日报|全市场|市场概览|金融.*抓取|stock_daily_report|batch_signal|"
    r"所有工具|全部工具|所有功能)",
    re.IGNORECASE,
)


def detect_extensions(messages: list[dict]) -> set[str]:
    """Detect which tool extensions are needed based on message content.

    Scans the last few user messages + all tool calls in the conversation
    to determine which extensions to activate.

    Args:
        messages: The conversation messages.

    Returns:
        Set of extension names to activate.
    """
    needed: set[str] = set()

    # Collect text to scan: last 5 user messages + all tool call names
    texts_to_scan: list[str] = []
    tool_names_seen: set[str] = set()

    user_msg_count = 0
    for msg in reversed(messages):
        role = msg.get("role", "")

        if role == "user" and user_msg_count < 5:
            content = msg.get("content", "")
            if isinstance(content, str):
                texts_to_scan.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts_to_scan.append(part.get("text", ""))
            user_msg_count += 1

        elif role == "assistant":
            # Check for tool calls in assistant messages
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", "")
                if name:
                    tool_names_seen.add(name)

        elif role == "tool":
            # Tool results indicate the extension is already in use
            pass

    # Check if we should force all extensions
    combined_text = " ".join(texts_to_scan)
    if _FORCE_ALL_PATTERN.search(combined_text):
        return set(EXTENSIONS.keys())

    # Pattern matching on text
    for ext_name, pattern in _INTENT_PATTERNS.items():
        if pattern.search(combined_text):
            needed.add(ext_name)

    # Check tool names already used (keep extensions that are in-flight)
    for tool_name in tool_names_seen:
        for ext_name, prefixes in EXTENSIONS.items():
            if any(tool_name.startswith(p) or tool_name == p for p in prefixes):
                needed.add(ext_name)

    # Co-activate related extensions
    for ext in list(needed):
        for co_ext in _CO_ACTIVATE.get(ext, []):
            needed.add(co_ext)

    return needed


def select_tool_names(
    all_tool_names: Sequence[str],
    messages: list[dict],
) -> list[str]:
    """Select which tools to expose to the LLM for this turn.

    Args:
        all_tool_names: All registered tool names.
        messages: Conversation messages.

    Returns:
        Filtered list of tool names.
    """
    needed_extensions = detect_extensions(messages)

    selected: list[str] = []
    for name in all_tool_names:
        # Core tools: always include
        if name in CORE_TOOLS:
            selected.append(name)
            continue

        # Extension tools: include only if extension is activated
        for ext_name, prefixes in EXTENSIONS.items():
            if ext_name in needed_extensions:
                if any(name.startswith(p) or name == p for p in prefixes):
                    selected.append(name)
                    break

    return selected
