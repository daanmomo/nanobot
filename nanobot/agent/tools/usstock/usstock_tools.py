"""
美股/港股分析工具

提供美股、港股市场分析所需的工具类，包括：
- 实时行情查询
- 历史数据获取
- 公司基本面分析
- 财务数据分析
"""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class USStockQuoteTool(Tool):
    """获取美股/港股实时行情工具。"""

    @property
    def name(self) -> str:
        return "usstock_quote"

    @property
    def description(self) -> str:
        return "获取美股或港股的实时行情数据，包括价格、涨跌幅、市值等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT, 0700.HK）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        symbol = kwargs.get("symbol", "")
        result = yfinance_api.get_stock_quote(symbol)
        return json.dumps(result, ensure_ascii=False, indent=2)


class USStockHistoryTool(Tool):
    """获取美股/港股历史数据工具。"""

    @property
    def name(self) -> str:
        return "usstock_history"

    @property
    def description(self) -> str:
        return "获取美股或港股的历史K线数据"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT, 0700.HK）",
                },
                "period": {
                    "type": "string",
                    "description": "时间范围：1d/5d/1mo/3mo/6mo/1y/2y/5y/max",
                    "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                },
                "interval": {
                    "type": "string",
                    "description": "K线间隔：1d（日线）/1wk（周线）/1mo（月线）",
                    "enum": ["1d", "1wk", "1mo"],
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        symbol = kwargs.get("symbol", "")
        period = kwargs.get("period", "3mo")
        interval = kwargs.get("interval", "1d")
        result = yfinance_api.get_stock_history(symbol, period, interval)
        return json.dumps(result, ensure_ascii=False, indent=2)


class USStockCompanyTool(Tool):
    """获取公司基本信息工具。"""

    @property
    def name(self) -> str:
        return "usstock_company"

    @property
    def description(self) -> str:
        return "获取美股或港股公司的基本信息，包括行业、简介、市值等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT, 0700.HK）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        symbol = kwargs.get("symbol", "")
        result = yfinance_api.get_company_info(symbol)
        return json.dumps(result, ensure_ascii=False, indent=2)


class USStockFinancialsTool(Tool):
    """获取公司财务数据工具。"""

    @property
    def name(self) -> str:
        return "usstock_financials"

    @property
    def description(self) -> str:
        return "获取美股或港股公司的财务数据，包括估值、盈利能力、收入、股息、资产负债等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT, 0700.HK）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        symbol = kwargs.get("symbol", "")
        result = yfinance_api.get_financials(symbol)
        return json.dumps(result, ensure_ascii=False, indent=2)


class USStockIndicesTool(Tool):
    """获取主要市场指数工具。"""

    @property
    def name(self) -> str:
        return "usstock_indices"

    @property
    def description(self) -> str:
        return "获取全球主要市场指数行情，包括标普500、道琼斯、纳斯达克、恒生指数等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        result = yfinance_api.get_major_indices()
        return json.dumps(result, ensure_ascii=False, indent=2)


class USStockSearchTool(Tool):
    """搜索美股/港股工具。"""

    @property
    def name(self) -> str:
        return "usstock_search"

    @property
    def description(self) -> str:
        return "通过股票代码或名称搜索美股、港股"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键字（股票代码或名称）",
                },
            },
            "required": ["keyword"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.usstock import yfinance_api

        keyword = kwargs.get("keyword", "")
        result = yfinance_api.search_stock(keyword)
        return json.dumps(result, ensure_ascii=False, indent=2)
