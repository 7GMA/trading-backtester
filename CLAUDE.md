# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_parser.py -v

# Run a single test
pytest tests/test_backtest.py::TestRunBacktest::test_rsi_strategy_runs -v

# Start Streamlit dashboard (port 8501)
streamlit run src/app/main.py

# Start FastAPI server (port 8000)
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# Start both with Docker
docker compose up
```

## Architecture

The app converts natural language trading strategies into executable backtests via a three-stage pipeline:

**NL Text -> ParsedStrategy (JSON) -> DynamicStrategy (class) -> Backtest Results**

1. **Parser** (`src/strategy/parser.py`): Takes user text, produces a `ParsedStrategy` Pydantic model. Two paths: Claude API (`parse_strategy`) or regex-based offline (`parse_strategy_offline`). The offline parser handles RSI, MACD, Golden Cross patterns in English and German.

2. **Executor** (`src/strategy/executor.py`): Converts `ParsedStrategy` into a `backtesting.py` Strategy subclass at runtime. Indicators must be stored as direct attributes via `setattr(self, _ind_attr_name(key), self.I(...))` -- backtesting.py tracks indicators through instance attributes, not dicts.

3. **Engine** (`src/backtest/engine.py`): Wraps `backtesting.py` with `run_backtest()` and `optimize_strategy()`. Three built-in strategies plus dynamic ones from the executor.

**Data flow**: Yahoo Finance -> DuckDB cache (`src/data/cache.py`) -> pandas DataFrame with indicators (`src/data/indicators.py`).

**Two frontends** serve the same core:
- Streamlit (`src/app/main.py` + 5 pages) -- interactive dashboard
- FastAPI (`src/api/server.py`) -- 7 REST endpoints at `/docs`

Both need `sys.path.insert` at the top because they run from different working directories.

## Key Design Decisions

- `ParsedStrategy` in `src/strategy/models.py` is the central data structure. Everything flows through it.
- DuckDB cache uses upsert (delete + insert) and compares dates with a buffer (5 days start, 3 days end) to handle weekends/holidays.
- The system prompt in `parser.py` accepts both English and German input. The offline parser regex patterns also handle German ("unter", "faellt unter", "kreuzt").
- Daily budget tracking ($0.30/day) is session-based in Streamlit, enforced in `src/app/pages/strategy.py`.
- All UI text is in English. No emojis anywhere in the codebase.
