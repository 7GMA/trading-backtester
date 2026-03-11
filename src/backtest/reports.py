"""Report generation for backtest results."""

from __future__ import annotations

import pandas as pd
import quantstats as qs


def generate_html_report(
    equity_curve: pd.DataFrame,
    benchmark_symbol: str = "SPY",
    title: str = "Backtest Report",
    output_path: str = "data/report.html",
) -> str:
    """
    Generate a full HTML performance report using quantstats.

    Args:
        equity_curve: DataFrame with 'Equity' column from backtesting.py
        benchmark_symbol: Benchmark ticker for comparison
        title: Report title
        output_path: Where to save the HTML file

    Returns:
        Path to generated HTML file
    """
    # Convert equity curve to returns
    returns = equity_curve["Equity"].pct_change().dropna()
    returns.index = pd.to_datetime(returns.index)

    qs.reports.html(
        returns,
        benchmark=benchmark_symbol,
        title=title,
        output=output_path,
    )

    return output_path


def print_summary(equity_curve: pd.DataFrame) -> None:
    """Print a quick quantstats summary to console."""
    returns = equity_curve["Equity"].pct_change().dropna()
    returns.index = pd.to_datetime(returns.index)
    qs.reports.basic(returns)
