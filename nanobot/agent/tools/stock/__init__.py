"""Stock analysis tools module for A-share market."""

from nanobot.agent.tools.stock.quant_tools import (
    QUANT_TOOLS,
    BacktestTool,
    BatchSignalTool,
    CompareStrategiesTool,
    GenerateSignalTool,
    ListStrategiesTool,
    ScreenStocksTool,
)
from nanobot.agent.tools.stock.stock_tools import (
    AddStockTool,
    CalculateIndicatorsTool,
    GenerateDailyReportTool,
    GetHistoryDataTool,
    GetIndexDataTool,
    GetMarketStatsTool,
    GetMoneyFlowTool,
    GetNorthFlowTool,
    GetRealtimeQuoteTool,
    GetSectorRankingTool,
    GetWatchlistTool,
    RemoveStockTool,
    SearchStockTool,
)

STOCK_TOOLS = [
    # 基础行情工具
    GetWatchlistTool,
    AddStockTool,
    RemoveStockTool,
    GetRealtimeQuoteTool,
    GetHistoryDataTool,
    GetIndexDataTool,
    GetMarketStatsTool,
    GetSectorRankingTool,
    GetMoneyFlowTool,
    GetNorthFlowTool,
    CalculateIndicatorsTool,
    SearchStockTool,
    GenerateDailyReportTool,
    # 量化交易工具
    *QUANT_TOOLS,
]

__all__ = [
    "STOCK_TOOLS",
    "QUANT_TOOLS",
    # 基础行情工具
    "GetWatchlistTool",
    "AddStockTool",
    "RemoveStockTool",
    "GetRealtimeQuoteTool",
    "GetHistoryDataTool",
    "GetIndexDataTool",
    "GetMarketStatsTool",
    "GetSectorRankingTool",
    "GetMoneyFlowTool",
    "GetNorthFlowTool",
    "CalculateIndicatorsTool",
    "SearchStockTool",
    "GenerateDailyReportTool",
    # 量化交易工具
    "BacktestTool",
    "ListStrategiesTool",
    "ScreenStocksTool",
    "GenerateSignalTool",
    "BatchSignalTool",
    "CompareStrategiesTool",
]
