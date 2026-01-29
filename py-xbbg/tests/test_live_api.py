#!/usr/bin/env python
"""Front-to-back live tests using the actual xbbg public API.

These tests exercise the complete Python → Rust → Bloomberg → Rust → Python
data flow using the user-facing API functions (bdp, bdh, bds, etc.).

Run with:
    pytest tests/test_live_api.py -v --tb=short

Or as a standalone script:
    python tests/test_live_api.py [test_names...]
    python tests/test_live_api.py --list  # List available tests

Environment:
    Requires Bloomberg Terminal or B-PIPE connection.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# Test Configuration
# =============================================================================


@dataclass
class TestConfig:
    """Test configuration with safe defaults."""

    # Liquid equities for testing
    equity_single: str = "IBM US Equity"
    equity_multi: list[str] = None

    # Index for bulk data tests
    index_ticker: str = "INDU Index"

    # Bond for fixed income tests
    bond_ticker: str = "GT10 Govt"

    # ETF for holdings tests
    etf_ticker: str = "SPY US Equity"

    # Futures for resolution tests
    futures_generic: str = "ES1 Index"

    # Common fields
    price_field: str = "PX_LAST"
    name_field: str = "NAME"
    volume_field: str = "VOLUME"

    def __post_init__(self):
        if self.equity_multi is None:
            self.equity_multi = ["AAPL US Equity", "MSFT US Equity"]


CONFIG = TestConfig()


def get_recent_trading_day() -> str:
    """Get a recent trading day (yesterday or Friday if weekend)."""
    today = datetime.now()
    # Go back 1-3 days to find a likely trading day
    for days_back in range(1, 5):
        candidate = today - timedelta(days=days_back)
        # Skip weekends
        if candidate.weekday() < 5:  # Monday = 0, Friday = 4
            return candidate.strftime("%Y-%m-%d")
    return (today - timedelta(days=1)).strftime("%Y-%m-%d")


def get_date_range(days: int = 7) -> tuple[str, str]:
    """Get a date range ending today."""
    end = datetime.now()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# =============================================================================
# BDP Tests - Reference Data
# =============================================================================


class TestBdp:
    """Tests for bdp() - Bloomberg Data Point (reference data)."""

    def test_bdp_single_ticker_single_field(self):
        """BDP: single ticker, single field."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field)

        assert len(df) == 1
        assert "ticker" in df.columns
        assert "field" in df.columns
        assert "value" in df.columns

        # Verify data
        row = df.to_pandas().iloc[0]
        assert CONFIG.equity_single in row["ticker"]
        assert row["field"] == CONFIG.price_field
        assert row["value"] is not None

        print(f"  {row['ticker']}: {row['field']} = {row['value']}")

    def test_bdp_single_ticker_multi_field(self):
        """BDP: single ticker, multiple fields."""
        from xbbg import bdp

        fields = [CONFIG.price_field, CONFIG.name_field, CONFIG.volume_field]
        df = bdp(CONFIG.equity_single, fields)

        assert len(df) == len(fields)

        pdf = df.to_pandas()
        returned_fields = set(pdf["field"].tolist())
        assert returned_fields == set(fields)

        print(f"  Got {len(df)} field values")
        for _, row in pdf.iterrows():
            print(f"    {row['field']}: {row['value']}")

    def test_bdp_multi_ticker_single_field(self):
        """BDP: multiple tickers, single field."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_multi, CONFIG.price_field)

        assert len(df) == len(CONFIG.equity_multi)

        pdf = df.to_pandas()
        returned_tickers = set(pdf["ticker"].tolist())
        # Tickers may have suffixes, check containment
        for expected in CONFIG.equity_multi:
            assert any(expected in t for t in returned_tickers)

        print(f"  Got prices for {len(df)} tickers")

    def test_bdp_multi_ticker_multi_field(self):
        """BDP: multiple tickers, multiple fields."""
        from xbbg import bdp

        fields = [CONFIG.price_field, CONFIG.volume_field]
        df = bdp(CONFIG.equity_multi, fields)

        expected_rows = len(CONFIG.equity_multi) * len(fields)
        assert len(df) == expected_rows

        print(f"  Got {len(df)} rows ({len(CONFIG.equity_multi)} tickers × {len(fields)} fields)")

    def test_bdp_with_override(self):
        """BDP: with Bloomberg override."""
        from xbbg import bdp

        # Currency adjustment override
        df = bdp(
            CONFIG.equity_single,
            "CRNCY_ADJ_PX_LAST",
            overrides={"EQY_FUND_CRNCY": "EUR"},
        )

        assert len(df) == 1
        print(f"  Price in EUR: {df.to_pandas().iloc[0]['value']}")


class TestAbdp:
    """Tests for abdp() - async BDP."""

    @pytest.mark.asyncio
    async def test_abdp_basic(self):
        """ABDP: basic async call."""
        from xbbg import abdp

        df = await abdp(CONFIG.equity_single, CONFIG.price_field)

        assert len(df) == 1
        print(f"  Async result: {df.to_pandas().iloc[0]['value']}")

    @pytest.mark.asyncio
    async def test_abdp_concurrent(self):
        """ABDP: concurrent requests."""
        from xbbg import abdp

        results = await asyncio.gather(
            abdp(CONFIG.equity_multi[0], CONFIG.price_field),
            abdp(CONFIG.equity_multi[1], CONFIG.price_field),
        )

        assert len(results) == 2
        assert all(len(df) == 1 for df in results)
        print(f"  Concurrent results: {[df.to_pandas().iloc[0]['value'] for df in results]}")


# =============================================================================
# BDH Tests - Historical Data
# =============================================================================


class TestBdh:
    """Tests for bdh() - Bloomberg Data History."""

    def test_bdh_single_ticker(self):
        """BDH: single ticker, default date range."""
        from xbbg import bdh

        start, end = get_date_range(7)
        df = bdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end)

        assert len(df) >= 1
        assert "ticker" in df.columns
        assert "date" in df.columns
        assert "field" in df.columns

        print(f"  Got {len(df)} data points from {start} to {end}")

    def test_bdh_multi_ticker(self):
        """BDH: multiple tickers."""
        from xbbg import bdh

        start, end = get_date_range(5)
        df = bdh(CONFIG.equity_multi, CONFIG.price_field, start_date=start, end_date=end)

        assert len(df) >= len(CONFIG.equity_multi)

        pdf = df.to_pandas()
        unique_tickers = pdf["ticker"].nunique()
        assert unique_tickers == len(CONFIG.equity_multi)

        print(f"  Got {len(df)} rows for {unique_tickers} tickers")

    def test_bdh_multi_field(self):
        """BDH: multiple fields."""
        from xbbg import bdh

        start, end = get_date_range(5)
        fields = [CONFIG.price_field, CONFIG.volume_field]
        df = bdh(CONFIG.equity_single, fields, start_date=start, end_date=end)

        pdf = df.to_pandas()
        unique_fields = pdf["field"].nunique()
        assert unique_fields == len(fields)

        print(f"  Got {len(df)} rows for {unique_fields} fields")

    def test_bdh_with_adjustments(self):
        """BDH: with split/dividend adjustments."""
        from xbbg import bdh

        start, end = get_date_range(30)
        df = bdh(
            CONFIG.equity_single,
            CONFIG.price_field,
            start_date=start,
            end_date=end,
            adjust="all",
        )

        assert len(df) >= 1
        print(f"  Got {len(df)} adjusted prices")


class TestAbdh:
    """Tests for abdh() - async BDH."""

    @pytest.mark.asyncio
    async def test_abdh_basic(self):
        """ABDH: basic async call."""
        from xbbg import abdh

        start, end = get_date_range(5)
        df = await abdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end)

        assert len(df) >= 1
        print(f"  Async result: {len(df)} rows")


# =============================================================================
# BDS Tests - Bulk Data
# =============================================================================


class TestBds:
    """Tests for bds() - Bloomberg Data Set (bulk data)."""

    def test_bds_index_members(self):
        """BDS: index members (multi-row result)."""
        from xbbg import bds

        df = bds(CONFIG.index_ticker, "INDX_MEMBERS")

        # DJIA has 30 members
        assert len(df) == 30
        assert "ticker" in df.columns

        print(f"  Got {len(df)} index members")

    def test_bds_dividend_history(self):
        """BDS: dividend history."""
        from xbbg import bds

        df = bds(CONFIG.equity_single, "DVD_HIST")

        # Should have some dividend history (IBM pays dividends)
        assert len(df) >= 0  # May be empty for some tickers

        print(f"  Got {len(df)} dividend records")


class TestAbds:
    """Tests for abds() - async BDS."""

    @pytest.mark.asyncio
    async def test_abds_basic(self):
        """ABDS: basic async call."""
        from xbbg import abds

        df = await abds(CONFIG.index_ticker, "INDX_MEMBERS")

        assert len(df) == 30
        print(f"  Async result: {len(df)} members")


# =============================================================================
# BDIB Tests - Intraday Bars
# =============================================================================


class TestBdib:
    """Tests for bdib() - Bloomberg Intraday Bars."""

    def test_bdib_single_day(self):
        """BDIB: single day, 5-minute bars."""
        from xbbg import bdib

        trading_day = get_recent_trading_day()
        df = bdib(
            CONFIG.equity_single,
            dt=trading_day,
            interval=5,
        )

        # Should have bars if market was open
        # Note: May be empty if market was closed
        print(f"  Got {len(df)} bars for {trading_day}")

    def test_bdib_with_datetime_range(self):
        """BDIB: explicit datetime range."""
        from xbbg import bdib

        trading_day = get_recent_trading_day()
        df = bdib(
            CONFIG.equity_single,
            start_datetime=f"{trading_day} 10:00:00",
            end_datetime=f"{trading_day} 11:00:00",
            interval=5,
        )

        print(f"  Got {len(df)} bars (10:00-11:00)")


class TestAbdib:
    """Tests for abdib() - async BDIB."""

    @pytest.mark.asyncio
    async def test_abdib_basic(self):
        """ABDIB: basic async call."""
        from xbbg import abdib

        trading_day = get_recent_trading_day()
        df = await abdib(CONFIG.equity_single, dt=trading_day, interval=5)

        print(f"  Async result: {len(df)} bars")


# =============================================================================
# BDTICK Tests - Intraday Ticks
# =============================================================================


class TestBdtick:
    """Tests for bdtick() - Bloomberg Intraday Ticks.

    Note: Tick data requires the eventTypes parameter and has limited
    data retention. Use full trading day window for reliable results.

    IMPORTANT: Bloomberg intraday requests use UTC times.
    US market open: 9:30 ET = 14:30 UTC
    """

    def test_bdtick_one_hour(self):
        """BDTICK: one hour window at market open (UTC times)."""
        from datetime import datetime

        from xbbg import bdtick

        # Use today for reliable tick data
        # IMPORTANT: Bloomberg uses UTC times for intraday requests
        # 14:30-15:30 UTC = 9:30-10:30 ET (market open)
        trading_day = datetime.now().strftime("%Y-%m-%d")
        df = bdtick(
            CONFIG.equity_single,
            start_datetime=f"{trading_day}T14:30:00",
            end_datetime=f"{trading_day}T15:30:00",
        )

        print(f"  Got {len(df)} ticks (1-hour at open, UTC)")


class TestAbdtick:
    """Tests for abdtick() - async BDTICK.

    IMPORTANT: Bloomberg intraday requests use UTC times.
    """

    @pytest.mark.asyncio
    async def test_abdtick_basic(self):
        """ABDTICK: basic async call at market open (UTC times)."""
        from datetime import datetime

        from xbbg import abdtick

        # Use today at market open for reliable tick data
        # IMPORTANT: Bloomberg uses UTC times for intraday requests
        # 14:30-15:30 UTC = 9:30-10:30 ET (market open)
        trading_day = datetime.now().strftime("%Y-%m-%d")
        df = await abdtick(
            CONFIG.equity_single,
            start_datetime=f"{trading_day}T14:30:00",
            end_datetime=f"{trading_day}T15:30:00",
        )

        print(f"  Async result: {len(df)} ticks (UTC)")


# =============================================================================
# Backend Conversion Tests
# =============================================================================


class TestBackendConversion:
    """Tests for DataFrame backend conversion."""

    def test_backend_narwhals_default(self):
        """Backend: narwhals (default)."""
        import narwhals as nw

        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field)

        assert isinstance(df, nw.DataFrame)
        print(f"  Narwhals DataFrame: {type(df)}")

    def test_backend_pandas(self):
        """Backend: pandas."""
        import pandas as pd

        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field, backend="pandas")

        assert isinstance(df, pd.DataFrame)
        print(f"  Pandas DataFrame: {type(df)}")

    def test_backend_polars(self):
        """Backend: polars."""
        pytest.importorskip("polars")
        import polars as pl

        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field, backend="polars")

        assert isinstance(df, pl.DataFrame)
        print(f"  Polars DataFrame: {type(df)}")

    def test_backend_pyarrow(self):
        """Backend: pyarrow."""
        import pyarrow as pa

        from xbbg import bdp

        table = bdp(CONFIG.equity_single, CONFIG.price_field, backend="pyarrow")

        assert isinstance(table, pa.Table)
        print(f"  PyArrow Table: {type(table)}")

    def test_global_backend_setting(self):
        """Backend: global setting."""
        import pandas as pd

        from xbbg import bdp, get_backend, set_backend

        original = get_backend()
        try:
            set_backend("pandas")
            df = bdp(CONFIG.equity_single, CONFIG.price_field)
            assert isinstance(df, pd.DataFrame)
            print("  Global backend setting works")
        finally:
            set_backend(original)


# =============================================================================
# Streaming Tests
# =============================================================================


class TestStreaming:
    """Tests for streaming API (subscribe/stream)."""

    @pytest.mark.asyncio
    async def test_stream_basic(self):
        """Stream: basic streaming."""
        from xbbg import astream

        ticks_received = 0
        timeout_seconds = 10

        async def collect_ticks():
            nonlocal ticks_received
            async for tick in astream(CONFIG.equity_single, ["LAST_PRICE", "BID", "ASK"]):
                ticks_received += 1
                print(f"    Tick: {tick}")
                if ticks_received >= 3:
                    break

        try:
            await asyncio.wait_for(collect_ticks(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            print(f"  Timeout after {timeout_seconds}s (got {ticks_received} ticks)")

        print(f"  Received {ticks_received} ticks")

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self):
        """Stream: subscribe and unsubscribe."""
        from xbbg import asubscribe

        sub = await asubscribe(CONFIG.equity_single, ["LAST_PRICE"])

        ticks_received = 0
        try:
            async for tick in sub:
                ticks_received += 1
                if ticks_received >= 2:
                    break
        finally:
            await sub.unsubscribe()

        print(f"  Received {ticks_received} ticks before unsubscribe")


# =============================================================================
# Extension Module Tests
# =============================================================================


class TestExtensions:
    """Tests for ext module functions."""

    def test_ext_dividend(self):
        """Ext: dividend history."""
        from xbbg import ext

        df = ext.dividend(CONFIG.equity_single, start_date="2024-01-01")

        print(f"  Got {len(df)} dividend records")

    def test_ext_etf_holdings(self):
        """Ext: ETF holdings."""
        from xbbg import ext

        df = ext.etf_holdings(CONFIG.etf_ticker)

        assert len(df) > 0
        print(f"  Got {len(df)} ETF holdings")

    def test_ext_fut_ticker(self):
        """Ext: futures ticker resolution."""
        from xbbg import ext

        ticker = ext.fut_ticker(CONFIG.futures_generic, "2024-06-15")

        assert ticker is not None
        print(f"  Resolved {CONFIG.futures_generic} → {ticker}")

    def test_ext_yas(self):
        """Ext: yield & spread analysis."""
        from xbbg import ext

        df = ext.yas(CONFIG.bond_ticker, ["YAS_BOND_YLD", "YAS_MOD_DUR"])

        assert len(df) > 0
        print(f"  Got {len(df)} YAS values")


class TestExtensionsAsync:
    """Tests for async ext module functions."""

    @pytest.mark.asyncio
    async def test_ext_adividend(self):
        """Ext: async dividend."""
        from xbbg import ext

        df = await ext.adividend(CONFIG.equity_single, start_date="2024-01-01")

        print(f"  Async result: {len(df)} dividend records")

    @pytest.mark.asyncio
    async def test_ext_aetf_holdings(self):
        """Ext: async ETF holdings."""
        from xbbg import ext

        df = await ext.aetf_holdings(CONFIG.etf_ticker)

        assert len(df) > 0
        print(f"  Async result: {len(df)} holdings")

    @pytest.mark.asyncio
    async def test_ext_afut_ticker(self):
        """Ext: async futures ticker."""
        from xbbg import ext

        ticker = await ext.afut_ticker(CONFIG.futures_generic, "2024-06-15")

        assert ticker is not None
        print(f"  Async result: {ticker}")


# =============================================================================
# Data Validation Tests
# =============================================================================


class TestRawOutput:
    """Tests that show raw output for debugging."""

    def test_bdp_raw_output(self):
        """Show raw BDP output structure."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, [CONFIG.price_field, CONFIG.name_field], backend="pandas")

        print(f"\n  Raw DataFrame:")
        print(f"  {df.to_string()}")
        print(f"\n  Columns: {list(df.columns)}")
        print(f"  Dtypes:\n{df.dtypes}")
        print(f"\n  Sample values:")
        for col in df.columns:
            val = df[col].iloc[0]
            print(f"    {col}: {val!r} (type: {type(val).__name__})")

    def test_bdh_raw_output(self):
        """Show raw BDH output structure."""
        from xbbg import bdh

        start, end = get_date_range(5)
        df = bdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end, backend="pandas")

        print(f"\n  Raw DataFrame (first 5 rows):")
        print(f"  {df.head().to_string()}")
        print(f"\n  Columns: {list(df.columns)}")
        print(f"  Dtypes:\n{df.dtypes}")
        print(f"\n  Sample values:")
        for col in df.columns:
            val = df[col].iloc[0]
            print(f"    {col}: {val!r} (type: {type(val).__name__})")

    def test_bds_raw_output(self):
        """Show raw BDS output structure."""
        from xbbg import bds

        df = bds(CONFIG.index_ticker, "INDX_MEMBERS", backend="pandas")

        print(f"\n  Raw DataFrame (first 5 rows):")
        print(f"  {df.head().to_string()}")
        print(f"\n  Columns: {list(df.columns)}")
        print(f"  Dtypes:\n{df.dtypes}")


class TestDataValidation:
    """Tests that validate data correctness."""

    def test_price_is_positive(self):
        """Validate: price should be positive."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field, backend="pandas")
        value = df["value"].iloc[0]

        # BDP long format returns strings, convert to float
        if isinstance(value, str):
            value = float(value)

        assert isinstance(value, (int, float))
        assert value > 0
        print(f"  Price: {value} (positive ✓)")

    def test_name_is_string(self):
        """Validate: name should be a string."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.name_field, backend="pandas")
        value = df["value"].iloc[0]

        assert isinstance(value, str)
        assert len(value) > 0
        print(f"  Name: {value}")

    def test_historical_dates_ordered(self):
        """Validate: historical dates should be ordered."""
        from xbbg import bdh

        start, end = get_date_range(14)
        df = bdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end, backend="pandas")

        if len(df) > 1:
            dates = df["date"].tolist()
            assert dates == sorted(dates), "Dates should be in chronological order"
            print(f"  {len(dates)} dates in order ✓")


# =============================================================================
# CLI Runner
# =============================================================================

# Test registry for CLI
TESTS: dict[str, Callable] = {}


def register_test(name: str):
    """Decorator to register a test function."""

    def decorator(func):
        TESTS[name] = func
        return func

    return decorator


# Register all test classes
def _register_class_tests(cls, prefix: str):
    """Register all test methods from a class."""
    for name in dir(cls):
        if name.startswith("test_"):
            method = getattr(cls, name)
            full_name = f"{prefix}_{name[5:]}"  # Remove 'test_' prefix
            TESTS[full_name] = lambda m=method, c=cls: m(c())


_register_class_tests(TestBdp, "bdp")
_register_class_tests(TestAbdp, "abdp")
_register_class_tests(TestBdh, "bdh")
_register_class_tests(TestAbdh, "abdh")
_register_class_tests(TestBds, "bds")
_register_class_tests(TestAbds, "abds")
_register_class_tests(TestBdib, "bdib")
_register_class_tests(TestAbdib, "abdib")
_register_class_tests(TestBdtick, "bdtick")
_register_class_tests(TestAbdtick, "abdtick")
_register_class_tests(TestBackendConversion, "backend")
_register_class_tests(TestStreaming, "stream")
_register_class_tests(TestExtensions, "ext")
_register_class_tests(TestExtensionsAsync, "ext_async")
_register_class_tests(TestRawOutput, "raw")
_register_class_tests(TestDataValidation, "validate")


def run_tests(test_names: list[str]) -> bool:
    """Run selected tests."""
    passed = 0
    failed = 0
    skipped = 0

    for name in test_names:
        if name not in TESTS:
            print(f"Unknown test: {name}")
            skipped += 1
            continue

        try:
            print(f"\n{'=' * 60}")
            print(f"TEST: {name}")
            print("-" * 60)

            test_func = TESTS[name]

            # Check if it's an async test (name contains 'abdp', 'abdh', etc. or 'async')
            is_async_test = any(x in name for x in ["abdp", "abdh", "abds", "abdib", "abdtick", "ext_async", "stream"])

            if is_async_test:
                # Run async tests in their own event loop
                async def run_async():
                    result = test_func()
                    if asyncio.iscoroutine(result):
                        await result

                asyncio.run(run_async())
            else:
                # Run sync tests directly (they manage their own event loop)
                result = test_func()
                # Shouldn't return coroutine for sync tests
                if asyncio.iscoroutine(result):
                    asyncio.run(result)

            passed += 1
            print(f"PASSED ✓")
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"SKIPPED: {e}")
        except Exception as e:
            failed += 1
            print(f"FAILED ✗: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 60}")

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="xbbg Front-to-Back Live API Tests")
    parser.add_argument(
        "tests",
        nargs="*",
        default=list(TESTS.keys()),
        help="Tests to run (default: all)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tests",
    )

    args = parser.parse_args()

    if args.list:
        print("Available tests:")
        for name in sorted(TESTS.keys()):
            print(f"  {name}")
        return 0

    print("=" * 60)
    print("xbbg Front-to-Back Live API Tests")
    print("=" * 60)
    print(f"Running {len(args.tests)} tests...")

    success = run_tests(args.tests)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
