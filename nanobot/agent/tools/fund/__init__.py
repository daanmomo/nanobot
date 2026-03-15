"""Fund analysis tools module."""

from nanobot.agent.tools.fund.fund_tools import (
    FundHoldingsTool,
    FundInfoTool,
    FundNavHistoryTool,
    FundNavTool,
    FundRankingTool,
    FundSearchTool,
)

FUND_TOOLS = [
    FundNavTool,
    FundNavHistoryTool,
    FundHoldingsTool,
    FundRankingTool,
    FundSearchTool,
    FundInfoTool,
]

__all__ = [
    "FUND_TOOLS",
    "FundNavTool",
    "FundNavHistoryTool",
    "FundHoldingsTool",
    "FundRankingTool",
    "FundSearchTool",
    "FundInfoTool",
]
