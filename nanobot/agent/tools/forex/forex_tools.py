"""
外汇分析工具

提供外汇/汇率分析所需的工具类，包括：
- 实时汇率查询
- 主要货币汇率
- 汇率换算
- 历史汇率
"""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class ForexRateTool(Tool):
    """获取实时汇率工具。"""

    @property
    def name(self) -> str:
        return "forex_rate"

    @property
    def description(self) -> str:
        return "获取指定货币对的实时汇率"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "currency_pair": {
                    "type": "string",
                    "description": "货币对（如 USD/CNY, EUR/CNY, GBP/CNY）",
                },
            },
            "required": ["currency_pair"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.forex import forex_api

        currency_pair = kwargs.get("currency_pair", "USD/CNY")
        result = forex_api.get_forex_rate(currency_pair)
        return json.dumps(result, ensure_ascii=False, indent=2)


class ForexMajorRatesTool(Tool):
    """获取主要汇率工具。"""

    @property
    def name(self) -> str:
        return "forex_major_rates"

    @property
    def description(self) -> str:
        return "获取主要货币对人民币的汇率（美元、欧元、英镑、日元、港币等）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.forex import forex_api

        result = forex_api.get_major_rates()
        return json.dumps(result, ensure_ascii=False, indent=2)


class ForexConvertTool(Tool):
    """汇率换算工具。"""

    @property
    def name(self) -> str:
        return "forex_convert"

    @property
    def description(self) -> str:
        return "货币换算，将一种货币金额转换为另一种货币"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "换算金额",
                },
                "from_currency": {
                    "type": "string",
                    "description": "源货币代码（如 USD, EUR, CNY）",
                },
                "to_currency": {
                    "type": "string",
                    "description": "目标货币代码（如 USD, EUR, CNY）",
                },
            },
            "required": ["amount", "from_currency", "to_currency"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.forex import forex_api

        amount = kwargs.get("amount", 0)
        from_currency = kwargs.get("from_currency", "USD")
        to_currency = kwargs.get("to_currency", "CNY")
        result = forex_api.convert_currency(amount, from_currency, to_currency)
        return json.dumps(result, ensure_ascii=False, indent=2)


class ForexHistoryTool(Tool):
    """获取历史汇率工具。"""

    @property
    def name(self) -> str:
        return "forex_history"

    @property
    def description(self) -> str:
        return "获取货币对的历史汇率数据"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "currency_pair": {
                    "type": "string",
                    "description": "货币对（如 USD/CNY）",
                },
                "days": {
                    "type": "integer",
                    "description": "历史天数（默认30天）",
                    "minimum": 7,
                    "maximum": 365,
                },
            },
            "required": ["currency_pair"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.forex import forex_api

        currency_pair = kwargs.get("currency_pair", "USD/CNY")
        days = kwargs.get("days", 30)
        result = forex_api.get_forex_history(currency_pair, days)
        return json.dumps(result, ensure_ascii=False, indent=2)
