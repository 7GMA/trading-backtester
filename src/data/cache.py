"""DuckDB cache layer for market data."""

import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol   VARCHAR,
            date     DATE,
            open     DOUBLE,
            high     DOUBLE,
            low      DOUBLE,
            close    DOUBLE,
            volume   BIGINT,
            PRIMARY KEY (symbol, date)
        )
    """)
    return conn


def save_ohlcv(df: pd.DataFrame, symbol: str, conn: duckdb.DuckDBPyConnection | None = None) -> int:
    """Save OHLCV data to cache. Returns number of rows inserted."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    tmp = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    tmp.columns = ["open", "high", "low", "close", "volume"]
    tmp["symbol"] = symbol.upper()
    tmp["date"] = tmp.index

    # Upsert: delete existing rows for this symbol in date range, then insert
    min_date = tmp["date"].min()
    max_date = tmp["date"].max()
    conn.execute(
        "DELETE FROM ohlcv WHERE symbol = ? AND date BETWEEN ? AND ?",
        [symbol.upper(), min_date, max_date],
    )
    conn.execute("INSERT INTO ohlcv SELECT symbol, date, open, high, low, close, volume FROM tmp")
    rows = len(tmp)

    if close_after:
        conn.close()
    return rows


def load_ohlcv(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Load OHLCV data from cache. Returns DataFrame with DatetimeIndex."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    query = "SELECT date, open, high, low, close, volume FROM ohlcv WHERE symbol = ?"
    params: list = [symbol.upper()]

    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)

    query += " ORDER BY date"
    df = conn.execute(query, params).fetchdf()

    if close_after:
        conn.close()

    if df.empty:
        return df

    df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    return df


def get_cached_symbols(conn: duckdb.DuckDBPyConnection | None = None) -> list[str]:
    """Return list of all symbols in cache."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    result = conn.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol").fetchall()

    if close_after:
        conn.close()
    return [row[0] for row in result]


def get_date_range(symbol: str, conn: duckdb.DuckDBPyConnection | None = None) -> tuple | None:
    """Return (min_date, max_date) for a symbol, or None if not cached."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    result = conn.execute(
        "SELECT MIN(date), MAX(date) FROM ohlcv WHERE symbol = ?",
        [symbol.upper()],
    ).fetchone()

    if close_after:
        conn.close()

    if result and result[0] is not None:
        return result
    return None
