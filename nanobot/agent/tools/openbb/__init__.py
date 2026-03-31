"""OpenBB financial data tools module."""

from nanobot.agent.tools.openbb.openbb_tools import (
    OpenBBCompanyProfileTool,
    OpenBBCryptoTool,
    OpenBBCurrencyTool,
    OpenBBEconomyTool,
    OpenBBEquityHistoryTool,
    OpenBBEquityQuoteTool,
    OpenBBFinancialsTool,
    OpenBBMetricsTool,
    OpenBBNewsTool,
    OpenBBSearchTool,
)

OPENBB_TOOLS = [
    OpenBBEquityQuoteTool,
    OpenBBEquityHistoryTool,
    OpenBBCompanyProfileTool,
    OpenBBFinancialsTool,
    OpenBBMetricsTool,
    OpenBBNewsTool,
    OpenBBCryptoTool,
    OpenBBCurrencyTool,
    OpenBBEconomyTool,
    OpenBBSearchTool,
]

__all__ = [
    "OPENBB_TOOLS",
    "OpenBBEquityQuoteTool",
    "OpenBBEquityHistoryTool",
    "OpenBBCompanyProfileTool",
    "OpenBBFinancialsTool",
    "OpenBBMetricsTool",
    "OpenBBNewsTool",
    "OpenBBCryptoTool",
    "OpenBBCurrencyTool",
    "OpenBBEconomyTool",
    "OpenBBSearchTool",
]
