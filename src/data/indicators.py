"""Technical indicators using pure pandas (no external dependency)."""

import pandas as pd
import numpy as np


def add_rsi(df: pd.DataFrame, length: int = 14, col: str = "Close") -> pd.DataFrame:
    """Add RSI column to DataFrame."""
    delta = df[col].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
    rs = avg_gain / avg_loss
    df[f"RSI_{length}"] = 100 - (100 / (1 + rs))
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "Close",
) -> pd.DataFrame:
    """Add MACD, MACD Signal, and MACD Histogram columns."""
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    df[f"MACD_{fast}_{slow}_{signal}"] = macd
    df[f"MACDs_{fast}_{slow}_{signal}"] = macd_signal
    df[f"MACDh_{fast}_{slow}_{signal}"] = macd_hist
    return df


def add_sma(df: pd.DataFrame, length: int = 50, col: str = "Close") -> pd.DataFrame:
    """Add Simple Moving Average."""
    df[f"SMA_{length}"] = df[col].rolling(window=length).mean()
    return df


def add_ema(df: pd.DataFrame, length: int = 20, col: str = "Close") -> pd.DataFrame:
    """Add Exponential Moving Average."""
    df[f"EMA_{length}"] = df[col].ewm(span=length, adjust=False).mean()
    return df


def add_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0, col: str = "Close") -> pd.DataFrame:
    """Add Bollinger Bands (Lower, Mid, Upper)."""
    sma = df[col].rolling(window=length).mean()
    rolling_std = df[col].rolling(window=length).std()
    df[f"BBL_{length}_{std}"] = sma - std * rolling_std
    df[f"BBM_{length}_{std}"] = sma
    df[f"BBU_{length}_{std}"] = sma + std * rolling_std
    return df


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add Average True Range."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    df[f"ATR_{length}"] = tr.rolling(window=length).mean()
    return df


def add_default_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add a standard set of indicators: RSI(14), MACD, SMA(50), SMA(200), EMA(20)."""
    df = add_rsi(df)
    df = add_macd(df)
    df = add_sma(df, length=50)
    df = add_sma(df, length=200)
    df = add_ema(df, length=20)
    return df
