"""
技术指标计算模块

提供常用的技术分析指标计算函数：
- MA（移动平均线）
- EMA（指数移动平均线）
- MACD（异同移动平均线）
- KDJ（随机指标）
- RSI（相对强弱指标）
"""

from typing import Any


def calc_ma(close_prices: list[float], period: int) -> list[float | None]:
    """计算移动平均线。

    参数：
        close_prices: 收盘价列表
        period: 移动平均周期

    返回：
        移动平均线数据列表
    """
    if len(close_prices) < period:
        return [None] * len(close_prices)
    result: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, len(close_prices)):
        result.append(sum(close_prices[i - period + 1 : i + 1]) / period)
    return result


def calc_ema(close_prices: list[float], period: int) -> list[float | None]:
    """计算指数移动平均线。

    参数：
        close_prices: 收盘价列表
        period: EMA周期

    返回：
        EMA数据列表
    """
    if len(close_prices) < period:
        return [None] * len(close_prices)
    multiplier = 2 / (period + 1)
    ema = [sum(close_prices[:period]) / period]
    for price in close_prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return [None] * (period - 1) + ema


def calc_macd(
    close_prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float | None]]:
    """计算MACD指标。

    参数：
        close_prices: 收盘价列表
        fast: 快线周期（默认12）
        slow: 慢线周期（默认26）
        signal: 信号线周期（默认9）

    返回：
        包含 dif、dea、macd 的字典
    """
    ema_fast = calc_ema(close_prices, fast)
    ema_slow = calc_ema(close_prices, slow)

    dif: list[float | None] = []
    for i in range(len(close_prices)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif.append(ema_fast[i] - ema_slow[i])
        else:
            dif.append(None)

    # 计算DEA (signal line)
    valid_dif = [d for d in dif if d is not None]
    if len(valid_dif) >= signal:
        dea_values = calc_ema(valid_dif, signal)
        dea: list[float | None] = [None] * (len(dif) - len(dea_values)) + dea_values
    else:
        dea = [None] * len(dif)

    # 计算MACD柱
    macd: list[float | None] = []
    for i in range(len(dif)):
        if dif[i] is not None and dea[i] is not None:
            macd.append((dif[i] - dea[i]) * 2)
        else:
            macd.append(None)

    return {"dif": dif, "dea": dea, "macd": macd}


def calc_kdj(
    high: list[float],
    low: list[float],
    close: list[float],
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> dict[str, list[float]]:
    """计算KDJ指标。

    参数：
        high: 最高价列表
        low: 最低价列表
        close: 收盘价列表
        n: RSV周期（默认9）
        m1: K值平滑系数（默认3）
        m2: D值平滑系数（默认3）

    返回：
        包含 k、d、j 的字典
    """
    if len(close) < n:
        return {
            "k": [50.0] * len(close),
            "d": [50.0] * len(close),
            "j": [50.0] * len(close),
        }

    rsv: list[float | None] = []
    for i in range(len(close)):
        if i < n - 1:
            rsv.append(None)
        else:
            lowest = min(low[i - n + 1 : i + 1])
            highest = max(high[i - n + 1 : i + 1])
            if highest == lowest:
                rsv.append(50.0)
            else:
                rsv.append((close[i] - lowest) / (highest - lowest) * 100)

    k = [50.0]
    d = [50.0]
    for i in range(1, len(rsv)):
        if rsv[i] is not None:
            k.append((m1 - 1) / m1 * k[-1] + 1 / m1 * rsv[i])
            d.append((m2 - 1) / m2 * d[-1] + 1 / m2 * k[-1])
        else:
            k.append(k[-1])
            d.append(d[-1])

    j = [3 * k[i] - 2 * d[i] for i in range(len(k))]

    return {"k": k, "d": d, "j": j}


def calc_rsi(close_prices: list[float], period: int = 14) -> list[float | None]:
    """计算RSI指标。

    参数：
        close_prices: 收盘价列表
        period: RSI周期（默认14）

    返回：
        RSI数据列表
    """
    if len(close_prices) < period + 1:
        return [None] * len(close_prices)

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(close_prices)):
        change = close_prices[i] - close_prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    rsi: list[float | None] = [None] * period
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi.append(100.0)
    else:
        rsi.append(100 - 100 / (1 + avg_gain / avg_loss))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rsi.append(100 - 100 / (1 + avg_gain / avg_loss))

    return rsi


def analyze_trend(
    indicators: dict[str, Any],
    thresholds: dict[str, Any] | None = None,
) -> list[str]:
    """根据技术指标生成趋势分析。

    参数：
        indicators: 包含各项技术指标的字典
        thresholds: 阈值配置

    返回：
        分析结论列表
    """
    if thresholds is None:
        thresholds = {}
    analysis = []

    # MA趋势分析
    if indicators.get("ma5") and indicators.get("ma10") and indicators.get("ma20"):
        close = indicators.get("close", 0)
        ma5 = indicators["ma5"]
        ma10 = indicators["ma10"]
        ma20 = indicators["ma20"]

        if close > ma5 > ma10 > ma20:
            analysis.append("均线多头排列，趋势向上")
        elif close < ma5 < ma10 < ma20:
            analysis.append("均线空头排列，趋势向下")
        elif close > ma5:
            analysis.append("股价站上5日线")
        else:
            analysis.append("股价跌破5日线")

    # MACD判断
    macd_dif = indicators.get("macd_dif")
    macd_dea = indicators.get("macd_dea")
    macd_hist = indicators.get("macd_hist")
    prev_dif = indicators.get("prev_macd_dif")
    prev_dea = indicators.get("prev_macd_dea")

    if macd_dif is not None and macd_dea is not None:
        if prev_dif is not None and prev_dea is not None:
            if prev_dif < prev_dea and macd_dif > macd_dea:
                analysis.append("MACD金叉，买入信号")
            elif prev_dif > prev_dea and macd_dif < macd_dea:
                analysis.append("MACD死叉，卖出信号")
            elif macd_hist and macd_hist > 0:
                analysis.append("MACD红柱，多头占优")
            else:
                analysis.append("MACD绿柱，空头占优")

    # KDJ判断
    kdj_overbought = thresholds.get("kdj_overbought", 80)
    kdj_oversold = thresholds.get("kdj_oversold", 20)
    kdj_k = indicators.get("kdj_k")
    kdj_d = indicators.get("kdj_d")

    if kdj_k is not None and kdj_d is not None:
        if kdj_k > kdj_overbought and kdj_d > kdj_overbought:
            analysis.append("KDJ超买区域，注意回调风险")
        elif kdj_k < kdj_oversold and kdj_d < kdj_oversold:
            analysis.append("KDJ超卖区域，关注反弹机会")

    # RSI判断
    rsi_overbought = thresholds.get("rsi_overbought", 70)
    rsi_oversold = thresholds.get("rsi_oversold", 30)
    rsi = indicators.get("rsi")

    if rsi is not None:
        if rsi > rsi_overbought:
            analysis.append("RSI超买，短期可能回调")
        elif rsi < rsi_oversold:
            analysis.append("RSI超卖，短期可能反弹")

    return analysis
