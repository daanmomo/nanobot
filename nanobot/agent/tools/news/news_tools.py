"""
财经新闻工具

提供财经新闻资讯所需的工具类，包括：
- 财经要闻
- 股票新闻
- 公司公告
- 研报资讯
- 财经快讯
"""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


class FinancialNewsTool(Tool):
    """获取财经要闻工具。"""

    @property
    def name(self) -> str:
        return "news_financial"

    @property
    def description(self) -> str:
        return "获取最新财经要闻"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "新闻数量（默认20条）",
                    "minimum": 5,
                    "maximum": 50,
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.news import news_api

        limit = kwargs.get("limit", 20)
        result = news_api.get_financial_news(limit)
        return json.dumps(result, ensure_ascii=False, indent=2)


class StockNewsTool(Tool):
    """获取股票新闻工具。"""

    @property
    def name(self) -> str:
        return "news_stock"

    @property
    def description(self) -> str:
        return "获取指定股票的相关新闻"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stock_code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "limit": {
                    "type": "integer",
                    "description": "新闻数量（默认10条）",
                    "minimum": 5,
                    "maximum": 30,
                },
            },
            "required": ["stock_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.news import news_api

        stock_code = kwargs.get("stock_code", "")
        limit = kwargs.get("limit", 10)
        result = news_api.get_stock_news(stock_code, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)


class CompanyAnnouncementsTool(Tool):
    """获取公司公告工具。"""

    @property
    def name(self) -> str:
        return "news_announcements"

    @property
    def description(self) -> str:
        return "获取上市公司公告"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stock_code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "limit": {
                    "type": "integer",
                    "description": "公告数量（默认10条）",
                    "minimum": 5,
                    "maximum": 30,
                },
            },
            "required": ["stock_code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.news import news_api

        stock_code = kwargs.get("stock_code", "")
        limit = kwargs.get("limit", 10)
        result = news_api.get_company_announcements(stock_code, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)


class ResearchReportsTool(Tool):
    """获取研究报告工具。"""

    @property
    def name(self) -> str:
        return "news_research"

    @property
    def description(self) -> str:
        return "获取券商研究报告"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stock_code": {
                    "type": "string",
                    "description": "股票代码（可选，为空则获取最新研报）",
                },
                "limit": {
                    "type": "integer",
                    "description": "研报数量（默认10条）",
                    "minimum": 5,
                    "maximum": 30,
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.news import news_api

        stock_code = kwargs.get("stock_code", "")
        limit = kwargs.get("limit", 10)
        result = news_api.get_research_reports(stock_code, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)


class FlashNewsTool(Tool):
    """获取财经快讯工具。"""

    @property
    def name(self) -> str:
        return "news_flash"

    @property
    def description(self) -> str:
        return "获取最新财经快讯"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "快讯数量（默认20条）",
                    "minimum": 10,
                    "maximum": 50,
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.news import news_api

        limit = kwargs.get("limit", 20)
        result = news_api.get_flash_news(limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
