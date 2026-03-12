"""Strategy Comparison page -- two strategies head-to-head."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from src.strategy.templates import TEMPLATES, get_template


st.title("Strategy Comparison")

st.caption("Compare two strategies head-to-head on the same asset.")

template_keys = list(TEMPLATES.keys())

# --- Strategy A ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Strategy A")
    source_a = st.radio("Source", ["Template", "Current session"], key="src_a", horizontal=True)
    if source_a == "Template":
        tmpl_a = st.selectbox("Template", template_keys, key="tmpl_a")
        strategy_a = get_template(tmpl_a)
    else:
        if "parsed_strategy" in st.session_state:
            strategy_a = st.session_state["parsed_strategy"]
        else:
            st.warning("No strategy in session.")
            strategy_a = None
    if strategy_a:
        st.info(f"**{strategy_a.name}** ({strategy_a.asset})")

with col_b:
    st.subheader("Strategy B")
    source_b = st.radio("Source", ["Template", "Current session"], key="src_b", horizontal=True)
    if source_b == "Template":
        # Default to a different template
        default_idx = min(1, len(template_keys) - 1)
        tmpl_b = st.selectbox("Template", template_keys, index=default_idx, key="tmpl_b")
        strategy_b = get_template(tmpl_b)
    else:
        if "parsed_strategy" in st.session_state:
            strategy_b = st.session_state["parsed_strategy"]
        else:
            st.warning("No strategy in session.")
            strategy_b = None
    if strategy_b:
        st.info(f"**{strategy_b.name}** ({strategy_b.asset})")

if strategy_a is None or strategy_b is None:
    st.stop()

st.divider()

# --- Configuration ---
st.subheader("Configuration")
col1, col2, col3, col4 = st.columns(4)
with col1:
    asset = st.text_input("Asset", value=strategy_a.asset, key="cmp_asset")
with col2:
    start_date = st.date_input("Start Date", value=None, key="cmp_start")
    start_str = str(start_date) if start_date else "2020-01-01"
with col3:
    cash = st.number_input("Capital ($)", value=10000, step=1000, min_value=100, key="cmp_cash")
with col4:
    commission = st.number_input("Commission (%)", value=0.1, step=0.05, min_value=0.0, format="%.2f", key="cmp_comm")

# Override assets to match
strategy_a_copy = strategy_a.model_copy()
strategy_b_copy = strategy_b.model_copy()
strategy_a_copy.asset = asset.upper()
strategy_b_copy.asset = asset.upper()

st.divider()

if st.button("Compare Strategies", type="primary", use_container_width=True):
    with st.spinner("Running comparison..."):
        try:
            from src.backtest.comparison import compare_strategies

            result = compare_strategies(
                strategy_a=strategy_a_copy,
                strategy_b=strategy_b_copy,
                start=start_str,
                cash=cash,
                commission=commission / 100,
            )
            st.session_state["comparison_result"] = result
        except Exception as e:
            st.error(f"Comparison error: {e}")
            import traceback
            st.code(traceback.format_exc())

# --- Results ---
if "comparison_result" in st.session_state:
    result = st.session_state["comparison_result"]
    ra = result["a"]
    rb = result["b"]
    winner = result["winner"]

    # Winner banner
    if winner == "a":
        st.success(f"Winner: **{ra['name']}** (Strategy A)")
    elif winner == "b":
        st.success(f"Winner: **{rb['name']}** (Strategy B)")
    else:
        st.info("Result: **Tie** -- both strategies perform similarly")

    st.divider()

    # Side-by-side key metrics
    st.subheader("Head-to-Head")
    comparison = result["comparison"]

    rows = []
    for item in comparison:
        val_a = item["a"]
        val_b = item["b"]
        w = item["winner"]

        fmt_a = _fmt(val_a)
        fmt_b = _fmt(val_b)

        if w == "a":
            fmt_a = f"**{fmt_a}**"
        elif w == "b":
            fmt_b = f"**{fmt_b}**"

        rows.append({
            "Metric": item["metric"],
            f"A: {ra['name']}": fmt_a,
            f"B: {rb['name']}": fmt_b,
            "Better": "A" if w == "a" else ("B" if w == "b" else "--"),
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.divider()

    # Equity curves overlay
    st.subheader("Equity Curves")
    fig = go.Figure()

    eq_a = ra.get("equity_curve")
    eq_b = rb.get("equity_curve")

    if eq_a is not None and not eq_a.empty and "Equity" in eq_a.columns:
        fig.add_trace(go.Scatter(
            x=eq_a.index, y=eq_a["Equity"],
            name=f"A: {ra['name']}",
            line=dict(color="#2196F3", width=2),
        ))

    if eq_b is not None and not eq_b.empty and "Equity" in eq_b.columns:
        fig.add_trace(go.Scatter(
            x=eq_b.index, y=eq_b["Equity"],
            name=f"B: {rb['name']}",
            line=dict(color="#F44336", width=2),
        ))

    fig.update_layout(
        height=500,
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _fmt(val) -> str:
    """Format a metric value for display."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)
