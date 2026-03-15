"""US Stock and HK Stock analysis tools module."""

from nanobot.agent.tools.usstock.usstock_tools import (
    USStockCompanyTool,
    USStockFinancialsTool,
    USStockHistoryTool,
    USStockIndicesTool,
    USStockQuoteTool,
    USStockSearchTool,
)

USSTOCK_TOOLS = [
    USStockQuoteTool,
    USStockHistoryTool,
    USStockCompanyTool,
    USStockFinancialsTool,
    USStockIndicesTool,
    USStockSearchTool,
]

__all__ = [
    "USSTOCK_TOOLS",
    "USStockQuoteTool",
    "USStockHistoryTool",
    "USStockCompanyTool",
    "USStockFinancialsTool",
    "USStockIndicesTool",
    "USStockSearchTool",
]
