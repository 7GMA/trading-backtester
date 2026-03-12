"""Backtest Results page -- charts, metrics, and PDF export."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


st.title("Backtest Results")

if "backtest_result" not in st.session_state:
    st.info("No backtest run yet. Go to 'Strategy Builder' to run one.")
    st.stop()

result = st.session_state["backtest_result"]
metrics = result["metrics"]
equity = result["equity_curve"]
trades = result["trades"]
df = result["df"]

# --- Key Metrics ---
st.subheader(f"{result['strategy_name']} -- {result['asset']}")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    val = metrics["total_return_pct"]
    st.metric("Total Return", f"{val:.1f}%" if val else "N/A",
              delta=f"vs B&H: {metrics['buy_hold_return_pct']:.1f}%" if metrics['buy_hold_return_pct'] else None)
with col2:
    st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}" if metrics['sharpe_ratio'] else "N/A")
with col3:
    st.metric("Max Drawdown", f"{metrics['max_drawdown_pct']:.1f}%" if metrics['max_drawdown_pct'] else "N/A")
with col4:
    st.metric("Trades", metrics["num_trades"] or 0)
with col5:
    st.metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%" if metrics['win_rate_pct'] else "N/A")

# --- PDF Export ---
st.divider()
col_export, col_spacer = st.columns([1, 3])
with col_export:
    if st.button("Export PDF Report", use_container_width=True):
        with st.spinner("Generating PDF..."):
            from src.backtest.pdf_report import generate_pdf_report
            pdf_bytes = generate_pdf_report(
                metrics=metrics,
                equity_curve=equity,
                trades=trades,
                strategy_name=result["strategy_name"],
                asset=result["asset"],
            )
            st.session_state["pdf_report"] = pdf_bytes

if "pdf_report" in st.session_state:
    with col_export:
        st.download_button(
            label="Download PDF",
            data=st.session_state["pdf_report"],
            file_name=f"backtest_{result['asset']}_{result['strategy_name'].replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.divider()

# --- Equity Curve ---
if not equity.empty and "Equity" in equity.columns:
    st.subheader("Equity Curve")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=("Portfolio Equity", "Drawdown"),
    )

    # Equity line
    fig.add_trace(
        go.Scatter(
            x=equity.index, y=equity["Equity"],
            name="Portfolio", line=dict(color="#2196F3", width=2),
            fill="tozeroy", fillcolor="rgba(33, 150, 243, 0.1)",
        ),
        row=1, col=1,
    )

    # Buy & Hold comparison
    if not df.empty:
        initial_price = df["Close"].iloc[0]
        bh_equity = (df["Close"] / initial_price) * (metrics.get("equity_start") or 10000)
        bh_aligned = bh_equity.reindex(equity.index, method="ffill")
        fig.add_trace(
            go.Scatter(
                x=bh_aligned.index, y=bh_aligned.values,
                name="Buy & Hold", line=dict(color="#FF9800", width=1, dash="dash"),
            ),
            row=1, col=1,
        )

    # Drawdown
    if "DrawdownPct" in equity.columns:
        fig.add_trace(
            go.Scatter(
                x=equity.index, y=equity["DrawdownPct"] * 100,
                name="Drawdown %", line=dict(color="#F44336", width=1),
                fill="tozeroy", fillcolor="rgba(244, 67, 54, 0.2)",
            ),
            row=2, col=1,
        )

    fig.update_layout(
        height=600,
        showlegend=True,
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Detailed Metrics ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Returns & Risk")
    metrics_table = {
        "Total Return": f"{metrics['total_return_pct']:.2f}%" if metrics['total_return_pct'] else "N/A",
        "Annual Return": f"{metrics['annual_return_pct']:.2f}%" if metrics['annual_return_pct'] else "N/A",
        "Buy & Hold": f"{metrics['buy_hold_return_pct']:.2f}%" if metrics['buy_hold_return_pct'] else "N/A",
        "Sharpe Ratio": f"{metrics['sharpe_ratio']:.3f}" if metrics['sharpe_ratio'] else "N/A",
        "Sortino Ratio": f"{metrics['sortino_ratio']:.3f}" if metrics['sortino_ratio'] else "N/A",
        "Max Drawdown": f"{metrics['max_drawdown_pct']:.2f}%" if metrics['max_drawdown_pct'] else "N/A",
        "Volatility (Ann.)": f"{metrics['volatility_ann_pct']:.2f}%" if metrics['volatility_ann_pct'] else "N/A",
        "Exposure Time": f"{metrics['exposure_time_pct']:.1f}%" if metrics['exposure_time_pct'] else "N/A",
    }
    st.dataframe(pd.DataFrame(metrics_table.items(), columns=["Metric", "Value"]), hide_index=True, use_container_width=True)

with col2:
    st.subheader("Trade Statistics")
    trade_table = {
        "# Trades": metrics['num_trades'] or 0,
        "Win Rate": f"{metrics['win_rate_pct']:.1f}%" if metrics['win_rate_pct'] else "N/A",
        "Best Trade": f"{metrics['best_trade_pct']:.2f}%" if metrics['best_trade_pct'] else "N/A",
        "Worst Trade": f"{metrics['worst_trade_pct']:.2f}%" if metrics['worst_trade_pct'] else "N/A",
        "Avg Trade": f"{metrics['avg_trade_pct']:.2f}%" if metrics['avg_trade_pct'] else "N/A",
        "Profit Factor": f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] else "N/A",
        "Final Equity": f"${metrics['equity_final']:,.2f}" if metrics['equity_final'] else "N/A",
        "Peak Equity": f"${metrics['equity_peak']:,.2f}" if metrics['equity_peak'] else "N/A",
    }
    st.dataframe(pd.DataFrame(trade_table.items(), columns=["Metric", "Value"]), hide_index=True, use_container_width=True)

# --- Trade List ---
if not trades.empty:
    st.divider()
    st.subheader("Trade Log")
    st.dataframe(trades, use_container_width=True)
