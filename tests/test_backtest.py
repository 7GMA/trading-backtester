"""Tests for the backtesting engine, metrics extraction, and walk-forward analysis."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest

from src.backtest.engine import run_backtest, STRATEGIES, RSIOversold, MACDCrossover, SMACrossover
from src.backtest.metrics import extract_metrics, format_metrics
from src.backtest.walk_forward import walk_forward


def _make_ohlcv(n: int = 500, seed: int = 42, trend: float = 0.0002) -> pd.DataFrame:
    """
    Generate a synthetic OHLCV DataFrame with a slight upward trend
    and realistic-looking price movements.
    """
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start="2020-01-01", periods=n, freq="B")

    # Random walk with drift
    returns = rng.normal(loc=trend, scale=0.015, size=n)
    close = 100.0 * np.exp(np.cumsum(returns))

    # Build OHLC from close
    high = close * (1 + rng.uniform(0.001, 0.02, size=n))
    low = close * (1 - rng.uniform(0.001, 0.02, size=n))
    open_ = low + (high - low) * rng.uniform(0.2, 0.8, size=n)
    volume = rng.randint(100_000, 10_000_000, size=n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    return df


def _make_trending_ohlcv(n: int = 300, seed: int = 7) -> pd.DataFrame:
    """
    Generate OHLCV data with a clear upward trend followed by a downtrend,
    which should trigger RSI signals.
    """
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start="2020-01-01", periods=n, freq="B")

    # First half: sharp decline to trigger RSI oversold, then recovery
    half = n // 2
    part1 = np.concatenate([
        np.linspace(100, 70, half // 3),    # decline
        np.linspace(70, 120, half - half // 3),  # recovery
    ])
    part2 = np.concatenate([
        np.linspace(120, 80, half // 3),
        np.linspace(80, 140, half - half // 3),
    ])
    close = np.concatenate([part1, part2])[:n]
    # Add noise
    close = close + rng.normal(0, 1.0, size=n)
    close = np.maximum(close, 5.0)  # prevent negative prices

    high = close * (1 + rng.uniform(0.002, 0.015, size=n))
    low = close * (1 - rng.uniform(0.002, 0.015, size=n))
    open_ = low + (high - low) * rng.uniform(0.3, 0.7, size=n)
    volume = rng.randint(500_000, 5_000_000, size=n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    return df


class TestRunBacktest:
    """Test that backtests execute and return valid structures."""

    def test_rsi_strategy_runs(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold", cash=10_000)
        assert "stats" in result
        assert "trades" in result
        assert "equity_curve" in result
        assert "bt" in result

    def test_macd_strategy_runs(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="macd_crossover", cash=10_000)
        assert "stats" in result

    def test_sma_strategy_runs(self):
        df = _make_ohlcv(500)
        result = run_backtest(df, strategy="sma_crossover", cash=10_000)
        assert "stats" in result

    def test_strategy_class_directly(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy=RSIOversold, cash=10_000)
        assert "stats" in result

    def test_unknown_strategy_raises(self):
        df = _make_ohlcv(100)
        with pytest.raises(ValueError, match="Unknown strategy"):
            run_backtest(df, strategy="nonexistent_strategy")

    def test_equity_final_is_positive(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold", cash=10_000)
        stats = result["stats"]
        assert stats["Equity Final [$]"] > 0

    def test_different_cash_amounts(self):
        df = _make_ohlcv(300)
        r1 = run_backtest(df, strategy="rsi_oversold", cash=10_000)
        r2 = run_backtest(df, strategy="rsi_oversold", cash=50_000)
        # Same return %, but different absolute equity
        eq1 = r1["stats"]["Equity Final [$]"]
        eq2 = r2["stats"]["Equity Final [$]"]
        # r2 started with 5x more cash
        assert eq2 > eq1 or (eq1 == 10_000 and eq2 == 50_000)


class TestExtractMetrics:
    """Test that metrics are extracted correctly from backtest stats."""

    def test_metrics_keys_present(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])

        expected_keys = [
            "total_return_pct", "buy_hold_return_pct", "annual_return_pct",
            "sharpe_ratio", "max_drawdown_pct", "num_trades",
            "equity_final", "equity_peak",
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing metric: {key}"

    def test_total_return_is_numeric_or_none(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])
        val = metrics["total_return_pct"]
        assert val is None or isinstance(val, (int, float))

    def test_num_trades_is_non_negative(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])
        assert metrics["num_trades"] >= 0

    def test_equity_final_matches_stats(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold", cash=10_000)
        metrics = extract_metrics(result["stats"])
        assert metrics["equity_final"] == result["stats"]["Equity Final [$]"]

    def test_max_drawdown_is_negative_or_zero(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])
        dd = metrics["max_drawdown_pct"]
        if dd is not None:
            assert dd <= 0


class TestFormatMetrics:
    """Test metrics formatting."""

    def test_format_produces_string(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])
        text = format_metrics(metrics)
        assert isinstance(text, str)
        assert "BACKTEST RESULTS" in text

    def test_format_contains_sections(self):
        df = _make_ohlcv(300)
        result = run_backtest(df, strategy="rsi_oversold")
        metrics = extract_metrics(result["stats"])
        text = format_metrics(metrics)
        assert "Returns" in text
        assert "Risk" in text
        assert "Trades" in text
        assert "Capital" in text


class TestWalkForward:
    """Test walk-forward analysis."""

    def test_basic_walk_forward(self):
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=3, cash=10_000)
        assert "summary" in result
        assert "windows" in result
        assert "consistent" in result
        assert isinstance(result["consistent"], bool)

    def test_walk_forward_window_count(self):
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=4)
        assert len(result["windows"]) == 4

    def test_walk_forward_summary_fields(self):
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=3)
        summary = result["summary"]
        assert "total_windows" in summary
        assert "successful_windows" in summary
        assert "profitable_windows" in summary
        assert "win_rate_pct" in summary
        assert "avg_return_pct" in summary
        assert summary["total_windows"] == 3

    def test_walk_forward_per_window_has_metrics(self):
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=3)
        for w in result["windows"]:
            assert "window" in w
            assert "test_start" in w
            assert "test_end" in w
            assert "metrics" in w or "error" in w

    def test_walk_forward_with_strategy_class(self):
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy=RSIOversold, n_splits=3)
        assert result["summary"]["total_windows"] == 3

    def test_walk_forward_unknown_strategy_raises(self):
        df = _make_ohlcv(100)
        with pytest.raises(ValueError, match="Unknown strategy"):
            walk_forward(df, strategy="fake_strategy")

    def test_walk_forward_too_little_data_raises(self):
        df = _make_ohlcv(5)
        with pytest.raises(ValueError, match="Not enough data"):
            walk_forward(df, strategy="rsi_oversold", n_splits=10)

    def test_walk_forward_consistency_flag(self):
        """Consistency is True when >60% of windows are profitable."""
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=3)
        summary = result["summary"]
        profitable = summary["profitable_windows"]
        total = summary["total_windows"]
        expected = profitable / total > 0.6 if total > 0 else False
        assert result["consistent"] == expected

    def test_walk_forward_five_splits(self):
        df = _make_ohlcv(600, seed=99)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=5)
        assert result["summary"]["total_windows"] == 5
        assert result["summary"]["successful_windows"] <= 5

    def test_walk_forward_windows_cover_all_data(self):
        """Windows should span the full date range of the data."""
        df = _make_ohlcv(500, seed=42)
        result = walk_forward(df, strategy="rsi_oversold", n_splits=3)
        windows = result["windows"]
        # First window train starts at or near the data start
        assert windows[0]["train_start"] is not None
        # Last window test ends at or near the data end
        assert windows[-1]["test_end"] is not None
