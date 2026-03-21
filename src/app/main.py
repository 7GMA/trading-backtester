"""Trading Strategy Backtester — Single-page Streamlit app."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from theme import inject_css, PLOTLY_DARK, CHART_COLORS
from src.strategy.parser import parse_strategy, parse_strategy_offline
from src.strategy.templates import TEMPLATES, get_template

st.set_page_config(
    page_title="Trading Backtester",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# --- Session State ---
if "api_costs" not in st.session_state:
    st.session_state["api_costs"] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}

DAILY_BUDGET_USD = 0.30

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("## Trading Strategy Backtester")
st.caption("Describe a trading strategy in plain English, backtest it on real market data.")

# ─────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────
cols = st.columns(len(TEMPLATES))
for i, (key, tmpl) in enumerate(TEMPLATES.items()):
    with cols[i]:
        if st.button(tmpl.name, key=f"tmpl_{key}", use_container_width=True):
            st.session_state["strategy_input"] = tmpl.description
            st.session_state["parsed_strategy"] = tmpl
            st.rerun()

# ─────────────────────────────────────────────
# STRATEGY INPUT
# ─────────────────────────────────────────────
st.markdown("---")
strategy_text = st.text_area(
    "Describe your strategy",
    value=st.session_state.get("strategy_input", ""),
    height=100,
    placeholder='e.g. "Buy Apple when RSI drops below 30. Sell at 10% profit or 5% loss."',
    label_visibility="collapsed",
)

col_ai, col_parse = st.columns([1, 1])
with col_ai:
    use_ai = st.checkbox("Use Claude AI Parser", value=False, help="Uses Claude API for complex strategies")
with col_parse:
    parse_clicked = st.button("Parse Strategy", type="primary", use_container_width=True)

if parse_clicked:
    if not strategy_text.strip():
        st.error("Please enter a strategy description.")
    else:
        st.session_state["strategy_input"] = strategy_text
        with st.spinner("Parsing..."):
            try:
                if use_ai:
                    if st.session_state.get("budget_exceeded"):
                        st.error("Daily AI budget exceeded. Use the offline parser.")
                        st.stop()
                    strategy, warnings, usage = parse_strategy(strategy_text)
                    costs = st.session_state["api_costs"]
                    costs["requests"] += 1
                    costs["input_tokens"] += usage.get("input_tokens", 0)
                    costs["output_tokens"] += usage.get("output_tokens", 0)
                else:
                    result = parse_strategy_offline(strategy_text)
                    if result is None:
                        st.warning("Offline parser could not recognize the strategy. Try the AI parser.")
                        st.stop()
                    strategy, warnings = result

                st.session_state["parsed_strategy"] = strategy
                if warnings:
                    for w in warnings:
                        st.warning(w)
                st.rerun()
            except Exception as e:
                st.error(f"Parse error: {e}")

# ─────────────────────────────────────────────
# PARSED STRATEGY + BACKTEST CONFIG
# ─────────────────────────────────────────────
if "parsed_strategy" in st.session_state:
    strategy = st.session_state["parsed_strategy"]

    st.markdown("---")

    # Strategy summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Strategy", strategy.name)
    with col2:
        st.metric("Asset", strategy.asset)
    with col3:
        st.metric("Timeframe", strategy.timeframe)

    with st.expander("Strategy Details"):
        st.markdown(f"**Entry** ({strategy.entry.logic.value})")
        for cond in strategy.entry.conditions:
            params = ", ".join(f"{k}={v}" for k, v in cond.params.items())
            st.markdown(f"- `{cond.indicator}({params})` {cond.operator.value} `{cond.value}`")

        exit_parts = []
        if strategy.exit.stop_loss:
            exit_parts.append(f"Stop Loss: {strategy.exit.stop_loss*100:.0f}%")
        if strategy.exit.take_profit:
            exit_parts.append(f"Take Profit: {strategy.exit.take_profit*100:.0f}%")
        if strategy.exit.trailing_stop:
            exit_parts.append(f"Trailing Stop: {strategy.exit.trailing_stop*100:.0f}%")
        for cond in strategy.exit.conditions:
            params = ", ".join(f"{k}={v}" for k, v in cond.params.items())
            exit_parts.append(f"{cond.indicator}({params}) {cond.operator.value} {cond.value}")
        if exit_parts:
            st.markdown("**Exit**")
            for part in exit_parts:
                st.markdown(f"- {part}")

        st.json(json.loads(strategy.model_dump_json()))

    # Backtest config
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        asset_override = st.text_input("Asset", value=strategy.asset)
    with c2:
        start_date = st.date_input("Start Date", value=None)
        start_str = str(start_date) if start_date else "2020-01-01"
    with c3:
        cash = st.number_input("Capital ($)", value=10000, step=1000, min_value=100)
    with c4:
        commission = st.number_input("Commission (%)", value=0.1, step=0.05, min_value=0.0, format="%.2f")

    if st.button("Run Backtest", type="primary", use_container_width=True):
        strategy.asset = asset_override.upper()
        with st.spinner(f"Running backtest for {strategy.asset}..."):
            try:
                from src.data.yahoo_client import fetch
                from src.strategy.executor import build_strategy
                from src.backtest.engine import run_backtest
                from src.backtest.metrics import extract_metrics

                df = fetch(strategy.asset, start=start_str)
                if df.empty:
                    st.error(f"No data found for {strategy.asset}.")
                    st.stop()

                StrategyClass = build_strategy(strategy)
                result = run_backtest(df, strategy=StrategyClass, cash=cash, commission=commission / 100)
                metrics = extract_metrics(result["stats"])

                st.session_state["backtest_result"] = {
                    "metrics": metrics,
                    "stats": result["stats"],
                    "trades": result["trades"],
                    "equity_curve": result["equity_curve"],
                    "df": df,
                    "strategy_name": strategy.name,
                    "asset": strategy.asset,
                }
                st.rerun()
            except Exception as e:
                st.error(f"Backtest error: {e}")
                import traceback
                st.code(traceback.format_exc())

# ─────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────
if "backtest_result" in st.session_state:
    r = st.session_state["backtest_result"]
    metrics = r["metrics"]
    equity = r["equity_curve"]
    trades = r["trades"]
    df = r["df"]

    st.markdown("---")
    st.markdown(f"### Results — {r['strategy_name']} on {r['asset']}")

    # Key metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        val = metrics["total_return_pct"]
        st.metric("Total Return", f"{val:.1f}%" if val else "N/A",
                  delta=f"vs B&H: {metrics['buy_hold_return_pct']:.1f}%" if metrics["buy_hold_return_pct"] else None)
    with m2:
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}" if metrics["sharpe_ratio"] else "N/A")
    with m3:
        st.metric("Max Drawdown", f"{metrics['max_drawdown_pct']:.1f}%" if metrics["max_drawdown_pct"] else "N/A")
    with m4:
        st.metric("Trades", metrics["num_trades"] or 0)
    with m5:
        st.metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%" if metrics["win_rate_pct"] else "N/A")

    # Equity curve
    if not equity.empty and "Equity" in equity.columns:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            row_heights=[0.7, 0.3], subplot_titles=("Portfolio Equity", "Drawdown"),
        )

        fig.add_trace(go.Scatter(
            x=equity.index, y=equity["Equity"],
            name="Portfolio", line=dict(color=CHART_COLORS[0], width=2),
            fill="tozeroy", fillcolor="rgba(88, 166, 255, 0.1)",
        ), row=1, col=1)

        if not df.empty:
            initial_price = df["Close"].iloc[0]
            bh_equity = (df["Close"] / initial_price) * (metrics.get("equity_start") or 10000)
            bh_aligned = bh_equity.reindex(equity.index, method="ffill")
            fig.add_trace(go.Scatter(
                x=bh_aligned.index, y=bh_aligned.values,
                name="Buy & Hold", line=dict(color=CHART_COLORS[3], width=1, dash="dash"),
            ), row=1, col=1)

        if "DrawdownPct" in equity.columns:
            fig.add_trace(go.Scatter(
                x=equity.index, y=equity["DrawdownPct"] * 100,
                name="Drawdown %", line=dict(color=CHART_COLORS[1], width=1),
                fill="tozeroy", fillcolor="rgba(248, 81, 73, 0.2)",
            ), row=2, col=1)

        fig.update_layout(height=550, showlegend=True, **PLOTLY_DARK)
        fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

    # Detailed metrics side by side
    left, right = st.columns(2)

    with left:
        st.markdown("**Returns & Risk**")
        returns_data = {
            "Total Return": f"{metrics['total_return_pct']:.2f}%" if metrics["total_return_pct"] else "N/A",
            "Annual Return": f"{metrics['annual_return_pct']:.2f}%" if metrics["annual_return_pct"] else "N/A",
            "Buy & Hold": f"{metrics['buy_hold_return_pct']:.2f}%" if metrics["buy_hold_return_pct"] else "N/A",
            "Sharpe": f"{metrics['sharpe_ratio']:.3f}" if metrics["sharpe_ratio"] else "N/A",
            "Sortino": f"{metrics['sortino_ratio']:.3f}" if metrics["sortino_ratio"] else "N/A",
            "Max Drawdown": f"{metrics['max_drawdown_pct']:.2f}%" if metrics["max_drawdown_pct"] else "N/A",
            "Volatility": f"{metrics['volatility_ann_pct']:.2f}%" if metrics["volatility_ann_pct"] else "N/A",
        }
        st.dataframe(pd.DataFrame(returns_data.items(), columns=["Metric", "Value"]),
                     hide_index=True, use_container_width=True)

    with right:
        st.markdown("**Trade Statistics**")
        trade_data = {
            "Trades": metrics["num_trades"] or 0,
            "Win Rate": f"{metrics['win_rate_pct']:.1f}%" if metrics["win_rate_pct"] else "N/A",
            "Best Trade": f"{metrics['best_trade_pct']:.2f}%" if metrics["best_trade_pct"] else "N/A",
            "Worst Trade": f"{metrics['worst_trade_pct']:.2f}%" if metrics["worst_trade_pct"] else "N/A",
            "Avg Trade": f"{metrics['avg_trade_pct']:.2f}%" if metrics["avg_trade_pct"] else "N/A",
            "Profit Factor": f"{metrics['profit_factor']:.2f}" if metrics["profit_factor"] else "N/A",
            "Final Equity": f"${metrics['equity_final']:,.2f}" if metrics["equity_final"] else "N/A",
        }
        st.dataframe(pd.DataFrame(trade_data.items(), columns=["Metric", "Value"]),
                     hide_index=True, use_container_width=True)

    # PDF export
    exp1, exp2 = st.columns([1, 3])
    with exp1:
        if st.button("Export PDF", use_container_width=True):
            with st.spinner("Generating PDF..."):
                from src.backtest.pdf_report import generate_pdf_report
                pdf_bytes = generate_pdf_report(
                    metrics=metrics, equity_curve=equity, trades=trades,
                    strategy_name=r["strategy_name"], asset=r["asset"],
                )
                st.session_state["pdf_report"] = pdf_bytes
        if "pdf_report" in st.session_state:
            st.download_button(
                "Download PDF", data=st.session_state["pdf_report"],
                file_name=f"backtest_{r['asset']}_{r['strategy_name'].replace(' ', '_')}.pdf",
                mime="application/pdf", use_container_width=True,
            )

    # Trade log
    if not trades.empty:
        with st.expander(f"Trade Log ({len(trades)} trades)"):
            st.dataframe(trades, use_container_width=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.caption("Built with Python, Streamlit, Claude API, and backtesting.py")
