"""Dashboard / Overview page."""

import streamlit as st
import pandas as pd

from src.data.cache import get_connection, get_cached_symbols, get_date_range
from src.strategy.templates import TEMPLATES


st.title("Dashboard")

# --- Cached Data Overview ---
st.subheader("Gecachte Marktdaten")
try:
    conn = get_connection()
    symbols = get_cached_symbols(conn)

    if symbols:
        rows = []
        for sym in symbols:
            dr = get_date_range(sym, conn)
            if dr:
                rows.append({"Symbol": sym, "Von": str(dr[0]), "Bis": str(dr[1])})
        conn.close()

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        conn.close()
        st.info("Noch keine Daten im Cache. Starte einen Backtest, um Daten zu laden.")
except Exception as e:
    st.error(f"Cache-Fehler: {e}")

st.divider()

# --- Quick Fetch ---
st.subheader("Daten laden")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    fetch_symbol = st.text_input("Symbol", value="AAPL", placeholder="z.B. AAPL, TSLA, BTC-USD")
with col2:
    fetch_start = st.date_input("Von", value=None)
with col3:
    if st.button("Laden", use_container_width=True):
        from src.data.yahoo_client import fetch
        from src.data.indicators import add_default_indicators

        with st.spinner(f"Lade {fetch_symbol}..."):
            start = str(fetch_start) if fetch_start else "2020-01-01"
            df = fetch(fetch_symbol.upper(), start=start)
            if not df.empty:
                df = add_default_indicators(df)
                st.success(f"{fetch_symbol.upper()}: {len(df)} Tage geladen")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.error(f"Keine Daten fuer {fetch_symbol} gefunden.")

st.divider()

# --- Available Templates ---
st.subheader("Verfuegbare Strategie-Templates")
for key, tmpl in TEMPLATES.items():
    with st.expander(f"**{tmpl.name}** -- {tmpl.asset}"):
        st.write(tmpl.description)
        st.markdown("**Entry:**")
        for c in tmpl.entry.conditions:
            params = ", ".join(f"{k}={v}" for k, v in c.params.items())
            st.markdown(f"- `{c.indicator}({params})` {c.operator.value} `{c.value}`")
        st.markdown("**Exit:**")
        if tmpl.exit.stop_loss:
            st.markdown(f"- Stop Loss: {tmpl.exit.stop_loss*100:.0f}%")
        if tmpl.exit.take_profit:
            st.markdown(f"- Take Profit: {tmpl.exit.take_profit*100:.0f}%")

# --- Last Backtest Result ---
if "backtest_result" in st.session_state:
    st.divider()
    st.subheader("Letzter Backtest")
    r = st.session_state["backtest_result"]
    m = r["metrics"]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Strategie", r["strategy_name"])
    with col2:
        st.metric("Return", f"{m['total_return_pct']:.1f}%" if m['total_return_pct'] else "N/A")
    with col3:
        st.metric("Sharpe", f"{m['sharpe_ratio']:.2f}" if m['sharpe_ratio'] else "N/A")
    with col4:
        st.metric("Trades", m["num_trades"] or 0)
