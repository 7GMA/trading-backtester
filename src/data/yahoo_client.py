"""Yahoo Finance data fetcher with DuckDB caching."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from src.data.cache import get_connection, save_ohlcv, load_ohlcv, get_date_range


def fetch(
    symbol: str,
    start: str = "2020-01-01",
    end: str | None = None,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a symbol. Uses DuckDB cache for daily data.

    Args:
        symbol: Ticker symbol (e.g. "AAPL", "BTC-USD")
        start: Start date string "YYYY-MM-DD"
        end: End date string (default: today)
        interval: "1d" or "1h" (only "1d" is cached)
        use_cache: Whether to use DuckDB cache (only for daily)

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    symbol = symbol.upper()
    cacheable = interval == "1d" and use_cache

    # Try cache first for daily data
    if cacheable:
        conn = get_connection()
        date_range = get_date_range(symbol, conn)

        if date_range:
            cached_start, cached_end = date_range
            start_dt = datetime.strptime(start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end, "%Y-%m-%d").date()
            # Allow buffer for weekends/holidays
            start_close_enough = (cached_start - start_dt).days <= 5
            end_close_enough = (end_dt - cached_end).days <= 3
            if start_close_enough and end_close_enough:
                df = load_ohlcv(symbol, start, end, conn)
                conn.close()
                if not df.empty:
                    print(f"[cache] {symbol}: {len(df)} rows from cache")
                    return df

        conn.close()

    # Fetch from Yahoo Finance
    print(f"[yahoo] Fetching {symbol} from {start} to {end} ({interval})...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

    if df.empty:
        print(f"[yahoo] No data returned for {symbol}")
        return df

    # Clean up: drop extra columns Yahoo sometimes adds
    keep_cols = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in keep_cols if c in df.columns]]

    # Remove timezone info from index for consistency
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    print(f"[yahoo] {symbol}: {len(df)} rows fetched")

    # Cache daily data
    if cacheable:
        conn = get_connection()
        save_ohlcv(df, symbol, conn)
        conn.close()
        print(f"[cache] {symbol}: cached")

    return df


def fetch_multiple(
    symbols: list[str],
    start: str = "2020-01-01",
    end: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch data for multiple symbols. Returns dict of symbol -> DataFrame."""
    result = {}
    for sym in symbols:
        df = fetch(sym, start=start, end=end)
        if not df.empty:
            result[sym] = df
    return result
