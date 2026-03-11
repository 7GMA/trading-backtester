"""Validation layer for parsed strategies."""

from __future__ import annotations

from src.strategy.models import ParsedStrategy, SUPPORTED_INDICATORS, Operator


def validate_strategy(strategy: ParsedStrategy) -> list[str]:
    """
    Validate a parsed strategy against supported indicators and rules.
    Returns list of error messages (empty = valid).
    """
    errors = []

    # Validate asset symbol
    if not strategy.asset or len(strategy.asset) > 10:
        errors.append(f"Invalid asset symbol: '{strategy.asset}'")

    # Validate entry conditions
    for cond in strategy.entry.conditions:
        errors.extend(_validate_condition(cond, "entry"))

    # Validate exit conditions
    for cond in strategy.exit.conditions:
        errors.extend(_validate_condition(cond, "exit"))

    # Validate exit percentages
    if strategy.exit.take_profit is not None:
        if not 0 < strategy.exit.take_profit < 1:
            errors.append(f"take_profit should be 0-1 (decimal), got {strategy.exit.take_profit}")
    if strategy.exit.stop_loss is not None:
        if not 0 < strategy.exit.stop_loss < 1:
            errors.append(f"stop_loss should be 0-1 (decimal), got {strategy.exit.stop_loss}")
    if strategy.exit.trailing_stop is not None:
        if not 0 < strategy.exit.trailing_stop < 1:
            errors.append(f"trailing_stop should be 0-1 (decimal), got {strategy.exit.trailing_stop}")

    # Must have at least some exit mechanism
    has_exit = (
        strategy.exit.take_profit is not None
        or strategy.exit.stop_loss is not None
        or strategy.exit.trailing_stop is not None
        or len(strategy.exit.conditions) > 0
    )
    if not has_exit:
        errors.append("Strategy must have at least one exit condition (take_profit, stop_loss, or indicator condition)")

    return errors


def _validate_condition(cond, context: str) -> list[str]:
    """Validate a single indicator condition."""
    errors = []
    indicator = cond.indicator.upper()

    if indicator not in SUPPORTED_INDICATORS:
        errors.append(
            f"[{context}] Unknown indicator: '{cond.indicator}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_INDICATORS.keys()))}"
        )
        return errors

    # Validate crossover operators have a string value (another indicator)
    if cond.operator in (Operator.CROSS_ABOVE, Operator.CROSS_BELOW):
        if cond.value is None:
            errors.append(f"[{context}] {indicator} crossover needs a comparison target (value)")

    # Validate numeric comparison has a numeric value
    if cond.operator in (Operator.LT, Operator.GT, Operator.LTE, Operator.GTE, Operator.EQ):
        if cond.value is None:
            errors.append(f"[{context}] {indicator} comparison needs a numeric value")

    return errors
