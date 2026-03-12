"""Multi-asset backtesting: run one strategy across multiple assets."""

from __future__ import annotations

import pandas as pd
import numpy as np

from src.backtest.engine import run_backtest
from src.backtest.metrics import extract_metrics
from src.data.yahoo_client import fetch
from src.strategy.executor import build_strategy
from src.strategy.models import ParsedStrategy


def run_multi_asset(
    parsed: ParsedStrategy,
    assets: list[str],
    start: str = "2020-01-01",
    end: str | None = None,
    cash: float = 10_000,
    commission: float = 0.001,
) -> dict:
    """
    Run the same strategy across multiple assets and aggregate results.

    Args:
        parsed: The parsed strategy (asset field is overridden per iteration).
        assets: List of ticker symbols to test.
        start: Backtest start date.
        end: Backtest end date (default: today).
        cash: Starting capital per asset.
        commission: Commission per trade.

    Returns:
        {
            "results": {symbol: {metrics, trades_count, equity_curve, error}},
            "summary": {aggregate stats across all assets},
            "rankings": [sorted by total return, best first],
        }
    """
    results: dict[str, dict] = {}

    for symbol in assets:
        symbol = symbol.upper().strip()
        if not symbol:
            continue

        try:
            # Override asset in a copy of the strategy
            strategy_copy = parsed.model_copy()
            strategy_copy.asset = symbol

            # Fetch data
            df = fetch(symbol, start=start, end=end)
            if df.empty:
                results[symbol] = {
                    "metrics": None,
                    "trades_count": 0,
                    "equity_curve": None,
                    "error": f"No data found for {symbol}",
                }
                continue

            # Build and run
            strategy_cls = build_strategy(strategy_copy)
            result = run_backtest(df, strategy_cls, cash=cash, commission=commission)
            metrics = extract_metrics(result["stats"])

            results[symbol] = {
                "metrics": metrics,
                "trades_count": int(metrics.get("num_trades") or 0),
                "equity_curve": result["equity_curve"],
                "error": None,
            }
        except Exception as e:
            results[symbol] = {
                "metrics": None,
                "trades_count": 0,
                "equity_curve": None,
                "error": str(e),
            }

    # Build summary
    successful = {k: v for k, v in results.items() if v["metrics"] is not None}
    summary = _build_summary(successful, cash)

    # Rankings by total return
    rankings = sorted(
        [
            {"asset": k, "return_pct": v["metrics"]["total_return_pct"] or 0}
            for k, v in successful.items()
        ],
        key=lambda x: x["return_pct"],
        reverse=True,
    )

    return {
        "results": results,
        "summary": summary,
        "rankings": rankings,
    }


def _build_summary(successful: dict, cash: float) -> dict:
    """Aggregate metrics across all successful backtests."""
    if not successful:
        return {
            "total_assets": 0,
            "successful": 0,
            "avg_return_pct": None,
            "best_asset": None,
            "worst_asset": None,
            "total_trades": 0,
            "avg_sharpe": None,
            "avg_win_rate": None,
        }

    returns = []
    sharpes = []
    win_rates = []
    total_trades = 0

    for symbol, data in successful.items():
        m = data["metrics"]
        if m["total_return_pct"] is not None:
            returns.append((symbol, m["total_return_pct"]))
        if m["sharpe_ratio"] is not None:
            sharpes.append(m["sharpe_ratio"])
        if m["win_rate_pct"] is not None:
            win_rates.append(m["win_rate_pct"])
        total_trades += int(m.get("num_trades") or 0)

    returns_sorted = sorted(returns, key=lambda x: x[1], reverse=True)

    return {
        "total_assets": len(successful),
        "successful": len(successful),
        "avg_return_pct": float(np.mean([r[1] for r in returns])) if returns else None,
        "best_asset": returns_sorted[0][0] if returns_sorted else None,
        "best_return_pct": returns_sorted[0][1] if returns_sorted else None,
        "worst_asset": returns_sorted[-1][0] if returns_sorted else None,
        "worst_return_pct": returns_sorted[-1][1] if returns_sorted else None,
        "total_trades": total_trades,
        "avg_sharpe": float(np.mean(sharpes)) if sharpes else None,
        "avg_win_rate": float(np.mean(win_rates)) if win_rates else None,
    }
