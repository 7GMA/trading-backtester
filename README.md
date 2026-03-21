# Trading Strategy Backtester

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-78%20passed-brightgreen.svg)](#running-tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](#api-endpoints)

Describe a trading strategy in plain English, backtest it on real market data, and see how it would have performed — no coding required.

```
"Buy Apple when RSI drops below 30. Sell at 10% profit or 5% loss."
                    ↓
         Parsed → Backtested → Charts + Metrics
                    ↓
  Return: 4.4% · Sharpe: 0.12 · 16 Trades · Win Rate: 56%
```

## Features

- **Write strategies in plain text** — type what you'd tell a trader, the app figures out the rest
- **Works without AI** — common patterns (RSI, MACD, Golden Cross) are parsed offline, no API key needed
- **AI parsing for complex input** — Claude Haiku handles anything the offline parser can't
- **Real market data** — pulls live prices from Yahoo Finance for any stock, ETF, or crypto
- **Interactive charts** — equity curve, drawdown, and buy & hold comparison in dark-themed Plotly charts
- **PDF export** — download a professional backtest report
- **REST API** — 7 endpoints with Swagger docs, so you can integrate it into your own tools
- **Test across assets** — run the same strategy on AAPL, TSLA, BTC-USD and compare results
- **50 free AI requests/day** — built-in rate limiting with usage tracking

## Quick Start

```bash
git clone https://github.com/7GMA/trading-backtester.git
cd trading-backtester

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the app (works without API key — use the offline parser)
streamlit run src/app/main.py

# Optional: enable AI parsing
cp .env.example .env
# Add your Anthropic API key to .env
```

**With Docker:**

```bash
docker compose up
# Dashboard: http://localhost:8501
# API docs:  http://localhost:8000/docs
```

## Architecture

```
+-----------------------------------------------------+
|          Streamlit Single-Page App (Dark Theme)      |
|  Templates | Strategy Input | Backtest | Results     |
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                FastAPI REST API (7 endpoints)        |
|  /parse  /backtest  /critique  /multi-asset  /compare|
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                   Core Engine                        |
|  NL Parser       Backtesting      PDF Reports       |
|  (Claude Haiku   Engine           (matplotlib)       |
|   + Offline)     (backtesting.py)                    |
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                   Data Layer                         |
|  Yahoo Finance -> DuckDB Cache -> pandas Indicators  |
+-----------------------------------------------------+
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/strategies/templates` | List pre-built templates |
| POST | `/parse` | NL text -> structured strategy |
| POST | `/backtest` | Run a backtest |
| POST | `/critique` | AI-powered strategy analysis |
| POST | `/multi-asset` | Test strategy across multiple assets |
| POST | `/compare` | Compare two strategies head-to-head |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

### Example: Full Workflow via API

```python
import requests

# 1. Parse strategy from natural language
resp = requests.post("http://localhost:8000/parse", json={
    "text": "Buy TSLA when MACD crosses above signal. 5% stop loss.",
    "use_ai": False
})
strategy = resp.json()["strategy"]

# 2. Run backtest
resp = requests.post("http://localhost:8000/backtest", json={
    "strategy": strategy,
    "start": "2020-01-01",
    "cash": 10000
})
result = resp.json()
print(f"Return: {result['metrics']['total_return_pct']:.1f}%")

# 3. Get AI critique
resp = requests.post("http://localhost:8000/critique", json={
    "strategy": strategy,
    "metrics": result["metrics"],
    "trades_count": result["trades_count"]
})
print(resp.json()["critique"])

# 4. Test across multiple assets
resp = requests.post("http://localhost:8000/multi-asset", json={
    "strategy": strategy,
    "assets": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
    "start": "2020-01-01"
})
for r in resp.json()["rankings"]:
    print(f"  {r['asset']}: {r['return_pct']:.1f}%")
```

## Supported Indicators

| Indicator | Parameters | Example Input |
|-----------|-----------|---------------|
| RSI | period (default: 14) | "RSI below 30" |
| MACD | fast, slow, signal | "MACD bullish crossover" |
| SMA | period | "SMA 50 crosses above SMA 200" |
| EMA | period (default: 20) | "EMA 20 above price" |
| Bollinger Bands | period, std | "Price below lower BB" |
| ATR | period (default: 14) | "ATR above 2.0" |

## Supported Assets

Any ticker Yahoo Finance supports:
- **US Stocks**: AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, META...
- **ETFs**: SPY, QQQ, VOO, IWM, DIA...
- **Crypto**: BTC-USD, ETH-USD, SOL-USD...
- **German/EU**: SAP.DE, SIE.DE, BMW.DE, ALV.DE, DTE.DE...
- **Indices**: ^GSPC (S&P 500), ^GDAXI (DAX)...

## Project Structure

```
src/
├── api/server.py            # FastAPI REST API (7 endpoints)
├── app/
│   ├── main.py              # Single-page Streamlit app
│   └── theme.py             # Dark theme CSS + Plotly layout
├── backtest/
│   ├── engine.py            # Backtesting wrapper
│   ├── metrics.py           # Performance metrics (20+)
│   ├── walk_forward.py      # Walk-forward validation
│   ├── multi_asset.py       # Multi-asset engine
│   ├── comparison.py        # Strategy comparison engine
│   ├── pdf_report.py        # PDF report generation
│   └── reports.py           # HTML report (quantstats)
├── data/
│   ├── yahoo_client.py      # Yahoo Finance + DuckDB caching
│   ├── cache.py             # DuckDB cache layer
│   └── indicators.py        # Technical indicators (pure pandas)
└── strategy/
    ├── parser.py            # NL -> Strategy (Claude Haiku + offline regex)
    ├── executor.py          # Strategy -> executable backtest class
    ├── models.py            # Pydantic models + validation schema
    ├── validator.py         # Strategy validation
    └── templates.py         # 4 pre-built strategies

tests/                       # 78 tests
├── test_backtest.py         # Engine + walk-forward (24 tests)
├── test_data.py             # DuckDB cache (16 tests)
├── test_multi_asset.py      # Multi-asset + comparison + PDF (16 tests)
└── test_parser.py           # NL parser (22 tests)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Backtesting | backtesting.py |
| Indicators | Pure pandas/numpy |
| Data Cache | DuckDB |
| Market Data | Yahoo Finance (yfinance) |
| AI | Claude Haiku 4.5 (Anthropic) |
| API | FastAPI + Uvicorn |
| Frontend | Streamlit (dark theme) |
| Charts | Plotly |
| Deployment | Docker + docker-compose |

## Running Tests

```bash
pytest tests/ -v
# 78 tests, 4 files, <10s runtime
```

## Disclaimer

This software is for **educational and research purposes only**. It does not constitute financial advice, investment recommendations, or solicitation to trade. Backtesting results do not guarantee future performance. The authors assume no liability for financial losses incurred through the use of this software. Always consult a qualified financial advisor before making investment decisions.

## License

[MIT](LICENSE)
