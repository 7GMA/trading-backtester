"""Technical indicators using pandas-ta."""

import pandas as pd
import pandas_ta as ta


def add_rsi(df: pd.DataFrame, length: int = 14, col: str = "Close") -> pd.DataFrame:
    """Add RSI column to DataFrame."""
    df[f"RSI_{length}"] = ta.rsi(df[col], length=length)
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "Close",
) -> pd.DataFrame:
    """Add MACD, MACD Signal, and MACD Histogram columns."""
    macd = ta.macd(df[col], fast=fast, slow=slow, signal=signal)
    df = pd.concat([df, macd], axis=1)
    return df


def add_sma(df: pd.DataFrame, length: int = 50, col: str = "Close") -> pd.DataFrame:
    """Add Simple Moving Average."""
    df[f"SMA_{length}"] = ta.sma(df[col], length=length)
    return df


def add_ema(df: pd.DataFrame, length: int = 20, col: str = "Close") -> pd.DataFrame:
    """Add Exponential Moving Average."""
    df[f"EMA_{length}"] = ta.ema(df[col], length=length)
    return df


def add_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0, col: str = "Close") -> pd.DataFrame:
    """Add Bollinger Bands (Lower, Mid, Upper)."""
    bb = ta.bbands(df[col], length=length, std=std)
    df = pd.concat([df, bb], axis=1)
    return df


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add Average True Range."""
    df[f"ATR_{length}"] = ta.atr(df["High"], df["Low"], df["Close"], length=length)
    return df


def add_default_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add a standard set of indicators: RSI(14), MACD, SMA(50), SMA(200), EMA(20)."""
    df = add_rsi(df)
    df = add_macd(df)
    df = add_sma(df, length=50)
    df = add_sma(df, length=200)
    df = add_ema(df, length=20)
    return df
