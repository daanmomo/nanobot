"""
Yahoo Finance API 封装模块

提供美股/港股数据接口的统一封装：
- 实时行情
- 历史K线
- 公司基本面
- 财务数据

参考: https://github.com/ranaroussi/yfinance
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

_YFINANCE_INSTALL_HINT = "yfinance 未安装，请运行: pip install yfinance"


def _import_yfinance():
    """延迟导入 yfinance。"""
    try:
        import yfinance as yf
        return yf
    except ImportError as e:
        raise ImportError(_YFINANCE_INSTALL_HINT) from e


# ==================== 实时行情 ====================


@api_error_handler("获取美股实时行情失败")
def get_stock_quote(symbol: str) -> dict[str, Any]:
    """
    获取股票实时行情。

    参数：
        symbol: 股票代码（如 AAPL, MSFT, 0700.HK）

    返回：
        包含实时行情数据的字典
    """
    yf = _import_yfinance()
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info or info.get("regularMarketPrice") is None:
        fast_info = ticker.fast_info
        if hasattr(fast_info, "last_price") and fast_info.last_price:
            return {
                "symbol": symbol.upper(),
                "price": safe_float(fast_info.last_price),
                "change": safe_float(getattr(fast_info, "last_price", 0) -
                                     getattr(fast_info, "previous_close", 0)),
                "change_pct": 0.0,
                "market_cap": format_large_number(getattr(fast_info, "market_cap", None)),
                "update_time": format_datetime(),
            }
        return {"error": f"未找到股票 {symbol}"}

    price = safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    prev_close = safe_float(info.get("regularMarketPreviousClose") or info.get("previousClose"))
    change = price - prev_close if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "symbol": symbol.upper(),
        "name": safe_str(info.get("shortName") or info.get("longName")),
        "price": price,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "open": safe_float(info.get("regularMarketOpen") or info.get("open")),
        "high": safe_float(info.get("regularMarketDayHigh") or info.get("dayHigh")),
        "low": safe_float(info.get("regularMarketDayLow") or info.get("dayLow")),
        "prev_close": prev_close,
        "volume": safe_float(info.get("regularMarketVolume") or info.get("volume")),
        "market_cap": format_large_number(info.get("marketCap")),
        "pe_ratio": safe_float(info.get("trailingPE")),
        "eps": safe_float(info.get("trailingEps")),
        "dividend_yield": safe_float(info.get("dividendYield", 0)) * 100,
        "52w_high": safe_float(info.get("fiftyTwoWeekHigh")),
        "52w_low": safe_float(info.get("fiftyTwoWeekLow")),
        "currency": safe_str(info.get("currency"), "USD"),
        "exchange": safe_str(info.get("exchange")),
        "update_time": format_datetime(),
    }


@api_error_handler("获取股票历史数据失败")
def get_stock_history(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
) -> dict[str, Any]:
    """
    获取股票历史 K 线数据。

    参数：
        symbol: 股票代码
        period: 时间范围 1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max
        interval: K线间隔 1m/2m/5m/15m/30m/60m/90m/1h/1d/5d/1wk/1mo/3mo

    返回：
        包含K线数据的字典
    """
    yf = _import_yfinance()
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        return {"error": f"未获取到股票 {symbol} 的历史数据"}

    records = []
    for date, row in df.iterrows():
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(safe_float(row.get("Open")), 2),
            "high": round(safe_float(row.get("High")), 2),
            "low": round(safe_float(row.get("Low")), 2),
            "close": round(safe_float(row.get("Close")), 2),
            "volume": int(safe_float(row.get("Volume"))),
        })

    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "count": len(records),
        "data": records,
    }


# ==================== 公司基本面 ====================


@api_error_handler("获取公司信息失败")
def get_company_info(symbol: str) -> dict[str, Any]:
    """
    获取公司基本信息。

    参数：
        symbol: 股票代码

    返回：
        包含公司信息的字典
    """
    yf = _import_yfinance()
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info:
        return {"error": f"未找到公司 {symbol}"}

    return {
        "symbol": symbol.upper(),
        "name": safe_str(info.get("longName")),
        "sector": safe_str(info.get("sector")),
        "industry": safe_str(info.get("industry")),
        "country": safe_str(info.get("country")),
        "website": safe_str(info.get("website")),
        "employees": info.get("fullTimeEmployees"),
        "description": safe_str(info.get("longBusinessSummary", ""))[:500],
        "market_cap": format_large_number(info.get("marketCap")),
        "enterprise_value": format_large_number(info.get("enterpriseValue")),
        "update_time": format_datetime(),
    }


@api_error_handler("获取财务数据失败")
def get_financials(symbol: str) -> dict[str, Any]:
    """
    获取公司财务数据。

    参数：
        symbol: 股票代码

    返回：
        包含财务数据的字典
    """
    yf = _import_yfinance()
    ticker = yf.Ticker(symbol)
    info = ticker.info

    if not info:
        return {"error": f"未找到公司 {symbol}"}

    return {
        "symbol": symbol.upper(),
        "name": safe_str(info.get("shortName")),
        "valuation": {
            "market_cap": format_large_number(info.get("marketCap")),
            "pe_trailing": safe_float(info.get("trailingPE")),
            "pe_forward": safe_float(info.get("forwardPE")),
            "peg_ratio": safe_float(info.get("pegRatio")),
            "price_to_book": safe_float(info.get("priceToBook")),
            "price_to_sales": safe_float(info.get("priceToSalesTrailing12Months")),
        },
        "profitability": {
            "profit_margin": safe_float(info.get("profitMargins", 0)) * 100,
            "operating_margin": safe_float(info.get("operatingMargins", 0)) * 100,
            "gross_margin": safe_float(info.get("grossMargins", 0)) * 100,
            "roe": safe_float(info.get("returnOnEquity", 0)) * 100,
            "roa": safe_float(info.get("returnOnAssets", 0)) * 100,
        },
        "income": {
            "revenue": format_large_number(info.get("totalRevenue")),
            "revenue_growth": safe_float(info.get("revenueGrowth", 0)) * 100,
            "earnings": format_large_number(info.get("netIncomeToCommon")),
            "earnings_growth": safe_float(info.get("earningsGrowth", 0)) * 100,
            "eps_trailing": safe_float(info.get("trailingEps")),
            "eps_forward": safe_float(info.get("forwardEps")),
        },
        "dividend": {
            "dividend_rate": safe_float(info.get("dividendRate")),
            "dividend_yield": safe_float(info.get("dividendYield", 0)) * 100,
            "payout_ratio": safe_float(info.get("payoutRatio", 0)) * 100,
        },
        "balance_sheet": {
            "total_cash": format_large_number(info.get("totalCash")),
            "total_debt": format_large_number(info.get("totalDebt")),
            "debt_to_equity": safe_float(info.get("debtToEquity")),
            "current_ratio": safe_float(info.get("currentRatio")),
            "quick_ratio": safe_float(info.get("quickRatio")),
        },
        "update_time": format_datetime(),
    }


# ==================== 主要指数 ====================


@api_error_handler("获取主要指数失败")
def get_major_indices() -> dict[str, Any]:
    """
    获取主要市场指数。

    返回：
        包含主要指数数据的字典
    """
    yf = _import_yfinance()

    indices = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
        "^RUT": "Russell 2000",
        "^VIX": "VIX",
        "^HSI": "恒生指数",
        "^N225": "日经225",
        "^FTSE": "富时100",
        "^GDAXI": "德国DAX",
    }

    results = []
    for symbol, name in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            fast_info = ticker.fast_info
            if hasattr(fast_info, "last_price") and fast_info.last_price:
                price = fast_info.last_price
                prev = getattr(fast_info, "previous_close", price)
                change = price - prev
                change_pct = (change / prev * 100) if prev else 0
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                })
        except Exception:
            continue

    return {
        "indices": results,
        "update_time": format_datetime(),
    }


# ==================== 股票搜索 ====================


POPULAR_STOCKS = [
    {"symbol": "AAPL", "name": "Apple Inc."},
    {"symbol": "MSFT", "name": "Microsoft Corporation"},
    {"symbol": "GOOGL", "name": "Alphabet Inc."},
    {"symbol": "AMZN", "name": "Amazon.com Inc."},
    {"symbol": "NVDA", "name": "NVIDIA Corporation"},
    {"symbol": "META", "name": "Meta Platforms Inc."},
    {"symbol": "TSLA", "name": "Tesla Inc."},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    {"symbol": "JPM", "name": "JPMorgan Chase"},
    {"symbol": "V", "name": "Visa Inc."},
    {"symbol": "JNJ", "name": "Johnson & Johnson"},
    {"symbol": "WMT", "name": "Walmart Inc."},
    {"symbol": "PG", "name": "Procter & Gamble"},
    {"symbol": "MA", "name": "Mastercard"},
    {"symbol": "HD", "name": "Home Depot"},
    {"symbol": "DIS", "name": "Walt Disney"},
    {"symbol": "NFLX", "name": "Netflix Inc."},
    {"symbol": "AMD", "name": "Advanced Micro Devices"},
    {"symbol": "INTC", "name": "Intel Corporation"},
    {"symbol": "CRM", "name": "Salesforce Inc."},
    {"symbol": "0700.HK", "name": "腾讯控股"},
    {"symbol": "9988.HK", "name": "阿里巴巴"},
    {"symbol": "9618.HK", "name": "京东集团"},
    {"symbol": "3690.HK", "name": "美团"},
    {"symbol": "9999.HK", "name": "网易"},
    {"symbol": "1810.HK", "name": "小米集团"},
    {"symbol": "2318.HK", "name": "中国平安"},
    {"symbol": "0005.HK", "name": "汇丰控股"},
    {"symbol": "1299.HK", "name": "友邦保险"},
    {"symbol": "0388.HK", "name": "香港交易所"},
]


def search_stock(keyword: str) -> dict[str, Any]:
    """
    搜索股票。

    参数：
        keyword: 搜索关键字

    返回：
        包含搜索结果的字典
    """
    keyword_lower = keyword.lower()
    results = []

    for stock in POPULAR_STOCKS:
        if (keyword_lower in stock["symbol"].lower() or
                keyword_lower in stock["name"].lower()):
            results.append(stock)
            if len(results) >= 10:
                break

    if not results and len(keyword) >= 1:
        try:
            yf = _import_yfinance()
            ticker = yf.Ticker(keyword.upper())
            info = ticker.info
            if info and info.get("shortName"):
                results.append({
                    "symbol": keyword.upper(),
                    "name": info.get("shortName"),
                })
        except Exception:
            pass

    return {
        "keyword": keyword,
        "count": len(results),
        "results": results,
    }


__all__ = [
    "get_stock_quote",
    "get_stock_history",
    "get_company_info",
    "get_financials",
    "get_major_indices",
    "search_stock",
]
