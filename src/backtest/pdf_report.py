"""PDF report generation using matplotlib."""

from __future__ import annotations

import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import numpy as np


def generate_pdf_report(
    metrics: dict,
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    strategy_name: str,
    asset: str,
) -> bytes:
    """
    Generate a multi-page PDF report with metrics, charts, and trade log.

    Returns:
        PDF file contents as bytes.
    """
    buf = io.BytesIO()

    with PdfPages(buf) as pdf:
        # Page 1: Title + Key Metrics
        _page_summary(pdf, metrics, strategy_name, asset)

        # Page 2: Equity Curve + Drawdown
        if not equity_curve.empty and "Equity" in equity_curve.columns:
            _page_equity_chart(pdf, equity_curve, strategy_name, asset)

        # Page 3: Detailed Metrics Table
        _page_metrics_table(pdf, metrics)

        # Page 4: Trade Log (if trades exist)
        if not trades.empty:
            _page_trade_log(pdf, trades)

    buf.seek(0)
    return buf.read()


def _page_summary(pdf: PdfPages, metrics: dict, strategy_name: str, asset: str):
    """Title page with key metrics summary."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    # Title
    fig.text(0.5, 0.92, "Backtest Report", ha="center", fontsize=24, fontweight="bold")
    fig.text(0.5, 0.88, f"{strategy_name} -- {asset}", ha="center", fontsize=16, color="#555")
    fig.text(0.5, 0.85, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ha="center", fontsize=10, color="#999")

    # Key metrics in a grid
    key_items = [
        ("Total Return", _fmt_pct(metrics.get("total_return_pct"))),
        ("Buy & Hold", _fmt_pct(metrics.get("buy_hold_return_pct"))),
        ("Annual Return", _fmt_pct(metrics.get("annual_return_pct"))),
        ("Sharpe Ratio", _fmt_num(metrics.get("sharpe_ratio"))),
        ("Sortino Ratio", _fmt_num(metrics.get("sortino_ratio"))),
        ("Max Drawdown", _fmt_pct(metrics.get("max_drawdown_pct"))),
        ("# Trades", str(metrics.get("num_trades", "N/A"))),
        ("Win Rate", _fmt_pct(metrics.get("win_rate_pct"))),
        ("Profit Factor", _fmt_num(metrics.get("profit_factor"))),
        ("Best Trade", _fmt_pct(metrics.get("best_trade_pct"))),
        ("Worst Trade", _fmt_pct(metrics.get("worst_trade_pct"))),
        ("Final Equity", _fmt_usd(metrics.get("equity_final"))),
    ]

    y_start = 0.75
    col_x = [0.15, 0.55]
    for i, (label, value) in enumerate(key_items):
        col = i % 2
        row = i // 2
        y = y_start - row * 0.06
        fig.text(col_x[col], y, f"{label}:", fontsize=11, fontweight="bold", color="#333")
        fig.text(col_x[col] + 0.22, y, value, fontsize=11, color="#000")

    # Period info
    fig.text(0.15, 0.35, f"Period: {metrics.get('start', 'N/A')} to {metrics.get('end', 'N/A')}", fontsize=10, color="#666")
    fig.text(0.15, 0.32, f"Duration: {metrics.get('duration', 'N/A')}", fontsize=10, color="#666")

    # Disclaimer
    fig.text(0.5, 0.05, "Past performance does not guarantee future results.", ha="center", fontsize=8, color="#aaa", style="italic")

    pdf.savefig(fig)
    plt.close(fig)


def _page_equity_chart(pdf: PdfPages, equity_curve: pd.DataFrame, strategy_name: str, asset: str):
    """Equity curve and drawdown chart."""
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 11), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"Equity Curve: {strategy_name} ({asset})", fontsize=14, fontweight="bold")

    # Equity curve
    ax1 = axes[0]
    ax1.plot(equity_curve.index, equity_curve["Equity"], color="#2196F3", linewidth=1.5, label="Portfolio")
    ax1.fill_between(equity_curve.index, equity_curve["Equity"], alpha=0.1, color="#2196F3")
    ax1.set_ylabel("Equity ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis="x", rotation=45)

    # Drawdown
    ax2 = axes[1]
    if "DrawdownPct" in equity_curve.columns:
        dd = equity_curve["DrawdownPct"] * 100
        ax2.fill_between(equity_curve.index, dd, 0, color="#F44336", alpha=0.4)
        ax2.plot(equity_curve.index, dd, color="#F44336", linewidth=0.8)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _page_metrics_table(pdf: PdfPages, metrics: dict):
    """Full metrics table page."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    fig.text(0.5, 0.95, "Detailed Metrics", ha="center", fontsize=16, fontweight="bold")

    sections = [
        ("Returns", [
            ("Total Return", _fmt_pct(metrics.get("total_return_pct"))),
            ("Buy & Hold Return", _fmt_pct(metrics.get("buy_hold_return_pct"))),
            ("Annual Return", _fmt_pct(metrics.get("annual_return_pct"))),
        ]),
        ("Risk", [
            ("Sharpe Ratio", _fmt_num(metrics.get("sharpe_ratio"))),
            ("Sortino Ratio", _fmt_num(metrics.get("sortino_ratio"))),
            ("Calmar Ratio", _fmt_num(metrics.get("calmar_ratio"))),
            ("Max Drawdown", _fmt_pct(metrics.get("max_drawdown_pct"))),
            ("Avg Drawdown", _fmt_pct(metrics.get("avg_drawdown_pct"))),
            ("Volatility (Ann.)", _fmt_pct(metrics.get("volatility_ann_pct"))),
        ]),
        ("Trades", [
            ("Total Trades", str(metrics.get("num_trades", "N/A"))),
            ("Win Rate", _fmt_pct(metrics.get("win_rate_pct"))),
            ("Profit Factor", _fmt_num(metrics.get("profit_factor"))),
            ("Best Trade", _fmt_pct(metrics.get("best_trade_pct"))),
            ("Worst Trade", _fmt_pct(metrics.get("worst_trade_pct"))),
            ("Avg Trade", _fmt_pct(metrics.get("avg_trade_pct"))),
            ("Expectancy", _fmt_pct(metrics.get("expectancy_pct"))),
        ]),
        ("Capital", [
            ("Final Equity", _fmt_usd(metrics.get("equity_final"))),
            ("Peak Equity", _fmt_usd(metrics.get("equity_peak"))),
            ("Exposure Time", _fmt_pct(metrics.get("exposure_time_pct"))),
        ]),
    ]

    y = 0.90
    for section_name, items in sections:
        y -= 0.02
        fig.text(0.1, y, section_name, fontsize=12, fontweight="bold", color="#2196F3")
        y -= 0.005
        for label, value in items:
            y -= 0.03
            fig.text(0.12, y, label, fontsize=10, color="#333")
            fig.text(0.55, y, value, fontsize=10, color="#000", fontweight="bold")

    pdf.savefig(fig)
    plt.close(fig)


def _page_trade_log(pdf: PdfPages, trades: pd.DataFrame):
    """Trade log table (first 40 trades)."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    fig.text(0.5, 0.96, "Trade Log", ha="center", fontsize=16, fontweight="bold")

    # Select key columns and limit rows
    display_trades = trades.head(40)
    cols_to_show = [c for c in ["Size", "EntryBar", "ExitBar", "EntryPrice", "ExitPrice", "PnL", "ReturnPct"] if c in display_trades.columns]

    if not cols_to_show:
        fig.text(0.5, 0.5, "No trade details available.", ha="center", fontsize=12, color="#999")
        pdf.savefig(fig)
        plt.close(fig)
        return

    # Header
    y = 0.92
    x_positions = [0.05 + i * (0.9 / len(cols_to_show)) for i in range(len(cols_to_show))]
    for i, col in enumerate(cols_to_show):
        fig.text(x_positions[i], y, col, fontsize=8, fontweight="bold", color="#333")
    y -= 0.015

    # Data rows
    for _, row in display_trades.iterrows():
        if y < 0.05:
            break
        for i, col in enumerate(cols_to_show):
            val = row.get(col, "")
            if isinstance(val, float):
                val = f"{val:.2f}"
            fig.text(x_positions[i], y, str(val)[:15], fontsize=7, color="#555")
        y -= 0.015

    if len(trades) > 40:
        fig.text(0.5, 0.02, f"Showing 40 of {len(trades)} trades.", ha="center", fontsize=8, color="#999")

    pdf.savefig(fig)
    plt.close(fig)


def _fmt_pct(val) -> str:
    return f"{val:.2f}%" if val is not None else "N/A"

def _fmt_num(val) -> str:
    return f"{val:.3f}" if val is not None else "N/A"

def _fmt_usd(val) -> str:
    return f"${val:,.2f}" if val is not None else "N/A"
