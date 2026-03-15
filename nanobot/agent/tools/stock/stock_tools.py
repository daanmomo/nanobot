"""
A股股票分析工具

提供 A 股市场分析所需的工具类，包括：
- 关注列表管理
- 实时行情查询
- 历史数据获取
- 技术指标计算
- 板块分析
- 资金流向
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool

# ==================== 配置与工具函数 ====================


def _get_workspace_path() -> Path:
    """获取工作区路径。"""
    return Path.home() / ".nanobot" / "workspace"


def _get_watchlist_path() -> Path:
    """获取关注列表路径。"""
    return _get_workspace_path() / "stock_watchlist.json"


def _load_watchlist() -> list[dict[str, Any]]:
    """加载关注列表。"""
    path = _get_watchlist_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_watchlist(watchlist: list[dict[str, Any]]) -> None:
    """保存关注列表。"""
    path = _get_watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def _detect_market(code: str) -> str:
    """根据股票代码判断市场。"""
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("4", "8")):
        return "bj"
    return "sz"


def _now_str() -> str:
    """当前时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 关注列表工具 ====================


class GetWatchlistTool(Tool):
    """获取股票关注列表工具。"""

    @property
    def name(self) -> str:
        return "stock_get_watchlist"

    @property
    def description(self) -> str:
        return "获取当前股票关注列表，返回已添加的股票代码和名称"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        watchlist = _load_watchlist()
        result = {"watchlist": watchlist, "count": len(watchlist)}
        return json.dumps(result, ensure_ascii=False, indent=2)


class AddStockTool(Tool):
    """添加股票到关注列表工具。"""

    @property
    def name(self) -> str:
        return "stock_add"

    @property
    def description(self) -> str:
        return "添加股票到关注列表。需要提供股票代码和名称。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字，如 600519）",
                },
                "name": {
                    "type": "string",
                    "description": "股票名称（如 贵州茅台）",
                },
                "market": {
                    "type": "string",
                    "description": "市场 sh/sz/bj/auto（默认 auto 自动判断）",
                    "enum": ["sh", "sz", "bj", "auto"],
                },
            },
            "required": ["code", "name"],
        }

    async def execute(self, **kwargs: Any) -> str:
        code = kwargs.get("code", "")
        name = kwargs.get("name", "")
        market = kwargs.get("market", "auto")

        if market == "auto":
            market = _detect_market(code)

        watchlist = _load_watchlist()
        if any(s.get("code") == code for s in watchlist):
            return json.dumps({"error": f"股票 {code} 已在关注列表中"}, ensure_ascii=False)

        watchlist.append({"code": code, "name": name, "market": market})
        _save_watchlist(watchlist)
        return json.dumps({"success": True, "message": f"已添加 {name}（{code}）"}, ensure_ascii=False)


class RemoveStockTool(Tool):
    """从关注列表移除股票工具。"""

    @property
    def name(self) -> str:
        return "stock_remove"

    @property
    def description(self) -> str:
        return "从关注列表移除指定股票"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要移除的股票代码（6位数字）",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        code = kwargs.get("code", "")
        watchlist = _load_watchlist()
        new_list = [s for s in watchlist if s.get("code") != code]
        if len(new_list) == len(watchlist):
            return json.dumps({"error": f"股票 {code} 不在关注列表中"}, ensure_ascii=False)
        _save_watchlist(new_list)
        return json.dumps({"success": True, "message": f"已移除股票 {code}"}, ensure_ascii=False)


# ==================== 行情数据工具 ====================


class GetRealtimeQuoteTool(Tool):
    """获取股票实时行情工具。"""

    @property
    def name(self) -> str:
        return "stock_realtime_quote"

    @property
    def description(self) -> str:
        return "获取指定股票的实时行情数据，包括价格、涨跌幅、成交量等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字，如 600519）",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        code = kwargs.get("code", "")
        result = akshare_api.get_stock_realtime_quote(code)
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetHistoryDataTool(Tool):
    """获取股票历史K线数据工具。"""

    @property
    def name(self) -> str:
        return "stock_history"

    @property
    def description(self) -> str:
        return "获取股票历史K线数据，包括开盘、最高、最低、收盘、成交量等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "period": {
                    "type": "string",
                    "description": "K线周期：daily（日线）/weekly（周线）/monthly（月线）",
                    "enum": ["daily", "weekly", "monthly"],
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式 YYYYMMDD（默认60天前）",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式 YYYYMMDD（默认今天）",
                },
                "adjust": {
                    "type": "string",
                    "description": "复权类型：qfq（前复权）/hfq（后复权）/空（不复权）",
                    "enum": ["qfq", "hfq", ""],
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        code = kwargs.get("code", "")
        period = kwargs.get("period", "daily")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        adjust = kwargs.get("adjust", "qfq")

        result = akshare_api.get_stock_history(code, period, start_date, end_date, adjust)
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetIndexDataTool(Tool):
    """获取主要指数行情工具。"""

    @property
    def name(self) -> str:
        return "stock_index"

    @property
    def description(self) -> str:
        return "获取主要指数实时行情，包括上证指数、深证成指、创业板指等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        result = akshare_api.get_index_spot()
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetMarketStatsTool(Tool):
    """获取市场统计数据工具。"""

    @property
    def name(self) -> str:
        return "stock_market_stats"

    @property
    def description(self) -> str:
        return "获取A股市场统计数据，包括涨跌家数、涨停跌停数量、总成交额等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        result = akshare_api.get_market_stats()
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetSectorRankingTool(Tool):
    """获取板块涨跌排名工具。"""

    @property
    def name(self) -> str:
        return "stock_sector_ranking"

    @property
    def description(self) -> str:
        return "获取行业板块或概念板块的涨跌排名"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sector_type": {
                    "type": "string",
                    "description": "板块类型：industry（行业板块）/concept（概念板块）",
                    "enum": ["industry", "concept"],
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        sector_type = kwargs.get("sector_type", "industry")
        if sector_type == "industry":
            result = akshare_api.get_industry_boards()
        else:
            result = akshare_api.get_concept_boards()
        result["sector_type"] = sector_type
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetMoneyFlowTool(Tool):
    """获取个股资金流向工具。"""

    @property
    def name(self) -> str:
        return "stock_money_flow"

    @property
    def description(self) -> str:
        return "获取指定股票的资金流向数据，包括主力净流入、大单中单小单净流入等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        code = kwargs.get("code", "")
        result = akshare_api.get_stock_fund_flow(code)
        return json.dumps(result, ensure_ascii=False, indent=2)


class GetNorthFlowTool(Tool):
    """获取北向资金流向工具。"""

    @property
    def name(self) -> str:
        return "stock_north_flow"

    @property
    def description(self) -> str:
        return "获取北向资金（沪股通、深股通）的流向数据"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        result = akshare_api.get_north_fund_flow()
        return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 技术指标工具 ====================


class CalculateIndicatorsTool(Tool):
    """计算股票技术指标工具。"""

    @property
    def name(self) -> str:
        return "stock_indicators"

    @property
    def description(self) -> str:
        return "计算股票技术指标，包括MA（移动平均线）、MACD、KDJ、RSI等，并给出趋势分析"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "股票代码（6位数字）",
                },
                "days": {
                    "type": "integer",
                    "description": "计算所需的历史天数（默认60天）",
                    "minimum": 30,
                    "maximum": 365,
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api
        from nanobot.agent.tools.stock.indicators import (
            analyze_trend,
            calc_kdj,
            calc_ma,
            calc_macd,
            calc_rsi,
        )

        code = kwargs.get("code", "")
        days = kwargs.get("days", 60)

        # 获取历史数据
        history = akshare_api.get_stock_history(
            code, "daily",
            (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        )
        if "error" in history:
            return json.dumps(history, ensure_ascii=False)

        data = history.get("data", [])
        if len(data) < 20:
            return json.dumps({"error": "历史数据不足，至少需要20个交易日"}, ensure_ascii=False)

        close = [d["close"] for d in data]
        high = [d["high"] for d in data]
        low = [d["low"] for d in data]

        # 计算 MA
        ma_periods = [5, 10, 20]
        ma_values = {f"ma{p}": calc_ma(close, p) for p in ma_periods}

        # 计算 MACD
        macd = calc_macd(close, 12, 26, 9)

        # 计算 KDJ
        kdj = calc_kdj(high, low, close, 9, 3, 3)

        # 计算 RSI
        rsi = calc_rsi(close, 14)

        # 组装结果
        latest: dict[str, Any] = {
            "code": code,
            "date": data[-1]["date"],
            "close": close[-1],
        }

        for p in ma_periods:
            ma = ma_values.get(f"ma{p}")
            if ma and ma[-1] is not None:
                latest[f"ma{p}"] = round(ma[-1], 2)

        latest["macd_dif"] = round(macd["dif"][-1], 4) if macd["dif"][-1] else None
        latest["macd_dea"] = round(macd["dea"][-1], 4) if macd["dea"][-1] else None
        latest["macd_hist"] = round(macd["macd"][-1], 4) if macd["macd"][-1] else None
        latest["kdj_k"] = round(kdj["k"][-1], 2)
        latest["kdj_d"] = round(kdj["d"][-1], 2)
        latest["kdj_j"] = round(kdj["j"][-1], 2)
        latest["rsi"] = round(rsi[-1], 2) if rsi[-1] else None
        latest["analysis"] = analyze_trend(latest)

        return json.dumps(latest, ensure_ascii=False, indent=2)


# ==================== 搜索工具 ====================


class SearchStockTool(Tool):
    """搜索股票工具。"""

    @property
    def name(self) -> str:
        return "stock_search"

    @property
    def description(self) -> str:
        return "通过股票代码或名称搜索股票"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键字（股票代码或名称）",
                },
            },
            "required": ["keyword"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        keyword = kwargs.get("keyword", "")
        result = akshare_api.search_stock(keyword)
        return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 报告生成工具 ====================


class GenerateDailyReportTool(Tool):
    """生成每日分析报告工具。"""

    @property
    def name(self) -> str:
        return "stock_daily_report"

    @property
    def description(self) -> str:
        return "生成A股市场每日分析报告，包括市场概况、板块涨幅、关注股票等"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from nanobot.agent.tools.stock import akshare_api

        def _safe_float(value: Any, default: float = 0.0) -> float:
            try:
                if value is None or value == "":
                    return default
                return float(value)
            except Exception:
                return default

        today = datetime.now()
        lines = [f"# A股市场日报 - {today.strftime('%Y年%m月%d日')}", ""]

        # 市场概况
        lines.append("## 市场概况\n")
        index_data = akshare_api.get_index_spot()
        if "indices" in index_data:
            lines.append("| 指数 | 收盘 | 涨跌幅 |")
            lines.append("|------|------|--------|")
            for idx in index_data["indices"][:7]:
                pct = _safe_float(idx.get("change_pct"))
                lines.append(
                    f"| {idx.get('name')} | {_safe_float(idx.get('price')):.2f} | "
                    f"{'+' if pct >= 0 else ''}{pct:.2f}% |"
                )
            lines.append("")

        stats = akshare_api.get_market_stats()
        if "error" not in stats:
            lines.append(f"- 上涨 {stats['up_count']} 家 / 下跌 {stats['down_count']} 家")
            lines.append(f"- 涨停 {stats['limit_up']} / 跌停 {stats['limit_down']}")
            lines.append(f"- 成交额 {stats['total_amount_yi']:.0f} 亿元\n")

        # 板块分析
        lines.append("## 行业板块涨幅 TOP5\n")
        industry = akshare_api.get_industry_boards()
        if "top_gainers" in industry:
            for i, s in enumerate(industry["top_gainers"][:5], 1):
                pct = _safe_float(s.get("change_pct"))
                lines.append(f"{i}. {s.get('name')} {'+' if pct >= 0 else ''}{pct:.2f}%")
            lines.append("")

        # 概念板块
        lines.append("## 概念板块涨幅 TOP5\n")
        concept = akshare_api.get_concept_boards()
        if "top_gainers" in concept:
            for i, s in enumerate(concept["top_gainers"][:5], 1):
                pct = _safe_float(s.get("change_pct"))
                lines.append(f"{i}. {s.get('name')} {'+' if pct >= 0 else ''}{pct:.2f}%")
            lines.append("")

        # 关注股票
        watchlist = _load_watchlist()
        if watchlist:
            lines.append("## 关注股票\n")
            for stock in watchlist:
                code = stock.get("code", "")
                if not code:
                    continue
                quote = akshare_api.get_stock_realtime_quote(code)
                if "error" in quote:
                    continue
                pct = _safe_float(quote.get("change_pct"))
                lines.append(
                    f"- **{quote.get('name')}**({code}): "
                    f"{_safe_float(quote.get('price')):.2f} ({'+' if pct >= 0 else ''}{pct:.2f}%)"
                )
            lines.append("")

        # 北向资金
        lines.append("## 北向资金\n")
        north = akshare_api.get_north_fund_flow()
        if "error" not in north:
            net = _safe_float(north.get("north_net"))
            lines.append(f"- 今日净流入: {'+' if net >= 0 else ''}{net / 1e8:.2f} 亿元")
            lines.append("")

        lines.append("---")
        lines.append(f"*生成时间: {_now_str()}*")

        report = "\n".join(lines)

        # 保存报告
        reports_dir = _get_workspace_path() / "stock_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"daily_{today.strftime('%Y%m%d')}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return json.dumps({
            "report": report,
            "path": str(report_path),
            "date": today.strftime("%Y%m%d"),
        }, ensure_ascii=False, indent=2)
