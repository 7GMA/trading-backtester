"""Tests for multi-asset backtesting and strategy comparison."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest

from src.backtest.multi_asset import run_multi_asset, _build_summary
from src.backtest.comparison import compare_strategies, _compare_metrics, _determine_winner
from src.strategy.models import (
    ParsedStrategy, EntryRule, ExitRule, IndicatorCondition, Operator, LogicOperator,
)
from src.strategy.templates import TEMPLATES, get_template


def _make_ohlcv(n: int = 300, seed: int = 42, trend: float = 0.0002) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start="2020-01-01", periods=n, freq="B")
    returns = rng.normal(loc=trend, scale=0.015, size=n)
    close = 100.0 * np.exp(np.cumsum(returns))
    high = close * (1 + rng.uniform(0.001, 0.02, size=n))
    low = close * (1 - rng.uniform(0.001, 0.02, size=n))
    open_ = low + (high - low) * rng.uniform(0.2, 0.8, size=n)
    volume = rng.randint(100_000, 10_000_000, size=n)
    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume,
    }, index=dates)


def _rsi_strategy(asset: str = "AAPL") -> ParsedStrategy:
    """Create a simple RSI strategy for testing."""
    return ParsedStrategy(
        name=f"RSI Test ({asset})",
        asset=asset,
        description="Test RSI strategy",
        entry=EntryRule(conditions=[
            IndicatorCondition(indicator="RSI", params={"period": 14}, operator=Operator.LT, value=30),
        ]),
        exit=ExitRule(take_profit=0.10, stop_loss=0.05),
    )


def _macd_strategy(asset: str = "AAPL") -> ParsedStrategy:
    """Create a MACD strategy for testing."""
    return ParsedStrategy(
        name=f"MACD Test ({asset})",
        asset=asset,
        description="Test MACD strategy",
        entry=EntryRule(conditions=[
            IndicatorCondition(
                indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                operator=Operator.CROSS_ABOVE, value="MACD_SIGNAL",
            ),
        ]),
        exit=ExitRule(stop_loss=0.05, take_profit=0.10),
    )


# ---- Multi-Asset: _build_summary tests ----

class TestBuildSummary:
    """Test the summary aggregation function."""

    def test_empty_input(self):
        summary = _build_summary({}, 10_000)
        assert summary["total_assets"] == 0
        assert summary["avg_return_pct"] is None
        assert summary["best_asset"] is None

    def test_single_asset(self):
        data = {
            "AAPL": {
                "metrics": {
                    "total_return_pct": 15.0,
                    "sharpe_ratio": 1.2,
                    "win_rate_pct": 60.0,
                    "num_trades": 10,
                },
            }
        }
        summary = _build_summary(data, 10_000)
        assert summary["total_assets"] == 1
        assert summary["avg_return_pct"] == 15.0
        assert summary["best_asset"] == "AAPL"
        assert summary["total_trades"] == 10

    def test_multiple_assets(self):
        data = {
            "AAPL": {"metrics": {"total_return_pct": 20.0, "sharpe_ratio": 1.5, "win_rate_pct": 65.0, "num_trades": 8}},
            "MSFT": {"metrics": {"total_return_pct": 10.0, "sharpe_ratio": 0.8, "win_rate_pct": 50.0, "num_trades": 12}},
            "TSLA": {"metrics": {"total_return_pct": -5.0, "sharpe_ratio": -0.2, "win_rate_pct": 30.0, "num_trades": 15}},
        }
        summary = _build_summary(data, 10_000)
        assert summary["total_assets"] == 3
        assert summary["best_asset"] == "AAPL"
        assert summary["worst_asset"] == "TSLA"
        assert summary["total_trades"] == 35
        assert abs(summary["avg_return_pct"] - (20 + 10 - 5) / 3) < 0.01


# ---- Comparison: _compare_metrics tests ----

class TestCompareMetrics:
    """Test metric-by-metric comparison."""

    def test_comparison_returns_all_metrics(self):
        m_a = {"total_return_pct": 10, "annual_return_pct": 5, "sharpe_ratio": 1.0,
               "sortino_ratio": 1.5, "max_drawdown_pct": -10, "win_rate_pct": 60,
               "profit_factor": 2.0, "num_trades": 20, "avg_trade_pct": 0.5,
               "exposure_time_pct": 40}
        m_b = {"total_return_pct": 15, "annual_return_pct": 7, "sharpe_ratio": 0.8,
               "sortino_ratio": 1.0, "max_drawdown_pct": -15, "win_rate_pct": 55,
               "profit_factor": 1.5, "num_trades": 30, "avg_trade_pct": 0.3,
               "exposure_time_pct": 60}
        result = _compare_metrics(m_a, m_b)
        assert len(result) == 10
        # total return: B is higher
        total_return_row = next(r for r in result if r["metric"] == "Total Return (%)")
        assert total_return_row["winner"] == "b"
        # sharpe: A is higher
        sharpe_row = next(r for r in result if r["metric"] == "Sharpe Ratio")
        assert sharpe_row["winner"] == "a"

    def test_tie_on_equal_values(self):
        m = {"total_return_pct": 10, "annual_return_pct": 5, "sharpe_ratio": 1.0,
             "sortino_ratio": 1.0, "max_drawdown_pct": -10, "win_rate_pct": 50,
             "profit_factor": 1.5, "num_trades": 20, "avg_trade_pct": 0.5,
             "exposure_time_pct": 40}
        result = _compare_metrics(m, m)
        for row in result:
            assert row["winner"] in ("tie",)

    def test_none_values_handled(self):
        m_a = {"total_return_pct": None, "annual_return_pct": None, "sharpe_ratio": None,
               "sortino_ratio": None, "max_drawdown_pct": None, "win_rate_pct": None,
               "profit_factor": None, "num_trades": 0, "avg_trade_pct": None,
               "exposure_time_pct": None}
        m_b = {"total_return_pct": 10, "annual_return_pct": 5, "sharpe_ratio": 1.0,
               "sortino_ratio": 1.0, "max_drawdown_pct": -5, "win_rate_pct": 50,
               "profit_factor": 1.5, "num_trades": 10, "avg_trade_pct": 0.5,
               "exposure_time_pct": 30}
        result = _compare_metrics(m_a, m_b)
        # None values should result in tie
        total_row = next(r for r in result if r["metric"] == "Total Return (%)")
        assert total_row["winner"] == "tie"


class TestDetermineWinner:
    """Test the overall winner determination."""

    def test_clear_winner_a(self):
        m_a = {"total_return_pct": 20, "sharpe_ratio": 2.0, "max_drawdown_pct": -5,
               "win_rate_pct": 70, "profit_factor": 3.0}
        m_b = {"total_return_pct": 5, "sharpe_ratio": 0.5, "max_drawdown_pct": -20,
               "win_rate_pct": 40, "profit_factor": 0.8}
        assert _determine_winner(m_a, m_b) == "a"

    def test_clear_winner_b(self):
        m_a = {"total_return_pct": -5, "sharpe_ratio": -0.5, "max_drawdown_pct": -30,
               "win_rate_pct": 30, "profit_factor": 0.5}
        m_b = {"total_return_pct": 20, "sharpe_ratio": 2.0, "max_drawdown_pct": -5,
               "win_rate_pct": 70, "profit_factor": 3.0}
        assert _determine_winner(m_a, m_b) == "b"

    def test_tie(self):
        m = {"total_return_pct": 10, "sharpe_ratio": 1.0, "max_drawdown_pct": -10,
             "win_rate_pct": 50, "profit_factor": 1.5}
        assert _determine_winner(m, m) == "tie"

    def test_mixed_results(self):
        m_a = {"total_return_pct": 20, "sharpe_ratio": 0.5, "max_drawdown_pct": -25,
               "win_rate_pct": 60, "profit_factor": 1.2}
        m_b = {"total_return_pct": 10, "sharpe_ratio": 1.8, "max_drawdown_pct": -8,
               "win_rate_pct": 55, "profit_factor": 1.5}
        # B should win: sharpe (weight 3) + drawdown (weight 2) + profit_factor (weight 1) = 6
        # A wins: return (weight 2) + win_rate (weight 1) = 3
        assert _determine_winner(m_a, m_b) == "b"


# ---- PDF Report tests ----

class TestPdfReport:
    """Test PDF report generation."""

    def test_generates_bytes(self):
        from src.backtest.pdf_report import generate_pdf_report

        metrics = {
            "total_return_pct": 15.5, "buy_hold_return_pct": 20.0, "annual_return_pct": 8.2,
            "sharpe_ratio": 1.1, "sortino_ratio": 1.5, "calmar_ratio": 0.8,
            "max_drawdown_pct": -12.5, "avg_drawdown_pct": -3.2,
            "volatility_ann_pct": 18.0, "num_trades": 25, "win_rate_pct": 55.0,
            "profit_factor": 1.8, "best_trade_pct": 8.5, "worst_trade_pct": -4.2,
            "avg_trade_pct": 0.6, "expectancy_pct": 0.4,
            "exposure_time_pct": 35.0, "start": "2020-01-02", "end": "2024-01-02",
            "duration": "1461 days", "equity_start": 10000, "equity_final": 11550,
            "equity_peak": 12000, "max_drawdown_duration": "120 days",
        }

        dates = pd.bdate_range("2020-01-01", periods=100, freq="B")
        equity = pd.DataFrame({
            "Equity": np.linspace(10000, 11550, 100),
            "DrawdownPct": np.random.uniform(-0.05, 0, 100),
        }, index=dates)

        trades = pd.DataFrame({
            "Size": [100, -100, 200],
            "EntryPrice": [100, 105, 95],
            "ExitPrice": [105, 100, 102],
            "PnL": [500, -500, 1400],
            "ReturnPct": [5.0, -4.76, 7.37],
        })

        pdf_bytes = generate_pdf_report(
            metrics=metrics,
            equity_curve=equity,
            trades=trades,
            strategy_name="Test Strategy",
            asset="AAPL",
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"  # Valid PDF header

    def test_empty_equity_curve(self):
        from src.backtest.pdf_report import generate_pdf_report

        metrics = {
            "total_return_pct": 0, "buy_hold_return_pct": 0, "annual_return_pct": 0,
            "sharpe_ratio": None, "sortino_ratio": None, "calmar_ratio": None,
            "max_drawdown_pct": None, "avg_drawdown_pct": None,
            "volatility_ann_pct": None, "num_trades": 0, "win_rate_pct": None,
            "profit_factor": None, "best_trade_pct": None, "worst_trade_pct": None,
            "avg_trade_pct": None, "expectancy_pct": None,
            "exposure_time_pct": 0, "start": "2020-01-01", "end": "2024-01-01",
            "duration": "1461 days", "equity_start": 10000, "equity_final": 10000,
            "equity_peak": 10000, "max_drawdown_duration": "0 days",
        }

        pdf_bytes = generate_pdf_report(
            metrics=metrics,
            equity_curve=pd.DataFrame(),
            trades=pd.DataFrame(),
            strategy_name="Empty Test",
            asset="TEST",
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
