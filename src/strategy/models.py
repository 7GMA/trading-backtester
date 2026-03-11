"""Pydantic models for parsed trading strategies."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Operator(str, Enum):
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    EQ = "=="
    CROSS_ABOVE = "crosses_above"
    CROSS_BELOW = "crosses_below"


class LogicOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class IndicatorCondition(BaseModel):
    """A single condition based on a technical indicator."""
    indicator: str = Field(description="Indicator name, e.g. RSI, MACD, SMA, EMA, BB, ATR")
    params: dict = Field(default_factory=dict, description="Indicator parameters, e.g. {period: 14}")
    operator: Operator = Field(description="Comparison operator")
    value: float | str | None = Field(
        default=None,
        description="Threshold value (number) or another indicator name for crossover comparisons",
    )


class EntryRule(BaseModel):
    """Entry conditions for the strategy."""
    conditions: list[IndicatorCondition] = Field(min_length=1)
    logic: LogicOperator = Field(default=LogicOperator.AND)


class ExitRule(BaseModel):
    """Exit conditions."""
    take_profit: float | None = Field(default=None, description="Take profit as decimal, e.g. 0.10 = 10%")
    stop_loss: float | None = Field(default=None, description="Stop loss as decimal, e.g. 0.05 = 5%")
    trailing_stop: float | None = Field(default=None, description="Trailing stop as decimal")
    conditions: list[IndicatorCondition] = Field(default_factory=list, description="Indicator-based exit conditions")
    logic: LogicOperator = Field(default=LogicOperator.AND)


class ParsedStrategy(BaseModel):
    """Complete parsed strategy from natural language input."""
    name: str = Field(description="Short descriptive name for the strategy")
    asset: str = Field(description="Ticker symbol, e.g. AAPL, BTC-USD, SPY")
    entry: EntryRule
    exit: ExitRule
    timeframe: str = Field(default="1d", description="Candle timeframe: 1d, 1h")
    description: str = Field(default="", description="Human-readable summary of the strategy")


# Supported indicators for validation
SUPPORTED_INDICATORS = {
    "RSI": {"params": ["period"], "defaults": {"period": 14}},
    "MACD": {"params": ["fast", "slow", "signal"], "defaults": {"fast": 12, "slow": 26, "signal": 9}},
    "SMA": {"params": ["period"], "defaults": {"period": 50}},
    "EMA": {"params": ["period"], "defaults": {"period": 20}},
    "BB": {"params": ["period", "std"], "defaults": {"period": 20, "std": 2.0}},
    "ATR": {"params": ["period"], "defaults": {"period": 14}},
    "VWAP": {"params": [], "defaults": {}},
    "STOCH": {"params": ["k_period", "d_period"], "defaults": {"k_period": 14, "d_period": 3}},
}
