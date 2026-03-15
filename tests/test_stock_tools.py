"""Tests for stock analysis tools."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from nanobot.agent.tools.stock.indicators import (
    analyze_trend,
    calc_ema,
    calc_kdj,
    calc_ma,
    calc_macd,
    calc_rsi,
)
from nanobot.agent.tools.stock.stock_tools import (
    AddStockTool,
    GetWatchlistTool,
    RemoveStockTool,
    _detect_market,
)


# ==================== Helper Functions ====================


def test_detect_market_shanghai() -> None:
    """Test market detection for Shanghai stocks."""
    assert _detect_market("600519") == "sh"
    assert _detect_market("601318") == "sh"
    assert _detect_market("900001") == "sh"


def test_detect_market_shenzhen() -> None:
    """Test market detection for Shenzhen stocks."""
    assert _detect_market("000001") == "sz"
    assert _detect_market("002594") == "sz"
    assert _detect_market("300750") == "sz"


def test_detect_market_beijing() -> None:
    """Test market detection for Beijing stocks."""
    assert _detect_market("430001") == "bj"
    assert _detect_market("830001") == "bj"


# ==================== Technical Indicators ====================


class TestCalcMA:
    """Tests for moving average calculation."""

    def test_basic_ma(self) -> None:
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        ma3 = calc_ma(prices, 3)
        assert ma3[0] is None
        assert ma3[1] is None
        assert ma3[2] == pytest.approx(11.0)  # (10+11+12)/3
        assert ma3[3] == pytest.approx(12.0)  # (11+12+13)/3
        assert ma3[4] == pytest.approx(13.0)  # (12+13+14)/3

    def test_insufficient_data(self) -> None:
        prices = [10.0, 11.0]
        ma5 = calc_ma(prices, 5)
        assert all(v is None for v in ma5)

    def test_single_period(self) -> None:
        prices = [10.0, 20.0, 30.0]
        ma1 = calc_ma(prices, 1)
        assert ma1 == [10.0, 20.0, 30.0]


class TestCalcEMA:
    """Tests for exponential moving average calculation."""

    def test_basic_ema(self) -> None:
        prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        ema3 = calc_ema(prices, 3)
        assert ema3[0] is None
        assert ema3[1] is None
        assert ema3[2] is not None
        # EMA should be calculated for remaining values
        assert len(ema3) == len(prices)

    def test_insufficient_data(self) -> None:
        prices = [10.0, 11.0]
        ema5 = calc_ema(prices, 5)
        assert all(v is None for v in ema5)


class TestCalcMACD:
    """Tests for MACD calculation."""

    def test_macd_output_structure(self) -> None:
        # Need at least 26 data points for slow EMA
        prices = [float(i) for i in range(30)]
        macd = calc_macd(prices, fast=12, slow=26, signal=9)
        assert "dif" in macd
        assert "dea" in macd
        assert "macd" in macd
        assert len(macd["dif"]) == len(prices)

    def test_macd_insufficient_data(self) -> None:
        prices = [10.0, 11.0, 12.0]
        macd = calc_macd(prices)
        # All values should be None for insufficient data
        assert all(v is None for v in macd["dif"])


class TestCalcKDJ:
    """Tests for KDJ calculation."""

    def test_kdj_output_structure(self) -> None:
        high = [float(i + 1) for i in range(20)]
        low = [float(i) for i in range(20)]
        close = [float(i + 0.5) for i in range(20)]
        kdj = calc_kdj(high, low, close, n=9)
        assert "k" in kdj
        assert "d" in kdj
        assert "j" in kdj
        assert len(kdj["k"]) == len(close)

    def test_kdj_default_values(self) -> None:
        # Insufficient data should return default 50.0 values
        high = [11.0, 12.0]
        low = [10.0, 11.0]
        close = [10.5, 11.5]
        kdj = calc_kdj(high, low, close, n=9)
        assert kdj["k"] == [50.0, 50.0]
        assert kdj["d"] == [50.0, 50.0]

    def test_kdj_same_high_low(self) -> None:
        # When high == low, RSV should be 50
        high = [10.0] * 15
        low = [10.0] * 15
        close = [10.0] * 15
        kdj = calc_kdj(high, low, close, n=9)
        # After the initial period, values should tend toward 50
        assert len(kdj["k"]) == 15


class TestCalcRSI:
    """Tests for RSI calculation."""

    def test_rsi_output_length(self) -> None:
        prices = [float(i) for i in range(20)]
        rsi = calc_rsi(prices, period=14)
        assert len(rsi) == len(prices)
        # First 14 values should be None
        assert all(v is None for v in rsi[:14])
        assert rsi[14] is not None

    def test_rsi_range(self) -> None:
        # RSI should be between 0 and 100
        prices = [10.0, 11.0, 10.5, 12.0, 11.5, 13.0, 12.5, 14.0, 13.5, 15.0,
                  14.5, 16.0, 15.5, 17.0, 16.5, 18.0]
        rsi = calc_rsi(prices, period=14)
        for v in rsi:
            if v is not None:
                assert 0 <= v <= 100

    def test_rsi_all_gains(self) -> None:
        # Continuously rising prices should give RSI close to 100
        prices = [float(i) for i in range(20)]
        rsi = calc_rsi(prices, period=14)
        assert rsi[-1] == 100.0  # All gains, no losses


class TestAnalyzeTrend:
    """Tests for trend analysis function."""

    def test_bullish_ma_trend(self) -> None:
        indicators = {
            "close": 100.0,
            "ma5": 98.0,
            "ma10": 95.0,
            "ma20": 90.0,
        }
        analysis = analyze_trend(indicators)
        assert any("多头排列" in a for a in analysis)

    def test_bearish_ma_trend(self) -> None:
        indicators = {
            "close": 80.0,
            "ma5": 85.0,
            "ma10": 90.0,
            "ma20": 95.0,
        }
        analysis = analyze_trend(indicators)
        assert any("空头排列" in a for a in analysis)

    def test_kdj_overbought(self) -> None:
        indicators = {
            "kdj_k": 85.0,
            "kdj_d": 82.0,
        }
        analysis = analyze_trend(indicators)
        assert any("超买" in a for a in analysis)

    def test_kdj_oversold(self) -> None:
        indicators = {
            "kdj_k": 15.0,
            "kdj_d": 18.0,
        }
        analysis = analyze_trend(indicators)
        assert any("超卖" in a for a in analysis)

    def test_rsi_overbought(self) -> None:
        indicators = {"rsi": 75.0}
        analysis = analyze_trend(indicators)
        assert any("RSI超买" in a for a in analysis)

    def test_rsi_oversold(self) -> None:
        indicators = {"rsi": 25.0}
        analysis = analyze_trend(indicators)
        assert any("RSI超卖" in a for a in analysis)

    def test_custom_thresholds(self) -> None:
        indicators = {"rsi": 65.0}
        # With default threshold (70), this should not trigger
        analysis = analyze_trend(indicators)
        assert not any("RSI超买" in a for a in analysis)
        # With custom threshold (60), this should trigger
        analysis = analyze_trend(indicators, thresholds={"rsi_overbought": 60})
        assert any("RSI超买" in a for a in analysis)


# ==================== Watchlist Tools ====================


class TestWatchlistTools:
    """Tests for watchlist management tools."""

    @pytest.fixture
    def temp_workspace(self, tmp_path: Path):
        """Create a temporary workspace for testing."""
        workspace = tmp_path / ".nanobot" / "workspace"
        workspace.mkdir(parents=True)
        return workspace

    @pytest.fixture
    def mock_workspace(self, temp_workspace: Path):
        """Mock the workspace path for watchlist tools."""
        with patch(
            "nanobot.agent.tools.stock.stock_tools._get_workspace_path",
            return_value=temp_workspace,
        ):
            yield temp_workspace

    async def test_get_empty_watchlist(self, mock_workspace: Path) -> None:
        tool = GetWatchlistTool()
        result = await tool.execute()
        data = json.loads(result)
        assert data["count"] == 0
        assert data["watchlist"] == []

    async def test_add_stock(self, mock_workspace: Path) -> None:
        tool = AddStockTool()
        result = await tool.execute(code="600519", name="贵州茅台")
        data = json.loads(result)
        assert data["success"] is True
        assert "600519" in data["message"]

    async def test_add_duplicate_stock(self, mock_workspace: Path) -> None:
        tool = AddStockTool()
        await tool.execute(code="600519", name="贵州茅台")
        result = await tool.execute(code="600519", name="贵州茅台")
        data = json.loads(result)
        assert "error" in data
        assert "已在关注列表中" in data["error"]

    async def test_remove_stock(self, mock_workspace: Path) -> None:
        add_tool = AddStockTool()
        remove_tool = RemoveStockTool()

        # Add first
        await add_tool.execute(code="600519", name="贵州茅台")

        # Remove
        result = await remove_tool.execute(code="600519")
        data = json.loads(result)
        assert data["success"] is True

    async def test_remove_nonexistent_stock(self, mock_workspace: Path) -> None:
        tool = RemoveStockTool()
        result = await tool.execute(code="999999")
        data = json.loads(result)
        assert "error" in data
        assert "不在关注列表中" in data["error"]

    async def test_watchlist_persistence(self, mock_workspace: Path) -> None:
        add_tool = AddStockTool()
        get_tool = GetWatchlistTool()

        # Add stock
        await add_tool.execute(code="600519", name="贵州茅台", market="sh")

        # Verify it persists
        result = await get_tool.execute()
        data = json.loads(result)
        assert data["count"] == 1
        assert data["watchlist"][0]["code"] == "600519"
        assert data["watchlist"][0]["name"] == "贵州茅台"
        assert data["watchlist"][0]["market"] == "sh"


# ==================== Tool Validation ====================


class TestStockToolValidation:
    """Tests for stock tool parameter validation."""

    def test_add_stock_parameters(self) -> None:
        tool = AddStockTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "code" in params["properties"]
        assert "name" in params["properties"]
        assert "code" in params["required"]
        assert "name" in params["required"]

    def test_add_stock_validation_missing_required(self) -> None:
        tool = AddStockTool()
        errors = tool.validate_params({"code": "600519"})
        assert any("name" in e for e in errors)

    def test_get_watchlist_no_params(self) -> None:
        tool = GetWatchlistTool()
        params = tool.parameters
        assert params["required"] == []

    def test_remove_stock_validation(self) -> None:
        tool = RemoveStockTool()
        errors = tool.validate_params({})
        assert any("code" in e for e in errors)
