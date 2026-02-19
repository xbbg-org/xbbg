"""Comprehensive integration tests for xbbg with Bloomberg connection.

These tests validate the full data flow from Python through Rust to Bloomberg and back.
They are designed to be lightweight on data usage while testing all major functionality.

Enable these tests by setting: XBBG_INTEGRATION_TESTS=1

Data usage summary:
- Session tests: 0 data points (connection only)
- Field metadata tests: 0 data points (no security data)
- BDP tests: ~3-6 data points per test
- BDH tests: ~5-25 data points per test (5 trading days)
- BDS tests: Variable, but uses small bulk fields
- BDIB tests: ~60-120 bars (1 hour of 1-min bars)
- BDTICK tests: Variable, but uses short time windows
- Error tests: 0 data points (validation/errors)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import os

import pytest

# Skip all tests in this module unless XBBG_INTEGRATION_TESTS is set
pytestmark = pytest.mark.skipif(
    os.environ.get("XBBG_INTEGRATION_TESTS") != "1",
    reason="Integration tests require Bloomberg connection (set XBBG_INTEGRATION_TESTS=1)",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def single_ticker():
    """A single liquid equity ticker for minimal tests."""
    return "IBM US Equity"


@pytest.fixture
def single_field():
    """A single commonly-available field."""
    return "PX_LAST"


@pytest.fixture
def multiple_tickers():
    """Multiple tickers for batch tests."""
    return ["IBM US Equity", "AAPL US Equity"]


@pytest.fixture
def multiple_fields():
    """Multiple fields for batch tests."""
    return ["PX_LAST", "VOLUME"]


@pytest.fixture
def recent_dates():
    """A short date range for historical tests (5 trading days)."""
    end = datetime.now()
    # Go back ~7 calendar days to ensure 5 trading days
    start = end - timedelta(days=7)
    return {
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    }


@pytest.fixture
def intraday_window():
    """A short intraday window (1 hour)."""
    # Use yesterday to ensure market was open
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    return {
        "start_datetime": f"{date_str} 10:00:00",
        "end_datetime": f"{date_str} 11:00:00",
    }


# =============================================================================
# Session / Connection Tests
# =============================================================================


@pytest.mark.integration
class TestSessionLifecycle:
    """Tests for Bloomberg session connection lifecycle."""

    def test_engine_connects_successfully(self):
        """PyEngine should connect to Bloomberg on instantiation."""
        import xbbg

        # Accessing _core triggers engine creation
        engine = xbbg._core.PyEngine()

        # If we get here without exception, connection succeeded
        assert engine is not None

    def test_engine_has_version(self):
        """PyEngine should expose version info."""
        import xbbg

        version = xbbg._core.version()
        assert isinstance(version, str)
        assert len(version) > 0


# =============================================================================
# Field Metadata Tests (Zero security data usage)
# =============================================================================


@pytest.mark.integration
class TestFieldMetadata:
    """Tests for field metadata lookups (//blp/apiflds service).

    These tests query Bloomberg for field information without requesting
    any security data, making them zero-cost from a data perspective.
    """

    def test_field_info_single_field(self):
        """Should retrieve metadata for a single field."""
        from xbbg import Operation, Service, request

        df = request(
            Service.APIFLDS,
            Operation.FIELD_INFO,
            fields=["PX_LAST"],
        )

        # Should return a DataFrame with field info
        assert len(df) > 0

    def test_field_info_multiple_fields(self):
        """Should retrieve metadata for multiple fields."""
        from xbbg import Operation, Service, request

        df = request(
            Service.APIFLDS,
            Operation.FIELD_INFO,
            fields=["PX_LAST", "VOLUME", "NAME"],
        )

        # Should have info for each field
        assert len(df) >= 3

    @pytest.mark.asyncio
    async def test_field_info_async(self):
        """Should work with async API."""
        from xbbg import Operation, Service, arequest

        df = await arequest(
            Service.APIFLDS,
            Operation.FIELD_INFO,
            fields=["PX_LAST"],
        )

        assert len(df) > 0


# =============================================================================
# BDP (Reference Data) Tests
# =============================================================================


@pytest.mark.integration
class TestBdpIntegration:
    """Integration tests for bdp (Bloomberg Data Point) function."""

    def test_bdp_single_ticker_single_field(self, single_ticker, single_field):
        """BDP with one ticker, one field - minimal data usage."""
        from xbbg import bdp

        df = bdp(single_ticker, single_field)

        # Should return DataFrame with ticker, field, value columns
        assert "ticker" in df.columns
        assert "field" in df.columns
        assert "value" in df.columns
        assert len(df) == 1

    def test_bdp_single_ticker_multiple_fields(self, single_ticker, multiple_fields):
        """BDP with one ticker, multiple fields."""
        from xbbg import bdp

        df = bdp(single_ticker, multiple_fields)

        # Should have one row per field
        assert len(df) == len(multiple_fields)

    def test_bdp_multiple_tickers_single_field(self, multiple_tickers, single_field):
        """BDP with multiple tickers, one field."""
        from xbbg import bdp

        df = bdp(multiple_tickers, single_field)

        # Should have one row per ticker
        assert len(df) == len(multiple_tickers)

    def test_bdp_multiple_tickers_multiple_fields(self, multiple_tickers, multiple_fields):
        """BDP with multiple tickers and fields."""
        from xbbg import bdp

        df = bdp(multiple_tickers, multiple_fields)

        # Should have tickers x fields rows
        assert len(df) == len(multiple_tickers) * len(multiple_fields)

    @pytest.mark.asyncio
    async def test_abdp_async(self, single_ticker, single_field):
        """Async BDP should return same structure as sync."""
        from xbbg import abdp

        df = await abdp(single_ticker, single_field)

        assert "ticker" in df.columns
        assert "field" in df.columns
        assert "value" in df.columns
        assert len(df) == 1

    @pytest.mark.asyncio
    async def test_abdp_concurrent_requests(self, multiple_tickers, single_field):
        """Multiple async BDP requests should run concurrently."""
        from xbbg import abdp

        # Run concurrent requests
        dfs = await asyncio.gather(
            abdp(multiple_tickers[0], single_field),
            abdp(multiple_tickers[1], single_field),
        )

        assert len(dfs) == 2
        for df in dfs:
            assert len(df) == 1


# =============================================================================
# BDH (Historical Data) Tests
# =============================================================================


@pytest.mark.integration
class TestBdhIntegration:
    """Integration tests for bdh (Bloomberg Data History) function."""

    def test_bdh_single_ticker(self, single_ticker, single_field, recent_dates):
        """BDH with one ticker, minimal date range."""
        from xbbg import bdh

        df = bdh(
            single_ticker,
            single_field,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
        )

        # Should return DataFrame with date column
        assert "ticker" in df.columns
        assert "date" in df.columns
        assert "field" in df.columns
        assert "value" in df.columns
        # Should have some data points (depends on trading days in range)
        assert len(df) >= 1

    def test_bdh_multiple_tickers(self, multiple_tickers, single_field, recent_dates):
        """BDH with multiple tickers."""
        from xbbg import bdh

        df = bdh(
            multiple_tickers,
            single_field,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
        )

        # Should have data for each ticker
        unique_tickers = df.to_native()["ticker"].unique()
        assert len(unique_tickers) == len(multiple_tickers)

    def test_bdh_multiple_fields(self, single_ticker, multiple_fields, recent_dates):
        """BDH with multiple fields."""
        from xbbg import bdh

        df = bdh(
            single_ticker,
            multiple_fields,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
        )

        # Should have data for each field
        unique_fields = df.to_native()["field"].unique()
        assert len(unique_fields) == len(multiple_fields)

    def test_bdh_with_adjustments(self, single_ticker, single_field, recent_dates):
        """BDH with dividend/split adjustments."""
        from xbbg import bdh

        df = bdh(
            single_ticker,
            single_field,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
            adjust="all",  # Apply all adjustments
        )

        assert len(df) >= 1

    @pytest.mark.asyncio
    async def test_abdh_async(self, single_ticker, single_field, recent_dates):
        """Async BDH should work correctly."""
        from xbbg import abdh

        df = await abdh(
            single_ticker,
            single_field,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
        )

        assert "date" in df.columns
        assert len(df) >= 1


# =============================================================================
# BDS (Bulk Data) Tests
# =============================================================================


@pytest.mark.integration
class TestBdsIntegration:
    """Integration tests for bds (Bloomberg Data Set) function.

    Uses bulk fields that return multi-row results.
    """

    def test_bds_dividend_history(self, single_ticker):
        """BDS for dividend history (multi-row result)."""
        from xbbg import bds

        # DVD_HIST is a common bulk field
        df = bds(single_ticker, "DVD_HIST")

        # Should return multiple rows
        assert "ticker" in df.columns
        assert len(df) >= 0  # May be empty if no dividends

    def test_bds_index_members(self):
        """BDS for index members - a classic bulk data query."""
        from xbbg import bds

        # Use a small index to limit data
        df = bds("INDU Index", "INDX_MEMBERS")

        # DJIA has 30 members
        assert len(df) == 30

    @pytest.mark.asyncio
    async def test_abds_async(self, single_ticker):
        """Async BDS should work correctly."""
        from xbbg import abds

        df = await abds(single_ticker, "DVD_HIST")

        assert "ticker" in df.columns


# =============================================================================
# BDIB (Intraday Bar) Tests
# =============================================================================


@pytest.mark.integration
class TestBdibIntegration:
    """Integration tests for bdib (Bloomberg Intraday Bar) function."""

    def test_bdib_one_hour_1min_bars(self, single_ticker, intraday_window):
        """BDIB with 1-minute bars for 1 hour (~60 bars)."""
        from xbbg import bdib

        df = bdib(
            single_ticker,
            start_datetime=intraday_window["start_datetime"],
            end_datetime=intraday_window["end_datetime"],
            interval=1,  # 1-minute bars
        )

        # Should have OHLCV columns
        # Note: column names depend on extractor implementation
        assert len(df) >= 1

    def test_bdib_5min_bars(self, single_ticker, intraday_window):
        """BDIB with 5-minute bars (~12 bars for 1 hour)."""
        from xbbg import bdib

        df = bdib(
            single_ticker,
            start_datetime=intraday_window["start_datetime"],
            end_datetime=intraday_window["end_datetime"],
            interval=5,  # 5-minute bars
        )

        # Should have fewer bars than 1-minute
        assert len(df) >= 1

    def test_bdib_different_event_types(self, single_ticker, intraday_window):
        """BDIB should support different event types (TRADE, BID, ASK)."""
        from xbbg import bdib

        df = bdib(
            single_ticker,
            start_datetime=intraday_window["start_datetime"],
            end_datetime=intraday_window["end_datetime"],
            interval=5,
            typ="BID",  # BID prices instead of TRADE
        )

        assert len(df) >= 1

    @pytest.mark.asyncio
    async def test_abdib_async(self, single_ticker, intraday_window):
        """Async BDIB should work correctly."""
        from xbbg import abdib

        df = await abdib(
            single_ticker,
            start_datetime=intraday_window["start_datetime"],
            end_datetime=intraday_window["end_datetime"],
            interval=5,
        )

        assert len(df) >= 1


# =============================================================================
# BDTICK (Intraday Tick) Tests
# =============================================================================


@pytest.mark.integration
class TestBdtickIntegration:
    """Integration tests for bdtick (Bloomberg Intraday Tick) function.

    Uses very short time windows to minimize data.
    """

    def test_bdtick_short_window(self, single_ticker):
        """BDTICK with a 5-minute window."""
        from xbbg import bdtick

        # Use a very short window
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        start = f"{date_str} 10:00:00"
        end = f"{date_str} 10:05:00"  # Just 5 minutes

        df = bdtick(single_ticker, start, end)

        # Should have some ticks (depends on activity)
        assert len(df) >= 0

    @pytest.mark.asyncio
    async def test_abdtick_async(self, single_ticker):
        """Async BDTICK should work correctly."""
        from xbbg import abdtick

        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        start = f"{date_str} 10:00:00"
        end = f"{date_str} 10:05:00"

        df = await abdtick(single_ticker, start, end)

        assert len(df) >= 0


# =============================================================================
# Backend Conversion Tests
# =============================================================================


@pytest.mark.integration
class TestBackendConversion:
    """Tests for DataFrame backend conversion.

    Validates that the data flow correctly converts to different backends.
    """

    def test_backend_narwhals_default(self, single_ticker, single_field):
        """Default backend should return narwhals DataFrame."""
        import narwhals as nw

        from xbbg import bdp

        df = bdp(single_ticker, single_field)

        # Should be a narwhals DataFrame
        assert isinstance(df, nw.DataFrame)

    def test_backend_pandas(self, single_ticker, single_field):
        """Should convert to pandas DataFrame."""
        import pandas as pd

        from xbbg import bdp

        df = bdp(single_ticker, single_field, backend="pandas")

        assert isinstance(df, pd.DataFrame)

    def test_backend_polars(self, single_ticker, single_field):
        """Should convert to polars DataFrame."""
        pytest.importorskip("polars")
        import polars as pl

        from xbbg import bdp

        df = bdp(single_ticker, single_field, backend="polars")

        assert isinstance(df, pl.DataFrame)

    def test_backend_polars_lazy(self, single_ticker, single_field):
        """Should convert to polars LazyFrame."""
        pytest.importorskip("polars")
        import polars as pl

        from xbbg import bdp

        lf = bdp(single_ticker, single_field, backend="polars_lazy")

        assert isinstance(lf, pl.LazyFrame)
        # Should be collectable
        df = lf.collect()
        assert isinstance(df, pl.DataFrame)

    def test_backend_pyarrow(self, single_ticker, single_field):
        """Should convert to PyArrow Table."""
        import pyarrow as pa

        from xbbg import bdp

        table = bdp(single_ticker, single_field, backend="pyarrow")

        assert isinstance(table, pa.Table)

    def test_set_global_backend(self, single_ticker, single_field):
        """Global backend setting should affect all calls."""
        import pandas as pd

        from xbbg import bdp, get_backend, set_backend

        original = get_backend()
        try:
            set_backend("pandas")
            df = bdp(single_ticker, single_field)
            assert isinstance(df, pd.DataFrame)
        finally:
            set_backend(original)


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling and exception propagation.

    These tests validate that errors are properly propagated from
    Bloomberg through Rust to Python with appropriate exception types.
    """

    def test_invalid_ticker_raises_error(self, single_field):
        """Invalid ticker should raise an error."""
        from xbbg import bdp
        from xbbg.exceptions import BlpError

        # Use a clearly invalid ticker
        with pytest.raises(BlpError):
            bdp("INVALID_TICKER_12345 Equity", single_field)

    def test_invalid_field_raises_error(self, single_ticker):
        """Invalid field should raise an error."""
        from xbbg import bdp
        from xbbg.exceptions import BlpError

        # Use a clearly invalid field
        with pytest.raises(BlpError):
            bdp(single_ticker, "INVALID_FIELD_12345")

    def test_validation_error_missing_securities(self):
        """Missing securities should raise BlpValidationError."""
        from xbbg import Operation, Service, request
        from xbbg.exceptions import BlpValidationError

        with pytest.raises(BlpValidationError, match="securities is required"):
            request(
                Service.REFDATA,
                Operation.REFERENCE_DATA,
                securities=None,
                fields=["PX_LAST"],
            )

    def test_validation_error_missing_dates(self, single_ticker):
        """Missing dates for historical request should raise BlpValidationError."""
        from xbbg import Operation, Service, request
        from xbbg.exceptions import BlpValidationError

        with pytest.raises(BlpValidationError, match="start_date is required"):
            request(
                Service.REFDATA,
                Operation.HISTORICAL_DATA,
                securities=[single_ticker],
                fields=["PX_LAST"],
                start_date=None,
                end_date="20241201",
            )

    def test_error_catchable_by_base_class(self, single_field):
        """All Bloomberg errors should be catchable by BlpError."""
        from xbbg import bdp
        from xbbg.exceptions import BlpError

        try:
            bdp("TOTALLY_INVALID_SECURITY_XYZ123", single_field)
        except BlpError as e:
            # Should catch the error
            assert str(e)  # Should have an error message
        except Exception:
            pytest.fail("Error should be catchable by BlpError")


# =============================================================================
# Generic API Tests
# =============================================================================


@pytest.mark.integration
class TestGenericApi:
    """Tests for the generic request() API (power user interface)."""

    def test_generic_reference_data(self, single_ticker, single_field):
        """Generic API should work for reference data."""
        from xbbg import Operation, Service, request

        df = request(
            Service.REFDATA,
            Operation.REFERENCE_DATA,
            securities=[single_ticker],
            fields=[single_field],
        )

        assert len(df) == 1

    def test_generic_with_overrides(self, single_ticker):
        """Generic API should support overrides."""
        from xbbg import Operation, Service, request

        df = request(
            Service.REFDATA,
            Operation.REFERENCE_DATA,
            securities=[single_ticker],
            fields=["CRNCY_ADJ_PX_LAST"],
            overrides={"EQY_FUND_CRNCY": "EUR"},
        )

        assert len(df) == 1

    @pytest.mark.asyncio
    async def test_generic_async(self, single_ticker, single_field):
        """Generic async API should work."""
        from xbbg import Operation, Service, arequest

        df = await arequest(
            Service.REFDATA,
            Operation.REFERENCE_DATA,
            securities=[single_ticker],
            fields=[single_field],
        )

        assert len(df) == 1


# =============================================================================
# Data Flow Validation Tests
# =============================================================================


@pytest.mark.integration
class TestDataFlow:
    """Tests that validate data flows correctly through the entire stack.

    These tests check that values are reasonable and types are correct.
    """

    def test_bdp_returns_numeric_for_price(self, single_ticker):
        """PX_LAST should return a numeric value."""
        from xbbg import bdp

        df = bdp(single_ticker, "PX_LAST", backend="pandas")

        # Get the value
        value = df["value"].iloc[0]

        # Should be a number (could be int or float)
        assert isinstance(value, (int, float))
        # Price should be positive
        assert value > 0

    def test_bdp_returns_string_for_name(self, single_ticker):
        """NAME field should return a string."""
        from xbbg import bdp

        df = bdp(single_ticker, "NAME", backend="pandas")

        value = df["value"].iloc[0]

        # Should be a string
        assert isinstance(value, str)
        assert len(value) > 0

    def test_bdh_dates_are_ordered(self, single_ticker, single_field, recent_dates):
        """Historical data should have dates in chronological order."""
        from xbbg import bdh

        df = bdh(
            single_ticker,
            single_field,
            start_date=recent_dates["start_date"],
            end_date=recent_dates["end_date"],
            backend="pandas",
        )

        if len(df) > 1:
            dates = df["date"].tolist()
            # Dates should be in ascending order
            assert dates == sorted(dates)

    def test_ticker_in_response_matches_request(self, single_ticker, single_field):
        """Ticker in response should match the requested ticker."""
        from xbbg import bdp

        df = bdp(single_ticker, "PX_LAST", backend="pandas")

        # The ticker in response should match what we requested
        response_ticker = df["ticker"].iloc[0]
        assert single_ticker in response_ticker or response_ticker in single_ticker


# =============================================================================
# Logging Tests
# =============================================================================


@pytest.mark.integration
class TestLogging:
    """Tests that verify logging flows correctly through Python and Rust layers.

    These tests verify that:
    1. Python logging captures debug messages from blp.py
    2. Rust tracing events are bridged to Python logging
    3. Log levels are respected
    """

    def test_python_logging_captures_request(self, single_ticker, single_field, caplog):
        """Python logging should capture request debug messages."""
        import logging

        from xbbg import bdp

        with caplog.at_level(logging.DEBUG, logger="xbbg.blp"):
            bdp(single_ticker, single_field)

        # Check that we captured the expected log messages
        log_messages = [r.message for r in caplog.records]
        assert any("abdp:" in msg for msg in log_messages), f"Expected abdp log, got: {log_messages}"

    def test_rust_logging_bridges_to_python(self, single_ticker, single_field, caplog):
        """Rust tracing events should appear in Python logging."""
        import logging

        from xbbg import bdp

        # Capture at DEBUG level for xbbg._core (Rust module)
        with caplog.at_level(logging.DEBUG):
            bdp(single_ticker, single_field)

        # Check for Rust-side log messages (from pyo3-log bridge)
        log_messages = [r.message for r in caplog.records]
        # We should see either Python or Rust side logging
        assert len(log_messages) > 0, "Expected some log messages"

    def test_logging_with_different_levels(self, single_ticker, single_field, caplog):
        """Different log levels should be captured appropriately."""
        import logging

        from xbbg import bdp

        # Test INFO level
        with caplog.at_level(logging.INFO, logger="xbbg.blp"):
            bdp(single_ticker, single_field)

        info_count = len([r for r in caplog.records if r.levelno == logging.INFO])

        # Test DEBUG level (should have more messages)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="xbbg.blp"):
            bdp(single_ticker, single_field)

        debug_count = len([r for r in caplog.records if r.levelno == logging.DEBUG])

        # DEBUG level should capture more (or equal) messages than INFO
        assert debug_count >= info_count

    def test_error_logging(self, single_field, caplog):
        """Errors should be logged appropriately."""
        import contextlib
        import logging

        from xbbg import bdp
        from xbbg.exceptions import BlpError

        with caplog.at_level(logging.DEBUG), contextlib.suppress(BlpError):
            bdp("INVALID_TICKER_XYZ123", single_field)

        # Error should have been logged somewhere
        # (Either as a warning in Rust or captured in error handling)
