"""
基金分析工具

提供中国公募基金分析所需的工具类，包括：
- 基金净值查询
- 基金持仓分析
- 基金排名
- 基金搜索
"""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class FundNavTool(Tool):
    """获取基金净值工具。"""

    @property
    def name(self) -> str:
        return "fund_nav"

    @property
    def description(self) -> str:
        return "获取基金最新净值数据，包括单位净值、涨跌幅等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fund_code": {
                    "type": "string",
                    "description": "基金代码（6位数字，如 000001）",
                },
            },
            "required": ["fund_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        fund_code = kwargs.get("fund_code", "")
        result = fund_api.get_fund_nav(fund_code)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FundNavHistoryTool(Tool):
    """获取基金历史净值工具。"""

    @property
    def name(self) -> str:
        return "fund_nav_history"

    @property
    def description(self) -> str:
        return "获取基金历史净值数据"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fund_code": {
                    "type": "string",
                    "description": "基金代码（6位数字）",
                },
                "days": {
                    "type": "integer",
                    "description": "历史天数（默认30天）",
                    "minimum": 7,
                    "maximum": 365,
                },
            },
            "required": ["fund_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        fund_code = kwargs.get("fund_code", "")
        days = kwargs.get("days", 30)
        result = fund_api.get_fund_nav_history(fund_code, days)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FundHoldingsTool(Tool):
    """获取基金持仓工具。"""

    @property
    def name(self) -> str:
        return "fund_holdings"

    @property
    def description(self) -> str:
        return "获取基金股票持仓，查看前十大重仓股"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fund_code": {
                    "type": "string",
                    "description": "基金代码（6位数字）",
                },
            },
            "required": ["fund_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        fund_code = kwargs.get("fund_code", "")
        result = fund_api.get_fund_holdings(fund_code)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FundRankingTool(Tool):
    """获取基金排名工具。"""

    @property
    def name(self) -> str:
        return "fund_ranking"

    @property
    def description(self) -> str:
        return "获取基金收益率排名"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fund_type": {
                    "type": "string",
                    "description": "基金类型",
                    "enum": ["全部", "股票型", "混合型", "债券型", "指数型", "QDII"],
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序字段",
                    "enum": ["近1周", "近1月", "近3月", "近6月", "近1年", "近3年"],
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        fund_type = kwargs.get("fund_type", "全部")
        sort_by = kwargs.get("sort_by", "近1年")
        result = fund_api.get_fund_ranking(fund_type, sort_by)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FundSearchTool(Tool):
    """搜索基金工具。"""

    @property
    def name(self) -> str:
        return "fund_search"

    @property
    def description(self) -> str:
        return "通过基金代码或名称搜索基金"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键字（基金代码或名称）",
                },
            },
            "required": ["keyword"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        keyword = kwargs.get("keyword", "")
        result = fund_api.search_fund(keyword)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FundInfoTool(Tool):
    """获取基金信息工具。"""

    @property
    def name(self) -> str:
        return "fund_info"

    @property
    def description(self) -> str:
        return "获取基金基本信息，包括名称、类型、净值等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fund_code": {
                    "type": "string",
                    "description": "基金代码（6位数字）",
                },
            },
            "required": ["fund_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.fund import fund_api

        fund_code = kwargs.get("fund_code", "")
        result = fund_api.get_fund_info(fund_code)
        return json.dumps(result, ensure_ascii=False, indent=2)
