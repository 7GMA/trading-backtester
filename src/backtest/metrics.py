"""Performance metrics extraction from backtest results."""

from __future__ import annotations

import pandas as pd
import numpy as np


def extract_metrics(stats) -> dict:
    """Extract key metrics from backtesting.py stats into a clean dict."""
    return {
        # Returns
        "total_return_pct": _safe(stats, "Return [%]"),
        "buy_hold_return_pct": _safe(stats, "Buy & Hold Return [%]"),
        "annual_return_pct": _safe(stats, "Return (Ann.) [%]"),

        # Risk
        "sharpe_ratio": _safe(stats, "Sharpe Ratio"),
        "sortino_ratio": _safe(stats, "Sortino Ratio"),
        "calmar_ratio": _safe(stats, "Calmar Ratio"),
        "max_drawdown_pct": _safe(stats, "Max. Drawdown [%]"),
        "avg_drawdown_pct": _safe(stats, "Avg. Drawdown [%]"),
        "max_drawdown_duration": str(_safe(stats, "Max. Drawdown Duration")),
        "volatility_ann_pct": _safe(stats, "Volatility (Ann.) [%]"),

        # Trades
        "num_trades": _safe(stats, "# Trades"),
        "win_rate_pct": _safe(stats, "Win Rate [%]"),
        "best_trade_pct": _safe(stats, "Best Trade [%]"),
        "worst_trade_pct": _safe(stats, "Worst Trade [%]"),
        "avg_trade_pct": _safe(stats, "Avg. Trade [%]"),
        "profit_factor": _safe(stats, "Profit Factor"),
        "expectancy_pct": _safe(stats, "Expectancy [%]"),

        # Time
        "exposure_time_pct": _safe(stats, "Exposure Time [%]"),
        "start": str(_safe(stats, "Start")),
        "end": str(_safe(stats, "End")),
        "duration": str(_safe(stats, "Duration")),

        # Capital
        "equity_start": _safe(stats, "Equity Initial [$]") if "Equity Initial [$]" in stats else None,
        "equity_final": _safe(stats, "Equity Final [$]"),
        "equity_peak": _safe(stats, "Equity Peak [$]"),
    }


def _safe(stats, key):
    """Safely get a value from stats."""
    try:
        val = stats[key]
        if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
            return None
        return val
    except (KeyError, IndexError):
        return None


def format_metrics(metrics: dict) -> str:
    """Format metrics as readable text table."""
    lines = [
        "=" * 50,
        "BACKTEST RESULTS",
        "=" * 50,
        "",
        f"  Period:          {metrics['start']} → {metrics['end']}",
        f"  Duration:        {metrics['duration']}",
        "",
        "── Returns ────────────────────────────",
        f"  Total Return:    {_fmt_pct(metrics['total_return_pct'])}",
        f"  Buy & Hold:      {_fmt_pct(metrics['buy_hold_return_pct'])}",
        f"  Annual Return:   {_fmt_pct(metrics['annual_return_pct'])}",
        "",
        "── Risk ───────────────────────────────",
        f"  Sharpe Ratio:    {_fmt_num(metrics['sharpe_ratio'])}",
        f"  Sortino Ratio:   {_fmt_num(metrics['sortino_ratio'])}",
        f"  Max Drawdown:    {_fmt_pct(metrics['max_drawdown_pct'])}",
        f"  Volatility:      {_fmt_pct(metrics['volatility_ann_pct'])}",
        "",
        "── Trades ─────────────────────────────",
        f"  # Trades:        {metrics['num_trades']}",
        f"  Win Rate:        {_fmt_pct(metrics['win_rate_pct'])}",
        f"  Best Trade:      {_fmt_pct(metrics['best_trade_pct'])}",
        f"  Worst Trade:     {_fmt_pct(metrics['worst_trade_pct'])}",
        f"  Avg Trade:       {_fmt_pct(metrics['avg_trade_pct'])}",
        f"  Profit Factor:   {_fmt_num(metrics['profit_factor'])}",
        "",
        "── Capital ────────────────────────────",
        f"  Final Equity:    {_fmt_usd(metrics['equity_final'])}",
        f"  Peak Equity:     {_fmt_usd(metrics['equity_peak'])}",
        "=" * 50,
    ]
    return "\n".join(lines)


def _fmt_pct(val) -> str:
    return f"{val:.2f}%" if val is not None else "N/A"

def _fmt_num(val) -> str:
    return f"{val:.3f}" if val is not None else "N/A"

def _fmt_usd(val) -> str:
    return f"${val:,.2f}" if val is not None else "N/A"
