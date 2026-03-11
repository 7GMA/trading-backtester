"""Natural language → ParsedStrategy using Claude API."""

from __future__ import annotations

import json
import os

import anthropic
from dotenv import load_dotenv

from src.strategy.models import ParsedStrategy, SUPPORTED_INDICATORS
from src.strategy.validator import validate_strategy

load_dotenv()

SYSTEM_PROMPT = f"""Du bist ein Trading-Strategie-Parser. Deine Aufgabe ist es, natürlichsprachliche Strategiebeschreibungen in strukturiertes JSON zu übersetzen.

## Unterstützte Indikatoren
{json.dumps({k: v["defaults"] for k, v in SUPPORTED_INDICATORS.items()}, indent=2)}

## Regeln
1. Gib NUR valides JSON zurück, KEIN zusätzlicher Text
2. Verwende nur Indikatoren aus der obigen Liste
3. Prozentangaben als Dezimalzahlen (10% → 0.10)
4. Erkenne gängige Synonyme:
   - "überverkauft" / "oversold" → RSI < 30
   - "überkauft" / "overbought" → RSI > 70
   - "Golden Cross" → SMA(50) crosses_above SMA(200)
   - "Death Cross" → SMA(50) crosses_below SMA(200)
   - "bullisches Crossover" → MACD crosses_above MACD_SIGNAL
5. Wenn kein Asset genannt wird, verwende "AAPL" als Default
6. Wenn kein Stop-Loss genannt wird, setze 0.05 (5%) als Default
7. Ticker müssen Yahoo Finance Format haben (z.B. BTC-USD, ETH-USD für Crypto)

## JSON Schema
{{
  "name": "Kurzer Name der Strategie",
  "asset": "TICKER",
  "timeframe": "1d",
  "description": "Menschenlesbare Beschreibung",
  "entry": {{
    "conditions": [
      {{
        "indicator": "RSI",
        "params": {{"period": 14}},
        "operator": "<",
        "value": 30
      }}
    ],
    "logic": "AND"
  }},
  "exit": {{
    "take_profit": 0.10,
    "stop_loss": 0.05,
    "trailing_stop": null,
    "conditions": [],
    "logic": "AND"
  }}
}}

## Erlaubte Operator-Werte
"<", ">", "<=", ">=", "==", "crosses_above", "crosses_below"
"""


def parse_strategy(
    user_input: str,
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None,
) -> tuple[ParsedStrategy, list[str], dict]:
    """
    Parse natural language strategy description into a ParsedStrategy.

    Returns:
        Tuple of (ParsedStrategy, list of validation warnings, usage dict)
    """
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No API key found. Set ANTHROPIC_API_KEY in .env or pass api_key parameter."
        )

    client = anthropic.Anthropic(api_key=key)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_input},
        ],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    raw_text = response.content[0].text.strip()

    # Extract JSON if wrapped in markdown code block
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        json_lines = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                inside = True
                continue
            elif line.startswith("```") and inside:
                break
            elif inside:
                json_lines.append(line)
        raw_text = "\n".join(json_lines)

    parsed = json.loads(raw_text)
    strategy = ParsedStrategy.model_validate(parsed)

    warnings = validate_strategy(strategy)

    return strategy, warnings, usage


def parse_strategy_offline(user_input: str) -> tuple[ParsedStrategy, list[str]] | None:
    """
    Simple rule-based parser for common patterns (no API needed).
    Returns None if the input can't be parsed with simple rules.
    """
    text = user_input.lower().strip()

    # Try to detect asset
    import re
    asset = "AAPL"
    # Skip known indicator names and common command words when detecting tickers
    _skip_words = {
        "RSI", "MACD", "SMA", "EMA", "ATR", "BB", "VWAP", "STOCH",
        "AND", "OR", "BUY", "SELL", "WHEN", "IF", "THE", "ON", "FOR",
        "WITH", "USE", "SET",
    }
    # Match patterns like "buy AAPL", "kaufe Apple", ticker symbols
    for ticker_match in re.finditer(r'\b([A-Z]{1,5}(?:-[A-Z]{1,5})?)\b', user_input):
        candidate = ticker_match.group(1)
        if candidate not in _skip_words:
            asset = candidate
            break

    # Common ticker aliases
    aliases = {
        "apple": "AAPL", "tesla": "TSLA", "google": "GOOGL", "amazon": "AMZN",
        "microsoft": "MSFT", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
        "nvidia": "NVDA", "meta": "META", "netflix": "NFLX",
    }
    for name, ticker in aliases.items():
        if name in text:
            asset = ticker
            break

    # Detect stop loss / take profit
    sl_match = re.search(r'(\d+)\s*%?\s*(stop.?loss|verlust|sl)', text)
    tp_match = re.search(r'(\d+)\s*%?\s*(take.?profit|gewinn|tp|profit)', text)
    stop_loss = int(sl_match.group(1)) / 100 if sl_match else 0.05
    take_profit = int(tp_match.group(1)) / 100 if tp_match else 0.10

    # Try to match known patterns
    from src.strategy.models import (
        ParsedStrategy, EntryRule, ExitRule, IndicatorCondition, Operator,
    )

    # RSI pattern
    rsi_match = re.search(r'rsi\s*(?:unter|below|<|fällt unter)\s*(\d+)', text)
    if rsi_match:
        threshold = int(rsi_match.group(1))
        strategy = ParsedStrategy(
            name=f"RSI Oversold ({asset})",
            asset=asset,
            description=user_input,
            entry=EntryRule(conditions=[
                IndicatorCondition(indicator="RSI", params={"period": 14}, operator=Operator.LT, value=threshold),
            ]),
            exit=ExitRule(take_profit=take_profit, stop_loss=stop_loss),
        )
        warnings = validate_strategy(strategy)
        return strategy, warnings

    # Golden Cross pattern
    if "golden cross" in text or ("sma" in text and "cross" in text):
        strategy = ParsedStrategy(
            name=f"Golden Cross ({asset})",
            asset=asset,
            description=user_input,
            entry=EntryRule(conditions=[
                IndicatorCondition(
                    indicator="SMA", params={"period": 50},
                    operator=Operator.CROSS_ABOVE, value="SMA_200",
                ),
            ]),
            exit=ExitRule(
                stop_loss=stop_loss,
                conditions=[
                    IndicatorCondition(
                        indicator="SMA", params={"period": 50},
                        operator=Operator.CROSS_BELOW, value="SMA_200",
                    ),
                ],
            ),
        )
        warnings = validate_strategy(strategy)
        return strategy, warnings

    # MACD pattern
    if "macd" in text and ("cross" in text or "crossover" in text or "kreuzt" in text):
        strategy = ParsedStrategy(
            name=f"MACD Crossover ({asset})",
            asset=asset,
            description=user_input,
            entry=EntryRule(conditions=[
                IndicatorCondition(
                    indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                    operator=Operator.CROSS_ABOVE, value="MACD_SIGNAL",
                ),
            ]),
            exit=ExitRule(
                stop_loss=stop_loss,
                take_profit=take_profit,
                conditions=[
                    IndicatorCondition(
                        indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                        operator=Operator.CROSS_BELOW, value="MACD_SIGNAL",
                    ),
                ],
            ),
        )
        warnings = validate_strategy(strategy)
        return strategy, warnings

    return None
