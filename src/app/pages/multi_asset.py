"""Multi-Asset Backtesting page -- run one strategy across multiple assets."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from src.strategy.templates import TEMPLATES, get_template
from src.strategy.parser import parse_strategy_offline


st.title("Multi-Asset Backtesting")

st.caption("Run the same strategy across multiple assets to find the best fit.")

# --- Strategy Selection ---
st.subheader("Strategy")

strategy_source = st.radio(
    "Select strategy source:",
    ["From current session", "From template"],
    horizontal=True,
)

parsed_strategy = None

if strategy_source == "From current session":
    if "parsed_strategy" in st.session_state:
        parsed_strategy = st.session_state["parsed_strategy"]
        st.info(f"Using: **{parsed_strategy.name}** (from Strategy Builder)")
    else:
        st.warning("No strategy in session. Go to Strategy Builder first, or select a template.")
else:
    template_name = st.selectbox("Template", list(TEMPLATES.keys()))
    if template_name:
        parsed_strategy = get_template(template_name)
        st.info(f"Using: **{parsed_strategy.name}**")

if parsed_strategy is None:
    st.stop()

st.divider()

# --- Asset Selection ---
st.subheader("Assets")

preset_groups = {
    "FAANG+": "AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA",
    "ETFs": "SPY, QQQ, IWM, DIA, VOO",
    "Crypto": "BTC-USD, ETH-USD, SOL-USD, ADA-USD",
    "DAX (German)": "SAP.DE, SIE.DE, BMW.DE, ALV.DE, DTE.DE",
}

col1, col2 = st.columns([1, 2])
with col1:
    preset = st.selectbox("Preset groups", ["Custom"] + list(preset_groups.keys()))
with col2:
    default_assets = preset_groups.get(preset, "AAPL, MSFT, GOOGL, TSLA, SPY")
    assets_input = st.text_input("Assets (comma-separated)", value=default_assets)

assets = [a.strip().upper() for a in assets_input.split(",") if a.strip()]

if not assets:
    st.error("Enter at least one asset.")
    st.stop()

st.caption(f"Testing {len(assets)} assets: {', '.join(assets)}")

# --- Configuration ---
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("Start Date", value=None, key="ma_start")
    start_str = str(start_date) if start_date else "2020-01-01"
with col2:
    cash = st.number_input("Capital per Asset ($)", value=10000, step=1000, min_value=100, key="ma_cash")
with col3:
    commission = st.number_input("Commission (%)", value=0.1, step=0.05, min_value=0.0, format="%.2f", key="ma_comm")

st.divider()

# --- Run ---
if st.button("Run Multi-Asset Backtest", type="primary", use_container_width=True):
    with st.spinner(f"Running {parsed_strategy.name} across {len(assets)} assets..."):
        from src.backtest.multi_asset import run_multi_asset

        result = run_multi_asset(
            parsed=parsed_strategy,
            assets=assets,
            start=start_str,
            cash=cash,
            commission=commission / 100,
        )
        st.session_state["multi_asset_result"] = result

# --- Results ---
if "multi_asset_result" in st.session_state:
    result = st.session_state["multi_asset_result"]
    summary = result["summary"]
    rankings = result["rankings"]

    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Assets Tested", summary["total_assets"])
    with col2:
        st.metric("Avg Return", f"{summary['avg_return_pct']:.1f}%" if summary['avg_return_pct'] is not None else "N/A")
    with col3:
        st.metric("Best Asset", summary.get("best_asset", "N/A"))
    with col4:
        st.metric("Total Trades", summary["total_trades"])

    st.divider()

    # Rankings table
    st.subheader("Rankings")
    if rankings:
        ranking_data = []
        for i, r in enumerate(rankings):
            asset_data = result["results"].get(r["asset"], {})
            m = asset_data.get("metrics", {}) or {}
            ranking_data.append({
                "Rank": i + 1,
                "Asset": r["asset"],
                "Return (%)": f"{r['return_pct']:.2f}" if r["return_pct"] else "N/A",
                "Sharpe": f"{m.get('sharpe_ratio', 0):.2f}" if m.get("sharpe_ratio") else "N/A",
                "Max DD (%)": f"{m.get('max_drawdown_pct', 0):.1f}" if m.get("max_drawdown_pct") else "N/A",
                "Trades": m.get("num_trades", 0) or 0,
                "Win Rate (%)": f"{m.get('win_rate_pct', 0):.1f}" if m.get("win_rate_pct") else "N/A",
            })
        st.dataframe(pd.DataFrame(ranking_data), hide_index=True, use_container_width=True)

    # Equity curves overlay
    st.subheader("Equity Curves")
    fig = go.Figure()
    colors = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#795548", "#607D8B"]

    for i, (symbol, data) in enumerate(result["results"].items()):
        eq = data.get("equity_curve")
        if eq is not None and not eq.empty and "Equity" in eq.columns:
            fig.add_trace(go.Scatter(
                x=eq.index, y=eq["Equity"],
                name=symbol,
                line=dict(color=colors[i % len(colors)], width=1.5),
            ))

    fig.update_layout(
        height=500,
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Errors
    errors = {k: v["error"] for k, v in result["results"].items() if v["error"]}
    if errors:
        with st.expander(f"Errors ({len(errors)} assets)"):
            for symbol, error in errors.items():
                st.warning(f"**{symbol}**: {error}")
