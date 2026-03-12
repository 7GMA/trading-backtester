# Trading Strategy Backtester

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-78%20passed-brightgreen.svg)](#running-tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](#api-endpoints)

A natural language-powered backtesting engine. Describe your trading strategy in plain English (or German), and get instant backtesting results with honest AI-powered critique.

```
"Buy Apple when RSI drops below 30. Sell at 10% profit or 5% loss."
                    |
         Strategy parsed -> Backtest run -> AI critique
                    |
  "Only 16 trades over 6 years. Low sample size.
   Strategy captured 4.4% vs 262% buy-and-hold.
   Consider adding a trend filter (SMA 200)."
```

## Features

| Feature | Description |
|---------|-------------|
| **NL Strategy Input** | Describe strategies in English or German. No coding required. |
| **AI Strategy Critic** | Claude analyzes results: flags overfitting, low sample size, suggests improvements |
| **Walk-Forward Validation** | Train/test split across multiple windows to detect overfitting |
| **Multi-Asset Testing** | Run one strategy across FAANG+, ETFs, Crypto, or DAX in one click |
| **Strategy Comparison** | Two strategies head-to-head with weighted scoring (Sharpe 3x, Return 2x, Drawdown 2x) |
| **PDF Reports** | 4-page professional report: summary, equity curve, metrics, trade log |
| **REST API** | 7 FastAPI endpoints with Swagger docs at `/docs` |
| **EU/German Focus** | Supports DAX, XETRA securities alongside US stocks and crypto |
| **Cost Transparency** | Live budget tracker -- users see exactly what AI requests cost |

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/trading-backtester.git
cd trading-backtester

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: add API key for AI features
cp .env.example .env
# Edit .env with your Anthropic API key

# Run the dashboard
streamlit run src/app/main.py
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
|               Streamlit Dashboard (5 pages)          |
|  Strategy Builder | Results | Multi-Asset | Compare  |
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                FastAPI REST API (7 endpoints)        |
|  /parse  /backtest  /critique  /multi-asset  /compare|
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                   Core Engine                        |
|  NL Parser       Backtesting      LLM Critic        |
|  (Claude API     Engine           (Claude Sonnet)    |
|   + Offline)     (backtesting.py)                    |
+------------------------+----------------------------+
                         |
+------------------------v----------------------------+
|                   Data Layer                         |
|  Yahoo Finance -> DuckDB Cache -> pandas-ta          |
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
├── app/                     # Streamlit dashboard
│   ├── main.py              # Entry point + cost tracker
│   └── pages/
│       ├── strategy.py      # NL strategy builder
│       ├── results.py       # Results + PDF export
│       ├── multi_asset.py   # Multi-asset backtesting
│       ├── compare.py       # Strategy comparison
│       └── dashboard.py     # Overview + data cache
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
│   └── indicators.py        # Technical indicators (pandas-ta)
└── strategy/
    ├── parser.py            # NL -> Strategy (Claude + offline regex)
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
| Language | Python 3.12 |
| Backtesting | backtesting.py |
| Indicators | pandas-ta (130+) |
| Data Cache | DuckDB |
| Market Data | Yahoo Finance (yfinance) |
| AI | Claude API (Anthropic) |
| API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Charts | Plotly |
| Deployment | Docker + docker-compose |

## Running Tests

```bash
pytest tests/ -v
# 78 tests, 4 files, <10s runtime
```

## Consulting & Integration

This project is available for white-label integration and custom consulting work:

- **Custom strategy development** -- build proprietary strategies for your firm
- **API integration** -- embed backtesting into your existing platform
- **Data source upgrades** -- swap Yahoo Finance for Polygon.io, EODHD, or your proprietary feed
- **Multi-language support** -- extend NL parsing beyond English/German

For inquiries, open an issue or reach out directly.

## Disclaimer

This software is for **educational and research purposes only**. It does not constitute financial advice, investment recommendations, or solicitation to trade. Backtesting results do not guarantee future performance. The authors assume no liability for financial losses incurred through the use of this software. Always consult a qualified financial advisor before making investment decisions.

## License

[MIT](LICENSE)
