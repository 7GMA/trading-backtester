"""Tests for DuckDB cache save/load cycle."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest
import duckdb

from src.data.cache import save_ohlcv, load_ohlcv, get_cached_symbols, get_date_range


def _make_ohlcv_df(n: int = 50, start: str = "2023-01-01", seed: int = 42) -> pd.DataFrame:
    """Create a small synthetic OHLCV DataFrame for testing."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start=start, periods=n, freq="B")
    close = 100 + rng.normal(0, 2, size=n).cumsum()
    close = np.maximum(close, 10)  # keep prices positive
    high = close + rng.uniform(0.5, 2.0, size=n)
    low = close - rng.uniform(0.5, 2.0, size=n)
    open_ = low + (high - low) * rng.uniform(0.3, 0.7, size=n)
    volume = rng.randint(100_000, 5_000_000, size=n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    return df


@pytest.fixture
def conn():
    """Create an in-memory DuckDB connection with the ohlcv table."""
    c = duckdb.connect(":memory:")
    c.execute("""
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
    yield c
    c.close()


class TestSaveLoadCycle:
    """Test that data survives a save -> load round trip."""

    def test_save_returns_row_count(self, conn):
        df = _make_ohlcv_df(30)
        rows = save_ohlcv(df, "TEST", conn=conn)
        assert rows == 30

    def test_load_returns_same_shape(self, conn):
        df = _make_ohlcv_df(30)
        save_ohlcv(df, "TEST", conn=conn)
        loaded = load_ohlcv("TEST", conn=conn)
        assert loaded.shape[0] == 30
        assert list(loaded.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_load_preserves_close_values(self, conn):
        df = _make_ohlcv_df(20)
        save_ohlcv(df, "ROUND", conn=conn)
        loaded = load_ohlcv("ROUND", conn=conn)
        np.testing.assert_allclose(
            loaded["Close"].values, df["Close"].values, rtol=1e-10
        )

    def test_load_preserves_ohlv_values(self, conn):
        df = _make_ohlcv_df(20)
        save_ohlcv(df, "FULL", conn=conn)
        loaded = load_ohlcv("FULL", conn=conn)
        for col in ["Open", "High", "Low", "Volume"]:
            np.testing.assert_allclose(
                loaded[col].values, df[col].values, rtol=1e-10
            )

    def test_load_has_datetime_index(self, conn):
        df = _make_ohlcv_df(10)
        save_ohlcv(df, "IDX", conn=conn)
        loaded = load_ohlcv("IDX", conn=conn)
        assert loaded.index.name == "Date"
        assert pd.api.types.is_datetime64_any_dtype(loaded.index)


class TestSymbolIsolation:
    """Test that different symbols are stored and retrieved independently."""

    def test_two_symbols_independent(self, conn):
        df1 = _make_ohlcv_df(20, seed=1)
        df2 = _make_ohlcv_df(20, seed=2)
        save_ohlcv(df1, "AAA", conn=conn)
        save_ohlcv(df2, "BBB", conn=conn)

        loaded1 = load_ohlcv("AAA", conn=conn)
        loaded2 = load_ohlcv("BBB", conn=conn)

        assert loaded1.shape[0] == 20
        assert loaded2.shape[0] == 20
        assert not np.allclose(loaded1["Close"].values, loaded2["Close"].values)

    def test_symbol_case_insensitive(self, conn):
        df = _make_ohlcv_df(10)
        save_ohlcv(df, "aapl", conn=conn)
        loaded = load_ohlcv("AAPL", conn=conn)
        assert loaded.shape[0] == 10

    def test_load_nonexistent_symbol_returns_empty(self, conn):
        loaded = load_ohlcv("NONEXISTENT", conn=conn)
        assert loaded.empty


class TestDateFiltering:
    """Test loading with date range filters."""

    def test_load_with_start_date(self, conn):
        df = _make_ohlcv_df(50, start="2023-01-01")
        save_ohlcv(df, "FILT", conn=conn)
        loaded = load_ohlcv("FILT", start="2023-02-01", conn=conn)
        assert all(loaded.index >= pd.Timestamp("2023-02-01"))

    def test_load_with_end_date(self, conn):
        df = _make_ohlcv_df(50, start="2023-01-01")
        save_ohlcv(df, "FILT2", conn=conn)
        loaded = load_ohlcv("FILT2", end="2023-02-01", conn=conn)
        assert all(loaded.index <= pd.Timestamp("2023-02-01"))

    def test_load_with_start_and_end(self, conn):
        df = _make_ohlcv_df(100, start="2023-01-01")
        save_ohlcv(df, "RANGE", conn=conn)
        loaded = load_ohlcv("RANGE", start="2023-02-01", end="2023-03-01", conn=conn)
        assert all(loaded.index >= pd.Timestamp("2023-02-01"))
        assert all(loaded.index <= pd.Timestamp("2023-03-01"))
        assert loaded.shape[0] > 0


class TestUpsert:
    """Test that saving the same symbol again updates rather than duplicates."""

    def test_upsert_replaces_overlapping_data(self, conn):
        df1 = _make_ohlcv_df(30, start="2023-01-01", seed=1)
        save_ohlcv(df1, "UPS", conn=conn)

        df2 = _make_ohlcv_df(30, start="2023-01-01", seed=2)
        save_ohlcv(df2, "UPS", conn=conn)

        loaded = load_ohlcv("UPS", conn=conn)
        assert loaded.shape[0] == 30
        np.testing.assert_allclose(
            loaded["Close"].values, df2["Close"].values, rtol=1e-10
        )


class TestCachedSymbols:
    """Test get_cached_symbols utility."""

    def test_empty_db_has_no_symbols(self, conn):
        symbols = get_cached_symbols(conn=conn)
        assert symbols == []

    def test_saved_symbols_are_listed(self, conn):
        save_ohlcv(_make_ohlcv_df(10), "AAPL", conn=conn)
        save_ohlcv(_make_ohlcv_df(10), "MSFT", conn=conn)
        symbols = get_cached_symbols(conn=conn)
        assert "AAPL" in symbols
        assert "MSFT" in symbols


class TestDateRange:
    """Test get_date_range utility."""

    def test_date_range_for_existing_symbol(self, conn):
        df = _make_ohlcv_df(30, start="2023-06-01")
        save_ohlcv(df, "DRNG", conn=conn)
        result = get_date_range("DRNG", conn=conn)
        assert result is not None
        min_date, max_date = result
        assert min_date is not None
        assert max_date is not None

    def test_date_range_for_missing_symbol(self, conn):
        result = get_date_range("MISSING", conn=conn)
        assert result is None
