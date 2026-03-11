"""Streamlit main app – Trading Strategy Backtester."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Trading Backtester",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize API cost tracker
if "api_costs" not in st.session_state:
    st.session_state["api_costs"] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}

# Navigation
pg = st.navigation([
    st.Page("pages/strategy.py", title="Strategy Builder"),
    st.Page("pages/results.py", title="Backtest Results"),
    st.Page("pages/dashboard.py", title="Dashboard"),
])

pg.run()

# --- Footer: API Cost Tracker ---
st.divider()
costs = st.session_state["api_costs"]
if costs["requests"] > 0:
    # Claude Sonnet pricing: $3/M input, $15/M output
    input_cost = (costs["input_tokens"] / 1_000_000) * 3.0
    output_cost = (costs["output_tokens"] / 1_000_000) * 15.0
    total_cost = input_cost + output_cost

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.caption(f"API Requests: {costs['requests']}")
    with col2:
        st.caption(f"Tokens: {costs['input_tokens']:,} in / {costs['output_tokens']:,} out")
    with col3:
        st.caption(f"Kosten: ${total_cost:.4f}")
    with col4:
        st.caption("Model: claude-sonnet-4")
else:
    st.caption("Keine API-Requests in dieser Session | Model: claude-sonnet-4 (bei AI-Parsing)")
