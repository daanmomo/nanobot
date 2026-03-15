"""
基金数据 API 封装模块

提供中国公募基金数据接口的统一封装：
- 基金净值
- 基金持仓
- 基金排名
- 基金搜索

参考: https://github.com/akfamily/akshare
"""

import logging
from typing import Any

from nanobot.agent.tools.common import (
    api_error_handler,
    format_datetime,
    safe_float_pandas,
    safe_str,
)

logger = logging.getLogger(__name__)

_AKSHARE_INSTALL_HINT = "akshare 未安装，请运行: pip install akshare"


def _import_akshare():
    """延迟导入 akshare。"""
    try:
        import akshare as ak
        return ak
    except ImportError as e:
        raise ImportError(_AKSHARE_INSTALL_HINT) from e


# ==================== 基金净值 ====================


@api_error_handler("获取基金净值失败")
def get_fund_nav(fund_code: str) -> dict[str, Any]:
    """
    获取基金最新净值。

    参数：
        fund_code: 基金代码（6位数字）

    返回：
        包含基金净值数据的字典
    """
    ak = _import_akshare()
    df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")

    if df.empty:
        return {"error": f"未找到基金 {fund_code}"}

    try:
        name_df = ak.fund_name_em()
        fund_info = name_df[name_df["基金代码"] == fund_code]
        fund_name = safe_str(fund_info["基金简称"].iloc[0]) if not fund_info.empty else ""
    except Exception:
        fund_name = ""

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    nav = safe_float_pandas(latest.get("单位净值"))
    prev_nav = safe_float_pandas(prev.get("单位净值"))
    change = nav - prev_nav
    change_pct = (change / prev_nav * 100) if prev_nav else 0

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "nav": round(nav, 4),
        "nav_date": safe_str(latest.get("净值日期")),
        "change": round(change, 4),
        "change_pct": round(change_pct, 2),
        "update_time": format_datetime(),
    }


@api_error_handler("获取基金历史净值失败")
def get_fund_nav_history(fund_code: str, days: int = 30) -> dict[str, Any]:
    """
    获取基金历史净值。

    参数：
        fund_code: 基金代码
        days: 历史天数

    返回：
        包含历史净值数据的字典
    """
    ak = _import_akshare()
    df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")

    if df.empty:
        return {"error": f"未找到基金 {fund_code}"}

    df = df.tail(days)

    records = []
    for _, row in df.iterrows():
        records.append({
            "date": safe_str(row.get("净值日期")),
            "nav": safe_float_pandas(row.get("单位净值")),
        })

    return {
        "fund_code": fund_code,
        "count": len(records),
        "data": records,
    }


# ==================== 基金持仓 ====================


@api_error_handler("获取基金持仓失败")
def get_fund_holdings(fund_code: str) -> dict[str, Any]:
    """
    获取基金股票持仓（前十大重仓股）。

    参数：
        fund_code: 基金代码

    返回：
        包含持仓数据的字典
    """
    ak = _import_akshare()

    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date="2024")
    except Exception:
        try:
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date="2023")
        except Exception:
            return {"error": f"未获取到基金 {fund_code} 的持仓数据"}

    if df.empty:
        return {"error": f"未获取到基金 {fund_code} 的持仓数据"}

    holdings = []
    for _, row in df.head(10).iterrows():
        holdings.append({
            "stock_code": safe_str(row.get("股票代码")),
            "stock_name": safe_str(row.get("股票名称")),
            "weight": safe_float_pandas(row.get("占净值比例")),
            "shares": safe_float_pandas(row.get("持股数")),
            "value": safe_float_pandas(row.get("持仓市值")),
        })

    return {
        "fund_code": fund_code,
        "report_date": safe_str(df["季度"].iloc[0]) if "季度" in df.columns else "",
        "holdings": holdings,
        "update_time": format_datetime(),
    }


# ==================== 基金排名 ====================


@api_error_handler("获取基金排名失败")
def get_fund_ranking(fund_type: str = "全部", sort_by: str = "近1年") -> dict[str, Any]:
    """
    获取基金排名。

    参数：
        fund_type: 基金类型（全部/股票型/混合型/债券型/指数型/QDII）
        sort_by: 排序字段（近1周/近1月/近3月/近6月/近1年/近3年）

    返回：
        包含排名数据的字典
    """
    ak = _import_akshare()
    df = ak.fund_open_fund_rank_em(symbol=fund_type)

    if df.empty:
        return {"error": "未获取到基金排名数据"}

    sort_map = {
        "近1周": "近1周",
        "近1月": "近1月",
        "近3月": "近3月",
        "近6月": "近6月",
        "近1年": "近1年",
        "近3年": "近3年",
    }
    sort_col = sort_map.get(sort_by, "近1年")

    import pandas as pd
    df[sort_col] = pd.to_numeric(df[sort_col], errors="coerce")
    df = df.sort_values(sort_col, ascending=False)

    rankings = []
    for _, row in df.head(20).iterrows():
        rankings.append({
            "code": safe_str(row.get("基金代码")),
            "name": safe_str(row.get("基金简称")),
            "nav": safe_float_pandas(row.get("单位净值")),
            "return_1w": safe_float_pandas(row.get("近1周")),
            "return_1m": safe_float_pandas(row.get("近1月")),
            "return_3m": safe_float_pandas(row.get("近3月")),
            "return_1y": safe_float_pandas(row.get("近1年")),
        })

    return {
        "fund_type": fund_type,
        "sort_by": sort_by,
        "rankings": rankings,
        "update_time": format_datetime(),
    }


# ==================== 基金搜索 ====================


@api_error_handler("搜索基金失败")
def search_fund(keyword: str) -> dict[str, Any]:
    """
    搜索基金。

    参数：
        keyword: 搜索关键字（基金代码或名称）

    返回：
        包含搜索结果的字典
    """
    ak = _import_akshare()
    df = ak.fund_name_em()

    if df.empty:
        return {"error": "未获取到基金列表"}

    keyword_lower = keyword.lower()
    results = []

    for _, row in df.iterrows():
        code = safe_str(row.get("基金代码"))
        name = safe_str(row.get("基金简称"))
        fund_type = safe_str(row.get("基金类型"))

        if keyword_lower in code.lower() or keyword_lower in name.lower():
            results.append({
                "code": code,
                "name": name,
                "type": fund_type,
            })
            if len(results) >= 10:
                break

    return {
        "keyword": keyword,
        "count": len(results),
        "results": results,
    }


# ==================== 基金信息 ====================


@api_error_handler("获取基金信息失败")
def get_fund_info(fund_code: str) -> dict[str, Any]:
    """
    获取基金基本信息。

    参数：
        fund_code: 基金代码

    返回：
        包含基金信息的字典
    """
    ak = _import_akshare()

    try:
        name_df = ak.fund_name_em()
        fund_info = name_df[name_df["基金代码"] == fund_code]
        if fund_info.empty:
            return {"error": f"未找到基金 {fund_code}"}

        fund_name = safe_str(fund_info["基金简称"].iloc[0])
        fund_type = safe_str(fund_info["基金类型"].iloc[0])
    except Exception:
        fund_name = ""
        fund_type = ""

    nav_data = get_fund_nav(fund_code)
    nav = nav_data.get("nav", 0) if "error" not in nav_data else 0

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "nav": nav,
        "update_time": format_datetime(),
    }


__all__ = [
    "get_fund_nav",
    "get_fund_nav_history",
    "get_fund_holdings",
    "get_fund_ranking",
    "search_fund",
    "get_fund_info",
]
