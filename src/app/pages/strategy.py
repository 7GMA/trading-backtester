"""Strategy Builder page -- enter strategies in natural language."""

import streamlit as st
import json

from src.strategy.parser import parse_strategy, parse_strategy_offline
from src.strategy.templates import TEMPLATES, get_template
from src.strategy.validator import validate_strategy


st.title("Strategy Builder")

# --- Template Selection ---
st.subheader("Templates")

cols_per_row = min(len(TEMPLATES), 4)
template_cols = st.columns(cols_per_row)
for i, (key, tmpl) in enumerate(TEMPLATES.items()):
    with template_cols[i % cols_per_row]:
        if st.button(tmpl.name, key=f"tmpl_{key}", use_container_width=True):
            st.session_state["strategy_input"] = tmpl.description
            st.session_state["parsed_strategy"] = tmpl
            st.rerun()

st.divider()

# --- Natural Language Input ---
st.subheader("Describe Your Strategy")
strategy_text = st.text_area(
    "Describe your trading strategy in natural language:",
    value=st.session_state.get("strategy_input", ""),
    height=120,
    placeholder='e.g. "Buy Apple when RSI drops below 30. Sell at 10% profit or 5% loss."',
)

col1, col2 = st.columns([1, 1])
with col1:
    use_ai = st.checkbox("Use Claude AI Parser", value=False, help="Uses Claude API for complex strategies")
with col2:
    if st.button("Parse Strategy", type="primary", use_container_width=True):
        if not strategy_text.strip():
            st.error("Please enter a strategy description.")
        else:
            st.session_state["strategy_input"] = strategy_text
            with st.spinner("Parsing strategy..."):
                try:
                    if use_ai:
                        if st.session_state.get("budget_exceeded"):
                            st.error("Daily AI budget exceeded ($0.30). Use the offline parser or try again tomorrow.")
                            st.stop()
                        strategy, warnings, usage = parse_strategy(strategy_text)
                        # Track API costs
                        costs = st.session_state["api_costs"]
                        costs["requests"] += 1
                        costs["input_tokens"] += usage.get("input_tokens", 0)
                        costs["output_tokens"] += usage.get("output_tokens", 0)
                    else:
                        result = parse_strategy_offline(strategy_text)
                        if result is None:
                            st.warning("Offline parser could not recognize the strategy. Enable 'Use Claude AI Parser' for complex strategies.")
                            st.stop()
                        strategy, warnings = result

                    st.session_state["parsed_strategy"] = strategy
                    if warnings:
                        for w in warnings:
                            st.warning(w)
                    st.rerun()
                except Exception as e:
                    st.error(f"Parse error: {e}")

# --- Show Parsed Strategy ---
if "parsed_strategy" in st.session_state:
    strategy = st.session_state["parsed_strategy"]
    st.divider()
    st.subheader("Parsed Strategy")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Asset", strategy.asset)
    with col2:
        st.metric("Timeframe", strategy.timeframe)
    with col3:
        st.metric("Name", strategy.name)

    # Entry conditions
    st.markdown("**Entry Conditions** " + f"({strategy.entry.logic.value})")
    for cond in strategy.entry.conditions:
        params_str = ", ".join(f"{k}={v}" for k, v in cond.params.items())
        st.markdown(f"- `{cond.indicator}({params_str})` {cond.operator.value} `{cond.value}`")

    # Exit conditions
    st.markdown("**Exit Rules**")
    exit_parts = []
    if strategy.exit.stop_loss:
        exit_parts.append(f"Stop Loss: {strategy.exit.stop_loss*100:.0f}%")
    if strategy.exit.take_profit:
        exit_parts.append(f"Take Profit: {strategy.exit.take_profit*100:.0f}%")
    if strategy.exit.trailing_stop:
        exit_parts.append(f"Trailing Stop: {strategy.exit.trailing_stop*100:.0f}%")
    for cond in strategy.exit.conditions:
        params_str = ", ".join(f"{k}={v}" for k, v in cond.params.items())
        exit_parts.append(f"{cond.indicator}({params_str}) {cond.operator.value} {cond.value}")
    for part in exit_parts:
        st.markdown(f"- {part}")

    # JSON view
    with st.expander("View JSON"):
        st.json(json.loads(strategy.model_dump_json()))

    st.divider()

    # --- Backtest Configuration ---
    st.subheader("Backtest Configuration")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        asset_override = st.text_input("Override Asset", value=strategy.asset)
    with col2:
        start_date = st.date_input("Start Date", value=None)
        start_str = str(start_date) if start_date else "2020-01-01"
    with col3:
        cash = st.number_input("Starting Capital ($)", value=10000, step=1000, min_value=100)
    with col4:
        commission = st.number_input("Commission (%)", value=0.1, step=0.05, min_value=0.0, format="%.2f")

    if st.button("Run Backtest", type="primary", use_container_width=True):
        strategy.asset = asset_override.upper()
        st.session_state["backtest_config"] = {
            "strategy": strategy,
            "start": start_str,
            "cash": cash,
            "commission": commission / 100,
        }

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

                st.success("Backtest complete! Switching to Results page.")
                st.switch_page("pages/results.py")

            except Exception as e:
                st.error(f"Backtest error: {e}")
                import traceback
                st.code(traceback.format_exc())
