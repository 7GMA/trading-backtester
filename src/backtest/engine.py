"""Backtesting engine wrapper around backtesting.py."""

from __future__ import annotations

import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

from src.data.indicators import add_rsi, add_macd, add_sma, add_ema, add_bollinger, add_atr


class StrategyBase(Strategy):
    """Base strategy class with helper methods for indicator access."""

    # Override these in subclasses
    slippage = 0.001  # 0.1% slippage per trade
    trade_cost = 5.0  # $5 flat fee per trade

    def indicator(self, name: str):
        """Get a precomputed indicator by column name."""
        return self.data.df[name] if name in self.data.df.columns else None


class RSIOversold(StrategyBase):
    """Buy when RSI drops below oversold, sell when overbought."""

    rsi_length = 14
    oversold = 30
    overbought = 70
    stop_loss = 0.05
    take_profit = 0.10

    def init(self):
        close = pd.Series(self.data.Close, index=self.data.df.index)
        import pandas_ta as ta
        rsi = ta.rsi(close, length=self.rsi_length)
        self.rsi = self.I(lambda: rsi, name=f"RSI_{self.rsi_length}")

    def next(self):
        if not self.position:
            if self.rsi[-1] < self.oversold:
                self.buy(sl=self.data.Close[-1] * (1 - self.stop_loss),
                         tp=self.data.Close[-1] * (1 + self.take_profit))
        elif self.rsi[-1] > self.overbought:
            self.position.close()


class MACDCrossover(StrategyBase):
    """Buy on bullish MACD crossover, sell on bearish."""

    fast = 12
    slow = 26
    signal = 9
    stop_loss = 0.05
    take_profit = 0.10

    def init(self):
        close = pd.Series(self.data.Close, index=self.data.df.index)
        import pandas_ta as ta
        macd_df = ta.macd(close, fast=self.fast, slow=self.slow, signal=self.signal)
        self.macd = self.I(lambda: macd_df.iloc[:, 0], name="MACD")
        self.macd_signal = self.I(lambda: macd_df.iloc[:, 2], name="MACD_Signal")

    def next(self):
        if not self.position:
            if crossover(self.macd, self.macd_signal):
                self.buy(sl=self.data.Close[-1] * (1 - self.stop_loss),
                         tp=self.data.Close[-1] * (1 + self.take_profit))
        elif crossover(self.macd_signal, self.macd):
            self.position.close()


class SMACrossover(StrategyBase):
    """Golden Cross / Death Cross strategy."""

    fast_period = 50
    slow_period = 200
    stop_loss = 0.07

    def init(self):
        close = pd.Series(self.data.Close, index=self.data.df.index)
        import pandas_ta as ta
        self.sma_fast = self.I(lambda: ta.sma(close, length=self.fast_period), name=f"SMA_{self.fast_period}")
        self.sma_slow = self.I(lambda: ta.sma(close, length=self.slow_period), name=f"SMA_{self.slow_period}")

    def next(self):
        if not self.position:
            if crossover(self.sma_fast, self.sma_slow):
                self.buy(sl=self.data.Close[-1] * (1 - self.stop_loss))
        elif crossover(self.sma_slow, self.sma_fast):
            self.position.close()


# Registry of built-in strategies
STRATEGIES = {
    "rsi_oversold": RSIOversold,
    "macd_crossover": MACDCrossover,
    "sma_crossover": SMACrossover,
}


def run_backtest(
    df: pd.DataFrame,
    strategy: type[Strategy] | str = "rsi_oversold",
    cash: float = 10_000,
    commission: float = 0.001,
    exclusive_orders: bool = True,
    **strategy_params,
) -> dict:
    """
    Run a backtest and return results.

    Args:
        df: OHLCV DataFrame
        strategy: Strategy class or name from STRATEGIES registry
        cash: Starting capital
        commission: Commission per trade (0.001 = 0.1%)
        exclusive_orders: If True, new orders cancel previous ones
        **strategy_params: Override strategy parameters

    Returns:
        Dict with 'stats' (Series), 'trades' (DataFrame), 'equity_curve' (DataFrame)
    """
    if isinstance(strategy, str):
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}")
        strategy = STRATEGIES[strategy]

    bt = Backtest(
        df,
        strategy,
        cash=cash,
        commission=commission,
        exclusive_orders=exclusive_orders,
    )

    stats = bt.run(**strategy_params)

    return {
        "stats": stats,
        "trades": stats._trades if hasattr(stats, "_trades") else pd.DataFrame(),
        "equity_curve": stats._equity_curve if hasattr(stats, "_equity_curve") else pd.DataFrame(),
        "bt": bt,
    }


def optimize_strategy(
    df: pd.DataFrame,
    strategy: type[Strategy] | str = "rsi_oversold",
    cash: float = 10_000,
    commission: float = 0.001,
    maximize: str = "Sharpe Ratio",
    **param_ranges,
) -> dict:
    """
    Optimize strategy parameters.

    Args:
        df: OHLCV DataFrame
        strategy: Strategy class or name
        maximize: Metric to optimize ("Sharpe Ratio", "Return [%]", etc.)
        **param_ranges: Parameter ranges as lists or range objects

    Returns:
        Dict with 'stats', 'best_params'
    """
    if isinstance(strategy, str):
        strategy = STRATEGIES[strategy]

    bt = Backtest(df, strategy, cash=cash, commission=commission, exclusive_orders=True)
    stats = bt.optimize(maximize=maximize, **param_ranges)

    best_params = {k: getattr(stats._strategy, k) for k in param_ranges}

    return {
        "stats": stats,
        "best_params": best_params,
        "bt": bt,
    }
