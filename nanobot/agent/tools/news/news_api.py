"""
财经新闻 API 封装模块

提供财经新闻数据接口的统一封装：
- 财经要闻
- 股票新闻
- 公司公告
- 研报资讯

数据来源：AKShare (东方财富、新浪财经等)
"""

import logging
from typing import Any

from nanobot.agent.tools.common import api_error_handler, format_datetime, safe_str

logger = logging.getLogger(__name__)

_AKSHARE_INSTALL_HINT = "akshare 未安装，请运行: pip install akshare"


def _import_akshare():
    """延迟导入 akshare。"""
    try:
        import akshare as ak
        return ak
    except ImportError as e:
        raise ImportError(_AKSHARE_INSTALL_HINT) from e


# ==================== 财经要闻 ====================


@api_error_handler("获取财经要闻失败")
def get_financial_news(limit: int = 20) -> dict[str, Any]:
    """
    获取财经要闻。

    参数：
        limit: 新闻数量限制

    返回：
        包含新闻列表的字典
    """
    ak = _import_akshare()

    try:
        df = ak.stock_news_em()
    except Exception:
        try:
            df = ak.news_cctv()
        except Exception:
            return {"error": "未获取到财经新闻"}

    if df.empty:
        return {"error": "未获取到财经新闻"}

    news_list = []
    for _, row in df.head(limit).iterrows():
        title = safe_str(row.get("新闻标题") or row.get("title") or row.get("标题"))
        content = safe_str(row.get("新闻内容") or row.get("content") or row.get("内容", ""))
        pub_time = safe_str(row.get("发布时间") or row.get("date") or row.get("时间"))

        if title:
            news_list.append({
                "title": title,
                "summary": content[:200] if content else "",
                "time": pub_time,
            })

    return {
        "news": news_list,
        "count": len(news_list),
        "update_time": format_datetime(),
    }


# ==================== 股票新闻 ====================


@api_error_handler("获取股票新闻失败")
def get_stock_news(stock_code: str, limit: int = 10) -> dict[str, Any]:
    """
    获取个股相关新闻。

    参数：
        stock_code: 股票代码
        limit: 新闻数量限制

    返回：
        包含新闻列表的字典
    """
    ak = _import_akshare()

    try:
        df = ak.stock_news_em(symbol=stock_code)
    except Exception:
        return {"error": f"未获取到股票 {stock_code} 的相关新闻"}

    if df.empty:
        return {"error": f"未获取到股票 {stock_code} 的相关新闻"}

    news_list = []
    for _, row in df.head(limit).iterrows():
        title = safe_str(row.get("新闻标题") or row.get("标题"))
        content = safe_str(row.get("新闻内容") or row.get("内容", ""))
        pub_time = safe_str(row.get("发布时间") or row.get("时间"))
        source = safe_str(row.get("文章来源") or row.get("来源"))

        if title:
            news_list.append({
                "title": title,
                "summary": content[:200] if content else "",
                "time": pub_time,
                "source": source,
            })

    return {
        "stock_code": stock_code,
        "news": news_list,
        "count": len(news_list),
        "update_time": format_datetime(),
    }


# ==================== 公司公告 ====================


@api_error_handler("获取公司公告失败")
def get_company_announcements(stock_code: str, limit: int = 10) -> dict[str, Any]:
    """
    获取公司公告。

    参数：
        stock_code: 股票代码
        limit: 公告数量限制

    返回：
        包含公告列表的字典
    """
    ak = _import_akshare()

    try:
        df = ak.stock_notice_report(symbol=stock_code)
    except Exception:
        return {"error": f"未获取到股票 {stock_code} 的公告"}

    if df.empty:
        return {"error": f"未获取到股票 {stock_code} 的公告"}

    announcements = []
    for _, row in df.head(limit).iterrows():
        title = safe_str(row.get("公告标题") or row.get("标题"))
        pub_date = safe_str(row.get("公告日期") or row.get("日期"))
        ann_type = safe_str(row.get("公告类型") or row.get("类型"))

        if title:
            announcements.append({
                "title": title,
                "date": pub_date,
                "type": ann_type,
            })

    return {
        "stock_code": stock_code,
        "announcements": announcements,
        "count": len(announcements),
        "update_time": format_datetime(),
    }


# ==================== 研报资讯 ====================


@api_error_handler("获取研报失败")
def get_research_reports(stock_code: str = "", limit: int = 10) -> dict[str, Any]:
    """
    获取研究报告。

    参数：
        stock_code: 股票代码（可选，为空则获取最新研报）
        limit: 研报数量限制

    返回：
        包含研报列表的字典
    """
    ak = _import_akshare()

    try:
        if stock_code:
            df = ak.stock_research_report_em(symbol=stock_code)
        else:
            df = ak.stock_research_report_em()
    except Exception:
        return {"error": "未获取到研究报告"}

    if df.empty:
        return {"error": "未获取到研究报告"}

    reports = []
    for _, row in df.head(limit).iterrows():
        title = safe_str(row.get("报告名称") or row.get("标题"))
        stock_name = safe_str(row.get("股票简称") or row.get("股票名称"))
        org = safe_str(row.get("机构名称") or row.get("研究机构"))
        author = safe_str(row.get("作者"))
        pub_date = safe_str(row.get("发布日期") or row.get("日期"))
        rating = safe_str(row.get("最新评级") or row.get("评级"))

        if title:
            reports.append({
                "title": title,
                "stock_name": stock_name,
                "organization": org,
                "author": author,
                "date": pub_date,
                "rating": rating,
            })

    return {
        "stock_code": stock_code if stock_code else "全市场",
        "reports": reports,
        "count": len(reports),
        "update_time": format_datetime(),
    }


# ==================== 快讯 ====================


@api_error_handler("获取快讯失败")
def get_flash_news(limit: int = 20) -> dict[str, Any]:
    """
    获取财经快讯。

    参数：
        limit: 快讯数量限制

    返回：
        包含快讯列表的字典
    """
    ak = _import_akshare()

    try:
        df = ak.stock_info_global_em()
    except Exception:
        try:
            df = ak.stock_info_global_sina()
        except Exception:
            return {"error": "未获取到财经快讯"}

    if df.empty:
        return {"error": "未获取到财经快讯"}

    flash_list = []
    for _, row in df.head(limit).iterrows():
        content = safe_str(row.get("内容") or row.get("content") or row.get("标题"))
        pub_time = safe_str(row.get("发布时间") or row.get("time") or row.get("时间"))

        if content:
            flash_list.append({
                "content": content,
                "time": pub_time,
            })

    return {
        "flash_news": flash_list,
        "count": len(flash_list),
        "update_time": format_datetime(),
    }


__all__ = [
    "get_financial_news",
    "get_stock_news",
    "get_company_announcements",
    "get_research_reports",
    "get_flash_news",
]
