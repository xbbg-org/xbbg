#!/usr/bin/env python
"""Front-to-back live tests using the actual xbbg public API.

These tests exercise the complete Python → Rust → Bloomberg → Rust → Python
data flow using the user-facing API functions (bdp, bdh, bds, etc.).
For low-level engine tests, see test_engine.py.

Run with:
    pytest tests/live/test_api.py -v --tb=short

Or as a standalone script:
    python tests/live/test_api.py [test_names...]
    python tests/live/test_api.py --list  # List available tests

Environment:
    Requires Bloomberg Terminal or B-PIPE connection.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# Test Configuration
# =============================================================================


@dataclass
class LiveTestConfig:
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

    # Streaming ticker — ES1 trades ~23h/day on Globex, works on most holidays
    streaming_ticker: str = "ES1 Index"

    # Common fields
    price_field: str = "PX_LAST"
    name_field: str = "NAME"
    volume_field: str = "VOLUME"

    def __post_init__(self):
        if self.equity_multi is None:
            self.equity_multi = ["AAPL US Equity", "MSFT US Equity"]


CONFIG = LiveTestConfig()


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

        logger.info(f"  {row['ticker']}: {row['field']} = {row['value']}")

    def test_bdp_single_ticker_multi_field(self):
        """BDP: single ticker, multiple fields."""
        from xbbg import bdp

        fields = [CONFIG.price_field, CONFIG.name_field, CONFIG.volume_field]
        df = bdp(CONFIG.equity_single, fields)

        assert len(df) == len(fields)

        pdf = df.to_pandas()
        returned_fields = set(pdf["field"].tolist())
        assert returned_fields == set(fields)

        logger.info(f"  Got {len(df)} field values")
        for _, row in pdf.iterrows():
            logger.info(f"    {row['field']}: {row['value']}")

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

        logger.info(f"  Got prices for {len(df)} tickers")

    def test_bdp_multi_ticker_multi_field(self):
        """BDP: multiple tickers, multiple fields."""
        from xbbg import bdp

        fields = [CONFIG.price_field, CONFIG.volume_field]
        df = bdp(CONFIG.equity_multi, fields)

        expected_rows = len(CONFIG.equity_multi) * len(fields)
        assert len(df) == expected_rows

        logger.info(f"  Got {len(df)} rows ({len(CONFIG.equity_multi)} tickers × {len(fields)} fields)")

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
        logger.info(f"  Price in EUR: {df.to_pandas().iloc[0]['value']}")


class TestAbdp:
    """Tests for abdp() - async BDP."""

    @pytest.mark.asyncio
    async def test_abdp_basic(self):
        """ABDP: basic async call."""
        from xbbg import abdp

        df = await abdp(CONFIG.equity_single, CONFIG.price_field)

        assert len(df) == 1
        logger.info(f"  Async result: {df.to_pandas().iloc[0]['value']}")

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
        logger.info(f"  Concurrent results: {[df.to_pandas().iloc[0]['value'] for df in results]}")


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

        logger.info(f"  Got {len(df)} data points from {start} to {end}")

    def test_bdh_multi_ticker(self):
        """BDH: multiple tickers."""
        from xbbg import bdh

        start, end = get_date_range(5)
        df = bdh(CONFIG.equity_multi, CONFIG.price_field, start_date=start, end_date=end)

        assert len(df) >= len(CONFIG.equity_multi)

        pdf = df.to_pandas()
        unique_tickers = pdf["ticker"].nunique()
        assert unique_tickers == len(CONFIG.equity_multi)

        logger.info(f"  Got {len(df)} rows for {unique_tickers} tickers")

    def test_bdh_multi_field(self):
        """BDH: multiple fields."""
        from xbbg import bdh

        start, end = get_date_range(5)
        fields = [CONFIG.price_field, CONFIG.volume_field]
        df = bdh(CONFIG.equity_single, fields, start_date=start, end_date=end)

        pdf = df.to_pandas()
        unique_fields = pdf["field"].nunique()
        assert unique_fields == len(fields)

        logger.info(f"  Got {len(df)} rows for {unique_fields} fields")

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
        logger.info(f"  Got {len(df)} adjusted prices")


class TestAbdh:
    """Tests for abdh() - async BDH."""

    @pytest.mark.asyncio
    async def test_abdh_basic(self):
        """ABDH: basic async call."""
        from xbbg import abdh

        start, end = get_date_range(5)
        df = await abdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end)

        assert len(df) >= 1
        logger.info(f"  Async result: {len(df)} rows")


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

        logger.info(f"  Got {len(df)} index members")

    def test_bds_dividend_history(self):
        """BDS: dividend history."""
        from xbbg import bds

        df = bds(CONFIG.equity_single, "DVD_HIST")

        # Should have some dividend history (IBM pays dividends)
        assert len(df) >= 0  # May be empty for some tickers

        logger.info(f"  Got {len(df)} dividend records")


class TestAbds:
    """Tests for abds() - async BDS."""

    @pytest.mark.asyncio
    async def test_abds_basic(self):
        """ABDS: basic async call."""
        from xbbg import abds

        df = await abds(CONFIG.index_ticker, "INDX_MEMBERS")

        assert len(df) == 30
        logger.info(f"  Async result: {len(df)} members")


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
        logger.info(f"  Got {len(df)} bars for {trading_day}")

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

        logger.info(f"  Got {len(df)} bars (10:00-11:00)")


class TestAbdib:
    """Tests for abdib() - async BDIB."""

    @pytest.mark.asyncio
    async def test_abdib_basic(self):
        """ABDIB: basic async call."""
        from xbbg import abdib

        trading_day = get_recent_trading_day()
        df = await abdib(CONFIG.equity_single, dt=trading_day, interval=5)

        logger.info(f"  Async result: {len(df)} bars")


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

        # Use a recent trading day (not today — may be a holiday)
        # IMPORTANT: Bloomberg uses UTC times for intraday requests
        # 14:30-15:30 UTC = 9:30-10:30 ET (market open)
        trading_day = get_recent_trading_day()
        df = bdtick(
            CONFIG.equity_single,
            start_datetime=f"{trading_day}T14:30:00",
            end_datetime=f"{trading_day}T15:30:00",
        )

        logger.info(f"  Got {len(df)} ticks for {trading_day} (1-hour at open, UTC)")


class TestAbdtick:
    """Tests for abdtick() - async BDTICK.

    IMPORTANT: Bloomberg intraday requests use UTC times.
    """

    @pytest.mark.asyncio
    async def test_abdtick_basic(self):
        """ABDTICK: basic async call at market open (UTC times)."""
        from datetime import datetime

        from xbbg import abdtick

        # Use a recent trading day (not today — may be a holiday)
        # IMPORTANT: Bloomberg uses UTC times for intraday requests
        # 14:30-15:30 UTC = 9:30-10:30 ET (market open)
        trading_day = get_recent_trading_day()
        df = await abdtick(
            CONFIG.equity_single,
            start_datetime=f"{trading_day}T14:30:00",
            end_datetime=f"{trading_day}T15:30:00",
        )

        logger.info(f"  Async result: {len(df)} ticks for {trading_day} (UTC)")


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
        logger.info(f"  Narwhals DataFrame: {type(df)}")

    def test_backend_pandas(self):
        """Backend: pandas."""
        import pandas as pd

        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field, backend="pandas")

        assert isinstance(df, pd.DataFrame)
        logger.info(f"  Pandas DataFrame: {type(df)}")

    def test_backend_polars(self):
        """Backend: polars."""
        pytest.importorskip("polars")
        import polars as pl

        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.price_field, backend="polars")

        assert isinstance(df, pl.DataFrame)
        logger.info(f"  Polars DataFrame: {type(df)}")

    def test_backend_pyarrow(self):
        """Backend: pyarrow."""
        import pyarrow as pa

        from xbbg import bdp

        table = bdp(CONFIG.equity_single, CONFIG.price_field, backend="pyarrow")

        assert isinstance(table, pa.Table)
        logger.info(f"  PyArrow Table: {type(table)}")

    def test_global_backend_setting(self):
        """Backend: global setting."""
        import pandas as pd

        from xbbg import bdp, get_backend, set_backend

        original = get_backend()
        try:
            set_backend("pandas")
            df = bdp(CONFIG.equity_single, CONFIG.price_field)
            assert isinstance(df, pd.DataFrame)
            logger.info("  Global backend setting works")
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
            async for tick in astream(CONFIG.streaming_ticker, ["LAST_PRICE", "BID", "ASK"]):
                ticks_received += 1
                logger.debug(f"    Tick: {tick}")
                if ticks_received >= 3:
                    break

        try:
            await asyncio.wait_for(collect_ticks(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"  Timeout after {timeout_seconds}s (got {ticks_received} ticks)")

        logger.info(f"  Received {ticks_received} ticks")

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self):
        """Stream: subscribe and unsubscribe."""
        from xbbg import asubscribe

        sub = await asubscribe(CONFIG.streaming_ticker, ["LAST_PRICE"])
        timeout_seconds = 15

        ticks_received = 0

        async def collect_ticks():
            nonlocal ticks_received
            async for tick in sub:
                ticks_received += 1
                if ticks_received >= 2:
                    break

        try:
            await asyncio.wait_for(collect_ticks(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"  Timeout after {timeout_seconds}s (got {ticks_received} ticks — market may be closed)")
        finally:
            await sub.unsubscribe()

        logger.info(f"  Received {ticks_received} ticks before unsubscribe")


# =============================================================================
# Extension Module Tests
# =============================================================================


class TestExtensions:
    """Tests for ext module functions."""

    def test_ext_dividend(self):
        """Ext: dividend history."""
        from xbbg import ext

        df = ext.dividend(CONFIG.equity_single, start_date="2024-01-01")

        logger.info(f"  Got {len(df)} dividend records")

    def test_ext_etf_holdings(self):
        """Ext: ETF holdings."""
        from xbbg import ext

        df = ext.etf_holdings(CONFIG.etf_ticker)

        assert len(df) > 0
        logger.info(f"  Got {len(df)} ETF holdings")

    def test_ext_fut_ticker(self):
        """Ext: futures ticker resolution."""
        from xbbg import ext

        ticker = ext.fut_ticker(CONFIG.futures_generic, "2024-06-15")

        assert ticker is not None
        logger.info(f"  Resolved {CONFIG.futures_generic} → {ticker}")

    def test_ext_yas(self):
        """Ext: yield & spread analysis."""
        from xbbg import ext

        df = ext.yas(CONFIG.bond_ticker, ["YAS_BOND_YLD", "YAS_MOD_DUR"])

        assert len(df) > 0
        logger.info(f"  Got {len(df)} YAS values")

    def test_ext_earnings(self):
        """Ext: earnings breakdown (renamed from earning)."""
        from xbbg import ext

        df = ext.earnings("AMD US Equity", by="Geo")
        logger.info(f"  Got {len(df)} earnings rows")

    def test_ext_turnover(self):
        """Ext: turnover data."""
        from xbbg import ext

        start, _ = get_date_range(7)
        df = ext.turnover(CONFIG.equity_single, start_date=start)
        logger.info(f"  Got {len(df)} turnover rows")

    def test_ext_active_futures(self):
        """Ext: active futures resolution."""
        from xbbg import ext

        trading_day = get_recent_trading_day()
        result = ext.active_futures(CONFIG.futures_generic, dt=trading_day)
        logger.info(f"  Active futures result: {result}")

    def test_ext_cdx_ticker(self):
        """Ext: CDX ticker resolution."""
        from xbbg import ext

        try:
            ticker = ext.cdx_ticker("CDX NA IG", "5Y")
            logger.info(f"  CDX ticker: {ticker}")
        except Exception as e:
            pytest.skip(f"CDX data not available: {e}")

    def test_ext_active_cdx(self):
        """Ext: active CDX."""
        from xbbg import ext

        try:
            df = ext.active_cdx("CDX NA IG")
            logger.info(f"  Got {len(df)} active CDX")
        except Exception as e:
            pytest.skip(f"CDX data not available: {e}")

    def test_ext_convert_ccy(self):
        """Ext: currency conversion (renamed from adjust_ccy)."""
        from xbbg import bdh, ext

        start, end = get_date_range(5)
        df = bdh(["VOD LN Equity"], CONFIG.price_field, start_date=start, end_date=end)
        df_usd = ext.convert_ccy(df, ccy="USD")
        logger.info(f"  Converted {len(df_usd)} rows to USD")

    def test_ext_preferreds(self):
        """Ext: preferred stocks."""
        from xbbg import ext

        try:
            df = ext.preferreds("BAC US Equity")
            logger.info(f"  Got {len(df)} preferred stocks")
        except Exception as e:
            pytest.skip(f"Preferreds data not available: {e}")

    def test_ext_corporate_bonds(self):
        """Ext: corporate bonds."""
        from xbbg import ext

        try:
            df = ext.corporate_bonds("AAPL")
            logger.info(f"  Got {len(df)} corporate bonds")
        except Exception as e:
            pytest.skip(f"Corporate bonds data not available: {e}")

    def test_ext_bqr(self):
        """Ext: BQR query."""
        from xbbg import ext

        try:
            df = ext.bqr("IBM US Equity")
            logger.info(f"  Got {len(df)} BQR results")
        except Exception as e:
            pytest.skip(f"BQR not available: {e}")


class TestExtensionsAsync:
    """Tests for async ext module functions."""

    @pytest.mark.asyncio
    async def test_ext_adividend(self):
        """Ext: async dividend."""
        from xbbg import ext

        df = await ext.adividend(CONFIG.equity_single, start_date="2024-01-01")

        logger.info(f"  Async result: {len(df)} dividend records")

    @pytest.mark.asyncio
    async def test_ext_aetf_holdings(self):
        """Ext: async ETF holdings."""
        from xbbg import ext

        df = await ext.aetf_holdings(CONFIG.etf_ticker)

        assert len(df) > 0
        logger.info(f"  Async result: {len(df)} holdings")

    @pytest.mark.asyncio
    async def test_ext_afut_ticker(self):
        """Ext: async futures ticker."""
        from xbbg import ext

        ticker = await ext.afut_ticker(CONFIG.futures_generic, "2024-06-15")

        assert ticker is not None
        logger.info(f"  Async result: {ticker}")

    @pytest.mark.asyncio
    async def test_ext_aearnings(self):
        """Ext: async earnings (renamed from aearning)."""
        from xbbg import ext

        df = await ext.aearnings("AMD US Equity", by="Geo")
        logger.info(f"  Async earnings: {len(df)} rows")

    @pytest.mark.asyncio
    async def test_ext_aturnover(self):
        """Ext: async turnover."""
        from xbbg import ext

        start, _ = get_date_range(7)
        df = await ext.aturnover(CONFIG.equity_single, start_date=start)
        logger.info(f"  Async turnover: {len(df)} rows")

    @pytest.mark.asyncio
    async def test_ext_aactive_futures(self):
        """Ext: async active futures."""
        from xbbg import ext

        trading_day = get_recent_trading_day()
        result = await ext.aactive_futures(CONFIG.futures_generic, dt=trading_day)
        logger.info(f"  Async active futures result: {result}")

    @pytest.mark.asyncio
    async def test_ext_acdx_ticker(self):
        """Ext: async CDX ticker."""
        from xbbg import ext

        try:
            ticker = await ext.acdx_ticker("CDX NA IG", "5Y")
            logger.info(f"  Async CDX: {ticker}")
        except Exception as e:
            pytest.skip(f"CDX not available: {e}")

    @pytest.mark.asyncio
    async def test_ext_aactive_cdx(self):
        """Ext: async active CDX."""
        from xbbg import ext

        try:
            df = await ext.aactive_cdx("CDX NA IG")
            logger.info(f"  Async active CDX: {len(df)} results")
        except Exception as e:
            pytest.skip(f"CDX not available: {e}")

    @pytest.mark.asyncio
    async def test_ext_aconvert_ccy(self):
        """Ext: async currency conversion (renamed from aadjust_ccy)."""
        from xbbg import abdh, ext

        start, end = get_date_range(5)
        df = await abdh(["VOD LN Equity"], CONFIG.price_field, start_date=start, end_date=end)
        df_usd = await ext.aconvert_ccy(df, ccy="USD")
        logger.info(f"  Async converted: {len(df_usd)} rows")

    @pytest.mark.asyncio
    async def test_ext_apreferreds(self):
        """Ext: async preferreds."""
        from xbbg import ext

        try:
            df = await ext.apreferreds("BAC US Equity")
            logger.info(f"  Async preferreds: {len(df)} results")
        except Exception as e:
            pytest.skip(f"Preferreds not available: {e}")

    @pytest.mark.asyncio
    async def test_ext_acorporate_bonds(self):
        """Ext: async corporate bonds."""
        from xbbg import ext

        try:
            df = await ext.acorporate_bonds("AAPL")
            logger.info(f"  Async bonds: {len(df)} results")
        except Exception as e:
            pytest.skip(f"Corporate bonds not available: {e}")

    @pytest.mark.asyncio
    async def test_ext_abqr(self):
        """Ext: async BQR."""
        from xbbg import ext

        try:
            df = await ext.abqr("IBM US Equity")
            logger.info(f"  Async BQR: {len(df)} results")
        except Exception as e:
            pytest.skip(f"BQR not available: {e}")


# =============================================================================
# Data Validation Tests
# =============================================================================


class TestRawOutput:
    """Tests that show raw output for debugging."""

    def test_bdp_raw_output(self):
        """Show raw BDP output structure."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, [CONFIG.price_field, CONFIG.name_field], backend="pandas")

        logger.debug(f"\n  Raw DataFrame:")
        logger.debug(f"  {df.to_string()}")
        logger.debug(f"\n  Columns: {list(df.columns)}")
        logger.debug(f"  Dtypes:\n{df.dtypes}")
        logger.debug(f"\n  Sample values:")
        for col in df.columns:
            val = df[col].iloc[0]
            logger.debug(f"    {col}: {val!r} (type: {type(val).__name__})")

    def test_bdh_raw_output(self):
        """Show raw BDH output structure."""
        from xbbg import bdh

        start, end = get_date_range(5)
        df = bdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end, backend="pandas")

        logger.debug(f"\n  Raw DataFrame (first 5 rows):")
        logger.debug(f"  {df.head().to_string()}")
        logger.debug(f"\n  Columns: {list(df.columns)}")
        logger.debug(f"  Dtypes:\n{df.dtypes}")
        logger.debug(f"\n  Sample values:")
        for col in df.columns:
            val = df[col].iloc[0]
            logger.debug(f"    {col}: {val!r} (type: {type(val).__name__})")

    def test_bds_raw_output(self):
        """Show raw BDS output structure."""
        from xbbg import bds

        df = bds(CONFIG.index_ticker, "INDX_MEMBERS", backend="pandas")

        logger.debug(f"\n  Raw DataFrame (first 5 rows):")
        logger.debug(f"  {df.head().to_string()}")
        logger.debug(f"\n  Columns: {list(df.columns)}")
        logger.debug(f"  Dtypes:\n{df.dtypes}")


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
        logger.info(f"  Price: {value} (positive ✓)")

    def test_name_is_string(self):
        """Validate: name should be a string."""
        from xbbg import bdp

        df = bdp(CONFIG.equity_single, CONFIG.name_field, backend="pandas")
        value = df["value"].iloc[0]

        assert isinstance(value, str)
        assert len(value) > 0
        logger.info(f"  Name: {value}")

    def test_historical_dates_ordered(self):
        """Validate: historical dates should be ordered."""
        from xbbg import bdh

        start, end = get_date_range(14)
        df = bdh(CONFIG.equity_single, CONFIG.price_field, start_date=start, end_date=end, backend="pandas")

        if len(df) > 1:
            dates = df["date"].tolist()
            assert dates == sorted(dates), "Dates should be in chronological order"
            logger.info(f"  {len(dates)} dates in order ✓")


# =============================================================================
# Additional API Coverage Tests
# =============================================================================


class TestBql:
    """Tests for bql() - basic BQL query."""

    def test_bql_basic(self):
        """BQL: basic query."""
        from xbbg import bql

        df = bql("get(px_last) for('IBM US Equity')")
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} BQL rows")


class TestAbql:
    """Tests for abql() - async version."""

    @pytest.mark.asyncio
    async def test_abql_basic(self):
        """ABQL: basic async call."""
        from xbbg import abql

        df = await abql("get(px_last) for('IBM US Equity')")
        assert len(df) >= 1
        logger.info(f"  Async BQL result: {len(df)} rows")


class TestBsrch:
    """Tests for bsrch() - Bloomberg search."""

    def test_bsrch_basic(self):
        """BSRCH: basic search query."""
        from xbbg import bsrch

        df = bsrch("FI:SOVR")
        if len(df) == 0:
            pytest.skip("bsrch returned 0 rows (domain may not be available for this account)")
        logger.info(f"  Got {len(df)} search results")


class TestAbsrch:
    """Tests for absrch() - async search."""

    @pytest.mark.asyncio
    async def test_absrch_basic(self):
        """ABSRCH: basic async search."""
        from xbbg import absrch

        df = await absrch("FI:SOVR")
        if len(df) == 0:
            pytest.skip("absrch returned 0 rows (domain may not be available for this account)")
        logger.info(f"  Async search result: {len(df)} rows")


class TestBflds:
    """Tests for bflds() - field metadata lookup."""

    def test_bflds_single(self):
        """BFLDS: single field metadata lookup."""
        from xbbg import bflds

        df = bflds("PX_LAST")
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} field info rows")

    def test_bflds_multi(self):
        """BFLDS: multiple field metadata lookup."""
        from xbbg import bflds

        df = bflds(["PX_LAST", "VOLUME", "NAME"])
        assert len(df) >= 3
        logger.info(f"  Got {len(df)} field info rows")


class TestAbflds:
    """Tests for abflds() - async field metadata lookup."""

    @pytest.mark.asyncio
    async def test_abflds_basic(self):
        """ABFLDS: basic async field metadata lookup."""
        from xbbg import abflds

        df = await abflds("PX_LAST")
        assert len(df) >= 1
        logger.info(f"  Async field info: {len(df)} rows")


class TestBeqs:
    """Tests for beqs() - equity screening."""

    def test_beqs_basic(self):
        """BEQS: basic equity screening."""
        from xbbg import beqs

        df = beqs("Core Capital Goods Makers")
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} screening results")


class TestAbeqs:
    """Tests for abeqs() - async equity screening."""

    @pytest.mark.asyncio
    async def test_abeqs_basic(self):
        """ABEQS: basic async screening."""
        from xbbg import abeqs

        df = await abeqs("Core Capital Goods Makers")
        assert len(df) >= 1
        logger.info(f"  Async screening: {len(df)} results")


class TestBlkp:
    """Tests for blkp() - security lookup."""

    def test_blkp_basic(self):
        """BLKP: basic lookup."""
        from xbbg import blkp

        df = blkp("IBM", max_results=5)
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} lookup results")


class TestAblkp:
    """Tests for ablkp() - async security lookup."""

    @pytest.mark.asyncio
    async def test_ablkp_basic(self):
        """ABLKP: basic async lookup."""
        from xbbg import ablkp

        df = await ablkp("IBM", max_results=5)
        assert len(df) >= 1
        logger.info(f"  Async lookup: {len(df)} results")


class TestBport:
    """Tests for bport() - portfolio data."""

    def test_bport_basic(self):
        """BPORT: basic portfolio request. May fail without portfolio access."""
        from xbbg import bport

        try:
            df = bport("U10378179-1 Client")
            logger.info(f"  Got {len(df)} portfolio rows")
        except Exception as e:
            pytest.skip(f"Portfolio access not available: {e}")


class TestAbport:
    """Tests for abport() - async portfolio data."""

    @pytest.mark.asyncio
    async def test_abport_basic(self):
        """ABPORT: basic async portfolio request."""
        from xbbg import abport

        try:
            df = await abport("U10378179-1 Client")
            logger.info(f"  Async portfolio: {len(df)} rows")
        except Exception as e:
            pytest.skip(f"Portfolio access not available: {e}")


class TestBcurves:
    """Tests for bcurves() - yield curves."""

    def test_bcurves_basic(self):
        """BCURVES: basic curve request."""
        from xbbg import bcurves

        df = bcurves(curveid="YCSW0023 Index")
        if len(df) == 0:
            pytest.skip("bcurves returned 0 rows (likely entitlement/permission issue)")
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} curve points")


class TestAbcurves:
    """Tests for abcurves() - async yield curves."""

    @pytest.mark.asyncio
    async def test_abcurves_basic(self):
        """ABCURVES: basic async curve request."""
        from xbbg import abcurves

        df = await abcurves(curveid="YCSW0023 Index")
        if len(df) == 0:
            pytest.skip("abcurves returned 0 rows (likely entitlement/permission issue)")
        assert len(df) >= 1
        logger.info(f"  Async curves: {len(df)} points")


class TestBgovts:
    """Tests for bgovts() - government bonds."""

    def test_bgovts_basic(self):
        """BGOVTS: basic government bond list."""
        from xbbg import bgovts

        df = bgovts("USD")
        if len(df) == 0:
            pytest.skip("bgovts returned 0 rows (likely entitlement/permission issue)")
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} government bonds")


class TestAbgovts:
    """Tests for abgovts() - async government bonds."""

    @pytest.mark.asyncio
    async def test_abgovts_basic(self):
        """ABGOVTS: basic async government bond list."""
        from xbbg import abgovts

        df = await abgovts("USD")
        if len(df) == 0:
            pytest.skip("abgovts returned 0 rows (likely entitlement/permission issue)")
        assert len(df) >= 1
        logger.info(f"  Async govts: {len(df)} bonds")


class TestRequest:
    """Tests for request() - generic service/operation API."""

    def test_request_basic(self):
        """Request: generic API with Service/Operation."""
        from xbbg import Operation, Service, request

        df = request(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=[CONFIG.equity_single],
            fields=[CONFIG.price_field],
        )
        assert len(df) >= 1
        logger.info(f"  Got {len(df)} request rows")


class TestArequest:
    """Tests for arequest() - async generic API."""

    @pytest.mark.asyncio
    async def test_arequest_basic(self):
        """ARequest: basic async generic request."""
        from xbbg import Operation, Service, arequest

        df = await arequest(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=[CONFIG.equity_single],
            fields=[CONFIG.price_field],
        )
        assert len(df) >= 1
        logger.info(f"  Async request: {len(df)} rows")


class TestVwap:
    """Tests for avwap() - streaming VWAP."""

    @pytest.mark.asyncio
    async def test_avwap_basic(self):
        """VWAP: basic streaming VWAP."""
        from xbbg import avwap

        ticks = 0

        async def collect():
            nonlocal ticks
            sub = await avwap(CONFIG.streaming_ticker)
            async for tick in sub:
                ticks += 1
                if ticks >= 2:
                    break

        try:
            await asyncio.wait_for(collect(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning(f"  VWAP timeout (got {ticks} ticks — market may be closed)")
        logger.info(f"  Got {ticks} VWAP ticks")


class TestMktbar:
    """Tests for amktbar() - streaming market bars."""

    @pytest.mark.asyncio
    async def test_amktbar_basic(self):
        """MKTBAR: streaming bars."""
        from xbbg import amktbar

        bars = 0

        async def collect():
            nonlocal bars
            sub = await amktbar(CONFIG.streaming_ticker, interval=1)
            async for bar in sub:
                bars += 1
                if bars >= 2:
                    break

        try:
            await asyncio.wait_for(collect(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning(f"  Mktbar timeout (got {bars} bars — market may be closed)")
        logger.info(f"  Got {bars} market bars")


class TestDepth:
    """Tests for adepth() - market depth streaming."""

    @pytest.mark.asyncio
    async def test_adepth_basic(self):
        """DEPTH: market depth (requires B-PIPE)."""
        from xbbg import adepth

        try:
            updates = 0
            sub = await adepth(CONFIG.streaming_ticker)

            async def collect():
                nonlocal updates
                async for update in sub:
                    updates += 1
                    if updates >= 2:
                        break

            await asyncio.wait_for(collect(), timeout=15)
            logger.info(f"  Got {updates} depth updates")
        except asyncio.TimeoutError:
            pytest.skip("No depth data received (B-PIPE likely not available)")
        except Exception as e:
            pytest.skip(f"B-PIPE not available: {e}")


class TestChains:
    """Tests for achains() - chain streaming."""

    @pytest.mark.asyncio
    async def test_achains_basic(self):
        """CHAINS: option/futures chains (requires B-PIPE)."""
        from xbbg import achains

        try:
            updates = 0
            sub = await achains(CONFIG.streaming_ticker)

            async def collect():
                nonlocal updates
                async for update in sub:
                    updates += 1
                    if updates >= 2:
                        break

            await asyncio.wait_for(collect(), timeout=15)
            logger.info(f"  Got {updates} chain updates")
        except asyncio.TimeoutError:
            pytest.skip("No chain data received (B-PIPE likely not available)")
        except Exception as e:
            pytest.skip(f"B-PIPE not available: {e}")


class TestConfig:
    """Tests for configure/connectivity/logging lifecycle APIs."""

    def test_configure(self):
        """Config: configure engine (may already be started by prior tests)."""
        from xbbg import configure

        try:
            configure()
            logger.info("  configure() succeeded")
        except RuntimeError:
            # Engine already started from prior tests — expected behavior
            logger.info("  configure() raised RuntimeError (engine already started) — expected")

    def test_is_connected(self):
        """Config: check connection status."""
        from xbbg import is_connected

        status = is_connected()
        assert isinstance(status, bool)
        logger.info(f"  Connected: {status}")

    def test_set_get_log_level(self):
        """Config: set and get log level."""
        from xbbg import get_log_level, set_log_level

        original = get_log_level()
        set_log_level("warn")
        assert get_log_level() == "warn"
        set_log_level(original)
        logger.info(f"  Log level round-trip: {original}")


class TestTa:
    """Tests for TA metadata APIs."""

    def test_ta_studies_list(self):
        """TA: list available studies."""
        from xbbg import ta_studies

        studies = ta_studies()
        assert isinstance(studies, list)
        assert len(studies) > 0
        logger.info(f"  Got {len(studies)} TA studies")

    def test_ta_study_params(self):
        """TA: get study parameters."""
        from xbbg import ta_studies, ta_study_params

        studies = ta_studies()
        if studies:
            params = ta_study_params(studies[0])
            assert isinstance(params, dict)
            logger.info(f"  Study '{studies[0]}' has {len(params)} params")


class TestBta:
    """Tests for bta() - technical analysis data."""

    def test_bta_basic(self):
        """BTA: basic TA request using SMA (has known defaults)."""
        from xbbg import bta

        start, end = get_date_range(30)
        df = bta(CONFIG.streaming_ticker, "sma", start_date=start, end_date=end)
        assert len(df) >= 1, f"Expected TA data, got {len(df)} rows"
        logger.info(f"  Got {len(df)} TA rows")


class TestAbta:
    """Tests for abta() - async technical analysis data."""

    @pytest.mark.asyncio
    async def test_abta_basic(self):
        """ABTA: basic async TA request using SMA (has known defaults)."""
        from xbbg import abta

        start, end = get_date_range(30)
        df = await abta(CONFIG.streaming_ticker, "sma", start_date=start, end_date=end)
        assert len(df) >= 1, f"Expected async TA data, got {len(df)} rows"
        logger.info(f"  Async TA result: {len(df)} rows")


class TestBops:
    """Tests for bops() - schema operations list."""

    def test_bops_basic(self):
        """BOPS: list operations for a service."""
        from xbbg import bops

        ops = bops()
        assert isinstance(ops, list)
        assert len(ops) > 0
        logger.info(f"  Got {len(ops)} operations")


class TestAbops:
    """Tests for abops() - async schema operations list."""

    @pytest.mark.asyncio
    async def test_abops_basic(self):
        """ABOPS: basic async operations list."""
        from xbbg import abops

        ops = await abops()
        assert isinstance(ops, list)
        assert len(ops) > 0
        logger.info(f"  Async ops: {len(ops)}")


class TestBschema:
    """Tests for bschema() - service schema."""

    def test_bschema_basic(self):
        """BSCHEMA: get service schema."""
        from xbbg import bschema

        schema = bschema()
        assert isinstance(schema, dict)
        assert "operations" in schema
        logger.info(f"  Got schema with {len(schema['operations'])} operations")


class TestAbschema:
    """Tests for abschema() - async service schema."""

    @pytest.mark.asyncio
    async def test_abschema_basic(self):
        """ABSCHEMA: basic async service schema."""
        from xbbg import abschema

        schema = await abschema()
        assert isinstance(schema, dict)
        assert "operations" in schema
        logger.info(f"  Async schema: {len(schema['operations'])} ops")


class TestSchemaIntrospection:
    """Tests for sync schema module helpers."""

    def test_get_schema(self):
        """Schema: get full service schema."""
        from xbbg import get_schema

        schema = get_schema("//blp/refdata")
        assert schema is not None
        logger.info(f"  Schema: {schema.service}")

    def test_list_operations(self):
        """Schema: list operations."""
        from xbbg import list_operations

        ops = list_operations("//blp/refdata")
        assert isinstance(ops, list)
        assert len(ops) > 0
        logger.info(f"  Operations: {ops}")

    def test_get_enum_values(self):
        """Schema: get enum values."""
        from xbbg import get_enum_values

        vals = get_enum_values("//blp/refdata", "HistoricalDataRequest", "periodicitySelection")
        if vals is not None:
            assert isinstance(vals, list)
            logger.info(f"  Enum values: {vals}")
        else:
            logger.info("  No enum values (schema may need caching first)")

    def test_list_valid_elements(self):
        """Schema: list valid elements."""
        from xbbg import list_valid_elements

        elems = list_valid_elements("//blp/refdata", "ReferenceDataRequest")
        if elems is not None:
            assert isinstance(elems, list)
            logger.info(f"  Valid elements: {len(elems)}")
        else:
            logger.info("  No elements (schema may need caching first)")


class TestSchemaIntrospectionAsync:
    """Tests for async schema module helpers."""

    @pytest.mark.asyncio
    async def test_aget_schema(self):
        """Schema: async get full service schema."""
        from xbbg import aget_schema

        schema = await aget_schema("//blp/refdata")
        assert schema is not None
        logger.info(f"  Async schema: {schema.service}")

    @pytest.mark.asyncio
    async def test_alist_operations(self):
        """Schema: async list operations."""
        from xbbg import alist_operations

        ops = await alist_operations("//blp/refdata")
        assert isinstance(ops, list)
        assert len(ops) > 0
        logger.info(f"  Async operations: {ops}")

    @pytest.mark.asyncio
    async def test_aget_enum_values(self):
        """Schema: async get enum values."""
        from xbbg import aget_enum_values

        vals = await aget_enum_values("//blp/refdata", "HistoricalDataRequest", "periodicitySelection")
        if vals is not None:
            assert isinstance(vals, list)
            logger.info(f"  Async enum: {vals}")
        else:
            logger.info("  No enum values")

    @pytest.mark.asyncio
    async def test_alist_valid_elements(self):
        """Schema: async list valid elements."""
        from xbbg import alist_valid_elements

        elems = await alist_valid_elements("//blp/refdata", "ReferenceDataRequest")
        if elems is not None:
            assert isinstance(elems, list)
            logger.info(f"  Async elements: {len(elems)}")
        else:
            logger.info("  No elements")


class TestFieldCache:
    """Tests for field cache helper APIs."""

    def test_resolve_field_types(self):
        """FieldCache: resolve field types."""
        from xbbg import resolve_field_types

        result = resolve_field_types(["PX_LAST", "VOLUME", "NAME"])
        assert result is not None
        logger.info(f"  Resolved {len(result)} field types")

    def test_get_field_info(self):
        """FieldCache: get field info."""
        from xbbg import get_field_info

        try:
            info = get_field_info(["PX_LAST"])
            logger.info(f"  Field info: {info}")
        except Exception as e:
            pytest.skip(f"Field cache not populated: {e}")

    def test_clear_field_cache(self):
        """FieldCache: clear cache."""
        from xbbg import clear_field_cache

        clear_field_cache()
        logger.info("  Cache cleared")


class TestFieldCacheAsync:
    """Tests for async field cache helper APIs."""

    @pytest.mark.asyncio
    async def test_aresolve_field_types(self):
        """FieldCache: async resolve field types."""
        from xbbg import aresolve_field_types

        result = await aresolve_field_types(["PX_LAST", "VOLUME"])
        assert result is not None
        logger.info(f"  Async resolved: {len(result)} fields")


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
_register_class_tests(TestBql, "bql")
_register_class_tests(TestAbql, "abql")
_register_class_tests(TestBsrch, "bsrch")
_register_class_tests(TestAbsrch, "absrch")
_register_class_tests(TestBflds, "bflds")
_register_class_tests(TestAbflds, "abflds")
_register_class_tests(TestBeqs, "beqs")
_register_class_tests(TestAbeqs, "abeqs")
_register_class_tests(TestBlkp, "blkp")
_register_class_tests(TestAblkp, "ablkp")
_register_class_tests(TestBport, "bport")
_register_class_tests(TestAbport, "abport")
_register_class_tests(TestBcurves, "bcurves")
_register_class_tests(TestAbcurves, "abcurves")
_register_class_tests(TestBgovts, "bgovts")
_register_class_tests(TestAbgovts, "abgovts")
_register_class_tests(TestRequest, "request")
_register_class_tests(TestArequest, "arequest")
_register_class_tests(TestVwap, "vwap")
_register_class_tests(TestMktbar, "mktbar")
_register_class_tests(TestDepth, "depth")
_register_class_tests(TestChains, "chains")
_register_class_tests(TestConfig, "config")
_register_class_tests(TestTa, "ta")
_register_class_tests(TestBta, "bta")
_register_class_tests(TestAbta, "abta")
_register_class_tests(TestBops, "bops")
_register_class_tests(TestAbops, "abops")
_register_class_tests(TestBschema, "bschema")
_register_class_tests(TestAbschema, "abschema")
_register_class_tests(TestSchemaIntrospection, "schema")
_register_class_tests(TestSchemaIntrospectionAsync, "schema_async")
_register_class_tests(TestFieldCache, "field_cache")
_register_class_tests(TestFieldCacheAsync, "field_cache_async")


def run_tests(test_names: list[str]) -> bool:
    """Run selected tests."""
    passed = 0
    failed = 0
    skipped = 0

    for name in test_names:
        if name not in TESTS:
            logger.warning(f"Unknown test: {name}")
            skipped += 1
            continue

        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"TEST: {name}")
            logger.info("-" * 60)

            test_func = TESTS[name]

            # Check if it's an async test (name contains 'abdp', 'abdh', etc. or 'async')
            is_async_test = any(
                x in name
                for x in [
                    "abdp",
                    "abdh",
                    "abds",
                    "abdib",
                    "abdtick",
                    "ext_async",
                    "stream",
                    "abql",
                    "absrch",
                    "abflds",
                    "abeqs",
                    "ablkp",
                    "abport",
                    "abcurves",
                    "abgovts",
                    "arequest",
                    "vwap",
                    "mktbar",
                    "depth",
                    "chains",
                    "abta",
                    "abops",
                    "abschema",
                    "schema_async",
                    "field_cache_async",
                ]
            )

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
            logger.info(f"PASSED ✓")
        except pytest.skip.Exception as e:
            skipped += 1
            logger.warning(f"SKIPPED: {e}")
        except Exception as e:
            failed += 1
            logger.error(f"FAILED ✗: {e}")
            import traceback

            traceback.print_exc()

    logger.info(f"\n{'=' * 60}")
    logger.info(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    logger.info(f"{'=' * 60}")

    return failed == 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
        logger.info("Available tests:")
        for name in sorted(TESTS.keys()):
            logger.info(f"  {name}")
        return 0

    logger.info("=" * 60)
    logger.info("xbbg Front-to-Back Live API Tests")
    logger.info("=" * 60)
    logger.info(f"Running {len(args.tests)} tests...")

    success = run_tests(args.tests)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
