"""Financial news tools module."""

from nanobot.agent.tools.news.news_tools import (
    CompanyAnnouncementsTool,
    FinancialNewsTool,
    FlashNewsTool,
    ResearchReportsTool,
    StockNewsTool,
)

NEWS_TOOLS = [
    FinancialNewsTool,
    StockNewsTool,
    CompanyAnnouncementsTool,
    ResearchReportsTool,
    FlashNewsTool,
]

__all__ = [
    "NEWS_TOOLS",
    "FinancialNewsTool",
    "StockNewsTool",
    "CompanyAnnouncementsTool",
    "ResearchReportsTool",
    "FlashNewsTool",
]
