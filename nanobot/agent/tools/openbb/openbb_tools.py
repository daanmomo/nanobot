"""
OpenBB 金融数据工具

通过 OpenBB 数据平台提供全面的金融数据工具，包括：
- 股票行情与历史数据
- 公司基本面与财务报表
- 估值指标
- 市场新闻
- 加密货币价格
- 外汇汇率
- 宏观经济日历
- 股票搜索
"""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class OpenBBEquityQuoteTool(Tool):
    """获取股票实时行情（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_equity_quote"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取股票实时行情数据，包括价格、涨跌幅、市值等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT, TSLA）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance，可选 fmp, intrinio）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        symbol = kwargs.get("symbol", "")
        provider = kwargs.get("provider", "yfinance")
        result = openbb_api.get_equity_quote(symbol, provider)
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBEquityHistoryTool(Tool):
    """获取股票历史数据（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_equity_history"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取股票历史K线数据，支持日线、周线、月线"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT）",
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD（默认 3 个月前）",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD（默认今天）",
                },
                "interval": {
                    "type": "string",
                    "description": "K线间隔",
                    "enum": ["1d", "1W", "1M"],
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_equity_history(
            symbol=kwargs.get("symbol", ""),
            start_date=kwargs.get("start_date", ""),
            end_date=kwargs.get("end_date", ""),
            interval=kwargs.get("interval", "1d"),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBCompanyProfileTool(Tool):
    """获取公司信息（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_company_profile"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取公司基本信息，包括行业、简介、市值等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_company_profile(
            symbol=kwargs.get("symbol", ""),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBFinancialsTool(Tool):
    """获取公司财务报表（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_financials"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取公司财务报表（利润表/资产负债表/现金流量表）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT）",
                },
                "statement": {
                    "type": "string",
                    "description": "报表类型：income（利润表）, balance（资产负债表）, cash（现金流量表）",
                    "enum": ["income", "balance", "cash"],
                },
                "period": {
                    "type": "string",
                    "description": "周期：annual（年报）, quarter（季报）",
                    "enum": ["annual", "quarter"],
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_financials(
            symbol=kwargs.get("symbol", ""),
            statement=kwargs.get("statement", "income"),
            period=kwargs.get("period", "annual"),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBMetricsTool(Tool):
    """获取公司估值指标（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_metrics"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取公司关键估值指标（PE/PB/PS/ROE/ROA/负债率等）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 AAPL, MSFT）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_metrics(
            symbol=kwargs.get("symbol", ""),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBNewsTool(Tool):
    """获取市场新闻（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_news"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取市场新闻或特定股票相关新闻"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "string",
                    "description": "股票代码（可选，逗号分隔，如 AAPL,MSFT）。为空则获取全球新闻",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数（默认 10）",
                    "minimum": 1,
                    "maximum": 30,
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_news(
            symbols=kwargs.get("symbols", ""),
            limit=kwargs.get("limit", 10),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBCryptoTool(Tool):
    """获取加密货币价格（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_crypto"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取加密货币价格数据（BTC, ETH 等）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "加密货币代码（如 BTC-USD, ETH-USD, SOL-USD）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_crypto_price(
            symbol=kwargs.get("symbol", ""),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBCurrencyTool(Tool):
    """获取外汇汇率（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_currency"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取外汇汇率数据（如 EUR/USD, USD/JPY, USD/CNY）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "货币对（如 EURUSD, USDJPY, USDCNY）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 yfinance）",
                },
            },
            "required": ["symbol"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_currency_price(
            symbol=kwargs.get("symbol", ""),
            provider=kwargs.get("provider", "yfinance"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBEconomyTool(Tool):
    """获取经济日历（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_economy"

    @property
    def description(self) -> str:
        return "通过 OpenBB 获取近期经济日历事件（CPI、GDP、非农等）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 fmp）",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.get_economic_calendar(
            provider=kwargs.get("provider", "fmp"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


class OpenBBSearchTool(Tool):
    """搜索股票（OpenBB）。"""

    @property
    def name(self) -> str:
        return "openbb_search"

    @property
    def description(self) -> str:
        return "通过 OpenBB 搜索股票，支持按名称或代码搜索"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键字（股票代码或公司名称）",
                },
                "provider": {
                    "type": "string",
                    "description": "数据源（默认 sec）",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.openbb import openbb_api

        result = openbb_api.search_equity(
            query=kwargs.get("query", ""),
            provider=kwargs.get("provider", "sec"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
