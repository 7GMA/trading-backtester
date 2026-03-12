"""Streamlit main app -- Trading Strategy Backtester."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Trading Backtester",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Daily budget per user session
DAILY_BUDGET_USD = 0.30

# Initialize API cost tracker
if "api_costs" not in st.session_state:
    st.session_state["api_costs"] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}

# Navigation
pg = st.navigation([
    st.Page("pages/strategy.py", title="Strategy Builder"),
    st.Page("pages/results.py", title="Backtest Results"),
    st.Page("pages/multi_asset.py", title="Multi-Asset"),
    st.Page("pages/compare.py", title="Compare"),
    st.Page("pages/dashboard.py", title="Dashboard"),
])

pg.run()

# --- Footer: Cost & Budget Display ---
costs = st.session_state["api_costs"]
input_cost = (costs["input_tokens"] / 1_000_000) * 3.0
output_cost = (costs["output_tokens"] / 1_000_000) * 15.0
total_cost = input_cost + output_cost
budget_pct = min(total_cost / DAILY_BUDGET_USD, 1.0) if DAILY_BUDGET_USD > 0 else 0

st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.progress(budget_pct, text=f"Daily budget: ${total_cost:.4f} / ${DAILY_BUDGET_USD:.2f}")

with col2:
    if costs["requests"] > 0:
        st.caption(f"{costs['requests']} requests | {costs['input_tokens'] + costs['output_tokens']:,} tokens")
    else:
        st.caption("No AI requests yet")

with col3:
    st.caption("claude-sonnet-4 | Free tier")

# Block further AI requests if over budget
if total_cost >= DAILY_BUDGET_USD:
    st.session_state["budget_exceeded"] = True
else:
    st.session_state["budget_exceeded"] = False
