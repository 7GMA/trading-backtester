"""FastAPI REST API for the Trading Backtester."""

from __future__ import annotations

import sys
from pathlib import Path

# Fix sys.path so src.* imports work when running with uvicorn
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.backtest.engine import run_backtest
from src.backtest.metrics import extract_metrics
from src.backtest.multi_asset import run_multi_asset
from src.backtest.comparison import compare_strategies
from src.data.yahoo_client import fetch
from src.strategy.executor import build_strategy
from src.strategy.models import ParsedStrategy
from src.strategy.parser import parse_strategy, parse_strategy_offline
from src.strategy.templates import TEMPLATES
from src.strategy.validator import validate_strategy

load_dotenv()

app = FastAPI(
    title="Trading Backtester API",
    description="REST API for parsing strategies, running backtests, and getting AI critiques.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    text: str = Field(description="Natural language strategy description")
    use_ai: bool = Field(default=False, description="Use Claude AI for parsing (requires API key)")


class ParseResponse(BaseModel):
    strategy: dict = Field(description="Parsed strategy JSON")
    warnings: list[str] = Field(default_factory=list)
    usage: dict | None = Field(default=None, description="Token usage (only with use_ai=True)")


class BacktestRequest(BaseModel):
    strategy: dict = Field(description="ParsedStrategy JSON")
    start: str = Field(default="2020-01-01", description="Backtest start date YYYY-MM-DD")
    end: str | None = Field(default=None, description="Backtest end date YYYY-MM-DD (default: today)")
    cash: float = Field(default=10_000, description="Starting capital")
    commission: float = Field(default=0.001, description="Commission per trade (0.001 = 0.1%)")


class BacktestResponse(BaseModel):
    metrics: dict = Field(description="Performance metrics")
    trades_count: int = Field(description="Number of trades executed")
    equity_curve_summary: dict = Field(description="Equity curve start/end/min/max")


class CritiqueRequest(BaseModel):
    strategy: dict = Field(description="ParsedStrategy JSON")
    metrics: dict = Field(description="Backtest metrics dict")
    trades_count: int = Field(default=0, description="Number of trades")


class CritiqueResponse(BaseModel):
    critique: str = Field(description="LLM analysis of the backtest results")


class TemplateInfo(BaseModel):
    key: str
    name: str
    asset: str
    description: str


class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]


class HealthResponse(BaseModel):
    status: str
    timestamp: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/strategies/templates", response_model=TemplatesResponse)
async def list_templates():
    """List available pre-built strategy templates."""
    items = []
    for key, tpl in TEMPLATES.items():
        items.append(TemplateInfo(
            key=key,
            name=tpl.name,
            asset=tpl.asset,
            description=tpl.description,
        ))
    return TemplatesResponse(templates=items)


@app.post("/parse", response_model=ParseResponse)
async def parse(req: ParseRequest):
    """Parse natural language into a structured strategy."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    if req.use_ai:
        try:
            strategy, warnings, usage = parse_strategy(req.text)
            return ParseResponse(
                strategy=strategy.model_dump(),
                warnings=warnings,
                usage=usage,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI parsing failed: {exc}")
    else:
        result = parse_strategy_offline(req.text)
        if result is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not parse strategy with offline rules. "
                    "Try use_ai=true or use a clearer pattern like "
                    "'Buy AAPL when RSI below 30' or 'Golden Cross on SPY'."
                ),
            )
        strategy, warnings = result
        return ParseResponse(
            strategy=strategy.model_dump(),
            warnings=warnings,
            usage=None,
        )


@app.post("/backtest", response_model=BacktestResponse)
async def backtest(req: BacktestRequest):
    """Run a backtest for the given strategy."""
    # Validate and build the strategy
    try:
        parsed = ParsedStrategy.model_validate(req.strategy)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid strategy JSON: {exc}")

    errors = validate_strategy(parsed)
    if errors:
        raise HTTPException(status_code=422, detail=f"Strategy validation errors: {errors}")

    # Build executable strategy class
    try:
        strategy_cls = build_strategy(parsed)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Strategy build failed: {exc}")

    # Fetch market data
    end_date = req.end or datetime.now().strftime("%Y-%m-%d")
    try:
        df = fetch(parsed.asset, start=req.start, end=end_date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed for {parsed.asset}: {exc}")

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for {parsed.asset} between {req.start} and {end_date}.",
        )

    # Run the backtest
    try:
        result = run_backtest(df, strategy_cls, cash=req.cash, commission=req.commission)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {exc}")

    # Extract metrics
    metrics = extract_metrics(result["stats"])
    trades_count = int(metrics.get("num_trades", 0) or 0)

    # Build equity curve summary
    eq = result.get("equity_curve")
    if eq is not None and not eq.empty and "Equity" in eq.columns:
        equity_series = eq["Equity"]
        equity_summary = {
            "start": float(equity_series.iloc[0]),
            "end": float(equity_series.iloc[-1]),
            "min": float(equity_series.min()),
            "max": float(equity_series.max()),
            "points": len(equity_series),
        }
    else:
        equity_summary = {"start": req.cash, "end": req.cash, "min": req.cash, "max": req.cash, "points": 0}

    return BacktestResponse(
        metrics=metrics,
        trades_count=trades_count,
        equity_curve_summary=equity_summary,
    )


# ---------------------------------------------------------------------------
# Critique endpoint – Claude-powered analysis
# ---------------------------------------------------------------------------

CRITIQUE_SYSTEM_PROMPT = """You are an experienced quantitative analyst reviewing trading backtest results. \
Provide honest, actionable feedback. Be direct and specific.

Structure your critique in these sections:

1. **Statistical Significance** – Assess whether the trade count is sufficient for reliable conclusions. \
   Fewer than 30 trades is generally unreliable. State the confidence level plainly.

2. **Performance vs. Buy & Hold** – Compare the strategy return to buy & hold. \
   If the strategy underperforms, say so clearly and explain why passive investing may be preferable.

3. **Risk Assessment** – Evaluate max drawdown, Sharpe ratio, Sortino ratio, and volatility. \
   Flag any concerning figures.

4. **Overfitting Risk** – Based on the strategy complexity (number of conditions, parameters) and trade count, \
   assess the likelihood that results are curve-fitted to historical data.

5. **Actionable Suggestions** – Provide 2-3 concrete improvements the trader could test.

Keep the response under 400 words. Be professional but blunt – the trader needs truth, not encouragement."""


@app.post("/critique", response_model=CritiqueResponse)
async def critique(req: CritiqueRequest):
    """Get an LLM critique of backtest results."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured. Cannot generate critique.",
        )

    # Build the user message with strategy and metrics context
    strategy_summary = json.dumps(req.strategy, indent=2, default=str)
    metrics_summary = json.dumps(req.metrics, indent=2, default=str)

    user_message = f"""Please critique this backtest:

## Strategy
```json
{strategy_summary}
```

## Results
- Trades: {req.trades_count}

## Metrics
```json
{metrics_summary}
```

Provide your honest analysis."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=CRITIQUE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        critique_text = response.content[0].text.strip()
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Critique generation failed: {exc}")

    return CritiqueResponse(critique=critique_text)


# ---------------------------------------------------------------------------
# Multi-Asset endpoint
# ---------------------------------------------------------------------------

class MultiAssetRequest(BaseModel):
    strategy: dict = Field(description="ParsedStrategy JSON")
    assets: list[str] = Field(description="List of ticker symbols to test")
    start: str = Field(default="2020-01-01", description="Backtest start date")
    end: str | None = Field(default=None, description="Backtest end date")
    cash: float = Field(default=10_000, description="Starting capital per asset")
    commission: float = Field(default=0.001, description="Commission per trade")


class MultiAssetResponse(BaseModel):
    results: dict = Field(description="Per-asset results {symbol: {metrics, trades_count, error}}")
    summary: dict = Field(description="Aggregate summary across all assets")
    rankings: list[dict] = Field(description="Assets ranked by return")


@app.post("/multi-asset", response_model=MultiAssetResponse)
async def multi_asset(req: MultiAssetRequest):
    """Run the same strategy across multiple assets."""
    try:
        parsed = ParsedStrategy.model_validate(req.strategy)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid strategy JSON: {exc}")

    if not req.assets:
        raise HTTPException(status_code=400, detail="At least one asset is required.")

    try:
        result = run_multi_asset(
            parsed=parsed,
            assets=req.assets,
            start=req.start,
            end=req.end,
            cash=req.cash,
            commission=req.commission,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Multi-asset backtest failed: {exc}")

    # Strip equity curves from results (too large for JSON response)
    clean_results = {}
    for symbol, data in result["results"].items():
        clean_results[symbol] = {
            "metrics": data["metrics"],
            "trades_count": data["trades_count"],
            "error": data["error"],
        }

    return MultiAssetResponse(
        results=clean_results,
        summary=result["summary"],
        rankings=result["rankings"],
    )


# ---------------------------------------------------------------------------
# Comparison endpoint
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    strategy_a: dict = Field(description="First strategy (ParsedStrategy JSON)")
    strategy_b: dict = Field(description="Second strategy (ParsedStrategy JSON)")
    start: str = Field(default="2020-01-01", description="Backtest start date")
    end: str | None = Field(default=None, description="Backtest end date")
    cash: float = Field(default=10_000, description="Starting capital")
    commission: float = Field(default=0.001, description="Commission per trade")


class CompareResponse(BaseModel):
    a: dict = Field(description="Strategy A results {name, metrics, trades_count}")
    b: dict = Field(description="Strategy B results {name, metrics, trades_count}")
    comparison: list[dict] = Field(description="Metric-by-metric comparison")
    winner: str = Field(description="'a', 'b', or 'tie'")


@app.post("/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    """Compare two strategies head-to-head on the same data."""
    try:
        parsed_a = ParsedStrategy.model_validate(req.strategy_a)
        parsed_b = ParsedStrategy.model_validate(req.strategy_b)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid strategy JSON: {exc}")

    try:
        result = compare_strategies(
            strategy_a=parsed_a,
            strategy_b=parsed_b,
            start=req.start,
            end=req.end,
            cash=req.cash,
            commission=req.commission,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {exc}")

    return CompareResponse(
        a={"name": result["a"]["name"], "metrics": result["a"]["metrics"], "trades_count": result["a"]["trades_count"]},
        b={"name": result["b"]["name"], "metrics": result["b"]["metrics"], "trades_count": result["b"]["trades_count"]},
        comparison=result["comparison"],
        winner=result["winner"],
    )


# ---------------------------------------------------------------------------
# Entrypoint for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
