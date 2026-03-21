"""Dark theme CSS and Plotly layout."""

import streamlit as st

CHART_COLORS = [
    "#58a6ff", "#f85149", "#3fb950", "#d29922",
    "#bc8cff", "#39d2c0", "#db6d28", "#8b949e",
]

PLOTLY_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#e6edf3"),
    xaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d"),
    yaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#8b949e")),
    margin=dict(l=20, r=20, t=40, b=20),
)


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        code, pre, .stCodeBlock { font-family: 'JetBrains Mono', monospace !important; }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header[data-testid="stHeader"] {background: transparent;}

        .main .block-container { padding-top: 2rem; max-width: 1100px; }

        div[data-testid="stMetric"] {
            background-color: #161b22;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 1rem;
        }
        div[data-testid="stMetric"] label { color: #8b949e !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #e6edf3 !important; }

        .stButton > button[kind="primary"] {
            background-color: #58a6ff; border: none; color: #fff;
            border-radius: 6px; font-weight: 600;
        }
        .stButton > button[kind="primary"]:hover { background-color: #4c95e6; }
        .stButton > button:not([kind="primary"]) {
            background-color: #1c2333; border: 1px solid #21262d;
            color: #e6edf3; border-radius: 6px;
        }

        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stNumberInput > div > div > input {
            background-color: #161b22 !important;
            border-color: #21262d !important;
            color: #e6edf3 !important;
        }

        .stDataFrame { border: 1px solid #21262d; border-radius: 8px; }
        hr { border-color: #21262d !important; }

        section[data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #21262d;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
