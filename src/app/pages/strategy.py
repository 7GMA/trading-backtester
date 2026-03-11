"""Strategy Builder page – enter strategies in natural language."""

import streamlit as st
import json

from src.strategy.parser import parse_strategy, parse_strategy_offline
from src.strategy.templates import TEMPLATES, get_template
from src.strategy.validator import validate_strategy


st.title("Strategy Builder")

# --- Template Selection ---
st.subheader("Vorlagen")

# Responsive: 2 columns on small screens, 4 on wide
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
st.subheader("Strategie beschreiben")
strategy_text = st.text_area(
    "Beschreibe deine Strategie in natuerlicher Sprache:",
    value=st.session_state.get("strategy_input", ""),
    height=120,
    placeholder='z.B. "Kaufe Apple wenn der RSI unter 30 faellt. Verkaufe bei 10% Gewinn oder 5% Verlust."',
)

col1, col2 = st.columns([1, 1])
with col1:
    use_ai = st.checkbox("Claude AI Parser verwenden", value=False, help="Nutzt die Claude API fuer komplexe Strategien")
with col2:
    if st.button("Strategie parsen", type="primary", use_container_width=True):
        if not strategy_text.strip():
            st.error("Bitte gib eine Strategie ein.")
        else:
            st.session_state["strategy_input"] = strategy_text
            with st.spinner("Strategie wird geparst..."):
                try:
                    if use_ai:
                        strategy, warnings, usage = parse_strategy(strategy_text)
                        # Track API costs
                        costs = st.session_state["api_costs"]
                        costs["requests"] += 1
                        costs["input_tokens"] += usage.get("input_tokens", 0)
                        costs["output_tokens"] += usage.get("output_tokens", 0)
                    else:
                        result = parse_strategy_offline(strategy_text)
                        if result is None:
                            st.warning("Offline-Parser konnte die Strategie nicht erkennen. Aktiviere 'Claude AI Parser' fuer komplexe Strategien.")
                            st.stop()
                        strategy, warnings = result

                    st.session_state["parsed_strategy"] = strategy
                    if warnings:
                        for w in warnings:
                            st.warning(w)
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Parsen: {e}")

# --- Show Parsed Strategy ---
if "parsed_strategy" in st.session_state:
    strategy = st.session_state["parsed_strategy"]
    st.divider()
    st.subheader("Geparsete Strategie")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Asset", strategy.asset)
    with col2:
        st.metric("Timeframe", strategy.timeframe)
    with col3:
        st.metric("Name", strategy.name)

    # Entry conditions
    st.markdown("**Entry Bedingungen** " + f"({strategy.entry.logic.value})")
    for cond in strategy.entry.conditions:
        params_str = ", ".join(f"{k}={v}" for k, v in cond.params.items())
        st.markdown(f"- `{cond.indicator}({params_str})` {cond.operator.value} `{cond.value}`")

    # Exit conditions
    st.markdown("**Exit Regeln**")
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
    with st.expander("JSON ansehen"):
        st.json(json.loads(strategy.model_dump_json()))

    st.divider()

    # --- Backtest Configuration ---
    st.subheader("Backtest Konfiguration")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        asset_override = st.text_input("Asset ueberschreiben", value=strategy.asset)
    with col2:
        start_date = st.date_input("Start", value=None)
        start_str = str(start_date) if start_date else "2020-01-01"
    with col3:
        cash = st.number_input("Startkapital ($)", value=10000, step=1000, min_value=100)
    with col4:
        commission = st.number_input("Kommission (%)", value=0.1, step=0.05, min_value=0.0, format="%.2f")

    if st.button("Backtest starten", type="primary", use_container_width=True):
        strategy.asset = asset_override.upper()
        st.session_state["backtest_config"] = {
            "strategy": strategy,
            "start": start_str,
            "cash": cash,
            "commission": commission / 100,
        }

        with st.spinner(f"Backtest laeuft fuer {strategy.asset}..."):
            try:
                from src.data.yahoo_client import fetch
                from src.strategy.executor import build_strategy
                from src.backtest.engine import run_backtest
                from src.backtest.metrics import extract_metrics

                df = fetch(strategy.asset, start=start_str)
                if df.empty:
                    st.error(f"Keine Daten fuer {strategy.asset} gefunden.")
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

                st.success("Backtest abgeschlossen! Wechsle zu 'Backtest Results' fuer Details.")
                st.switch_page("pages/results.py")

            except Exception as e:
                st.error(f"Backtest Fehler: {e}")
                import traceback
                st.code(traceback.format_exc())
