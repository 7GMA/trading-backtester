"""Walk-Forward Analysis for strategy validation."""

from __future__ import annotations

import pandas as pd
import numpy as np

from src.backtest.engine import run_backtest, STRATEGIES
from src.backtest.metrics import extract_metrics


def walk_forward(
    df: pd.DataFrame,
    strategy,
    n_splits: int = 5,
    train_pct: float = 0.7,
    cash: float = 10_000,
    commission: float = 0.001,
) -> dict:
    """
    Walk-forward analysis: split data into sequential train/test windows,
    run the strategy on each test period, and aggregate results.

    This validates that a strategy isn't overfit to a single historical period
    by testing it across multiple non-overlapping time windows.

    Args:
        df: OHLCV DataFrame with DatetimeIndex.
        strategy: Strategy class (from engine.py) or string name from STRATEGIES.
        n_splits: Number of train/test windows.
        train_pct: Fraction of each window used for training (warmup).
        cash: Starting capital per window.
        commission: Commission per trade.

    Returns:
        {
            "summary": {aggregate metrics across all windows},
            "windows": [per-window result dicts],
            "consistent": bool  # True if >60% of windows are profitable
        }
    """
    if isinstance(strategy, str):
        if strategy not in STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}"
            )
        strategy = STRATEGIES[strategy]

    n_rows = len(df)
    if n_rows < n_splits * 2:
        raise ValueError(
            f"Not enough data: {n_rows} rows for {n_splits} splits. "
            f"Need at least {n_splits * 2} rows."
        )

    # Calculate window size and split boundaries
    window_size = n_rows // n_splits
    windows: list[dict] = []

    for i in range(n_splits):
        start = i * window_size
        end = min(start + window_size, n_rows)
        if i == n_splits - 1:
            end = n_rows  # last window gets any remainder

        window_df = df.iloc[start:end].copy()
        train_end = int(len(window_df) * train_pct)

        # Test portion is everything after the training portion
        test_df = window_df.iloc[train_end:].copy()

        if len(test_df) < 2:
            continue

        window_result = {
            "window": i + 1,
            "train_start": str(window_df.index[0].date()) if hasattr(window_df.index[0], "date") else str(window_df.index[0]),
            "train_end": str(window_df.index[train_end - 1].date()) if hasattr(window_df.index[train_end - 1], "date") else str(window_df.index[train_end - 1]),
            "test_start": str(test_df.index[0].date()) if hasattr(test_df.index[0], "date") else str(test_df.index[0]),
            "test_end": str(test_df.index[-1].date()) if hasattr(test_df.index[-1], "date") else str(test_df.index[-1]),
            "test_rows": len(test_df),
        }

        try:
            result = run_backtest(
                test_df,
                strategy=strategy,
                cash=cash,
                commission=commission,
            )
            metrics = extract_metrics(result["stats"])
            window_result["metrics"] = metrics
            window_result["profitable"] = (
                metrics.get("total_return_pct") is not None
                and metrics["total_return_pct"] > 0
            )
            window_result["error"] = None
        except Exception as e:
            window_result["metrics"] = None
            window_result["profitable"] = False
            window_result["error"] = str(e)

        windows.append(window_result)

    # Aggregate summary across all successful windows
    successful = [w for w in windows if w["metrics"] is not None]
    profitable_count = sum(1 for w in windows if w["profitable"])
    total_windows = len(windows)

    summary: dict = {
        "total_windows": total_windows,
        "successful_windows": len(successful),
        "profitable_windows": profitable_count,
        "win_rate_pct": (profitable_count / total_windows * 100) if total_windows > 0 else 0,
    }

    if successful:
        returns = [w["metrics"]["total_return_pct"] for w in successful if w["metrics"]["total_return_pct"] is not None]
        sharpes = [w["metrics"]["sharpe_ratio"] for w in successful if w["metrics"]["sharpe_ratio"] is not None]
        num_trades = [w["metrics"]["num_trades"] for w in successful if w["metrics"]["num_trades"] is not None]

        summary["avg_return_pct"] = float(np.mean(returns)) if returns else None
        summary["std_return_pct"] = float(np.std(returns)) if returns else None
        summary["min_return_pct"] = float(np.min(returns)) if returns else None
        summary["max_return_pct"] = float(np.max(returns)) if returns else None
        summary["avg_sharpe"] = float(np.mean(sharpes)) if sharpes else None
        summary["total_trades"] = int(np.sum(num_trades)) if num_trades else 0
    else:
        summary["avg_return_pct"] = None
        summary["std_return_pct"] = None
        summary["min_return_pct"] = None
        summary["max_return_pct"] = None
        summary["avg_sharpe"] = None
        summary["total_trades"] = 0

    consistent = (profitable_count / total_windows > 0.6) if total_windows > 0 else False

    return {
        "summary": summary,
        "windows": windows,
        "consistent": consistent,
    }
