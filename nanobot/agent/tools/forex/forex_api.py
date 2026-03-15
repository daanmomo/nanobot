"""
外汇数据 API 封装模块

提供外汇/汇率数据接口的统一封装：
- 实时汇率
- 历史汇率
- 汇率换算

数据来源：AKShare (中国外汇交易中心)
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


# ==================== 货币对映射 ====================


CURRENCY_PAIRS = {
    "USD/CNY": {"name": "美元/人民币", "symbol": "USDCNY"},
    "EUR/CNY": {"name": "欧元/人民币", "symbol": "EURCNY"},
    "GBP/CNY": {"name": "英镑/人民币", "symbol": "GBPCNY"},
    "JPY/CNY": {"name": "日元/人民币", "symbol": "JPYCNY"},
    "HKD/CNY": {"name": "港币/人民币", "symbol": "HKDCNY"},
    "AUD/CNY": {"name": "澳元/人民币", "symbol": "AUDCNY"},
    "CAD/CNY": {"name": "加元/人民币", "symbol": "CADCNY"},
    "SGD/CNY": {"name": "新加坡元/人民币", "symbol": "SGDCNY"},
    "CHF/CNY": {"name": "瑞士法郎/人民币", "symbol": "CHFCNY"},
    "NZD/CNY": {"name": "新西兰元/人民币", "symbol": "NZDCNY"},
}

CURRENCY_NAMES = {
    "USD": "美元",
    "EUR": "欧元",
    "GBP": "英镑",
    "JPY": "日元",
    "CNY": "人民币",
    "HKD": "港币",
    "AUD": "澳元",
    "CAD": "加元",
    "SGD": "新加坡元",
    "CHF": "瑞士法郎",
    "NZD": "新西兰元",
    "KRW": "韩元",
    "THB": "泰铢",
    "MYR": "马来西亚林吉特",
}


# ==================== 实时汇率 ====================


@api_error_handler("获取实时汇率失败")
def get_forex_rate(currency_pair: str = "USD/CNY") -> dict[str, Any]:
    """
    获取实时汇率。

    参数：
        currency_pair: 货币对（如 USD/CNY, EUR/CNY）

    返回：
        包含汇率数据的字典
    """
    ak = _import_akshare()
    df = ak.fx_spot_quote()

    if df.empty:
        return {"error": "未获取到汇率数据"}

    pair_upper = currency_pair.upper().replace(" ", "")
    if "/" not in pair_upper:
        pair_upper = f"{pair_upper}/CNY"

    base_currency = pair_upper.split("/")[0]

    # 处理日元特殊格式 (100JPY/CNY)
    search_pairs = [pair_upper]
    if base_currency == "JPY":
        search_pairs.append("100JPY/CNY")

    for _, row in df.iterrows():
        row_pair = safe_str(row.get("货币对", "")).upper()
        if row_pair in search_pairs or row_pair.replace("100", "") == pair_upper:
            buy_rate = safe_float_pandas(row.get("买报价"))
            sell_rate = safe_float_pandas(row.get("卖报价"))

            # 100日元转换为1日元
            if "100JPY" in row_pair:
                buy_rate = buy_rate / 100
                sell_rate = sell_rate / 100

            mid_rate = (buy_rate + sell_rate) / 2 if buy_rate and sell_rate else buy_rate

            return {
                "currency_pair": pair_upper,
                "base_currency": base_currency,
                "quote_currency": "CNY",
                "rate": round(mid_rate, 6),
                "buy_rate": round(buy_rate, 6),
                "sell_rate": round(sell_rate, 6) if sell_rate else None,
                "mid_rate": round(mid_rate, 6),
                "update_time": format_datetime(),
            }

    return {"error": f"未找到货币对 {currency_pair}"}


@api_error_handler("获取主要汇率失败")
def get_major_rates() -> dict[str, Any]:
    """
    获取主要货币对人民币汇率。

    返回：
        包含主要汇率的字典
    """
    ak = _import_akshare()
    df = ak.fx_spot_quote()

    if df.empty:
        return {"error": "未获取到汇率数据"}

    rates = []
    # 货币对到中文名称的映射
    pair_to_name = {
        "USD/CNY": "美元",
        "EUR/CNY": "欧元",
        "GBP/CNY": "英镑",
        "100JPY/CNY": "日元",
        "HKD/CNY": "港币",
        "AUD/CNY": "澳元",
        "CAD/CNY": "加元",
    }

    for _, row in df.iterrows():
        pair = safe_str(row.get("货币对", "")).upper()
        if pair in pair_to_name:
            buy_rate = safe_float_pandas(row.get("买报价"))
            sell_rate = safe_float_pandas(row.get("卖报价"))
            mid_rate = (buy_rate + sell_rate) / 2 if buy_rate and sell_rate else buy_rate

            # 100日元转换为1日元
            if "100JPY" in pair:
                mid_rate = mid_rate / 100

            rates.append({
                "currency": pair_to_name[pair],
                "pair": pair.replace("100", ""),
                "rate": round(mid_rate, 6),
            })

    return {
        "rates": rates,
        "base": "CNY",
        "update_time": format_datetime(),
    }


# ==================== 汇率换算 ====================


@api_error_handler("汇率换算失败")
def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> dict[str, Any]:
    """
    货币换算。

    参数：
        amount: 金额
        from_currency: 源货币代码（如 USD, EUR）
        to_currency: 目标货币代码（如 CNY）

    返回：
        包含换算结果的字典
    """
    from_upper = from_currency.upper()
    to_upper = to_currency.upper()

    if to_upper == "CNY":
        rate_data = get_forex_rate(f"{from_upper}/CNY")
        if "error" in rate_data:
            return rate_data
        rate = rate_data.get("rate", 0)
        converted = amount * rate
    elif from_upper == "CNY":
        rate_data = get_forex_rate(f"{to_upper}/CNY")
        if "error" in rate_data:
            return rate_data
        rate = rate_data.get("rate", 0)
        converted = amount / rate if rate else 0
        rate = 1 / rate if rate else 0
    else:
        from_rate_data = get_forex_rate(f"{from_upper}/CNY")
        to_rate_data = get_forex_rate(f"{to_upper}/CNY")
        if "error" in from_rate_data:
            return from_rate_data
        if "error" in to_rate_data:
            return to_rate_data
        from_rate = from_rate_data.get("rate", 0)
        to_rate = to_rate_data.get("rate", 0)
        rate = from_rate / to_rate if to_rate else 0
        converted = amount * rate

    return {
        "from_currency": from_upper,
        "to_currency": to_upper,
        "amount": amount,
        "rate": round(rate, 6),
        "converted": round(converted, 2),
        "update_time": format_datetime(),
    }


# ==================== 历史汇率 ====================


@api_error_handler("获取历史汇率失败")
def get_forex_history(currency_pair: str = "USD/CNY", days: int = 30) -> dict[str, Any]:
    """
    获取历史汇率。

    参数：
        currency_pair: 货币对
        days: 历史天数

    返回：
        包含历史汇率的字典
    """
    ak = _import_akshare()

    pair_upper = currency_pair.upper().replace(" ", "")
    if "/" not in pair_upper:
        pair_upper = f"{pair_upper}/CNY"

    base_currency = pair_upper.split("/")[0]

    symbol_map = {
        "USD": "美元",
        "EUR": "欧元",
        "GBP": "英镑",
        "JPY": "100日元",
        "HKD": "港币",
        "AUD": "澳元",
        "CAD": "加元",
    }

    symbol = symbol_map.get(base_currency, base_currency)

    try:
        df = ak.currency_boc_safe(symbol=symbol)
    except Exception:
        return {"error": f"未找到货币对 {currency_pair} 的历史数据"}

    if df.empty:
        return {"error": f"未获取到 {currency_pair} 的历史数据"}

    df = df.tail(days)

    records = []
    for _, row in df.iterrows():
        date = safe_str(row.get("日期"))
        rate = safe_float_pandas(row.get("中间价") or row.get("汇买价"))

        if base_currency == "JPY" and rate > 1:
            rate = rate / 100

        records.append({
            "date": date,
            "rate": round(rate, 4),
        })

    return {
        "currency_pair": pair_upper,
        "count": len(records),
        "data": records,
    }


__all__ = [
    "get_forex_rate",
    "get_major_rates",
    "convert_currency",
    "get_forex_history",
    "CURRENCY_PAIRS",
    "CURRENCY_NAMES",
]
