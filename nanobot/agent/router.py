"""Smart model routing — use cheap models for simple messages.

Ported from Hermes Agent (agent/smart_model_routing.py) with simplifications:
- No runtime_provider dependency
- Returns model name directly instead of full route dict
- Integrates with nanobot's single-provider architecture

Conservative by design: if there's ANY sign of complexity, keep the primary model.
"""

from __future__ import annotations

import re

from loguru import logger

# Keywords that indicate a complex task requiring the strong model
_COMPLEX_KEYWORDS = frozenset({
    # Development
    "debug", "debugging", "implement", "implementation", "refactor",
    "patch", "traceback", "stacktrace", "exception", "error",
    # Analysis
    "analyze", "analysis", "investigate", "architecture", "design",
    "compare", "benchmark", "optimize", "optimise", "review",
    # Tools & infra
    "terminal", "shell", "tool", "tools", "pytest", "test", "tests",
    "plan", "planning", "delegate", "subagent", "cron",
    "docker", "kubernetes",
    # Research
    "research", "搜索", "调研", "分析", "研究",
    # Finance
    "回测", "backtest", "策略", "持仓", "选股",
    # Content creation
    "写文章", "写报告", "总结", "翻译", "translate",
    # File operations
    "文件", "上传", "下载", "创建", "修改",
})

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# Default thresholds
_MAX_SIMPLE_CHARS = 160
_MAX_SIMPLE_WORDS = 28


def is_simple_message(text: str) -> bool:
    """Determine if a user message is simple enough for a cheap model.

    A message is considered "simple" if ALL of the following are true:
    - Short (≤ 160 chars, ≤ 28 words)
    - Single line (≤ 1 newline)
    - No code blocks or backticks
    - No URLs
    - No complex keywords

    Args:
        text: User message text.

    Returns:
        True if the message is simple.
    """
    text = (text or "").strip()
    if not text:
        return False

    # Length checks
    if len(text) > _MAX_SIMPLE_CHARS:
        return False
    if len(text.split()) > _MAX_SIMPLE_WORDS:
        return False

    # Structural checks
    if text.count("\n") > 1:
        return False
    if "```" in text or "`" in text:
        return False
    if _URL_RE.search(text):
        return False

    # Keyword checks
    lowered = text.lower()
    words = {token.strip(".,:;!?()[]{}\"'`") for token in lowered.split()}
    if words & _COMPLEX_KEYWORDS:
        return False

    # Chinese: check if any complex keyword is a substring
    for kw in _COMPLEX_KEYWORDS:
        if len(kw) > 1 and kw in lowered:
            return False

    return True


def choose_model(
    user_message: str,
    primary_model: str,
    cheap_model: str | None = None,
) -> tuple[str, str | None]:
    """Choose the appropriate model for a user message.

    Args:
        user_message: The user's message text.
        primary_model: The default strong model.
        cheap_model: Optional cheaper/faster model for simple queries.

    Returns:
        Tuple of (model_to_use, routing_reason).
        routing_reason is None if using primary model, "simple_turn" if routed to cheap.
    """
    if not cheap_model:
        return primary_model, None

    if cheap_model == primary_model:
        return primary_model, None

    if is_simple_message(user_message):
        logger.info(f"[Router] Simple message → {cheap_model}")
        return cheap_model, "simple_turn"

    return primary_model, None
