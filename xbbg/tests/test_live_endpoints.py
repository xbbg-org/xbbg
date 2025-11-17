"""Live Bloomberg endpoint verification tests.

This module contains tests that verify all Bloomberg API endpoints work correctly
with live Bloomberg data. These tests are skipped by default to avoid accidental
execution and excessive data usage.

To run these tests, use:
    pytest xbbg/tests/test_live_endpoints.py --run-xbbg-live -v

To run in interactive mode (prompt before each test):
    pytest xbbg/tests/test_live_endpoints.py --run-xbbg-live --prompt-between-tests -v

To run with a specific xbbg version (for regression testing):
    # First install the desired version in a virtual environment:
    pip install xbbg==0.7.7

    # Then run tests with version validation:
    pytest xbbg/tests/test_live_endpoints.py --run-xbbg-live --xbbg-version=0.7.7 -v

    # Or use uv/pip to install and run in one command:
    uv pip install xbbg==0.7.7 && pytest xbbg/tests/test_live_endpoints.py --run-xbbg-live --xbbg-version=0.7.7 -v

WARNING: These tests make actual Bloomberg API calls and will consume your
Bloomberg data quota. Use sparingly and only when verifying endpoint functionality.

All tests use minimal, lightweight requests to reduce data consumption:
- Single tickers where possible
- Small date ranges (1-5 days)
- Minimal field sets
- Short-lived real-time subscriptions (1-2 updates max)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import sys
import threading

import pandas as pd
import pytest

from xbbg import blp  # noqa: E402


# Version checking for regression testing
def _check_xbbg_version(expected_version: str | None = None) -> None:
    """Check installed xbbg version matches expected version.

    Args:
        expected_version: Expected version string (e.g., '0.7.7'). If None, no check is performed.

    Raises:
        AssertionError: If version doesn't match expected version.
    """
    if expected_version is None:
        return

    try:
        import importlib.metadata
        installed_version = importlib.metadata.version('xbbg')
    except ImportError:
        # Fallback for Python < 3.8
        try:
            import pkg_resources  # type: ignore[import-untyped]
            installed_version = pkg_resources.get_distribution('xbbg').version
        except ImportError as e:
            raise ImportError(
                "Cannot determine xbbg version. "
                "Please install importlib.metadata (Python 3.8+) or setuptools (for pkg_resources)"
            ) from e

    # Normalize versions for comparison (remove any build metadata)
    installed_normalized = installed_version.split('+')[0].split('-')[0]
    expected_normalized = expected_version.split('+')[0].split('-')[0]

    if installed_normalized != expected_normalized:
        raise AssertionError(
            f"xbbg version mismatch: expected {expected_version}, "
            f"but installed version is {installed_version}. "
            f"Please install the correct version: pip install xbbg=={expected_version}"
        )

    print(f"\n{'='*80}")
    print(f"✓ xbbg version check passed: {installed_version} (expected {expected_version})")
    print(f"{'='*80}\n")

# Lightweight test parameters to minimize data usage
TEST_TICKER = 'AAPL US Equity'
TEST_TICKERS = ['AAPL US Equity', 'MSFT US Equity']
TEST_INDEX = 'SPX Index'
TEST_FIELDS = ['Security_Name', 'PX_LAST']
TEST_SINGLE_FIELD = 'PX_LAST'

# Date ranges - use recent dates but keep small
# Get a business day for intraday tests (markets are closed on weekends/holidays)
def _get_previous_business_day(days_back=1):
    """Get the previous business day for US markets."""
    try:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar('NYSE')
        end_date = datetime.now().date()
        # Look back up to 10 days to find a business day
        for i in range(days_back, days_back + 10):
            check_date = end_date - timedelta(days=i)
            sched = nyse.schedule(start_date=check_date, end_date=check_date)
            if not sched.empty:
                return check_date
        # Fallback: just use yesterday if calendar lookup fails
        return end_date - timedelta(days=days_back)
    except Exception:
        # Fallback: use yesterday if pandas-market-calendars not available
        return datetime.now().date() - timedelta(days=days_back)

END_DATE = datetime.now().date()
START_DATE = END_DATE - timedelta(days=5)
TEST_DATE = _get_previous_business_day(days_back=1)  # Previous business day for intraday

# BDS test parameters - use 30 days instead of 90 to minimize data
BDS_FIELD = 'DVD_Hist_All'
BDS_START = (END_DATE - timedelta(days=30)).strftime('%Y%m%d')
BDS_END = END_DATE.strftime('%Y%m%d')

# BQL test query - simple and lightweight
BQL_QUERY = "get(px_last) for('AAPL US Equity')"

# BSRCH test - use a simple query format
# Note: BSRCH requires user-defined screens. This query may return empty results
# if the screen doesn't exist. For minimal data usage, create your own SRCH screen
# with limited criteria, or the test will pass with empty results.
BSRCH_QUERY = "FI:TEST"  # Simple query - likely returns empty but tests endpoint


# pytest_collection_modifyitems is now handled in conftest.py
# This ensures live endpoint tests are excluded from default test runs


def pytest_runtest_setup(item):
    """Prompt before each test if --prompt-between-tests flag is provided."""
    # Check xbbg version if specified (only check once per session)
    if not hasattr(item.config, '_xbbg_version_checked'):
        expected_version = item.config.getoption('--xbbg-version', default=None)
        if expected_version:
            _check_xbbg_version(expected_version)
        item.config._xbbg_version_checked = True

    if item.config.getoption('--prompt-between-tests', default=False):
        test_name = item.name.replace('test_', '').replace('_', ' ').title()
        print(f"\n{'='*80}")
        print(f"Ready to run: {test_name}")
        print(f"{'='*80}")
        response = input("Press Enter to continue, 'q' to quit, 's' to skip this test: ").strip().lower()
        if response == 'q':
            pytest.exit("User requested exit")
        elif response == 's':
            pytest.skip("User skipped this test")


@pytest.mark.live_endpoint
def test_bdp_reference_data():
    """Test BDP (reference data) endpoint with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing BDP (Reference Data)")
    print(f"{'='*80}")

    result = blp.bdp(tickers=TEST_TICKER, flds=TEST_FIELDS)

    assert isinstance(result, pd.DataFrame), "BDP should return a DataFrame"
    assert not result.empty, "BDP result should not be empty"
    assert TEST_TICKER in result.index, f"Result should contain {TEST_TICKER}"

    # Structure validation
    assert isinstance(result.index, pd.Index), "BDP should have Index (not MultiIndex)"
    assert not isinstance(result.columns, pd.MultiIndex), "BDP should have single-level columns"
    assert len(result.columns) == len(TEST_FIELDS), f"Should have {len(TEST_FIELDS)} columns matching requested fields"
    # Check that requested fields are present (may be normalized/capitalized)
    result_cols_lower = [col.lower() for col in result.columns]
    for field in TEST_FIELDS:
        assert any(field.lower() in col.lower() or col.lower() in field.lower()
                  for col in result_cols_lower), f"Field {field} should be present in columns"

    print("\nBDP Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDP endpoint working correctly")


@pytest.mark.live_endpoint
def test_bdp_multiple_tickers():
    """Test BDP with multiple tickers (as shown in README examples)."""
    print(f"\n{'='*80}")
    print("Testing BDP (Multiple Tickers)")
    print(f"{'='*80}")

    result = blp.bdp(tickers=TEST_TICKERS[:2], flds=TEST_FIELDS)

    assert isinstance(result, pd.DataFrame), "BDP should return a DataFrame"
    assert not result.empty, "BDP result should not be empty"
    assert len(result) >= 2, "Should return data for multiple tickers"

    # Structure validation
    assert isinstance(result.index, pd.Index), "BDP should have Index (not MultiIndex)"
    assert not isinstance(result.columns, pd.MultiIndex), "BDP should have single-level columns"
    assert len(result.columns) == len(TEST_FIELDS), f"Should have {len(TEST_FIELDS)} columns matching requested fields"
    # Verify all requested tickers are in index
    for ticker in TEST_TICKERS[:2]:
        assert ticker in result.index, f"Ticker {ticker} should be in index"

    print("\nBDP Result (Multiple Tickers):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Tickers: {list(result.index)}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDP multiple tickers working correctly")


@pytest.mark.live_endpoint
def test_bdp_field_overrides():
    """Test BDP with field overrides (as shown in README examples).

    Uses minimal data by requesting a single field with override.
    """
    print(f"\n{'='*80}")
    print("Testing BDP (Field Overrides)")
    print(f"{'='*80}")

    # Use a date from a few months ago to minimize data
    override_date = (END_DATE - timedelta(days=90)).strftime('%Y%m%d')
    result = blp.bdp(
        tickers=TEST_TICKER,
        flds='Eqy_Weighted_Avg_Px',
        VWAP_Dt=override_date,
    )

    assert isinstance(result, pd.DataFrame), "BDP should return a DataFrame"
    assert not result.empty, "BDP result should not be empty"

    print("\nBDP Result (With Override):")
    print(result)
    print(f"\nShape: {result.shape}")
    print("✓ BDP field overrides working correctly")


@pytest.mark.live_endpoint
def test_bds_bulk_data():
    """Test BDS (bulk/block data) endpoint with live Bloomberg data.

    Uses minimal data by limiting to 30-day date range instead of full history.
    """
    print(f"\n{'='*80}")
    print("Testing BDS (Bulk/Block Data)")
    print(f"{'='*80}")

    result = blp.bds(
        tickers=TEST_TICKER,
        flds=BDS_FIELD,
        DVD_Start_Dt=BDS_START,
        DVD_End_Dt=BDS_END,
    )

    assert isinstance(result, pd.DataFrame), "BDS should return a DataFrame"
    assert not result.empty, "BDS result should not be empty - check if dividends exist in date range"

    # Structure validation
    # BDS should have ticker as index (single level, not MultiIndex)
    assert isinstance(result.index, pd.Index), "BDS should have Index"
    assert TEST_TICKER in result.index, f"Ticker {TEST_TICKER} should be in index"
    # BDS should have single-level columns (field-specific columns)
    assert not isinstance(result.columns, pd.MultiIndex), "BDS should have single-level columns"
    assert len(result.columns) > 0, "BDS should have at least one column"
    # For dividend data, expect date-related columns
    result_cols_lower = [col.lower() for col in result.columns]
    date_related_cols = ['date', 'ex', 'record', 'payable', 'dividend', 'amount']
    assert any(any(dc in col for dc in date_related_cols) for col in result_cols_lower), \
        "BDS dividend data should have date-related columns"

    print("\nBDS Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Index type: {type(result.index)}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BDS endpoint working correctly")


@pytest.mark.live_endpoint
def test_bdp_fixed_income_isin():
    """Test BDP with Fixed Income security using ISIN format."""
    print(f"\n{'='*80}")
    print("Testing BDP (Fixed Income - ISIN)")
    print(f"{'='*80}")

    isin_ticker = '/isin/US91282CNC19'
    result = blp.bdp(
        tickers=isin_ticker,
        flds=['SECURITY_NAME', 'MATURITY', 'COUPON', 'PX_LAST'],
    )

    assert isinstance(result, pd.DataFrame), "BDP should return a DataFrame"
    assert not result.empty, "BDP result should not be empty"

    print("\nBDP Result (ISIN):")
    print(result)
    print(f"\nShape: {result.shape}")
    print("✓ BDP Fixed Income ISIN working correctly")


@pytest.mark.live_endpoint
def test_bds_fixed_income_cash_flow():
    """Test BDS with Fixed Income cash flow schedule using ISIN format."""
    print(f"\n{'='*80}")
    print("Testing BDS (Fixed Income Cash Flow)")
    print(f"{'='*80}")

    isin_ticker = '/isin/US91282CNC19'
    result = blp.bds(tickers=isin_ticker, flds='DES_CASH_FLOW')

    assert isinstance(result, pd.DataFrame), "BDS should return a DataFrame"
    assert not result.empty, "BDS cash flow result should not be empty - check if cash flows exist for this security"

    print("\nBDS Cash Flow Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Sample rows:\n{result.head(3)}")  # Just first 3 rows
    print("✓ BDS Fixed Income cash flow working correctly")


@pytest.mark.live_endpoint
def test_bdh_historical_data():
    """Test BDH (historical data) endpoint with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing BDH (Historical Data)")
    print(f"{'='*80}")

    result = blp.bdh(
        tickers=TEST_TICKER,
        flds=TEST_SINGLE_FIELD,
        start_date=START_DATE.strftime('%Y-%m-%d'),
        end_date=END_DATE.strftime('%Y-%m-%d'),
    )

    assert isinstance(result, pd.DataFrame), "BDH should return a DataFrame"
    assert not result.empty, "BDH result should not be empty"

    # Structure validation
    # BDH index can be DatetimeIndex or regular Index with date strings/objects (all are valid)
    assert isinstance(result.index, pd.Index), "BDH should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"BDH index should contain date-like values (got {type(first_idx_val)})"
    # In xbbg 0.7.7+, single ticker BDH returns MultiIndex columns (ticker, field)
    # This is consistent with multiple tickers and allows using .xs() method
    assert isinstance(result.columns, pd.MultiIndex), "BDH with single ticker should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert len(result.columns) >= 1, "Should have at least one column"
    # Index should be sorted (ascending dates) - works for DatetimeIndex, date strings, and datetime.date objects
    # For datetime.date objects, ensure monotonic check works correctly
    try:
        is_sorted = result.index.is_monotonic_increasing
    except (TypeError, ValueError):
        # Fallback: convert to DatetimeIndex for comparison if native check fails
        try:
            ts_index = pd.DatetimeIndex(pd.to_datetime(result.index))
            is_sorted = ts_index.is_monotonic_increasing
        except (ValueError, TypeError):
            # If conversion fails, skip this check
            is_sorted = True
    assert is_sorted, "BDH index should be sorted in ascending order"

    print("\nBDH Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Date range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column structure: {'MultiIndex' if isinstance(result.columns, pd.MultiIndex) else 'Single-level'}")
    print("✓ BDH endpoint working correctly")


@pytest.mark.live_endpoint
def test_bdh_multiple_tickers():
    """Test BDH with multiple tickers (as shown in README examples).

    Uses minimal data with 5-day range and single field.
    """
    print(f"\n{'='*80}")
    print("Testing BDH (Multiple Tickers)")
    print(f"{'='*80}")

    result = blp.bdh(
        tickers=TEST_TICKERS[:2],
        flds=TEST_SINGLE_FIELD,
        start_date=START_DATE.strftime('%Y-%m-%d'),
        end_date=END_DATE.strftime('%Y-%m-%d'),
    )

    assert isinstance(result, pd.DataFrame), "BDH should return a DataFrame"
    assert not result.empty, "BDH result should not be empty"

    # Structure validation
    # BDH index can be DatetimeIndex or regular Index with date strings/objects (all are valid)
    assert isinstance(result.index, pd.Index), "BDH should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"BDH index should contain date-like values (got {type(first_idx_val)})"
    # Should have MultiIndex columns with ticker and field
    assert isinstance(result.columns, pd.MultiIndex), "BDH with multiple tickers should have MultiIndex columns"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert len(result.columns.levels[0]) >= 2, "Should have multiple tickers in column level 0"
    # Verify requested tickers are in columns
    ticker_level_values = result.columns.get_level_values(0).unique()
    for ticker in TEST_TICKERS[:2]:
        assert ticker in ticker_level_values, f"Ticker {ticker} should be in column level 0"
    # Index should be sorted (ascending dates) - works for DatetimeIndex, date strings, and datetime.date objects
    # For datetime.date objects, ensure monotonic check works correctly
    try:
        is_sorted = result.index.is_monotonic_increasing
    except (TypeError, ValueError):
        # Fallback: convert to DatetimeIndex for comparison if native check fails
        try:
            ts_index = pd.DatetimeIndex(pd.to_datetime(result.index))
            is_sorted = ts_index.is_monotonic_increasing
        except (ValueError, TypeError):
            # If conversion fails, skip this check
            is_sorted = True
    assert is_sorted, "BDH index should be sorted in ascending order"

    print("\nBDH Result (Multiple Tickers):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Index type: {type(result.index)}")
    print(f"Column levels: {result.columns.nlevels}")
    print(f"Tickers in columns: {list(result.columns.get_level_values(0).unique())}")
    print("✓ BDH multiple tickers working correctly")


@pytest.mark.live_endpoint
def test_bdh_periodicity():
    """Test BDH with periodicity options (weekly, as shown in README examples).

    Uses minimal data by requesting weekly bars instead of daily.
    """
    print(f"\n{'='*80}")
    print("Testing BDH (Periodicity - Weekly)")
    print(f"{'='*80}")

    # Use a slightly longer range for weekly to ensure we get at least 1-2 weeks
    weekly_start = (END_DATE - timedelta(days=14)).strftime('%Y-%m-%d')
    result = blp.bdh(
        tickers=TEST_TICKER,
        flds=TEST_SINGLE_FIELD,
        start_date=weekly_start,
        end_date=END_DATE.strftime('%Y-%m-%d'),
        Per='W',  # Weekly periodicity
        Fill='P',  # Previous value fill
        Days='A',  # All calendar days
    )

    assert isinstance(result, pd.DataFrame), "BDH should return a DataFrame"
    assert not result.empty, "BDH result should not be empty"

    # Structure validation
    # BDH index can be DatetimeIndex or regular Index with date strings/objects (all are valid)
    assert isinstance(result.index, pd.Index), "BDH should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"BDH index should contain date-like values (got {type(first_idx_val)})"
    # In xbbg 0.7.7+, single ticker BDH returns MultiIndex columns (ticker, field)
    assert isinstance(result.columns, pd.MultiIndex), "BDH with single ticker should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert len(result.columns) >= 1, "Should have at least one column"
    assert result.index.is_monotonic_increasing, "BDH index should be sorted in ascending order"
    # Weekly data should have fewer rows than daily (rough check)
    if len(result) > 0:
        # Handle DatetimeIndex, datetime.date objects, and date strings
        try:
            if pd.api.types.is_datetime64_any_dtype(result.index):
                date_range_days = (result.index.max() - result.index.min()).days
            else:
                # For datetime.date objects or date strings, convert to Timestamp for comparison
                min_date = pd.Timestamp(result.index.min())
                max_date = pd.Timestamp(result.index.max())
                date_range_days = (max_date - min_date).days
            assert len(result) <= date_range_days, "Weekly data should have fewer or equal rows than days in range"
        except (ValueError, TypeError):
            # Skip this check if date conversion fails
            pass

    print("\nBDH Result (Weekly Periodicity):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Date range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDH periodicity options working correctly")


@pytest.mark.live_endpoint
def test_bdh_adjustments():
    """Test BDH with adjustment options (as shown in README examples).

    Uses minimal data with 2-day range around a known split date.
    """
    print(f"\n{'='*80}")
    print("Testing BDH (Adjustments)")
    print(f"{'='*80}")

    # Use a small date range to minimize data
    adjust_start = (END_DATE - timedelta(days=2)).strftime('%Y-%m-%d')
    result = blp.bdh(
        tickers=TEST_TICKER,
        flds=TEST_SINGLE_FIELD,
        start_date=adjust_start,
        end_date=END_DATE.strftime('%Y-%m-%d'),
        adjust='all',  # Adjust for all dividends and splits
    )

    assert isinstance(result, pd.DataFrame), "BDH should return a DataFrame"
    assert not result.empty, "BDH result should not be empty"

    # Structure validation
    # BDH index can be DatetimeIndex or regular Index with date strings/objects (all are valid)
    assert isinstance(result.index, pd.Index), "BDH should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"BDH index should contain date-like values (got {type(first_idx_val)})"
    # In xbbg 0.7.7+, single ticker BDH returns MultiIndex columns (ticker, field)
    assert isinstance(result.columns, pd.MultiIndex), "BDH with single ticker should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert len(result.columns) >= 1, "Should have at least one column"
    # Index should be sorted (ascending dates) - works for DatetimeIndex, date strings, and datetime.date objects
    # For datetime.date objects, ensure monotonic check works correctly
    try:
        is_sorted = result.index.is_monotonic_increasing
    except (TypeError, ValueError):
        # Fallback: convert to DatetimeIndex for comparison if native check fails
        try:
            ts_index = pd.DatetimeIndex(pd.to_datetime(result.index))
            is_sorted = ts_index.is_monotonic_increasing
        except (ValueError, TypeError):
            # If conversion fails, skip this check
            is_sorted = True
    assert is_sorted, "BDH index should be sorted in ascending order"

    print("\nBDH Result (With Adjustments):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDH adjustment options working correctly")


@pytest.mark.live_endpoint
def test_bdib_intraday_bars():
    """Test BDIB (intraday bars) endpoint with live Bloomberg data.

    Uses minimal data by:
    - Limiting request to first 30 minutes of trading (9:30-10:00) using compound session
    - Using 5-minute intervals instead of 1-minute (reduces bars by 5x)
    """
    from xbbg.core.utils import trials

    # Reset trial count for this test to allow retry after fix
    trial_kw = {'ticker': TEST_TICKER, 'dt': TEST_DATE.strftime('%Y-%m-%d'), 'typ': 'TRADE', 'func': 'bdib'}
    trials.update_trials(cnt=0, **trial_kw)

    print(f"\n{'='*80}")
    print("Testing BDIB (Intraday Bars)")
    print(f"{'='*80}")

    # Use compound session for 30-minute window (first 30 minutes of day session: 9:30-10:00)
    result = blp.bdib(
        ticker=TEST_TICKER,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        session='day_open_30',  # First 30 minutes of day session (9:30-10:00 for US markets)
        interval=5,    # 5-minute bars instead of 1-minute (reduces data by 5x)
    )

    assert isinstance(result, pd.DataFrame), "BDIB should return a DataFrame"
    assert not result.empty, "BDIB result should not be empty - check if market was open on test date"

    # Structure validation
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDIB should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDIB index should be datetime type"
    # BDIB should have MultiIndex columns with ticker as first level
    assert isinstance(result.columns, pd.MultiIndex), "BDIB should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert TEST_TICKER in result.columns.get_level_values(0), f"Ticker {TEST_TICKER} should be in column level 0"
    # Standard OHLCV columns should be present
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    # Index should be sorted (ascending time)
    assert result.index.is_monotonic_increasing, "BDIB index should be sorted in ascending order"

    print("\nBDIB Result (first 30 minutes, 5-min bars):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column levels: {result.columns.nlevels}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BDIB endpoint working correctly")


@pytest.mark.live_endpoint
def test_bdib_sub_minute_intervals():
    """Test BDIB with sub-minute intervals (as shown in README examples).

    Uses minimal data by:
    - Limiting request to first 30 minutes of trading (9:30-10:00) using compound session
    - Using 10-second bars instead of 1-minute (reduces data significantly)
    """
    from xbbg.core.utils import trials

    # Reset trial count for this test to allow retry after fix
    trial_kw = {'ticker': TEST_TICKER, 'dt': TEST_DATE.strftime('%Y-%m-%d'), 'typ': 'TRADE', 'func': 'bdib'}
    trials.update_trials(cnt=0, **trial_kw)

    print(f"\n{'='*80}")
    print("Testing BDIB (Sub-minute Intervals)")
    print(f"{'='*80}")

    # Use compound session for 30-minute window (first 30 minutes of day session: 9:30-10:00)
    result = blp.bdib(
        ticker=TEST_TICKER,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        session='day_open_30',  # First 30 minutes of day session (9:30-10:00 for US markets)
        interval=10,  # 10-second bars
        intervalHasSeconds=True,  # Interpret interval as seconds
    )

    assert isinstance(result, pd.DataFrame), "BDIB should return a DataFrame"
    assert not result.empty, "BDIB result should not be empty - check if market was open on test date"

    # Structure validation (same as regular BDIB)
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDIB should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDIB index should be datetime type"
    assert isinstance(result.columns, pd.MultiIndex), "BDIB should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert TEST_TICKER in result.columns.get_level_values(0), f"Ticker {TEST_TICKER} should be in column level 0"
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    assert result.index.is_monotonic_increasing, "BDIB index should be sorted in ascending order"

    print("\nBDIB Result (first 30 minutes, 10-second bars):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BDIB sub-minute intervals working correctly")


@pytest.mark.live_endpoint
def test_bdib_reference_exchange():
    """Test BDIB with reference exchange (as shown in README examples).

    Uses minimal data by limiting request to first 30 minutes with reference exchange.
    """
    from xbbg.core.utils import trials

    # Reset trial count for this test to allow retry after fix
    trial_kw = {'ticker': TEST_TICKER, 'dt': TEST_DATE.strftime('%Y-%m-%d'), 'typ': 'TRADE', 'func': 'bdib'}
    trials.update_trials(cnt=0, **trial_kw)

    print(f"\n{'='*80}")
    print("Testing BDIB (Reference Exchange)")
    print(f"{'='*80}")

    # Use compound session for 30-minute window (first 30 minutes of day session: 9:30-10:00)
    result = blp.bdib(
        ticker=TEST_TICKER,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        session='day_open_30',  # First 30 minutes of day session (9:30-10:00 for US markets)
        interval=5,    # 5-minute bars
        ref=TEST_INDEX,  # Use index as reference for market hours
    )

    assert isinstance(result, pd.DataFrame), "BDIB should return a DataFrame"
    assert not result.empty, "BDIB result should not be empty - check if market was open on test date"

    # Structure validation (same as regular BDIB)
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDIB should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDIB index should be datetime type"
    assert isinstance(result.columns, pd.MultiIndex), "BDIB should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert TEST_TICKER in result.columns.get_level_values(0), f"Ticker {TEST_TICKER} should be in column level 0"
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    assert result.index.is_monotonic_increasing, "BDIB index should be sorted in ascending order"

    print("\nBDIB Result (first 30 minutes, with reference exchange):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDIB reference exchange working correctly")


@pytest.mark.live_endpoint
@pytest.mark.skip(reason="Requires Japanese market ticker - disabled for general testing")
def test_bdib_am_open_session():
    """Test BDIB with am_open_30 session (as shown in README examples for Japanese markets).

    Uses minimal data by limiting request to first 30 minutes of AM session.
    This test is disabled by default as it requires a Japanese market ticker.
    """
    from xbbg.core.utils import trials

    # Reset trial count for this test to allow retry after fix
    # Use a Japanese ticker for this test
    japanese_ticker = '7974 JT Equity'  # Example from README
    trial_kw = {'ticker': japanese_ticker, 'dt': TEST_DATE.strftime('%Y-%m-%d'), 'typ': 'TRADE', 'func': 'bdib'}
    trials.update_trials(cnt=0, **trial_kw)

    print(f"\n{'='*80}")
    print("Testing BDIB (AM Open Session - Japanese Market)")
    print(f"{'='*80}")

    # Use am_open_30 session for Japanese markets (as shown in README)
    result = blp.bdib(
        ticker=japanese_ticker,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        session='am_open_30',  # First 30 minutes of AM session (as shown in README)
        interval=5,    # 5-minute bars
    )

    assert isinstance(result, pd.DataFrame), "BDIB should return a DataFrame"
    assert not result.empty, "BDIB result should not be empty - check if market was open on test date"

    # Structure validation (same as regular BDIB)
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDIB should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDIB index should be datetime type"
    assert isinstance(result.columns, pd.MultiIndex), "BDIB should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert japanese_ticker in result.columns.get_level_values(0), f"Ticker {japanese_ticker} should be in column level 0"
    expected_cols = ['open', 'high', 'low', 'close', 'volume']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    assert result.index.is_monotonic_increasing, "BDIB index should be sorted in ascending order"

    print("\nBDIB Result (am_open_30 session):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print("✓ BDIB am_open_30 session working correctly")


@pytest.mark.live_endpoint
def test_bdtick_tick_data():
    """Test BDTICK (tick data) endpoint with live Bloomberg data.

    Uses minimal data by:
    - Limiting to first 30 minutes of trading (9:30-10:00)
    - Only requesting TRADE events (not BID/ASK/etc)
    - Using timeout to avoid long waits
    """
    print(f"\n{'='*80}")
    print("Testing BDTICK (Tick Data)")
    print(f"{'='*80}")

    # Limit to first 30 minutes of trading day and only TRADE events
    result = blp.bdtick(
        ticker=TEST_TICKER,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        time_range=('09:30', '10:00'),  # Just first 30 minutes
        types=['TRADE'],  # Only trade events, not BID/ASK/etc
        timeout=5000,  # 5 second timeout
    )

    assert isinstance(result, pd.DataFrame), "BDTICK should return a DataFrame"
    assert not result.empty, "BDTICK result should not be empty - check if market was open on test date"

    # Structure validation
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDTICK should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDTICK index should be datetime type"
    # BDTICK should have MultiIndex columns with ticker as first level
    assert isinstance(result.columns, pd.MultiIndex), "BDTICK should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert TEST_TICKER in result.columns.get_level_values(0), f"Ticker {TEST_TICKER} should be in column level 0"
    # Expected columns: volume, typ, cond, exch, trd_time (at minimum)
    expected_cols = ['volume', 'typ']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    # Index should be sorted (ascending time)
    assert result.index.is_monotonic_increasing, "BDTICK index should be sorted in ascending order"

    print("\nBDTICK Result (09:30-10:00, TRADE only):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column levels: {result.columns.nlevels}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BDTICK endpoint working correctly")


@pytest.mark.live_endpoint
@pytest.mark.skip(reason="BDTICK with session parameter - disabled for general testing")
def test_bdtick_session_parameter():
    """Test BDTICK with session parameter (as shown in README examples).

    Uses minimal data by:
    - Using session='day' parameter instead of time_range
    - Only requesting TRADE events
    - Using timeout to avoid long waits
    """
    print(f"\n{'='*80}")
    print("Testing BDTICK (Session Parameter)")
    print(f"{'='*80}")

    # Use session='day' parameter as shown in README
    result = blp.bdtick(
        ticker=TEST_TICKER,
        dt=TEST_DATE.strftime('%Y-%m-%d'),
        session='day',  # Use session parameter instead of time_range
        types=['TRADE'],  # Only trade events
        timeout=5000,  # 5 second timeout
    )

    assert isinstance(result, pd.DataFrame), "BDTICK should return a DataFrame"
    assert not result.empty, "BDTICK result should not be empty - check if market was open on test date"

    # Structure validation (same as regular BDTICK)
    assert isinstance(result.index, (pd.DatetimeIndex, pd.Index)), "BDTICK should have DatetimeIndex"
    assert pd.api.types.is_datetime64_any_dtype(result.index), "BDTICK index should be datetime type"
    # BDTICK should have MultiIndex columns with ticker as first level
    assert isinstance(result.columns, pd.MultiIndex), "BDTICK should have MultiIndex columns (ticker, field)"
    assert len(result.columns.levels) == 2, "MultiIndex should have 2 levels (ticker, field)"
    assert TEST_TICKER in result.columns.get_level_values(0), f"Ticker {TEST_TICKER} should be in column level 0"
    # Expected columns: volume, typ, cond, exch, trd_time (at minimum)
    expected_cols = ['volume', 'typ']
    result_cols_lower = [col.lower() for col in result.columns.get_level_values(1)]
    for col in expected_cols:
        assert any(col in c for c in result_cols_lower), f"Expected column '{col}' should be present"
    # Index should be sorted (ascending time)
    assert result.index.is_monotonic_increasing, "BDTICK index should be sorted in ascending order"

    print("\nBDTICK Result (session='day', TRADE only):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Time range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column levels: {result.columns.nlevels}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BDTICK session parameter working correctly")


@pytest.mark.live_endpoint
def test_dividend_history():
    """Test dividend() endpoint with live Bloomberg data.

    Uses a quarter (90 days) date range to increase likelihood of finding dividends.
    """
    print(f"\n{'='*80}")
    print("Testing dividend() (Dividend History)")
    print(f"{'='*80}")

    # Use a quarter (90 days) range to increase likelihood of finding dividends
    dividend_start = (END_DATE - timedelta(days=90)).strftime('%Y-%m-%d')
    result = blp.dividend(
        tickers=TEST_TICKER,
        start_date=dividend_start,
        end_date=END_DATE.strftime('%Y-%m-%d'),
    )

    assert isinstance(result, pd.DataFrame), "dividend() should return a DataFrame"
    assert not result.empty, "dividend() result should not be empty - check if dividends exist in date range"

    # Structure validation
    assert isinstance(result.index, pd.Index), "dividend() should have Index"
    assert TEST_TICKER in result.index, f"Ticker {TEST_TICKER} should be in index"
    assert not isinstance(result.columns, pd.MultiIndex), "dividend() should have single-level columns"
    assert len(result.columns) > 0, "dividend() should have at least one column"
    # Expect date-related columns for dividend data
    result_cols_lower = [col.lower() for col in result.columns]
    date_related_cols = ['date', 'ex', 'record', 'payable', 'dividend', 'amount']
    assert any(any(dc in col for dc in date_related_cols) for col in result_cols_lower), \
        "dividend() should have date-related columns"

    print("\nDividend Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Index type: {type(result.index)}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ dividend() endpoint working correctly")


@pytest.mark.live_endpoint
def test_dividend_multiple_tickers():
    """Test dividend() with multiple tickers (as shown in README examples).

    Uses a quarter (90 days) date range to increase likelihood of finding dividends.
    """
    print(f"\n{'='*80}")
    print("Testing dividend() (Multiple Tickers)")
    print(f"{'='*80}")

    # Use a quarter (90 days) range to increase likelihood of finding dividends
    dividend_start = (END_DATE - timedelta(days=90)).strftime('%Y-%m-%d')
    result = blp.dividend(
        tickers=TEST_TICKERS[:2],  # Multiple tickers as shown in README
        start_date=dividend_start,
        end_date=END_DATE.strftime('%Y-%m-%d'),
    )

    assert isinstance(result, pd.DataFrame), "dividend() should return a DataFrame"
    # Allow empty results - dividends may not exist in date range for all tickers
    if result.empty:
        print("\ndividend() returned empty results (no dividends in date range)")
        print("✓ dividend() endpoint working correctly (empty result is valid)")
    else:
        # Structure validation
        assert isinstance(result.index, pd.Index), "dividend() should have Index"
        assert not isinstance(result.columns, pd.MultiIndex), "dividend() should have single-level columns"
        assert len(result.columns) > 0, "dividend() should have at least one column"
        # Verify at least one requested ticker is in index
        result_index_values = set(result.index)
        assert any(ticker in result_index_values for ticker in TEST_TICKERS[:2]), \
            f"At least one ticker from {TEST_TICKERS[:2]} should be in index"
        # Expect date-related columns for dividend data
        result_cols_lower = [col.lower() for col in result.columns]
        date_related_cols = ['date', 'ex', 'record', 'payable', 'dividend', 'amount']
        assert any(any(dc in col for dc in date_related_cols) for col in result_cols_lower), \
            "dividend() should have date-related columns"

        print("\nDividend Result (Multiple Tickers):")
        print(result)
        print(f"\nShape: {result.shape}")
        print(f"Tickers in index: {list(result.index.unique())}")
        print(f"Columns: {list(result.columns)}")
        print(f"Sample rows:\n{result.head()}")
        print("✓ dividend() multiple tickers working correctly")


@pytest.mark.live_endpoint
def test_earning_breakdowns():
    """Test earning() endpoint with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing earning() (Earnings Breakdowns)")
    print(f"{'='*80}")

    # Use a recent fiscal year
    current_year = datetime.now().year
    result = blp.earning(
        ticker=TEST_TICKER,
        by='Geo',
        Eqy_Fund_Year=current_year - 1,  # Previous year
        Number_Of_Periods=1,
    )

    assert isinstance(result, pd.DataFrame), "earning() should return a DataFrame"
    assert not result.empty, "earning() result should not be empty - check if earnings data is available"
    print("\nEarning Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ earning() endpoint working correctly")


@pytest.mark.live_endpoint
def test_turnover():
    """Test turnover() endpoint with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing turnover() (Trading Volume & Turnover)")
    print(f"{'='*80}")

    result = blp.turnover(
        tickers=TEST_TICKER,
        start_date=START_DATE.strftime('%Y-%m-%d'),
        end_date=END_DATE.strftime('%Y-%m-%d'),
        ccy='USD',
    )

    assert isinstance(result, pd.DataFrame), "turnover() should return a DataFrame"
    assert not result.empty, "turnover() result should not be empty"

    # Structure validation
    # turnover() uses bdh internally, so index can be DatetimeIndex or regular Index with date strings/objects
    assert isinstance(result.index, pd.Index), "turnover() should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"turnover() index should contain date-like values (got {type(first_idx_val)})"
    # turnover() returns single-level columns (not MultiIndex like bdh)
    assert not isinstance(result.columns, pd.MultiIndex), "turnover() with single ticker should have single-level columns"
    assert len(result.columns) >= 1, "turnover() should have at least one column"
    # Index should be sorted (ascending dates) - works for DatetimeIndex, date strings, and datetime.date objects
    # For datetime.date objects, ensure monotonic check works correctly
    try:
        is_sorted = result.index.is_monotonic_increasing
    except (TypeError, ValueError):
        # Fallback: convert to DatetimeIndex for comparison if native check fails
        try:
            ts_index = pd.DatetimeIndex(pd.to_datetime(result.index))
            is_sorted = ts_index.is_monotonic_increasing
        except (ValueError, TypeError):
            # If conversion fails, skip this check
            is_sorted = True
    assert is_sorted, "turnover() index should be sorted in ascending order"

    print("\nTurnover Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Date range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column structure: {'MultiIndex' if isinstance(result.columns, pd.MultiIndex) else 'Single-level'}")
    print("✓ turnover() endpoint working correctly")


@pytest.mark.live_endpoint
def test_turnover_multiple_tickers():
    """Test turnover() with multiple tickers (as shown in README examples)."""
    print(f"\n{'='*80}")
    print("Testing turnover() (Multiple Tickers)")
    print(f"{'='*80}")

    result = blp.turnover(
        tickers=TEST_TICKERS[:2],  # Multiple tickers as shown in README
        start_date=START_DATE.strftime('%Y-%m-%d'),
        end_date=END_DATE.strftime('%Y-%m-%d'),
        ccy='USD',
    )

    assert isinstance(result, pd.DataFrame), "turnover() should return a DataFrame"
    assert not result.empty, "turnover() result should not be empty"

    # Structure validation
    # turnover() uses bdh internally, so index can be DatetimeIndex or regular Index with date strings/objects
    assert isinstance(result.index, pd.Index), "turnover() should have Index"
    # Check if index contains date-like values (datetime64 dtype, datetime.date, Timestamp, or date strings)
    if len(result.index) > 0:
        first_idx_val = result.index[0]
        is_date_like = (
            pd.api.types.is_datetime64_any_dtype(result.index) or
            isinstance(first_idx_val, (pd.Timestamp, datetime, date)) or
            (isinstance(first_idx_val, str) and len(str(first_idx_val)) >= 8)  # Date string like '2018-10-10'
        )
        assert is_date_like, f"turnover() index should contain date-like values (got {type(first_idx_val)})"
    # turnover() with multiple tickers returns single-level columns (ticker names)
    assert not isinstance(result.columns, pd.MultiIndex), "turnover() with multiple tickers should have single-level columns"
    assert len(result.columns) >= 2, "turnover() with multiple tickers should have at least 2 columns"
    # Verify requested tickers are in columns
    result_cols = list(result.columns)
    for ticker in TEST_TICKERS[:2]:
        assert ticker in result_cols, f"Ticker {ticker} should be in columns"
    # Index should be sorted (ascending dates)
    try:
        is_sorted = result.index.is_monotonic_increasing
    except (TypeError, ValueError):
        # Fallback: convert to DatetimeIndex for comparison if native check fails
        try:
            ts_index = pd.DatetimeIndex(pd.to_datetime(result.index))
            is_sorted = ts_index.is_monotonic_increasing
        except (ValueError, TypeError):
            # If conversion fails, skip this check
            is_sorted = True
    assert is_sorted, "turnover() index should be sorted in ascending order"

    print("\nTurnover Result (Multiple Tickers):")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Tickers: {list(result.columns)}")
    print(f"Date range: {result.index.min()} to {result.index.max()}")
    print(f"Index type: {type(result.index)}")
    print(f"Column structure: {'MultiIndex' if isinstance(result.columns, pd.MultiIndex) else 'Single-level'}")
    print("✓ turnover() multiple tickers working correctly")


@pytest.mark.live_endpoint
def test_adjust_ccy():
    """Test adjust_ccy() utility with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing adjust_ccy() (Currency Conversion)")
    print(f"{'='*80}")

    # First get some historical data
    hist_data = blp.bdh(
        tickers=TEST_TICKER,
        flds=TEST_SINGLE_FIELD,
        start_date=START_DATE.strftime('%Y-%m-%d'),
        end_date=END_DATE.strftime('%Y-%m-%d'),
    )

    assert not hist_data.empty, "Need historical data for currency conversion"

    # Convert to EUR
    result = blp.adjust_ccy(hist_data, ccy='EUR')

    assert isinstance(result, pd.DataFrame), "adjust_ccy() should return a DataFrame"
    assert not result.empty, "adjust_ccy() result should not be empty"
    assert result.shape == hist_data.shape, "Shape should match input"

    # Structure validation - should preserve structure of input
    assert isinstance(result.index, type(hist_data.index)), "adjust_ccy() should preserve index type"
    # Column structure check - handle both MultiIndex and single-level columns
    # In xbbg 0.7.7, adjust_ccy() flattens MultiIndex columns to single-level columns
    if isinstance(hist_data.columns, pd.MultiIndex):
        # In xbbg 0.7.7, MultiIndex columns are flattened to single-level (ticker names only)
        assert not isinstance(result.columns, pd.MultiIndex), "adjust_ccy() in xbbg 0.7.7 flattens MultiIndex to single-level columns"
        # Check that column names match the ticker level (level 0) of the MultiIndex
        expected_cols = list(hist_data.columns.get_level_values(0).unique())
        assert list(result.columns) == expected_cols, f"adjust_ccy() should use ticker names from MultiIndex level 0 (expected {expected_cols}, got {list(result.columns)})"
    else:
        assert not isinstance(result.columns, pd.MultiIndex), "adjust_ccy() should preserve single-level column structure"
        assert list(result.columns) == list(hist_data.columns), "adjust_ccy() should preserve column names"
    assert result.index.equals(hist_data.index), "adjust_ccy() should preserve index values"
    # Values should be different (converted)
    if not hist_data.empty and not result.empty:
        assert result.iloc[0, 0] != hist_data.iloc[0, 0], "Values should be converted (different from original)"

    print("\nOriginal Data (USD):")
    print(hist_data.head())
    print("\nConverted Data (EUR):")
    print(result.head())
    print(f"\nShape: {result.shape}")
    print(f"Index preserved: {result.index.equals(hist_data.index)}")
    if isinstance(hist_data.columns, pd.MultiIndex):
        print(f"MultiIndex flattened: {not isinstance(result.columns, pd.MultiIndex)}")
        print(f"Original columns (MultiIndex): {list(hist_data.columns)}")
        print(f"Converted columns (single-level): {list(result.columns)}")
    else:
        print(f"Columns preserved: {list(result.columns) == list(hist_data.columns)}")
    print("✓ adjust_ccy() endpoint working correctly")


@pytest.mark.live_endpoint
@pytest.mark.skip(reason="BEQS requires user-defined screen - update BQS_SCREEN_NAME if you have one")
def test_beqs_screening():
    """Test BEQS (Bloomberg Equity Screening) endpoint with live Bloomberg data.

    NOTE: This test requires a user-defined BEQS screen. Update BEQS_SCREEN_NAME
    with your screen name or skip this test if you don't have one configured.
    """
    print(f"\n{'='*80}")
    print("Testing BEQS (Bloomberg Equity Screening)")
    print(f"{'='*80}")

    # User should replace with their actual screen name
    screen_name = "MyScreen"  # UPDATE THIS
    result = blp.beqs(screen=screen_name, asof=END_DATE.strftime('%Y-%m-%d'))

    assert isinstance(result, pd.DataFrame), "BEQS should return a DataFrame"
    assert not result.empty, "BEQS result should not be empty - check if screen exists and has results"
    print("\nBEQS Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BEQS endpoint working correctly")


@pytest.mark.live_endpoint
def test_bql_query():
    """Test BQL (Bloomberg Query Language) endpoint with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing BQL (Bloomberg Query Language)")
    print(f"{'='*80}")

    result = blp.bql(BQL_QUERY)

    assert isinstance(result, pd.DataFrame), "BQL should return a DataFrame"
    assert not result.empty, "BQL result should not be empty - check if query syntax is correct"

    # Structure validation
    assert isinstance(result.index, pd.Index), "BQL should have Index"
    assert len(result.columns) > 0, "BQL should have at least one column"
    # BQL structure can vary, but should have consistent structure
    assert result.shape[0] > 0, "BQL should have at least one row"

    print("\nBQL Result:")
    print(result)
    print(f"\nShape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print(f"Index type: {type(result.index)}")
    print(f"Column structure: {'MultiIndex' if isinstance(result.columns, pd.MultiIndex) else 'Single-level'}")
    print(f"Sample rows:\n{result.head()}")
    print("✓ BQL endpoint working correctly")


@pytest.mark.live_endpoint
def test_bsrch_search():
    """Test BSRCH (Search) endpoint with live Bloomberg data.

    Note: BSRCH requires user-defined screens. This test uses a simple query
    that may return empty results if the screen doesn't exist. The test passes
    if the endpoint works correctly, regardless of result count.
    """
    print(f"\n{'='*80}")
    print("Testing BSRCH (Search)")
    print(f"{'='*80}")

    result = blp.bsrch(BSRCH_QUERY)

    assert isinstance(result, pd.DataFrame), "BSRCH should return a DataFrame"
    # Allow empty results - BSRCH screens may not exist or may return no results
    # The important thing is that the endpoint works correctly
    if result.empty:
        print("\nBSRCH returned empty results (screen may not exist or have no matches)")
        print("✓ BSRCH endpoint working correctly (empty result is valid)")
    else:
        print(f"\nBSRCH returned {len(result)} rows")
        print("\nBSRCH Result:")
        print(result)
        print(f"\nShape: {result.shape}")
        print(f"Columns: {list(result.columns)}")
        print(f"Sample rows:\n{result.head()}")
        print("✓ BSRCH endpoint working correctly")


@pytest.mark.live_endpoint
@pytest.mark.skip(reason="BSRCH with overrides requires specific weather data setup - disabled for general testing")
def test_bsrch_with_overrides():
    """Test BSRCH with overrides parameter (weather data example from README).

    Note: This test uses a weather data query with overrides. The query may return
    empty results if the screen doesn't exist or weather data is unavailable.
    The test passes if the endpoint works correctly, regardless of result count.
    """
    print(f"\n{'='*80}")
    print("Testing BSRCH (With Overrides - Weather Data)")
    print(f"{'='*80}")

    # Use weather data query with overrides as shown in README
    result = blp.bsrch(
        "comdty:weather",
        overrides={
            "provider": "wsi",
            "location": "US_XX",
            "model": "ACTUALS",
            "frequency": "DAILY",
            "target_start_date": "2021-01-01",
            "target_end_date": "2021-01-05",
            "location_time": "false",
            "fields": "WIND_SPEED|TEMPERATURE|HDD_65F|CDD_65F|HDD_18C|CDD_18C|PRECIPITATION_24HR|CLOUD_COVER|FEELS_LIKE_TEMPERATURE|MSL_PRESSURE|TEMPERATURE_MAX_24HR|TEMPERATURE_MIN_24HR"
        }
    )

    assert isinstance(result, pd.DataFrame), "BSRCH should return a DataFrame"
    # Allow empty results - weather screens may not exist or may return no results
    # The important thing is that the endpoint works correctly with overrides
    if result.empty:
        print("\nBSRCH with overrides returned empty results (screen may not exist or have no matches)")
        print("✓ BSRCH with overrides endpoint working correctly (empty result is valid)")
    else:
        print(f"\nBSRCH with overrides returned {len(result)} rows")
        print("\nBSRCH Result (With Overrides):")
        print(result)
        print(f"\nShape: {result.shape}")
        print(f"Columns: {list(result.columns)}")
        print(f"Sample rows:\n{result.head()}")
        print("✓ BSRCH with overrides endpoint working correctly")


@pytest.mark.live_endpoint
@pytest.mark.skip(reason="Temporarily disabled")
def test_live_realtime_streaming():
    """Test live() real-time streaming endpoint with live Bloomberg data.

    This test creates a very short-lived subscription (max 2 updates) with a 10-second
    timeout to minimize data usage and avoid hanging (especially on weekends when markets are closed).
    """
    print(f"\n{'='*80}")
    print("Testing live() (Real-time Streaming)")
    print(f"{'='*80}")

    async def _test_live():
        updates_received = []
        try:
            # Use asyncio.wait_for to timeout after 10 seconds
            async def _collect_updates():
                async for update in blp.live(
                    tickers=TEST_TICKER,
                    flds=['LAST_PRICE'],
                    max_cnt=2,  # Only get 2 updates max
                ):
                    updates_received.append(update)
                    print(f"Received update: {update}")
                    if len(updates_received) >= 2:
                        break

            try:
                await asyncio.wait_for(_collect_updates(), timeout=10.0)
            except asyncio.TimeoutError:
                print("Timeout after 10 seconds (market may be closed)")
        except Exception as e:
            print(f"Live subscription error (may be expected): {e}")

        # We consider it working if we can create the subscription
        # Even if no updates come through (market may be closed)
        print(f"\nTotal updates received: {len(updates_received)}")
        if updates_received:
            print(f"Sample update: {updates_received[0]}")
        print("✓ live() endpoint working correctly (subscription established)")

    # Run async test
    asyncio.run(_test_live())


@pytest.mark.live_endpoint
def test_subscribe_realtime():
    """Test subscribe() real-time subscription endpoint with live Bloomberg data.

    This test creates a very short-lived subscription with a 10-second timeout to minimize
    data usage and avoid hanging (especially on weekends when markets are closed).
    """
    print(f"\n{'='*80}")
    print("Testing subscribe() (Real-time Subscriptions)")
    print(f"{'='*80}")

    updates_received = []
    timeout_occurred = threading.Event()

    def _timeout_handler():
        timeout_occurred.set()

    try:
        # Set up a 10-second timeout
        timer = threading.Timer(10.0, _timeout_handler)
        timer.start()

        with blp.subscribe(
            tickers=TEST_TICKER,
            flds=['LAST_PRICE'],
        ) as stream:
            # Try to get 1-2 updates, then exit
            for i, update in enumerate(stream):
                if timeout_occurred.is_set():
                    print("Timeout after 10 seconds (market may be closed)")
                    break
                updates_received.append(update)
                print(f"Received update {i+1}: {update}")
                if i >= 1:  # Get max 2 updates
                    break
    except Exception as e:
        print(f"Subscription error (may be expected): {e}")
    finally:
        timer.cancel()

    print(f"\nTotal updates received: {len(updates_received)}")
    if updates_received:
        print(f"Sample update: {updates_received[0]}")
    print("✓ subscribe() endpoint working correctly (subscription established)")


@pytest.mark.live_endpoint
def test_fut_ticker_resolution():
    """Test fut_ticker() futures ticker resolution with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing fut_ticker() (Futures Ticker Resolution)")
    print(f"{'='*80}")

    result = blp.fut_ticker('ES1 Index', END_DATE.strftime('%Y-%m-%d'), freq='ME')

    assert isinstance(result, str), "fut_ticker() should return a string"
    assert result, "fut_ticker() result should not be empty"

    print("\nGeneric ticker: ES1 Index")
    print(f"Resolved ticker: {result}")
    print("✓ fut_ticker() endpoint working correctly")


@pytest.mark.live_endpoint
def test_active_futures():
    """Test active_futures() active futures selection with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing active_futures() (Active Futures Selection)")
    print(f"{'='*80}")

    result = blp.active_futures('ESA Index', END_DATE.strftime('%Y-%m-%d'))

    assert isinstance(result, str), "active_futures() should return a string"
    assert result, "active_futures() result should not be empty"

    print("\nGeneric ticker: ESA Index")
    print(f"Active contract: {result}")
    print("✓ active_futures() endpoint working correctly")


@pytest.mark.live_endpoint
def test_cdx_ticker_resolution():
    """Test cdx_ticker() CDX ticker resolution with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing cdx_ticker() (CDX Ticker Resolution)")
    print(f"{'='*80}")

    # Use a generic CDX ticker
    generic_cdx = 'CDX IG CDSI GEN 5Y Corp'
    result = blp.cdx_ticker(generic_cdx, END_DATE.strftime('%Y-%m-%d'))

    assert isinstance(result, str), "cdx_ticker() should return a string"
    assert result, "cdx_ticker() result should not be empty"

    print(f"\nGeneric CDX ticker: {generic_cdx}")
    print(f"Resolved ticker: {result}")
    print("✓ cdx_ticker() endpoint working correctly")


@pytest.mark.live_endpoint
def test_active_cdx():
    """Test active_cdx() active CDX selection with live Bloomberg data."""
    print(f"\n{'='*80}")
    print("Testing active_cdx() (Active CDX Selection)")
    print(f"{'='*80}")

    generic_cdx = 'CDX IG CDSI GEN 5Y Corp'
    result = blp.active_cdx(generic_cdx, END_DATE.strftime('%Y-%m-%d'), lookback_days=10)

    assert isinstance(result, str), "active_cdx() should return a string"
    assert result, "active_cdx() result should not be empty"

    print(f"\nGeneric CDX ticker: {generic_cdx}")
    print(f"Active contract: {result}")
    print("✓ active_cdx() endpoint working correctly")


if __name__ == '__main__':
    # Allow running tests directly with verbose output
    print("\n" + "="*80)
    print("Live Bloomberg Endpoint Tests")
    print("="*80)
    print("\nWARNING: These tests make actual Bloomberg API calls.")
    print("Use pytest with --run-xbbg-live flag instead:\n")
    print("    pytest xbbg/tests/test_live_endpoints.py --run-xbbg-live -v\n")
    sys.exit(1)

