"""Pre-built strategy templates for quick use."""

from src.strategy.models import (
    ParsedStrategy, EntryRule, ExitRule, IndicatorCondition, Operator, LogicOperator,
)

TEMPLATES: dict[str, ParsedStrategy] = {
    "rsi_oversold": ParsedStrategy(
        name="RSI Oversold Bounce",
        asset="AAPL",
        description="Buy when RSI drops below 30, sell at 10% profit or 5% loss",
        entry=EntryRule(
            conditions=[
                IndicatorCondition(indicator="RSI", params={"period": 14}, operator=Operator.LT, value=30),
            ]
        ),
        exit=ExitRule(take_profit=0.10, stop_loss=0.05),
    ),
    "macd_crossover": ParsedStrategy(
        name="MACD Bullish Crossover",
        asset="AAPL",
        description="Buy on bullish MACD crossover, sell on bearish crossover or 5% stop loss",
        entry=EntryRule(
            conditions=[
                IndicatorCondition(
                    indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                    operator=Operator.CROSS_ABOVE, value="MACD_SIGNAL",
                ),
            ]
        ),
        exit=ExitRule(
            stop_loss=0.05,
            conditions=[
                IndicatorCondition(
                    indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                    operator=Operator.CROSS_BELOW, value="MACD_SIGNAL",
                ),
            ],
        ),
    ),
    "golden_cross": ParsedStrategy(
        name="Golden Cross",
        asset="SPY",
        description="Buy when SMA 50 crosses above SMA 200, sell when it crosses below",
        entry=EntryRule(
            conditions=[
                IndicatorCondition(
                    indicator="SMA", params={"period": 50},
                    operator=Operator.CROSS_ABOVE, value="SMA_200",
                ),
            ]
        ),
        exit=ExitRule(
            stop_loss=0.07,
            conditions=[
                IndicatorCondition(
                    indicator="SMA", params={"period": 50},
                    operator=Operator.CROSS_BELOW, value="SMA_200",
                ),
            ],
        ),
    ),
    "rsi_macd_combo": ParsedStrategy(
        name="RSI + MACD Combo",
        asset="AAPL",
        description="Buy when RSI < 30 AND MACD crosses above signal. Sell at 10% profit or 5% loss.",
        entry=EntryRule(
            conditions=[
                IndicatorCondition(indicator="RSI", params={"period": 14}, operator=Operator.LT, value=30),
                IndicatorCondition(
                    indicator="MACD", params={"fast": 12, "slow": 26, "signal": 9},
                    operator=Operator.CROSS_ABOVE, value="MACD_SIGNAL",
                ),
            ],
            logic=LogicOperator.AND,
        ),
        exit=ExitRule(take_profit=0.10, stop_loss=0.05),
    ),
}


def get_template(name: str, asset: str | None = None) -> ParsedStrategy:
    """Get a template, optionally overriding the asset."""
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATES.keys())}")
    strategy = TEMPLATES[name].model_copy()
    if asset:
        strategy.asset = asset.upper()
    return strategy
