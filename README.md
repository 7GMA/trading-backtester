# Trading Strategy Backtester

A natural language-powered backtesting engine. Describe your trading strategy in plain English (or German), and get instant backtesting results with honest AI-powered critique.

```
"Buy Apple when RSI drops below 30. Sell at 10% profit or 5% loss."
                    ↓
         Strategy parsed → Backtest run → AI critique
                    ↓
  "Only 16 trades over 6 years. Low sample size.
   Strategy captured 4.4% vs 262% buy-and-hold.
   Consider adding a trend filter (SMA 200)."
```

## What makes this different

- **Natural language input** — No coding required. Describe strategies in English or German.
- **AI Strategy Critic** — After each backtest, Claude analyzes your results and tells you *why* your strategy works or doesn't. Flags overfitting, low sample size, and suggests improvements.
- **Walk-forward validation** — Splits data into train/test windows to detect overfitting. Not just one backtest, but proof that your strategy generalizes.
- **Multi-asset backtesting** — Run the same strategy across multiple assets at once. See which stocks, ETFs, or crypto your strategy works best on.
- **Strategy comparison** — Test two strategies head-to-head on the same data with weighted scoring across Sharpe, return, drawdown, and more.
- **PDF report export** — Generate professional multi-page PDF reports with equity curves, metrics, and trade logs.
- **European market focus** — Supports DAX, Euro Stoxx, and XETRA-traded securities alongside US stocks and crypto.
- **REST API** — Full FastAPI backend with 7 endpoints. Integrate backtesting into your own tools.

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/trading-backtester.git
cd trading-backtester

# Setup
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Add your API key (optional, needed for AI parsing + critique)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Run the dashboard
streamlit run src/app/main.py
```

Or with Docker:

```bash
docker compose up
# Dashboard: http://localhost:8501
# API: http://localhost:8000/docs
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Streamlit Dashboard                   │
│         Strategy Builder → Results → Dashboard        │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  FastAPI REST API                     │
│     POST /parse  /backtest  /critique  /walk-forward │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                    Core Engine                        │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ NL Parser    │  │ Backtesting │  │ LLM Critic │  │
│  │ (Claude API  │  │ Engine      │  │ (Claude    │  │
│  │  + Offline)  │  │ (backtesting│  │  Sonnet)   │  │
│  │              │  │  .py)       │  │            │  │
│  └──────────────┘  └─────────────┘  └────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                    Data Layer                         │
│  Yahoo Finance → DuckDB Cache → pandas-ta Indicators │
└─────────────────────────────────────────────────────┘
```

## API Usage

```python
import requests

# Parse a strategy from natural language
resp = requests.post("http://localhost:8000/parse", json={
    "text": "Buy TSLA when MACD crosses above signal. 5% stop loss.",
    "use_ai": False
})
strategy = resp.json()["strategy"]

# Run backtest
resp = requests.post("http://localhost:8000/backtest", json={
    "strategy": strategy,
    "start": "2020-01-01",
    "cash": 10000
})
result = resp.json()

# Get AI critique
resp = requests.post("http://localhost:8000/critique", json={
    "strategy": strategy,
    "metrics": result["metrics"],
    "trades_count": result["trades_count"]
})
print(resp.json()["critique"])

# Multi-asset: test one strategy across many stocks
resp = requests.post("http://localhost:8000/multi-asset", json={
    "strategy": strategy,
    "assets": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
    "start": "2020-01-01",
    "cash": 10000
})
print(resp.json()["rankings"])

# Compare two strategies head-to-head
resp = requests.post("http://localhost:8000/compare", json={
    "strategy_a": strategy_a,
    "strategy_b": strategy_b,
    "start": "2020-01-01",
    "cash": 10000
})
print(f"Winner: {resp.json()['winner']}")
```

## Supported Indicators

| Indicator | Parameters | Example |
|-----------|-----------|---------|
| RSI | period (default: 14) | "RSI below 30" |
| MACD | fast, slow, signal | "MACD bullish crossover" |
| SMA | period | "SMA 50 crosses above SMA 200" |
| EMA | period (default: 20) | "EMA 20 above price" |
| Bollinger Bands | period, std | "Price below lower BB" |
| ATR | period (default: 14) | "ATR above 2.0" |

## Supported Assets

Any ticker Yahoo Finance supports:
- **US Stocks**: AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, META...
- **ETFs**: SPY, QQQ, VOO, IWM...
- **Crypto**: BTC-USD, ETH-USD, SOL-USD...
- **German Stocks**: SAP.DE, SIE.DE, BMW.DE, ALV.DE...
- **Indices**: ^GSPC (S&P 500), ^GDAXI (DAX)...

## Project Structure

```
src/
├── api/server.py          # FastAPI REST API (7 endpoints)
├── app/                   # Streamlit dashboard
│   ├── main.py
│   └── pages/
│       ├── strategy.py    # Strategy builder
│       ├── results.py     # Backtest results + PDF export
│       ├── multi_asset.py # Multi-asset backtesting
│       ├── compare.py     # Strategy comparison
│       └── dashboard.py   # Overview
├── backtest/
│   ├── engine.py          # Backtesting wrapper
│   ├── metrics.py         # Performance metrics
│   ├── reports.py         # HTML report generation
│   ├── walk_forward.py    # Walk-forward validation
│   ├── multi_asset.py     # Multi-asset backtesting
│   ├── comparison.py      # Strategy comparison engine
│   └── pdf_report.py      # PDF report generation
├── data/
│   ├── yahoo_client.py    # Yahoo Finance + caching
│   ├── cache.py           # DuckDB cache layer
│   └── indicators.py      # Technical indicators
└── strategy/
    ├── parser.py           # NL → Strategy (Claude + offline)
    ├── executor.py         # Strategy → executable backtest
    ├── models.py           # Pydantic models
    ├── validator.py        # Strategy validation
    └── templates.py        # Pre-built strategies
```

## Tech Stack

- **Python 3.12** — Core language
- **backtesting.py** — Backtesting engine
- **pandas-ta** — 130+ technical indicators
- **DuckDB** — Local analytical database for market data cache
- **yfinance** — Market data (Yahoo Finance)
- **Claude API (Anthropic)** — NL parsing + strategy critique
- **FastAPI** — REST API
- **Streamlit** — Dashboard UI
- **Plotly** — Interactive charts
- **Docker** — Containerized deployment

## Running Tests

```bash
pytest tests/ -v
# 78 tests across 4 test files
```

## Limitations

- Yahoo Finance is not an official API — data can have gaps or break
- Daily data only for most reliable results (intraday < 1h is unreliable)
- Backtesting results do not guarantee future performance
- German/EU stock data coverage via Yahoo is limited

## License

MIT
