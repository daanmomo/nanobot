"""
OpenBB 数据平台 API 封装模块

提供通过 OpenBB SDK 获取金融数据的统一接口：
- 股票行情与历史数据
- 公司基本面与财务数据
- 市场新闻
- 加密货币数据
- 外汇汇率
- 宏观经济指标

参考: https://docs.openbb.co/python/reference
"""

import logging
from typing import Any

from nanobot.agent.tools.common import (
    api_error_handler,
    format_datetime,
    format_large_number,
    safe_float,
    safe_str,
)

logger = logging.getLogger(__name__)

_OPENBB_INSTALL_HINT = "openbb 未安装，请运行: pip install openbb"


def _import_openbb():
    """延迟导入 openbb。"""
    try:
        from openbb import obb
        return obb
    except ImportError as e:
        raise ImportError(_OPENBB_INSTALL_HINT) from e


# ==================== 股票行情 ====================


@api_error_handler("获取股票行情失败")
def get_equity_quote(symbol: str, provider: str = "yfinance") -> dict[str, Any]:
    """
    获取股票实时行情。

    参数：
        symbol: 股票代码（如 AAPL, MSFT）
        provider: 数据源（yfinance, fmp, intrinio 等）
    """
    obb = _import_openbb()
    result = obb.equity.price.quote(symbol=symbol, provider=provider)
    data = result.to_dict()

    if not data or "results" not in data or not data["results"]:
        return {"error": f"未找到股票 {symbol}"}

    item = data["results"][0] if isinstance(data["results"], list) else data["results"]

    price = safe_float(item.get("last_price") or item.get("price") or item.get("close"))
    prev_close = safe_float(item.get("prev_close") or item.get("previous_close"))
    change = price - prev_close if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "symbol": safe_str(item.get("symbol"), symbol.upper()),
        "name": safe_str(item.get("name") or item.get("short_name")),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "open": safe_float(item.get("open")),
        "high": safe_float(item.get("high")),
        "low": safe_float(item.get("low")),
        "prev_close": prev_close,
        "volume": safe_float(item.get("volume")),
        "market_cap": format_large_number(item.get("market_cap")),
        "pe_ratio": safe_float(item.get("pe_ratio")),
        "update_time": format_datetime(),
    }


@api_error_handler("获取股票历史数据失败")
def get_equity_history(
    symbol: str,
    start_date: str = "",
    end_date: str = "",
    interval: str = "1d",
    provider: str = "yfinance",
) -> dict[str, Any]:
    """
    获取股票历史 K 线数据。

    参数：
        symbol: 股票代码
        start_date: 开始日期 YYYY-MM-DD（默认 3 个月前）
        end_date: 结束日期 YYYY-MM-DD（默认今天）
        interval: K线间隔 1d/1W/1M
        provider: 数据源
    """
    obb = _import_openbb()

    kwargs: dict[str, Any] = {"symbol": symbol, "interval": interval, "provider": provider}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date

    result = obb.equity.price.historical(**kwargs)
    df = result.to_dataframe()

    if df.empty:
        return {"error": f"未获取到 {symbol} 的历史数据"}

    records = []
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
        records.append({
            "date": date_str,
            "open": round(safe_float(row.get("open")), 2),
            "high": round(safe_float(row.get("high")), 2),
            "low": round(safe_float(row.get("low")), 2),
            "close": round(safe_float(row.get("close")), 2),
            "volume": int(safe_float(row.get("volume"))),
        })

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(records),
        "data": records[-60:],  # 最多返回 60 条避免过长
    }


# ==================== 公司基本面 ====================


@api_error_handler("获取公司信息失败")
def get_company_profile(symbol: str, provider: str = "yfinance") -> dict[str, Any]:
    """获取公司基本信息。"""
    obb = _import_openbb()
    result = obb.equity.profile(symbol=symbol, provider=provider)
    data = result.to_dict()

    if not data or "results" not in data or not data["results"]:
        return {"error": f"未找到公司 {symbol}"}

    item = data["results"][0] if isinstance(data["results"], list) else data["results"]

    return {
        "symbol": symbol.upper(),
        "name": safe_str(item.get("name") or item.get("long_name")),
        "sector": safe_str(item.get("sector")),
        "industry": safe_str(item.get("industry")),
        "country": safe_str(item.get("country")),
        "website": safe_str(item.get("website")),
        "employees": item.get("full_time_employees"),
        "description": safe_str(item.get("long_business_summary", ""))[:500],
        "market_cap": format_large_number(item.get("market_cap")),
        "update_time": format_datetime(),
    }


@api_error_handler("获取财务数据失败")
def get_financials(
    symbol: str,
    statement: str = "income",
    period: str = "annual",
    provider: str = "yfinance",
) -> dict[str, Any]:
    """
    获取公司财务报表数据。

    参数：
        symbol: 股票代码
        statement: 报表类型 income/balance/cash
        period: annual/quarter
        provider: 数据源
    """
    obb = _import_openbb()

    func_map = {
        "income": obb.equity.fundamental.income,
        "balance": obb.equity.fundamental.balance,
        "cash": obb.equity.fundamental.cash,
    }

    func = func_map.get(statement)
    if not func:
        return {"error": f"不支持的报表类型: {statement}，可选: income/balance/cash"}

    result = func(symbol=symbol, period=period, provider=provider, limit=4)
    df = result.to_dataframe()

    if df.empty:
        return {"error": f"未获取到 {symbol} 的{statement}报表数据"}

    records = []
    for idx, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
            if isinstance(val, (int, float)):
                record[col] = round(val, 2) if isinstance(val, float) else val
            else:
                record[col] = str(val) if val is not None else None
        records.append(record)

    return {
        "symbol": symbol.upper(),
        "statement": statement,
        "period": period,
        "count": len(records),
        "data": records,
    }


@api_error_handler("获取估值指标失败")
def get_metrics(symbol: str, provider: str = "yfinance") -> dict[str, Any]:
    """获取公司关键估值指标。"""
    obb = _import_openbb()
    result = obb.equity.fundamental.metrics(symbol=symbol, provider=provider)
    data = result.to_dict()

    if not data or "results" not in data or not data["results"]:
        return {"error": f"未找到 {symbol} 的估值指标"}

    item = data["results"][0] if isinstance(data["results"], list) else data["results"]

    return {
        "symbol": symbol.upper(),
        "market_cap": format_large_number(item.get("market_cap")),
        "pe_ratio": safe_float(item.get("pe_ratio")),
        "forward_pe": safe_float(item.get("forward_pe")),
        "peg_ratio": safe_float(item.get("peg_ratio")),
        "pb_ratio": safe_float(item.get("pb_ratio")),
        "ps_ratio": safe_float(item.get("ps_ratio")),
        "dividend_yield": safe_float(item.get("dividend_yield")),
        "eps_ttm": safe_float(item.get("earnings_per_share")),
        "revenue_per_share": safe_float(item.get("revenue_per_share")),
        "roe": safe_float(item.get("return_on_equity")),
        "roa": safe_float(item.get("return_on_assets")),
        "debt_to_equity": safe_float(item.get("debt_to_equity")),
        "current_ratio": safe_float(item.get("current_ratio")),
        "update_time": format_datetime(),
    }


# ==================== 市场新闻 ====================


@api_error_handler("获取市场新闻失败")
def get_news(
    symbols: str = "",
    limit: int = 10,
    provider: str = "yfinance",
) -> dict[str, Any]:
    """
    获取市场新闻。

    参数：
        symbols: 股票代码（可选，逗号分隔）
        limit: 返回条数
        provider: 数据源
    """
    obb = _import_openbb()

    kwargs: dict[str, Any] = {"limit": limit, "provider": provider}
    if symbols:
        kwargs["symbol"] = symbols

    result = obb.news.world(**kwargs) if not symbols else obb.news.company(**kwargs)
    df = result.to_dataframe()

    if df.empty:
        return {"error": "未获取到新闻数据"}

    articles = []
    for _, row in df.head(limit).iterrows():
        articles.append({
            "title": safe_str(row.get("title")),
            "date": str(row.get("date", "")),
            "source": safe_str(row.get("source") or row.get("publisher")),
            "url": safe_str(row.get("url") or row.get("link")),
            "summary": safe_str(row.get("text", ""))[:200],
        })

    return {
        "symbols": symbols,
        "count": len(articles),
        "articles": articles,
    }


# ==================== 加密货币 ====================


@api_error_handler("获取加密货币数据失败")
def get_crypto_price(
    symbol: str,
    provider: str = "yfinance",
) -> dict[str, Any]:
    """
    获取加密货币价格。

    参数：
        symbol: 加密货币代码（如 BTC-USD, ETH-USD）
    """
    obb = _import_openbb()
    result = obb.crypto.price.historical(symbol=symbol, provider=provider)
    df = result.to_dataframe()

    if df.empty:
        return {"error": f"未获取到 {symbol} 的数据"}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    price = safe_float(latest.get("close"))
    prev_price = safe_float(prev.get("close"))
    change = price - prev_price
    change_pct = (change / prev_price * 100) if prev_price else 0

    return {
        "symbol": symbol.upper(),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "high": round(safe_float(latest.get("high")), 2),
        "low": round(safe_float(latest.get("low")), 2),
        "volume": safe_float(latest.get("volume")),
        "update_time": format_datetime(),
    }


# ==================== 外汇 ====================


@api_error_handler("获取外汇汇率失败")
def get_currency_price(
    symbol: str,
    provider: str = "yfinance",
) -> dict[str, Any]:
    """
    获取外汇汇率。

    参数：
        symbol: 货币对（如 EURUSD, USDJPY, USDCNY）
    """
    obb = _import_openbb()
    result = obb.currency.price.historical(symbol=symbol, provider=provider)
    df = result.to_dataframe()

    if df.empty:
        return {"error": f"未获取到 {symbol} 的汇率数据"}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    rate = safe_float(latest.get("close"))
    prev_rate = safe_float(prev.get("close"))
    change = rate - prev_rate
    change_pct = (change / prev_rate * 100) if prev_rate else 0

    return {
        "symbol": symbol.upper(),
        "rate": round(rate, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "update_time": format_datetime(),
    }


# ==================== 宏观经济 ====================


@api_error_handler("获取经济指标失败")
def get_economic_calendar(
    provider: str = "fmp",
) -> dict[str, Any]:
    """获取近期经济日历事件。"""
    obb = _import_openbb()
    result = obb.economy.calendar(provider=provider)
    df = result.to_dataframe()

    if df.empty:
        return {"error": "未获取到经济日历数据"}

    events = []
    for _, row in df.head(20).iterrows():
        events.append({
            "date": str(row.get("date", "")),
            "event": safe_str(row.get("event")),
            "country": safe_str(row.get("country")),
            "actual": safe_str(row.get("actual")),
            "forecast": safe_str(row.get("forecast") or row.get("consensus")),
            "previous": safe_str(row.get("previous")),
        })

    return {
        "count": len(events),
        "events": events,
    }


# ==================== 股票筛选 ====================


@api_error_handler("股票搜索失败")
def search_equity(query: str, provider: str = "sec") -> dict[str, Any]:
    """
    搜索股票。

    参数：
        query: 搜索关键字（公司名或代码）
    """
    obb = _import_openbb()
    result = obb.equity.search(query=query, provider=provider)
    df = result.to_dataframe()

    if df.empty:
        return {"keyword": query, "count": 0, "results": []}

    results = []
    for _, row in df.head(10).iterrows():
        results.append({
            "symbol": safe_str(row.get("symbol")),
            "name": safe_str(row.get("name") or row.get("company_name")),
        })

    return {
        "keyword": query,
        "count": len(results),
        "results": results,
    }


__all__ = [
    "get_equity_quote",
    "get_equity_history",
    "get_company_profile",
    "get_financials",
    "get_metrics",
    "get_news",
    "get_crypto_price",
    "get_currency_price",
    "get_economic_calendar",
    "search_equity",
]
