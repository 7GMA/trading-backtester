"""Convert ParsedStrategy → executable backtesting.py Strategy class."""

from __future__ import annotations

import json
import pandas as pd
import numpy as np
from backtesting import Strategy
from backtesting.lib import crossover

from src.strategy.models import ParsedStrategy, Operator, LogicOperator


def _ind_attr_name(name: str) -> str:
    """Convert indicator name to a valid attribute name."""
    return f"_dyn_{name.replace('-', '_').replace('.', '_')}"


def build_strategy(parsed: ParsedStrategy) -> type[Strategy]:
    """
    Dynamically build a backtesting.py Strategy class from a ParsedStrategy.
    Indicators are stored as direct attributes (required by backtesting.py).
    """
    entry_rule = parsed.entry
    exit_rule = parsed.exit

    # Pre-compute which indicators we need
    all_conditions = list(entry_rule.conditions) + list(exit_rule.conditions)
    indicator_keys: list[str] = []

    for cond in all_conditions:
        ind = cond.indicator.upper()
        if ind == "RSI":
            indicator_keys.append(f"RSI_{cond.params.get('period', 14)}")
        elif ind == "MACD":
            f, s, sg = cond.params.get("fast", 12), cond.params.get("slow", 26), cond.params.get("signal", 9)
            indicator_keys.append(f"MACD_{f}_{s}_{sg}")
            indicator_keys.append(f"MACDs_{f}_{s}_{sg}")
        elif ind == "SMA":
            period = cond.params.get("period", 50)
            indicator_keys.append(f"SMA_{period}")
            if isinstance(cond.value, str) and cond.value.upper().startswith("SMA_"):
                indicator_keys.append(cond.value.upper())
        elif ind == "EMA":
            indicator_keys.append(f"EMA_{cond.params.get('period', 20)}")
        elif ind == "BB":
            period = cond.params.get("period", 20)
            indicator_keys.extend([f"BBL_{period}", f"BBM_{period}", f"BBU_{period}"])
        elif ind == "ATR":
            indicator_keys.append(f"ATR_{cond.params.get('period', 14)}")

    indicator_keys = list(dict.fromkeys(indicator_keys))  # deduplicate, keep order

    class DynamicStrategy(Strategy):
        _stop_loss = exit_rule.stop_loss
        _take_profit = exit_rule.take_profit
        _entry_rule = entry_rule
        _exit_rule = exit_rule
        _indicator_keys = indicator_keys

        def init(self):
            import pandas_ta as ta
            close = pd.Series(self.data.Close, index=self.data.df.index)
            high = pd.Series(self.data.High, index=self.data.df.index)
            low = pd.Series(self.data.Low, index=self.data.df.index)

            computed = set()
            for cond in list(self._entry_rule.conditions) + list(self._exit_rule.conditions):
                ind = cond.indicator.upper()

                if ind == "RSI":
                    period = cond.params.get("period", 14)
                    key = f"RSI_{period}"
                    if key not in computed:
                        data = ta.rsi(close, length=period)
                        setattr(self, _ind_attr_name(key), self.I(lambda d=data: d, name=key))
                        computed.add(key)

                elif ind == "MACD":
                    f = cond.params.get("fast", 12)
                    s = cond.params.get("slow", 26)
                    sg = cond.params.get("signal", 9)
                    macd_key = f"MACD_{f}_{s}_{sg}"
                    sig_key = f"MACDs_{f}_{s}_{sg}"
                    if macd_key not in computed:
                        macd_df = ta.macd(close, fast=f, slow=s, signal=sg)
                        setattr(self, _ind_attr_name(macd_key), self.I(lambda d=macd_df.iloc[:, 0]: d, name=macd_key))
                        setattr(self, _ind_attr_name(sig_key), self.I(lambda d=macd_df.iloc[:, 2]: d, name=sig_key))
                        computed.add(macd_key)
                        computed.add(sig_key)

                elif ind == "SMA":
                    period = cond.params.get("period", 50)
                    key = f"SMA_{period}"
                    if key not in computed:
                        data = ta.sma(close, length=period)
                        setattr(self, _ind_attr_name(key), self.I(lambda d=data: d, name=key))
                        computed.add(key)
                    # Also compute the comparison target SMA
                    if isinstance(cond.value, str) and cond.value.upper().startswith("SMA_"):
                        other_key = cond.value.upper()
                        if other_key not in computed:
                            other_period = int(other_key.split("_")[1])
                            other_data = ta.sma(close, length=other_period)
                            setattr(self, _ind_attr_name(other_key), self.I(lambda d=other_data: d, name=other_key))
                            computed.add(other_key)

                elif ind == "EMA":
                    period = cond.params.get("period", 20)
                    key = f"EMA_{period}"
                    if key not in computed:
                        data = ta.ema(close, length=period)
                        setattr(self, _ind_attr_name(key), self.I(lambda d=data: d, name=key))
                        computed.add(key)

                elif ind == "BB":
                    period = cond.params.get("period", 20)
                    std = cond.params.get("std", 2.0)
                    bbl_key = f"BBL_{period}"
                    if bbl_key not in computed:
                        bb = ta.bbands(close, length=period, std=std)
                        setattr(self, _ind_attr_name(f"BBL_{period}"), self.I(lambda d=bb.iloc[:, 0]: d, name=f"BBL_{period}"))
                        setattr(self, _ind_attr_name(f"BBM_{period}"), self.I(lambda d=bb.iloc[:, 1]: d, name=f"BBM_{period}"))
                        setattr(self, _ind_attr_name(f"BBU_{period}"), self.I(lambda d=bb.iloc[:, 2]: d, name=f"BBU_{period}"))
                        computed.update([f"BBL_{period}", f"BBM_{period}", f"BBU_{period}"])

                elif ind == "ATR":
                    period = cond.params.get("period", 14)
                    key = f"ATR_{period}"
                    if key not in computed:
                        data = ta.atr(high, low, close, length=period)
                        setattr(self, _ind_attr_name(key), self.I(lambda d=data: d, name=key))
                        computed.add(key)

        def _get_ind(self, key: str):
            """Get indicator by key name."""
            return getattr(self, _ind_attr_name(key), None)

        def next(self):
            if not self.position:
                if _check_conditions(self._entry_rule.conditions, self._entry_rule.logic, self):
                    kwargs = {}
                    price = self.data.Close[-1]
                    if self._stop_loss:
                        kwargs["sl"] = price * (1 - self._stop_loss)
                    if self._take_profit:
                        kwargs["tp"] = price * (1 + self._take_profit)
                    self.buy(**kwargs)
            else:
                if self._exit_rule.conditions:
                    if _check_conditions(self._exit_rule.conditions, self._exit_rule.logic, self):
                        self.position.close()

    DynamicStrategy.__name__ = parsed.name.replace(" ", "_").replace("(", "").replace(")", "")
    DynamicStrategy.__qualname__ = DynamicStrategy.__name__
    return DynamicStrategy


def _resolve_indicator(strategy, cond, as_value: bool = False):
    """Resolve an indicator reference to its data array."""
    ind = cond.indicator.upper()

    if as_value and isinstance(cond.value, str):
        val_str = cond.value.upper()
        result = strategy._get_ind(val_str)
        if result is not None:
            return result
        # Try MACD signal match
        if "SIGNAL" in val_str:
            for key in strategy._indicator_keys:
                if key.startswith("MACDs"):
                    return strategy._get_ind(key)
        return None

    if ind == "RSI":
        return strategy._get_ind(f"RSI_{cond.params.get('period', 14)}")
    elif ind == "MACD":
        f, s, sg = cond.params.get("fast", 12), cond.params.get("slow", 26), cond.params.get("signal", 9)
        return strategy._get_ind(f"MACD_{f}_{s}_{sg}")
    elif ind == "SMA":
        return strategy._get_ind(f"SMA_{cond.params.get('period', 50)}")
    elif ind == "EMA":
        return strategy._get_ind(f"EMA_{cond.params.get('period', 20)}")
    elif ind == "ATR":
        return strategy._get_ind(f"ATR_{cond.params.get('period', 14)}")

    return None


def _eval_condition(cond, strategy) -> bool:
    """Evaluate a single indicator condition."""
    ind_data = _resolve_indicator(strategy, cond)
    if ind_data is None:
        return False

    op = cond.operator

    if op in (Operator.CROSS_ABOVE, Operator.CROSS_BELOW):
        target = _resolve_indicator(strategy, cond, as_value=True)
        if target is None:
            return False
        if op == Operator.CROSS_ABOVE:
            return crossover(ind_data, target)
        else:
            return crossover(target, ind_data)

    # Numeric comparisons
    val = float(cond.value) if cond.value is not None else 0
    current = ind_data[-1]

    if np.isnan(current):
        return False

    if op == Operator.LT:
        return current < val
    elif op == Operator.GT:
        return current > val
    elif op == Operator.LTE:
        return current <= val
    elif op == Operator.GTE:
        return current >= val
    elif op == Operator.EQ:
        return abs(current - val) < 1e-9

    return False


def _check_conditions(conditions, logic, strategy) -> bool:
    """Check all conditions with AND/OR logic."""
    results = [_eval_condition(c, strategy) for c in conditions]
    if logic == LogicOperator.AND:
        return all(results)
    return any(results)
