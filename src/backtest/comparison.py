"""Strategy comparison: run two strategies on the same data and compare."""

from __future__ import annotations

import pandas as pd
import numpy as np

from src.backtest.engine import run_backtest
from src.backtest.metrics import extract_metrics
from src.data.yahoo_client import fetch
from src.strategy.executor import build_strategy
from src.strategy.models import ParsedStrategy


def compare_strategies(
    strategy_a: ParsedStrategy,
    strategy_b: ParsedStrategy,
    start: str = "2020-01-01",
    end: str | None = None,
    cash: float = 10_000,
    commission: float = 0.001,
) -> dict:
    """
    Run two strategies on the same asset/timeframe and compare results.

    Both strategies are tested on the same underlying data (uses strategy_a's asset).

    Returns:
        {
            "a": {name, metrics, trades_count, equity_curve},
            "b": {name, metrics, trades_count, equity_curve},
            "comparison": {metric-by-metric comparison with winner},
            "winner": "a" | "b" | "tie",
            "df": the underlying price data,
        }
    """
    asset = strategy_a.asset
    df = fetch(asset, start=start, end=end)
    if df.empty:
        raise ValueError(f"No data found for {asset}")

    result_a = _run_single(df, strategy_a, cash, commission)
    result_b = _run_single(df, strategy_b, cash, commission)

    comparison = _compare_metrics(result_a["metrics"], result_b["metrics"])

    return {
        "a": result_a,
        "b": result_b,
        "comparison": comparison,
        "winner": _determine_winner(result_a["metrics"], result_b["metrics"]),
        "df": df,
    }


def _run_single(df: pd.DataFrame, parsed: ParsedStrategy, cash: float, commission: float) -> dict:
    """Run a single strategy and return results."""
    strategy_cls = build_strategy(parsed)
    result = run_backtest(df, strategy_cls, cash=cash, commission=commission)
    metrics = extract_metrics(result["stats"])
    return {
        "name": parsed.name,
        "metrics": metrics,
        "trades_count": int(metrics.get("num_trades") or 0),
        "equity_curve": result["equity_curve"],
    }


COMPARISON_METRICS = [
    ("total_return_pct", "Total Return (%)", "higher"),
    ("annual_return_pct", "Annual Return (%)", "higher"),
    ("sharpe_ratio", "Sharpe Ratio", "higher"),
    ("sortino_ratio", "Sortino Ratio", "higher"),
    ("max_drawdown_pct", "Max Drawdown (%)", "higher"),  # less negative = better
    ("win_rate_pct", "Win Rate (%)", "higher"),
    ("profit_factor", "Profit Factor", "higher"),
    ("num_trades", "# Trades", "info"),
    ("avg_trade_pct", "Avg Trade (%)", "higher"),
    ("exposure_time_pct", "Exposure Time (%)", "info"),
]


def _compare_metrics(metrics_a: dict, metrics_b: dict) -> list[dict]:
    """Build a metric-by-metric comparison."""
    rows = []
    for key, label, direction in COMPARISON_METRICS:
        val_a = metrics_a.get(key)
        val_b = metrics_b.get(key)

        if direction == "info" or val_a is None or val_b is None:
            winner = "tie"
        elif direction == "higher":
            if val_a > val_b:
                winner = "a"
            elif val_b > val_a:
                winner = "b"
            else:
                winner = "tie"
        else:
            winner = "tie"

        rows.append({
            "metric": label,
            "a": val_a,
            "b": val_b,
            "winner": winner,
        })
    return rows


def _determine_winner(metrics_a: dict, metrics_b: dict) -> str:
    """Determine overall winner based on key metrics."""
    score_a = 0
    score_b = 0

    # Key metrics for overall scoring
    key_metrics = [
        ("total_return_pct", 2),   # weight 2
        ("sharpe_ratio", 3),       # weight 3 (risk-adjusted matters most)
        ("max_drawdown_pct", 2),   # weight 2 (less negative = better)
        ("win_rate_pct", 1),       # weight 1
        ("profit_factor", 1),      # weight 1
    ]

    for key, weight in key_metrics:
        val_a = metrics_a.get(key)
        val_b = metrics_b.get(key)
        if val_a is not None and val_b is not None:
            if val_a > val_b:
                score_a += weight
            elif val_b > val_a:
                score_b += weight

    if score_a > score_b:
        return "a"
    elif score_b > score_a:
        return "b"
    return "tie"
