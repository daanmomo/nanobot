"""
AKShare API 封装模块

提供 AKShare 数据接口的统一封装：
- A股行情
- 指数数据
- 板块数据
- 资金流向数据

参考: https://github.com/akfamily/akshare
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from nanobot.agent.tools.common import (
    api_error_handler,
    format_date,
    format_datetime,
    safe_float_pandas,
    safe_optional_float,
    safe_str,
)

logger = logging.getLogger(__name__)

_AKSHARE_INSTALL_HINT = "akshare 未安装，请运行: pip install akshare"

# Aliases for internal use (shorter names)
_safe_float = safe_float_pandas
_safe_optional_float = safe_optional_float
_safe_str = safe_str
_format_datetime = format_datetime
_format_date = format_date


def _api_error_handler(error_prefix: str):
    """装饰器：统一处理 API 调用异常（支持 akshare ImportError）。"""
    base_handler = api_error_handler(error_prefix)

    def decorator(func):
        wrapped = base_handler(func)

        def wrapper(*args, **kwargs):
            result = wrapped(*args, **kwargs)
            # Replace generic ImportError message with akshare-specific hint
            if isinstance(result, dict) and "error" in result:
                if "ImportError" in str(result.get("error", "")):
                    result["error"] = _AKSHARE_INSTALL_HINT
            return result
        return wrapper
    return decorator


def _import_akshare():
    """延迟导入 akshare，避免启动时加载耗时。"""
    try:
        import akshare as ak
        return ak
    except ImportError as e:
        raise ImportError(_AKSHARE_INSTALL_HINT) from e


def _days_ago(days: int, fmt: str = "%Y%m%d") -> str:
    """获取 N 天前的日期字符串。"""
    return (datetime.now() - timedelta(days=days)).strftime(fmt)


# ==================== 缓存机制 ====================


@dataclass(frozen=True)
class _DataFrameCache:
    """DataFrame 缓存容器。"""

    fetched_at: float
    df: Any
    df_indexed: Any = None


class CacheManager:
    """简单的缓存管理器。"""

    _caches: dict[str, _DataFrameCache] = {}

    @classmethod
    def get(cls, key: str, ttl_seconds: float = 6.0) -> _DataFrameCache | None:
        """获取缓存，过期返回 None。"""
        cache = cls._caches.get(key)
        if cache is None:
            return None
        if time.time() - cache.fetched_at > ttl_seconds:
            return None
        return cache

    @classmethod
    def set(cls, key: str, df: Any, index_col: str | None = None) -> _DataFrameCache:
        """设置缓存。"""
        df_indexed = None
        if index_col and hasattr(df, "set_index"):
            try:
                df_indexed = df.set_index(index_col, drop=False)
            except Exception:
                pass
        cache = _DataFrameCache(fetched_at=time.time(), df=df, df_indexed=df_indexed)
        cls._caches[key] = cache
        return cache

    @classmethod
    def clear(cls, key: str | None = None) -> None:
        """清除缓存。"""
        if key:
            cls._caches.pop(key, None)
        else:
            cls._caches.clear()


# ==================== A股行情 ====================


def get_a_share_spot(ttl_seconds: float = 6.0) -> _DataFrameCache:
    """
    获取 A 股全市场实时行情（带缓存）。

    使用 ak.stock_zh_a_spot_em() 获取东方财富沪深京A股实时行情。

    参数：
        ttl_seconds: 缓存有效期（秒）

    返回：
        _DataFrameCache 对象，包含 df 和 df_indexed
    """
    cache_key = "a_share_spot"
    cache = CacheManager.get(cache_key, ttl_seconds)
    if cache is not None:
        return cache

    ak = _import_akshare()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_spot_em()
            return CacheManager.set(cache_key, df, index_col="代码")
        except Exception as e:
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2
                logger.warning(
                    "获取A股行情失败 (尝试 %s/%s)，%ss 后重试: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    e,
                )
                time.sleep(delay)
            else:
                raise


@_api_error_handler("获取A股实时行情失败")
def get_stock_realtime_quote(code: str) -> dict[str, Any]:
    """
    获取单只 A 股实时行情。

    参数：
        code: 股票代码（6位数字）

    返回：
        包含实时行情数据的字典
    """
    cache = get_a_share_spot()
    df_idx = cache.df_indexed

    try:
        row = df_idx.loc[code]
        if hasattr(row, "iloc"):
            row = row.iloc[0]
    except KeyError:
        df = cache.df
        stock_data = df[df["代码"] == code]
        if stock_data.empty:
            return {"error": f"未找到股票 {code}"}
        row = stock_data.iloc[0]

    def _get(key: str, default: Any = None) -> Any:
        try:
            return row.get(key, default) if hasattr(row, "get") else row[key]
        except (KeyError, TypeError):
            return default

    return {
        "code": code,
        "name": _safe_str(_get("名称")),
        "price": _safe_float(_get("最新价")),
        "change": _safe_float(_get("涨跌额")),
        "change_pct": _safe_float(_get("涨跌幅")),
        "open": _safe_float(_get("今开")),
        "high": _safe_float(_get("最高")),
        "low": _safe_float(_get("最低")),
        "pre_close": _safe_float(_get("昨收")),
        "volume": _safe_float(_get("成交量")),
        "amount": _safe_float(_get("成交额")),
        "turnover_rate": _safe_float(_get("换手率")),
        "pe_ratio": _safe_optional_float(_get("市盈率-动态")),
        "pb_ratio": _safe_optional_float(_get("市净率")),
        "total_mv": _safe_float(_get("总市值")),
        "circ_mv": _safe_float(_get("流通市值")),
        "update_time": _format_datetime(),
    }


@_api_error_handler("获取A股历史行情失败")
def get_stock_history(
    code: str,
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> dict[str, Any]:
    """
    获取 A 股历史 K 线数据。

    参数：
        code: 股票代码（6位数字）
        period: 周期 daily/weekly/monthly
        start_date: 开始日期 YYYYMMDD，默认60天前
        end_date: 结束日期 YYYYMMDD，默认今天
        adjust: 复权类型 qfq(前复权)/hfq(后复权)/空(不复权)

    返回：
        包含K线数据的字典
    """
    if end_date is None:
        end_date = _format_date()
    if start_date is None:
        start_date = _days_ago(60)

    ak = _import_akshare()
    df = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )

    if df.empty:
        return {"error": f"未获取到股票 {code} 的历史数据"}

    records = []
    for r in df.to_dict(orient="records"):
        records.append(
            {
                "date": _safe_str(r.get("日期")),
                "open": _safe_float(r.get("开盘")),
                "high": _safe_float(r.get("最高")),
                "low": _safe_float(r.get("最低")),
                "close": _safe_float(r.get("收盘")),
                "volume": _safe_float(r.get("成交量")),
                "amount": _safe_float(r.get("成交额")),
                "turnover": _safe_float(r.get("换手率")),
            }
        )

    return {
        "code": code,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "count": len(records),
        "data": records,
    }


@_api_error_handler("获取股票列表失败")
def get_stock_list() -> dict[str, Any]:
    """
    获取 A 股全市场股票列表。

    返回：
        包含股票代码和名称的字典
    """
    ak = _import_akshare()
    df = ak.stock_info_a_code_name()

    stocks = []
    for _, row in df.iterrows():
        stocks.append(
            {
                "code": _safe_str(row.get("code")),
                "name": _safe_str(row.get("name")),
            }
        )

    return {"count": len(stocks), "stocks": stocks}


# ==================== 指数行情 ====================


@_api_error_handler("获取指数行情失败")
def get_index_spot(symbol: str = "上证系列指数") -> dict[str, Any]:
    """
    获取主要指数实时行情。

    参数：
        symbol: 指数类型，可选 "沪深重要指数"/"上证系列指数"/"深证系列指数"/"中证系列指数"

    返回：
        包含指数行情数据的字典
    """
    ak = _import_akshare()
    df = ak.stock_zh_index_spot_em(symbol=symbol)

    if df.empty:
        return {"error": "未获取到指数数据"}

    # 主要指数代码
    main_indices = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000688": "科创50",
        "000300": "沪深300",
        "000016": "上证50",
        "000905": "中证500",
    }

    indices = []
    for _, row in df.iterrows():
        code = _safe_str(row.get("代码"))
        name = main_indices.get(code) or _safe_str(row.get("名称"))
        if code in main_indices or len(indices) < 10:
            indices.append(
                {
                    "code": code,
                    "name": name,
                    "price": _safe_float(row.get("最新价")),
                    "change": _safe_float(row.get("涨跌额")),
                    "change_pct": _safe_float(row.get("涨跌幅")),
                    "volume": _safe_float(row.get("成交量")),
                    "amount": _safe_float(row.get("成交额")),
                }
            )

    return {"indices": indices, "update_time": _format_datetime()}


# ==================== 市场统计 ====================


@_api_error_handler("获取市场统计失败")
def get_market_stats(
    limit_up_threshold: float = 9.9,
    limit_down_threshold: float = -9.9,
) -> dict[str, Any]:
    """
    获取市场统计数据。

    参数：
        limit_up_threshold: 涨停阈值
        limit_down_threshold: 跌停阈值

    返回：
        包含涨跌家数、涨停跌停数量等的字典
    """
    import pandas as pd
    cache = get_a_share_spot()
    df = cache.df

    pct = pd.to_numeric(df.get("涨跌幅"), errors="coerce")
    amount = pd.to_numeric(df.get("成交额"), errors="coerce")

    up_count = int((pct > 0).sum())
    down_count = int((pct < 0).sum())
    flat_count = int((pct == 0).sum())
    limit_up = int((pct >= limit_up_threshold).sum())
    limit_down = int((pct <= limit_down_threshold).sum())
    total_amount = float(amount.sum(skipna=True))
    total_stocks = len(df)

    return {
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "total_amount": total_amount,
        "total_amount_yi": round(total_amount / 1e8, 2),
        "total_stocks": total_stocks,
        "update_time": _format_datetime(),
    }


# ==================== 板块数据 ====================


@_api_error_handler("获取行业板块失败")
def get_industry_boards() -> dict[str, Any]:
    """
    获取行业板块涨跌排名。

    返回：
        包含板块涨跌排名的字典
    """
    ak = _import_akshare()
    df = ak.stock_board_industry_name_em()

    if df.empty:
        return {"error": "未获取到行业板块数据"}

    df = df.sort_values("涨跌幅", ascending=False)

    top_gainers = []
    for _, row in df.head(10).iterrows():
        top_gainers.append(
            {
                "name": _safe_str(row.get("板块名称")),
                "change_pct": _safe_float(row.get("涨跌幅")),
                "leader": _safe_str(row.get("领涨股票")),
                "amount": _safe_float(row.get("成交额")),
            }
        )

    top_losers = []
    for _, row in df.tail(10).iloc[::-1].iterrows():
        top_losers.append(
            {
                "name": _safe_str(row.get("板块名称")),
                "change_pct": _safe_float(row.get("涨跌幅")),
            }
        )

    return {
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "update_time": _format_datetime(),
    }


@_api_error_handler("获取概念板块失败")
def get_concept_boards() -> dict[str, Any]:
    """
    获取概念板块涨跌排名。

    返回：
        包含板块涨跌排名的字典
    """
    ak = _import_akshare()
    df = ak.stock_board_concept_name_em()

    if df.empty:
        return {"error": "未获取到概念板块数据"}

    df = df.sort_values("涨跌幅", ascending=False)

    top_gainers = []
    for _, row in df.head(10).iterrows():
        top_gainers.append(
            {
                "name": _safe_str(row.get("板块名称")),
                "change_pct": _safe_float(row.get("涨跌幅")),
                "leader": _safe_str(row.get("领涨股票")),
                "amount": _safe_float(row.get("成交额")),
            }
        )

    top_losers = []
    for _, row in df.tail(10).iloc[::-1].iterrows():
        top_losers.append(
            {
                "name": _safe_str(row.get("板块名称")),
                "change_pct": _safe_float(row.get("涨跌幅")),
            }
        )

    return {
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "update_time": _format_datetime(),
    }


# ==================== 资金流向 ====================


@_api_error_handler("获取个股资金流向失败")
def get_stock_fund_flow(code: str, market: str = "") -> dict[str, Any]:
    """
    获取个股资金流向数据。

    参数：
        code: 股票代码
        market: 市场 sh/sz/bj，空则自动判断

    返回：
        包含资金流向数据的字典
    """
    ak = _import_akshare()

    # 自动判断市场
    if not market:
        if code.startswith(("6", "9")):
            market = "sh"
        elif code.startswith(("4", "8")):
            market = "bj"
        else:
            market = "sz"

    df = ak.stock_individual_fund_flow(stock=code, market=market)

    if df.empty:
        return {"error": f"未获取到股票 {code} 的资金流向数据"}

    row = df.iloc[-1]
    return {
        "code": code,
        "date": _safe_str(row.get("日期")),
        "main_net_inflow": _safe_float(row.get("主力净流入-净额")),
        "main_net_inflow_pct": _safe_float(row.get("主力净流入-净占比")),
        "super_large_net": _safe_float(row.get("超大单净流入-净额")),
        "large_net": _safe_float(row.get("大单净流入-净额")),
        "medium_net": _safe_float(row.get("中单净流入-净额")),
        "small_net": _safe_float(row.get("小单净流入-净额")),
    }


@_api_error_handler("获取北向资金失败")
def get_north_fund_flow() -> dict[str, Any]:
    """
    获取北向资金流向数据。

    返回：
        包含沪股通、深股通资金流向的字典
    """
    ak = _import_akshare()
    df = ak.stock_hsgt_hist_em(symbol="北向资金")

    if df.empty:
        return {"error": "未获取到北向资金数据"}

    row = df.iloc[-1]
    return {
        "date": _safe_str(row.get("日期")),
        "north_net": _safe_float(row.get("当日资金流入") or row.get("资金流入")),
        "north_balance": _safe_float(row.get("当日余额")),
        "update_time": _format_datetime(),
    }


# ==================== 股票搜索 ====================


@_api_error_handler("搜索股票失败")
def search_stock(keyword: str) -> dict[str, Any]:
    """
    通过关键字搜索股票。

    参数：
        keyword: 搜索关键字（股票代码、名称或拼音）

    返回：
        包含搜索结果的字典
    """
    stock_list = get_stock_list()
    if "error" in stock_list:
        return stock_list

    results = []
    keyword_lower = keyword.lower()

    for stock in stock_list.get("stocks", []):
        code = stock.get("code", "")
        name = stock.get("name", "")

        # 匹配代码或名称
        if keyword_lower in code.lower() or keyword_lower in name.lower():
            results.append({"code": code, "name": name})
            if len(results) >= 10:
                break

    return {
        "keyword": keyword,
        "count": len(results),
        "results": results,
    }


__all__ = [
    "CacheManager",
    "get_a_share_spot",
    "get_stock_realtime_quote",
    "get_stock_history",
    "get_stock_list",
    "get_index_spot",
    "get_market_stats",
    "get_industry_boards",
    "get_concept_boards",
    "get_stock_fund_flow",
    "get_north_fund_flow",
    "search_stock",
]
