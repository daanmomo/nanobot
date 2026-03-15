"""
A股量化交易核心模块

提供量化交易所需的核心功能：
- 策略回测引擎
- 多种交易策略
- 选股筛选器
- 信号生成器
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from nanobot.agent.tools.stock.indicators import (
    calc_kdj,
    calc_ma,
    calc_macd,
    calc_rsi,
)

# ==================== 数据结构 ====================


@dataclass
class Trade:
    """交易记录"""

    date: str
    action: str  # "buy" or "sell"
    price: float
    shares: int
    amount: float
    reason: str = ""


@dataclass
class Position:
    """持仓信息"""

    shares: int = 0
    avg_cost: float = 0.0
    total_cost: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""

    strategy_name: str
    code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float  # 总收益率 (%)
    annual_return: float  # 年化收益率 (%)
    max_drawdown: float  # 最大回撤 (%)
    sharpe_ratio: float  # 夏普比率
    win_rate: float  # 胜率 (%)
    trade_count: int  # 交易次数
    profit_trades: int  # 盈利交易次数
    loss_trades: int  # 亏损交易次数
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)  # 资金曲线

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "code": self.code,
            "period": f"{self.start_date} ~ {self.end_date}",
            "initial_capital": self.initial_capital,
            "final_value": round(self.final_value, 2),
            "total_return": f"{self.total_return:.2f}%",
            "annual_return": f"{self.annual_return:.2f}%",
            "max_drawdown": f"{self.max_drawdown:.2f}%",
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "win_rate": f"{self.win_rate:.2f}%",
            "trade_count": self.trade_count,
            "profit_trades": self.profit_trades,
            "loss_trades": self.loss_trades,
            "trades": [
                {
                    "date": t.date,
                    "action": t.action,
                    "price": t.price,
                    "shares": t.shares,
                    "amount": round(t.amount, 2),
                    "reason": t.reason,
                }
                for t in self.trades[-20:]  # 最近20笔交易
            ],
        }


@dataclass
class Signal:
    """交易信号"""

    code: str
    name: str
    date: str
    action: str  # "buy" / "sell" / "hold"
    strategy: str
    strength: int  # 信号强度 1-5
    price: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "date": self.date,
            "action": self.action,
            "strategy": self.strategy,
            "strength": self.strength,
            "price": self.price,
            "reasons": self.reasons,
        }


# ==================== 策略基类 ====================


class Strategy(ABC):
    """策略基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    def description(self) -> str:
        """策略描述"""
        return ""

    @abstractmethod
    def generate_signals(
        self,
        data: list[dict],
        **params: Any,
    ) -> list[int]:
        """
        生成交易信号

        参数:
            data: K线数据列表，每个元素包含 date, open, high, low, close, volume
            params: 策略参数

        返回:
            信号列表，1=买入, -1=卖出, 0=持有
        """
        pass


# ==================== 内置策略 ====================


class DualMAStrategy(Strategy):
    """双均线策略"""

    @property
    def name(self) -> str:
        return "dual_ma"

    @property
    def description(self) -> str:
        return "双均线金叉死叉策略：短期均线上穿长期均线买入，下穿卖出"

    def generate_signals(
        self,
        data: list[dict],
        short_period: int = 5,
        long_period: int = 20,
        **kwargs: Any,
    ) -> list[int]:
        close = [d["close"] for d in data]
        ma_short = calc_ma(close, short_period)
        ma_long = calc_ma(close, long_period)

        signals = [0] * len(data)
        for i in range(1, len(data)):
            if ma_short[i] is None or ma_long[i] is None:
                continue
            if ma_short[i - 1] is None or ma_long[i - 1] is None:
                continue

            # 金叉：短期均线上穿长期均线
            if ma_short[i - 1] <= ma_long[i - 1] and ma_short[i] > ma_long[i]:
                signals[i] = 1
            # 死叉：短期均线下穿长期均线
            elif ma_short[i - 1] >= ma_long[i - 1] and ma_short[i] < ma_long[i]:
                signals[i] = -1

        return signals


class MACDStrategy(Strategy):
    """MACD策略"""

    @property
    def name(self) -> str:
        return "macd"

    @property
    def description(self) -> str:
        return "MACD金叉死叉策略：DIF上穿DEA买入，下穿卖出"

    def generate_signals(
        self,
        data: list[dict],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        **kwargs: Any,
    ) -> list[int]:
        close = [d["close"] for d in data]
        macd = calc_macd(close, fast, slow, signal)
        dif = macd["dif"]
        dea = macd["dea"]

        signals = [0] * len(data)
        for i in range(1, len(data)):
            if dif[i] is None or dea[i] is None:
                continue
            if dif[i - 1] is None or dea[i - 1] is None:
                continue

            # 金叉
            if dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]:
                signals[i] = 1
            # 死叉
            elif dif[i - 1] >= dea[i - 1] and dif[i] < dea[i]:
                signals[i] = -1

        return signals


class KDJStrategy(Strategy):
    """KDJ策略"""

    @property
    def name(self) -> str:
        return "kdj"

    @property
    def description(self) -> str:
        return "KDJ超买超卖策略：K线超卖区金叉买入，超买区死叉卖出"

    def generate_signals(
        self,
        data: list[dict],
        n: int = 9,
        oversold: float = 20,
        overbought: float = 80,
        **kwargs: Any,
    ) -> list[int]:
        high = [d["high"] for d in data]
        low = [d["low"] for d in data]
        close = [d["close"] for d in data]
        kdj = calc_kdj(high, low, close, n)
        k = kdj["k"]
        d = kdj["d"]

        signals = [0] * len(data)
        for i in range(1, len(data)):
            # K 在超卖区上穿 D
            if k[i - 1] <= d[i - 1] and k[i] > d[i] and k[i] < oversold + 20:
                signals[i] = 1
            # K 在超买区下穿 D
            elif k[i - 1] >= d[i - 1] and k[i] < d[i] and k[i] > overbought - 20:
                signals[i] = -1

        return signals


class RSIStrategy(Strategy):
    """RSI策略"""

    @property
    def name(self) -> str:
        return "rsi"

    @property
    def description(self) -> str:
        return "RSI超买超卖策略：RSI低于超卖线买入，高于超买线卖出"

    def generate_signals(
        self,
        data: list[dict],
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70,
        **kwargs: Any,
    ) -> list[int]:
        close = [d["close"] for d in data]
        rsi = calc_rsi(close, period)

        signals = [0] * len(data)
        for i in range(1, len(data)):
            if rsi[i] is None or rsi[i - 1] is None:
                continue

            # RSI 从超卖区向上突破
            if rsi[i - 1] <= oversold and rsi[i] > oversold:
                signals[i] = 1
            # RSI 从超买区向下突破
            elif rsi[i - 1] >= overbought and rsi[i] < overbought:
                signals[i] = -1

        return signals


class BreakoutStrategy(Strategy):
    """突破策略"""

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def description(self) -> str:
        return "N日突破策略：突破N日最高价买入，跌破N日最低价卖出"

    def generate_signals(
        self,
        data: list[dict],
        period: int = 20,
        **kwargs: Any,
    ) -> list[int]:
        signals = [0] * len(data)

        for i in range(period, len(data)):
            window_high = max(d["high"] for d in data[i - period : i])
            window_low = min(d["low"] for d in data[i - period : i])
            current_close = data[i]["close"]

            # 突破N日最高价
            if current_close > window_high:
                signals[i] = 1
            # 跌破N日最低价
            elif current_close < window_low:
                signals[i] = -1

        return signals


class VolumeBreakoutStrategy(Strategy):
    """放量突破策略"""

    @property
    def name(self) -> str:
        return "volume_breakout"

    @property
    def description(self) -> str:
        return "放量突破策略：成交量放大且价格突破时买入"

    def generate_signals(
        self,
        data: list[dict],
        price_period: int = 20,
        volume_ratio: float = 2.0,
        volume_ma_period: int = 5,
        **kwargs: Any,
    ) -> list[int]:
        signals = [0] * len(data)

        for i in range(max(price_period, volume_ma_period), len(data)):
            # 计算成交量均值
            vol_ma = sum(d["volume"] for d in data[i - volume_ma_period : i]) / volume_ma_period
            current_vol = data[i]["volume"]

            # 计算价格区间
            window_high = max(d["high"] for d in data[i - price_period : i])
            current_close = data[i]["close"]

            # 放量突破
            if current_vol > vol_ma * volume_ratio and current_close > window_high:
                signals[i] = 1
            # 放量下跌
            elif current_vol > vol_ma * volume_ratio and data[i]["close"] < data[i - 1]["close"]:
                signals[i] = -1

        return signals


class TurtleStrategy(Strategy):
    """海龟交易策略"""

    @property
    def name(self) -> str:
        return "turtle"

    @property
    def description(self) -> str:
        return "海龟交易策略：突破20日高点买入，跌破10日低点卖出"

    def generate_signals(
        self,
        data: list[dict],
        entry_period: int = 20,
        exit_period: int = 10,
        **kwargs: Any,
    ) -> list[int]:
        signals = [0] * len(data)

        for i in range(max(entry_period, exit_period), len(data)):
            entry_high = max(d["high"] for d in data[i - entry_period : i])
            exit_low = min(d["low"] for d in data[i - exit_period : i])
            current_close = data[i]["close"]

            if current_close > entry_high:
                signals[i] = 1
            elif current_close < exit_low:
                signals[i] = -1

        return signals


# ==================== 策略注册表 ====================


STRATEGIES: dict[str, Strategy] = {
    "dual_ma": DualMAStrategy(),
    "macd": MACDStrategy(),
    "kdj": KDJStrategy(),
    "rsi": RSIStrategy(),
    "breakout": BreakoutStrategy(),
    "volume_breakout": VolumeBreakoutStrategy(),
    "turtle": TurtleStrategy(),
}


def get_strategy(name: str) -> Strategy | None:
    """获取策略实例"""
    return STRATEGIES.get(name)


def list_strategies() -> list[dict[str, str]]:
    """列出所有可用策略"""
    return [
        {"name": s.name, "description": s.description}
        for s in STRATEGIES.values()
    ]


# ==================== 回测引擎 ====================


class BacktestEngine:
    """回测引擎"""

    def __init__(
        self,
        initial_capital: float = 100000,
        commission_rate: float = 0.0003,  # 佣金率 0.03%
        stamp_tax: float = 0.001,  # 印花税 0.1% (卖出时收取)
        slippage: float = 0.001,  # 滑点 0.1%
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.stamp_tax = stamp_tax
        self.slippage = slippage

    def run(
        self,
        data: list[dict],
        strategy: Strategy,
        code: str = "",
        **params: Any,
    ) -> BacktestResult:
        """
        运行回测

        参数:
            data: K线数据
            strategy: 策略实例
            code: 股票代码
            params: 策略参数
        """
        if len(data) < 30:
            raise ValueError("数据不足，至少需要30个交易日")

        signals = strategy.generate_signals(data, **params)

        capital = self.initial_capital
        position = Position()
        trades: list[Trade] = []
        equity_curve: list[dict] = []
        peak_equity = capital

        for i, (bar, signal) in enumerate(zip(data, signals)):
            price = bar["close"]
            date = bar["date"]

            # 计算当前权益
            current_equity = capital + position.shares * price
            peak_equity = max(peak_equity, current_equity)

            equity_curve.append({
                "date": date,
                "equity": round(current_equity, 2),
                "drawdown": round((peak_equity - current_equity) / peak_equity * 100, 2),
            })

            if signal == 1 and position.shares == 0:
                # 买入
                buy_price = price * (1 + self.slippage)
                shares = int(capital * 0.95 / buy_price / 100) * 100  # 按手买入
                if shares > 0:
                    amount = shares * buy_price
                    commission = max(amount * self.commission_rate, 5)  # 最低5元
                    total_cost = amount + commission

                    if total_cost <= capital:
                        capital -= total_cost
                        position.shares = shares
                        position.avg_cost = buy_price
                        position.total_cost = total_cost

                        trades.append(Trade(
                            date=date,
                            action="buy",
                            price=round(buy_price, 2),
                            shares=shares,
                            amount=round(total_cost, 2),
                            reason=strategy.name,
                        ))

            elif signal == -1 and position.shares > 0:
                # 卖出
                sell_price = price * (1 - self.slippage)
                amount = position.shares * sell_price
                commission = max(amount * self.commission_rate, 5)
                stamp = amount * self.stamp_tax
                net_amount = amount - commission - stamp

                capital += net_amount

                trades.append(Trade(
                    date=date,
                    action="sell",
                    price=round(sell_price, 2),
                    shares=position.shares,
                    amount=round(net_amount, 2),
                    reason=strategy.name,
                ))

                position = Position()

        # 计算最终权益（如果还有持仓）
        final_price = data[-1]["close"]
        final_value = capital + position.shares * final_price

        # 计算统计指标
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        # 年化收益率
        days = len(data)
        years = days / 252
        annual_return = ((final_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        # 最大回撤
        max_drawdown = max(e["drawdown"] for e in equity_curve) if equity_curve else 0

        # 夏普比率 (假设无风险利率 3%)
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                r = (equity_curve[i]["equity"] - equity_curve[i - 1]["equity"]) / equity_curve[i - 1]["equity"]
                returns.append(r)
            if returns:
                import statistics
                avg_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0.01
                sharpe_ratio = (avg_return * 252 - 0.03) / (std_return * (252 ** 0.5)) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # 胜率统计
        profit_trades = 0
        loss_trades = 0
        i = 0
        while i < len(trades) - 1:
            if trades[i].action == "buy" and trades[i + 1].action == "sell":
                if trades[i + 1].amount > trades[i].amount:
                    profit_trades += 1
                else:
                    loss_trades += 1
                i += 2
            else:
                i += 1

        trade_count = profit_trades + loss_trades
        win_rate = (profit_trades / trade_count * 100) if trade_count > 0 else 0

        return BacktestResult(
            strategy_name=strategy.name,
            code=code,
            start_date=data[0]["date"],
            end_date=data[-1]["date"],
            initial_capital=self.initial_capital,
            final_value=final_value,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            trade_count=trade_count,
            profit_trades=profit_trades,
            loss_trades=loss_trades,
            trades=trades,
            equity_curve=equity_curve,
        )


# ==================== 选股筛选器 ====================


class StockScreener:
    """选股筛选器"""

    @staticmethod
    def screen_by_ma(
        stocks_data: dict[str, list[dict]],
        ma_periods: list[int] = [5, 10, 20],
        condition: str = "bullish",  # "bullish" 多头排列, "bearish" 空头排列
    ) -> list[dict]:
        """
        均线筛选

        参数:
            stocks_data: {code: kline_data}
            ma_periods: 均线周期列表
            condition: bullish=多头排列, bearish=空头排列
        """
        results = []

        for code, data in stocks_data.items():
            if len(data) < max(ma_periods) + 1:
                continue

            close = [d["close"] for d in data]
            mas = [calc_ma(close, p) for p in ma_periods]

            # 获取最新的均线值
            latest_mas = []
            for ma in mas:
                if ma[-1] is not None:
                    latest_mas.append(ma[-1])

            if len(latest_mas) != len(ma_periods):
                continue

            current_price = close[-1]

            if condition == "bullish":
                # 多头排列：价格 > MA5 > MA10 > MA20
                is_match = current_price > latest_mas[0]
                for i in range(len(latest_mas) - 1):
                    is_match = is_match and latest_mas[i] > latest_mas[i + 1]
            else:
                # 空头排列
                is_match = current_price < latest_mas[0]
                for i in range(len(latest_mas) - 1):
                    is_match = is_match and latest_mas[i] < latest_mas[i + 1]

            if is_match:
                results.append({
                    "code": code,
                    "price": current_price,
                    "ma_values": {f"ma{p}": round(v, 2) for p, v in zip(ma_periods, latest_mas)},
                    "condition": condition,
                })

        return results

    @staticmethod
    def screen_by_macd_cross(
        stocks_data: dict[str, list[dict]],
        cross_type: str = "golden",  # "golden" 金叉, "death" 死叉
        days: int = 3,  # 最近N天内发生
    ) -> list[dict]:
        """MACD金叉/死叉筛选"""
        results = []

        for code, data in stocks_data.items():
            if len(data) < 35:
                continue

            close = [d["close"] for d in data]
            macd = calc_macd(close)
            dif = macd["dif"]
            dea = macd["dea"]

            # 检查最近N天是否发生金叉/死叉
            for i in range(-days, 0):
                if dif[i] is None or dea[i] is None:
                    continue
                if dif[i - 1] is None or dea[i - 1] is None:
                    continue

                is_cross = False
                if cross_type == "golden":
                    is_cross = dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]
                else:
                    is_cross = dif[i - 1] >= dea[i - 1] and dif[i] < dea[i]

                if is_cross:
                    results.append({
                        "code": code,
                        "price": close[-1],
                        "cross_date": data[i]["date"],
                        "cross_type": cross_type,
                        "dif": round(dif[-1], 4),
                        "dea": round(dea[-1], 4),
                    })
                    break

        return results

    @staticmethod
    def screen_by_volume(
        stocks_data: dict[str, list[dict]],
        volume_ratio: float = 2.0,
        price_change_min: float = 0,  # 最小涨幅%
    ) -> list[dict]:
        """放量筛选"""
        results = []

        for code, data in stocks_data.items():
            if len(data) < 6:
                continue

            # 计算5日平均成交量
            volumes = [d["volume"] for d in data[-6:-1]]
            avg_volume = sum(volumes) / len(volumes)

            current = data[-1]
            current_volume = current["volume"]

            if avg_volume == 0:
                continue

            ratio = current_volume / avg_volume
            price_change = (current["close"] - data[-2]["close"]) / data[-2]["close"] * 100

            if ratio >= volume_ratio and price_change >= price_change_min:
                results.append({
                    "code": code,
                    "price": current["close"],
                    "volume_ratio": round(ratio, 2),
                    "price_change": round(price_change, 2),
                    "date": current["date"],
                })

        return results

    @staticmethod
    def screen_by_rsi(
        stocks_data: dict[str, list[dict]],
        rsi_threshold: float = 30,
        condition: str = "oversold",  # "oversold" 超卖, "overbought" 超买
    ) -> list[dict]:
        """RSI筛选"""
        results = []

        for code, data in stocks_data.items():
            if len(data) < 20:
                continue

            close = [d["close"] for d in data]
            rsi = calc_rsi(close, 14)

            if rsi[-1] is None:
                continue

            is_match = False
            if condition == "oversold":
                is_match = rsi[-1] < rsi_threshold
            else:
                is_match = rsi[-1] > (100 - rsi_threshold)

            if is_match:
                results.append({
                    "code": code,
                    "price": close[-1],
                    "rsi": round(rsi[-1], 2),
                    "condition": condition,
                })

        return results


# ==================== 信号生成器 ====================


class SignalGenerator:
    """交易信号生成器"""

    def __init__(self):
        self.strategies = list(STRATEGIES.values())

    def generate(
        self,
        code: str,
        name: str,
        data: list[dict],
        strategies: list[str] | None = None,
    ) -> Signal:
        """
        生成综合交易信号

        参数:
            code: 股票代码
            name: 股票名称
            data: K线数据
            strategies: 使用的策略列表，None表示全部
        """
        if len(data) < 30:
            return Signal(
                code=code,
                name=name,
                date=datetime.now().strftime("%Y-%m-%d"),
                action="hold",
                strategy="insufficient_data",
                strength=0,
                price=data[-1]["close"] if data else 0,
                reasons=["数据不足，无法生成信号"],
            )

        buy_signals = 0
        sell_signals = 0
        reasons: list[str] = []

        strategy_list = strategies or list(STRATEGIES.keys())

        for strategy_name in strategy_list:
            strategy = get_strategy(strategy_name)
            if not strategy:
                continue

            signals = strategy.generate_signals(data)
            if signals[-1] == 1:
                buy_signals += 1
                reasons.append(f"{strategy.name}: 买入信号")
            elif signals[-1] == -1:
                sell_signals += 1
                reasons.append(f"{strategy.name}: 卖出信号")

        # 综合判断
        if buy_signals > sell_signals and buy_signals >= 2:
            action = "buy"
            strength = min(buy_signals, 5)
        elif sell_signals > buy_signals and sell_signals >= 2:
            action = "sell"
            strength = min(sell_signals, 5)
        else:
            action = "hold"
            strength = 0
            if not reasons:
                reasons.append("无明确信号")

        return Signal(
            code=code,
            name=name,
            date=data[-1]["date"],
            action=action,
            strategy="combined",
            strength=strength,
            price=data[-1]["close"],
            reasons=reasons,
        )
