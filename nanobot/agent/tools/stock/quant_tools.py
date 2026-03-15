"""
A股量化交易工具

提供量化交易相关的 Tool 类：
- 策略回测
- 选股筛选
- 交易信号生成
"""

import json
from datetime import datetime, timedelta
from typing import Any

from nanobot.agent.tools.base import Tool

# ==================== 策略回测工具 ====================


class BacktestTool(Tool):
    """策略回测工具"""

    @property
    def name(self) -> str:
        return "stock_backtest"

    @property
    def description(self) -> str:
        return (
            "对指定股票运行量化策略回测，计算收益率、最大回撤、夏普比率等指标。"
            "支持策略: dual_ma(双均线), macd, kdj, rsi, breakout(突破), volume_breakout(放量突破), turtle(海龟)"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字，如 600519）",
                },
                "strategy": {
                    "type": "string",
                    "description": "策略名称: dual_ma/macd/kdj/rsi/breakout/volume_breakout/turtle",
                    "enum": ["dual_ma", "macd", "kdj", "rsi", "breakout", "volume_breakout", "turtle"],
                },
                "days": {
                    "type": "integer",
                    "description": "回测天数（默认250，约1年）",
                    "minimum": 60,
                    "maximum": 1000,
                },
                "initial_capital": {
                    "type": "number",
                    "description": "初始资金（默认100000）",
                },
                "params": {
                    "type": "object",
                    "description": "策略参数（可选）",
                    "properties": {
                        "short_period": {"type": "integer", "description": "短期均线周期（dual_ma策略）"},
                        "long_period": {"type": "integer", "description": "长期均线周期（dual_ma策略）"},
                        "period": {"type": "integer", "description": "周期参数（breakout/rsi等策略）"},
                        "oversold": {"type": "number", "description": "超卖阈值（kdj/rsi策略）"},
                        "overbought": {"type": "number", "description": "超买阈值（kdj/rsi策略）"},
                    },
                },
            },
            "required": ["code", "strategy"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.quant import BacktestEngine, get_strategy

        code = kwargs.get("code", "")
        strategy_name = kwargs.get("strategy", "dual_ma")
        days = kwargs.get("days", 250)
        initial_capital = kwargs.get("initial_capital", 100000)
        params = kwargs.get("params", {})

        strategy = get_strategy(strategy_name)
        if not strategy:
            return json.dumps({"error": f"未知策略: {strategy_name}"}, ensure_ascii=False)

        # 获取历史数据
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        history = akshare_api.get_stock_history(code, "daily", start_date)

        if "error" in history:
            return json.dumps(history, ensure_ascii=False)

        data = history.get("data", [])
        if len(data) < 30:
            return json.dumps({"error": "历史数据不足，至少需要30个交易日"}, ensure_ascii=False)

        # 运行回测
        engine = BacktestEngine(initial_capital=initial_capital)
        try:
            result = engine.run(data, strategy, code, **params)
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": f"回测失败: {str(e)}"}, ensure_ascii=False)


class ListStrategiesTool(Tool):
    """列出可用策略工具"""

    @property
    def name(self) -> str:
        return "stock_list_strategies"

    @property
    def description(self) -> str:
        return "列出所有可用的量化交易策略及其说明"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock.quant import list_strategies

        strategies = list_strategies()
        return json.dumps({
            "strategies": strategies,
            "count": len(strategies),
        }, ensure_ascii=False, indent=2)


# ==================== 选股筛选工具 ====================


class ScreenStocksTool(Tool):
    """选股筛选工具"""

    @property
    def name(self) -> str:
        return "stock_screen"

    @property
    def description(self) -> str:
        return (
            "根据技术指标筛选股票。"
            "支持筛选条件: ma_bullish(均线多头排列), ma_bearish(均线空头排列), "
            "macd_golden(MACD金叉), macd_death(MACD死叉), volume(放量), rsi_oversold(RSI超卖), rsi_overbought(RSI超买)"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "description": "筛选条件",
                    "enum": [
                        "ma_bullish", "ma_bearish",
                        "macd_golden", "macd_death",
                        "volume",
                        "rsi_oversold", "rsi_overbought",
                    ],
                },
                "codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要筛选的股票代码列表（默认从关注列表筛选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量限制（默认10）",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["condition"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.quant import StockScreener
        from nanobot.agent.tools.stock.stock_tools import _load_watchlist

        condition = kwargs.get("condition", "")
        codes = kwargs.get("codes", [])
        limit = kwargs.get("limit", 10)

        # 如果没有指定股票，使用关注列表
        if not codes:
            watchlist = _load_watchlist()
            codes = [s["code"] for s in watchlist]

        if not codes:
            return json.dumps({"error": "未指定股票代码，且关注列表为空"}, ensure_ascii=False)

        # 获取所有股票的历史数据
        stocks_data: dict[str, list[dict]] = {}
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

        for code in codes:
            history = akshare_api.get_stock_history(code, "daily", start_date)
            if "error" not in history and history.get("data"):
                stocks_data[code] = history["data"]

        if not stocks_data:
            return json.dumps({"error": "未能获取任何股票数据"}, ensure_ascii=False)

        # 根据条件筛选
        screener = StockScreener()
        results: list[dict] = []

        if condition == "ma_bullish":
            results = screener.screen_by_ma(stocks_data, condition="bullish")
        elif condition == "ma_bearish":
            results = screener.screen_by_ma(stocks_data, condition="bearish")
        elif condition == "macd_golden":
            results = screener.screen_by_macd_cross(stocks_data, cross_type="golden")
        elif condition == "macd_death":
            results = screener.screen_by_macd_cross(stocks_data, cross_type="death")
        elif condition == "volume":
            results = screener.screen_by_volume(stocks_data)
        elif condition == "rsi_oversold":
            results = screener.screen_by_rsi(stocks_data, condition="oversold")
        elif condition == "rsi_overbought":
            results = screener.screen_by_rsi(stocks_data, rsi_threshold=70, condition="overbought")
        else:
            return json.dumps({"error": f"未知筛选条件: {condition}"}, ensure_ascii=False)

        return json.dumps({
            "condition": condition,
            "total_screened": len(codes),
            "matched": len(results),
            "results": results[:limit],
        }, ensure_ascii=False, indent=2)


# ==================== 交易信号工具 ====================


class GenerateSignalTool(Tool):
    """生成交易信号工具"""

    @property
    def name(self) -> str:
        return "stock_signal"

    @property
    def description(self) -> str:
        return "为指定股票生成综合交易信号，综合多种策略判断买入/卖出/持有"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "strategies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "使用的策略列表（默认全部策略）",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.quant import SignalGenerator

        code = kwargs.get("code", "")
        strategies = kwargs.get("strategies", None)

        # 获取股票名称
        quote = akshare_api.get_stock_realtime_quote(code)
        name = quote.get("name", code) if "error" not in quote else code

        # 获取历史数据
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        history = akshare_api.get_stock_history(code, "daily", start_date)

        if "error" in history:
            return json.dumps(history, ensure_ascii=False)

        data = history.get("data", [])

        # 生成信号
        generator = SignalGenerator()
        signal = generator.generate(code, name, data, strategies)

        return json.dumps(signal.to_dict(), ensure_ascii=False, indent=2)


class BatchSignalTool(Tool):
    """批量生成交易信号工具"""

    @property
    def name(self) -> str:
        return "stock_batch_signal"

    @property
    def description(self) -> str:
        return "为关注列表中的所有股票批量生成交易信号"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filter_action": {
                    "type": "string",
                    "description": "只返回指定操作的信号: buy/sell/all（默认all）",
                    "enum": ["buy", "sell", "all"],
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.quant import SignalGenerator
        from nanobot.agent.tools.stock.stock_tools import _load_watchlist

        filter_action = kwargs.get("filter_action", "all")

        watchlist = _load_watchlist()
        if not watchlist:
            return json.dumps({"error": "关注列表为空，请先添加股票"}, ensure_ascii=False)

        generator = SignalGenerator()
        signals: list[dict] = []
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

        for stock in watchlist:
            code = stock.get("code", "")
            name = stock.get("name", code)

            history = akshare_api.get_stock_history(code, "daily", start_date)
            if "error" in history:
                continue

            data = history.get("data", [])
            if not data:
                continue

            signal = generator.generate(code, name, data)

            if filter_action == "all" or signal.action == filter_action:
                signals.append(signal.to_dict())

        # 按信号强度排序
        signals.sort(key=lambda x: x["strength"], reverse=True)

        return json.dumps({
            "total": len(watchlist),
            "generated": len(signals),
            "filter": filter_action,
            "signals": signals,
        }, ensure_ascii=False, indent=2)


# ==================== 策略比较工具 ====================


class CompareStrategiesTool(Tool):
    """策略比较工具"""

    @property
    def name(self) -> str:
        return "stock_compare_strategies"

    @property
    def description(self) -> str:
        return "对同一股票比较多种策略的回测效果，帮助选择最优策略"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "strategies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要比较的策略列表（默认比较所有策略）",
                },
                "days": {
                    "type": "integer",
                    "description": "回测天数（默认250）",
                    "minimum": 60,
                    "maximum": 1000,
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.quant import STRATEGIES, BacktestEngine, get_strategy

        code = kwargs.get("code", "")
        strategy_names = kwargs.get("strategies", list(STRATEGIES.keys()))
        days = kwargs.get("days", 250)

        # 获取历史数据
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        history = akshare_api.get_stock_history(code, "daily", start_date)

        if "error" in history:
            return json.dumps(history, ensure_ascii=False)

        data = history.get("data", [])
        if len(data) < 30:
            return json.dumps({"error": "历史数据不足"}, ensure_ascii=False)

        engine = BacktestEngine()
        results: list[dict] = []

        for name in strategy_names:
            strategy = get_strategy(name)
            if not strategy:
                continue

            try:
                result = engine.run(data, strategy, code)
                results.append({
                    "strategy": name,
                    "total_return": f"{result.total_return:.2f}%",
                    "annual_return": f"{result.annual_return:.2f}%",
                    "max_drawdown": f"{result.max_drawdown:.2f}%",
                    "sharpe_ratio": round(result.sharpe_ratio, 2),
                    "win_rate": f"{result.win_rate:.2f}%",
                    "trade_count": result.trade_count,
                })
            except Exception:
                continue

        # 按总收益率排序
        results.sort(key=lambda x: float(x["total_return"].rstrip("%")), reverse=True)

        return json.dumps({
            "code": code,
            "period": f"{data[0]['date']} ~ {data[-1]['date']}",
            "comparison": results,
            "best_strategy": results[0]["strategy"] if results else None,
        }, ensure_ascii=False, indent=2)


# ==================== 导出 ====================


QUANT_TOOLS = [
    BacktestTool,
    ListStrategiesTool,
    ScreenStocksTool,
    GenerateSignalTool,
    BatchSignalTool,
    CompareStrategiesTool,
]
