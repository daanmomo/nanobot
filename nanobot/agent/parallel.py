"""Parallel tool execution for independent tool calls.

Inspired by Hermes Agent's parallel tool execution.
Read-only tools run concurrently; write tools run sequentially unless
targeting independent paths.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable, Awaitable

from loguru import logger


# Tools that must never run concurrently (interactive / user-facing)
_NEVER_PARALLEL_TOOLS = frozenset({"message", "spawn", "think"})

# Read-only tools safe for concurrent execution
_PARALLEL_SAFE_TOOLS = frozenset({
    "read_file",
    "list_dir",
    "web_search",
    "ddg_search",
    "tencent_search",
    "web_fetch",
    "stock_realtime_quote",
    "stock_history",
    "stock_index",
    "stock_market_stats",
    "stock_sector_ranking",
    "stock_indicators",
    "stock_money_flow",
    "stock_north_flow",
    "stock_search",
    "stock_signal",
    "usstock_quote",
    "usstock_history",
    "usstock_company",
    "usstock_financials",
    "usstock_indices",
    "usstock_search",
    "fund_nav",
    "fund_nav_history",
    "fund_holdings",
    "fund_ranking",
    "fund_search",
    "fund_info",
    "forex_rate",
    "forex_major_rates",
    "forex_convert",
    "forex_history",
    "news_financial",
    "news_stock",
    "news_announcements",
    "news_research",
    "news_flash",
    "openbb_equity_quote",
    "openbb_equity_history",
    "openbb_company_profile",
    "openbb_financials",
    "openbb_metrics",
    "openbb_news",
    "openbb_crypto",
    "openbb_currency",
    "openbb_economy",
    "openbb_search",
    "screenshot",
    "browser_open",
    "browser_screenshot",
    "browser_extract",
})

# File tools can run concurrently when targeting independent paths
_PATH_SCOPED_TOOLS = frozenset({"read_file", "write_file", "edit_file"})

# Maximum concurrent tool workers
_MAX_TOOL_WORKERS = 8


def should_parallelize(tool_calls: list[dict[str, Any]]) -> bool:
    """Return True when a tool-call batch is safe to run concurrently.

    Args:
        tool_calls: List of tool call dicts with 'name' and 'arguments' keys.

    Returns:
        True if all tools in the batch can safely run in parallel.
    """
    if len(tool_calls) <= 1:
        return False

    tool_names = [tc.get("name", "") for tc in tool_calls]

    # Never parallel if any interactive tool is present
    if any(name in _NEVER_PARALLEL_TOOLS for name in tool_names):
        return False

    reserved_paths: list[Path] = []

    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return False
        if not isinstance(args, dict):
            return False

        # Path-scoped tools: check for path conflicts
        if name in _PATH_SCOPED_TOOLS:
            raw_path = args.get("path", "")
            if not isinstance(raw_path, str) or not raw_path.strip():
                return False
            path = Path(raw_path).expanduser().resolve()
            if any(_paths_overlap(path, existing) for existing in reserved_paths):
                return False
            reserved_paths.append(path)
            continue

        # Must be in the safe list
        if name not in _PARALLEL_SAFE_TOOLS:
            return False

    return True


def _paths_overlap(a: Path, b: Path) -> bool:
    """Check if two paths overlap (same file or parent/child)."""
    try:
        a.relative_to(b)
        return True
    except ValueError:
        pass
    try:
        b.relative_to(a)
        return True
    except ValueError:
        pass
    return a == b


async def execute_parallel(
    tool_calls: list[dict[str, Any]],
    executor: Callable[[str, dict], Awaitable[str]],
) -> list[tuple[str, str, str]]:
    """Execute tool calls concurrently.

    Args:
        tool_calls: List of dicts with 'id', 'name', 'arguments'.
        executor: Async function(name, args) -> result string.

    Returns:
        List of (tool_call_id, tool_name, result) tuples in original order.
    """
    semaphore = asyncio.Semaphore(_MAX_TOOL_WORKERS)

    async def _run_one(tc: dict) -> tuple[str, str, str]:
        tc_id = tc.get("id", "")
        name = tc.get("name", "")
        args = tc.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        async with semaphore:
            try:
                result = await executor(name, args)
            except Exception as e:
                result = f"Error: {e}"
                logger.error(f"[Parallel] Tool {name} failed: {e}")
            return (tc_id, name, result)

    tasks = [_run_one(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks)

    logger.info(f"[Parallel] Executed {len(tool_calls)} tools concurrently")
    return list(results)
