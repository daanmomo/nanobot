"""Forex analysis tools module."""

from nanobot.agent.tools.forex.forex_tools import (
    ForexConvertTool,
    ForexHistoryTool,
    ForexMajorRatesTool,
    ForexRateTool,
)

FOREX_TOOLS = [
    ForexRateTool,
    ForexMajorRatesTool,
    ForexConvertTool,
    ForexHistoryTool,
]

__all__ = [
    "FOREX_TOOLS",
    "ForexRateTool",
    "ForexMajorRatesTool",
    "ForexConvertTool",
    "ForexHistoryTool",
]
