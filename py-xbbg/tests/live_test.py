#!/usr/bin/env python
"""Live Bloomberg API test script.

Tests each API endpoint with real Bloomberg data.
Control which tests run via command line arguments.

Usage:
    python tests/live_test.py              # Run all tests
    python tests/live_test.py bdp bdh      # Run only bdp and bdh tests
    python tests/live_test.py --list       # List available tests
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def get_engine():
    """Create and return a Bloomberg engine."""
    from xbbg._core import PyEngine

    return PyEngine()


async def test_bdp(engine):
    """Test Reference Data (bdp) - single point data."""
    print("Testing: bdp (Reference Data)")
    print("-" * 40)

    params = {
        "service": "//blp/refdata",
        "operation": "ReferenceDataRequest",
        "extractor": "refdata",
        "securities": ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"],
        "fields": ["PX_LAST", "NAME", "CUR_MKT_CAP"],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    # Group by ticker for display
    tickers = result["ticker"].to_pylist()
    fields = result["field"].to_pylist()
    values = result["value"].to_pylist()

    current_ticker = None
    for t, f, v in zip(tickers, fields, values):
        if t != current_ticker:
            print(f"\n  {t}:")
            current_ticker = t
        print(f"    {f}: {v}")

    print()
    return True


async def test_bdh(engine):
    """Test Historical Data (bdh) - time series data."""
    print("Testing: bdh (Historical Data)")
    print("-" * 40)

    # Get last 5 trading days
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    params = {
        "service": "//blp/refdata",
        "operation": "HistoricalDataRequest",
        "extractor": "histdata",
        "securities": ["SPY US Equity"],
        "fields": ["PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW", "VOLUME"],
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")
    print()

    # Display as table
    dates = result["date"].to_pylist()
    px_last = result["PX_LAST"].to_pylist()
    volume = result["VOLUME"].to_pylist()

    print("  Date        | PX_LAST  | Volume")
    print("  " + "-" * 35)
    for d, p, v in zip(dates, px_last, volume):
        vol_str = f"{v / 1e6:.1f}M" if v else "N/A"
        print(f"  {d}  | {p:8.2f} | {vol_str}")

    print()
    return True


async def test_bdh_multi(engine):
    """Test Historical Data with multiple securities."""
    print("Testing: bdh_multi (Historical Data - Multiple Securities)")
    print("-" * 40)

    end_date = date.today()
    start_date = end_date - timedelta(days=5)

    params = {
        "service": "//blp/refdata",
        "operation": "HistoricalDataRequest",
        "extractor": "histdata",
        "securities": ["AAPL US Equity", "MSFT US Equity"],
        "fields": ["PX_LAST"],
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Rows: {result.num_rows}")

    tickers = result["ticker"].to_pylist()
    dates = result["date"].to_pylist()
    prices = result["PX_LAST"].to_pylist()

    current_ticker = None
    for t, d, p in zip(tickers, dates, prices):
        if t != current_ticker:
            print(f"\n  {t}:")
            current_ticker = t
        print(f"    {d}: {p:.2f}")

    print()
    return True


async def test_bds(engine):
    """Test Bulk Data (bds) - bulk reference data."""
    print("Testing: bds (Bulk Data)")
    print("-" * 40)

    params = {
        "service": "//blp/refdata",
        "operation": "ReferenceDataRequest",
        "extractor": "bulk",
        "securities": ["SPY US Equity"],
        "fields": ["TOP_20_HOLDERS_PUBLIC_FILINGS"],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=60.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Top 5 holders:")
        for i, col in enumerate(result.schema.names[:5]):
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_bdib(engine):
    """Test Intraday Bars (bdib) - intraday OHLCV bars."""
    print("Testing: bdib (Intraday Bars)")
    print("-" * 40)

    # Get bars from yesterday (market hours in UTC)
    # US market: 9:30 AM - 4:00 PM ET = 14:30 - 21:00 UTC
    yesterday = date.today() - timedelta(days=1)
    start_dt = f"{yesterday.strftime('%Y-%m-%d')}T14:30:00"
    end_dt = f"{yesterday.strftime('%Y-%m-%d')}T15:30:00"

    params = {
        "service": "//blp/refdata",
        "operation": "IntradayBarRequest",
        "extractor": "intraday_bar",
        "security": "SPY US Equity",
        "event_type": "TRADE",
        "interval": 5,  # 5-minute bars
        "start_datetime": start_dt,
        "end_datetime": end_dt,
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  First 5 bars:")
        times = result["time"].to_pylist()[:5] if "time" in result.schema.names else []
        opens = result["open"].to_pylist()[:5] if "open" in result.schema.names else []
        closes = result["close"].to_pylist()[:5] if "close" in result.schema.names else []

        for t, o, c in zip(times, opens, closes):
            print(f"    {t}: open={o:.2f}, close={c:.2f}")

    print()
    return True


async def test_bdtick(engine):
    """Test Intraday Ticks (bdtick) - tick-level data."""
    print("Testing: bdtick (Intraday Ticks)")
    print("-" * 40)

    # Get ticks from yesterday (market hours in UTC)
    # US market opens at 9:30 AM ET = 14:30 UTC
    yesterday = date.today() - timedelta(days=1)
    start_dt = f"{yesterday.strftime('%Y-%m-%d')}T14:30:00"
    end_dt = f"{yesterday.strftime('%Y-%m-%d')}T14:31:00"  # Just 1 minute

    params = {
        "service": "//blp/refdata",
        "operation": "IntradayTickRequest",
        "extractor": "intraday_tick",
        "security": "SPY US Equity",
        "event_types": ["TRADE"],  # Must specify event types for tick data
        "start_datetime": start_dt,
        "end_datetime": end_dt,
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print(f"\n  First 5 ticks (of {result.num_rows}):")
        for col in result.schema.names[:4]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_field_info(engine):
    """Test Field Info - get field metadata."""
    print("Testing: field_info (Field Metadata)")
    print("-" * 40)

    params = {
        "service": "//blp/apiflds",
        "operation": "FieldInfoRequest",
        "extractor": "fieldinfo",
        "field_ids": ["PX_LAST", "VOLUME", "NAME", "MARKET_CAP"],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Field info:")
        for col in result.schema.names:
            values = result[col].to_pylist()
            print(f"    {col}: {values}")

    print()
    return True


async def test_schema_introspection(engine):
    """Test Schema Introspection - get service schema."""
    print("Testing: schema (Service Introspection)")
    print("-" * 40)

    # List operations for //blp/refdata
    ops = await engine.list_operations("//blp/refdata")
    print(f"  Operations in //blp/refdata: {len(ops)}")
    print(f"  Available: {', '.join(ops[:5])}...")

    # Get valid elements for HistoricalDataRequest
    elements = await engine.list_valid_elements("//blp/refdata", "HistoricalDataRequest")
    print(f"\n  Elements for HistoricalDataRequest: {len(elements)}")
    print(f"  Sample: {', '.join(sorted(elements)[:8])}...")

    print()
    return True


async def test_ext_functions(engine):
    """Test Extension Functions from xbbg-ext."""
    print("Testing: ext (Extension Functions)")
    print("-" * 40)

    from xbbg._core import (
        ext_parse_date,
        ext_fmt_date,
        ext_is_specific_contract,
        ext_generate_futures_candidates,
        ext_build_fx_pair,
        ext_same_currency,
        ext_get_futures_months,
    )

    # Date parsing
    parsed = ext_parse_date("2024-03-15")
    print(f"  parse_date('2024-03-15'): {parsed}")

    formatted = ext_fmt_date(2024, 3, 15, "%Y%m%d")
    print(f"  fmt_date(2024, 3, 15): {formatted}")

    # Ticker utilities
    is_specific = ext_is_specific_contract("ESH24 Index")
    print(f"  is_specific_contract('ESH24 Index'): {is_specific}")

    is_generic = ext_is_specific_contract("ES1 Index")
    print(f"  is_specific_contract('ES1 Index'): {is_generic}")

    # Futures candidates
    candidates = ext_generate_futures_candidates("ES1 Index", 2024, 3, 15, "Q", 4)
    print(f"  generate_futures_candidates('ES1 Index', Q, 4):")
    for ticker, year, month in candidates:
        print(f"    {ticker} ({year}-{month:02d})")

    # FX pair building
    fx = ext_build_fx_pair("GBp", "USD")
    print(f"  build_fx_pair('GBp', 'USD'): {fx}")

    # Currency comparison
    same = ext_same_currency("GBP", "GBp")
    print(f"  same_currency('GBP', 'GBp'): {same}")

    # Constants
    months = ext_get_futures_months()
    print(f"  futures_months: {dict(list(months.items())[:6])}...")

    print()
    return True


async def test_bql(engine):
    """Test Bloomberg Query Language (bql) - BQL queries."""
    print("Testing: bql (Bloomberg Query Language)")
    print("-" * 40)

    # BQL request via //blp/bqlsvc service
    params = {
        "service": "//blp/bqlsvc",
        "operation": "sendQuery",
        "extractor": "bql",
        "elements": [("expression", "get(px_last) for('AAPL US Equity')")],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=60.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  BQL Results:")
        for col in result.schema.names[:5]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_bsrch(engine):
    """Test Bloomberg Search (bsrch) - saved searches.

    Note: BSRCH requires a valid Domain (saved search name). Common domains include
    user-created screens. The test uses a generic domain that may return 0 results
    if no matching saved searches exist.
    """
    print("Testing: bsrch (Bloomberg Search)")
    print("-" * 40)

    # BSRCH request via //blp/exrsvc service
    # Note: Domain must be a valid saved search name (user-specific)
    # Using FI:SOVR as an example - may return error if not available
    params = {
        "service": "//blp/exrsvc",
        "operation": "ExcelGetGridRequest",
        "extractor": "generic",  # Use generic to see full response
        "elements": [("Domain", "FI:SOVR")],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=60.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Response:")
        for col in result.schema.names[:5]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    # Check for error message in response
    if "path" in result.schema.names:
        paths = result["path"].to_pylist()
        if "Error" in paths:
            print("\n  Note: Domain may not be valid for this Bloomberg account")

    print()
    return True


async def test_blkp(engine):
    """Test Security Lookup (blkp) - search for securities."""
    print("Testing: blkp (Security Lookup)")
    print("-" * 40)

    # instrumentListRequest via //blp/instruments service
    params = {
        "service": "//blp/instruments",
        "operation": "instrumentListRequest",
        "extractor": "generic",
        "elements": [
            ("query", "Apple"),
            ("yellowKeyFilter", "YK_FILTER_EQTY"),
            ("maxResults", "10"),
        ],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Search results:")
        for col in result.schema.names[:3]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_bcurves(engine):
    """Test Yield Curve List (bcurves) - search for curves."""
    print("Testing: bcurves (Yield Curve List)")
    print("-" * 40)

    # curveListRequest via //blp/instruments service
    # Use 'query' parameter for text search (required for results)
    params = {
        "service": "//blp/instruments",
        "operation": "curveListRequest",
        "extractor": "generic",
        "elements": [
            ("query", "Treasury"),
            ("maxResults", "10"),
        ],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Curves found:")
        for col in result.schema.names[:5]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_bgovts(engine):
    """Test Government Securities List (bgovts) - search for govt bonds."""
    print("Testing: bgovts (Government Securities List)")
    print("-" * 40)

    # govtListRequest via //blp/instruments service
    # Use 'query' parameter for text search (required for results)
    params = {
        "service": "//blp/instruments",
        "operation": "govtListRequest",
        "extractor": "generic",
        "elements": [
            ("query", "US Treasury"),
            ("maxResults", "10"),
        ],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=30.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Government securities found:")
        for col in result.schema.names[:5]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_beqs(engine):
    """Test Equity Screening (beqs) - run saved screens."""
    print("Testing: beqs (Equity Screening)")
    print("-" * 40)

    # BeqsRequest via //blp/refdata service
    # Using a Bloomberg GLOBAL screen that should exist
    params = {
        "service": "//blp/refdata",
        "operation": "BeqsRequest",
        "extractor": "generic",
        "elements": [
            ("screenName", "TOP_DECL_DVD"),
            ("screenType", "GLOBAL"),
            ("Group", "General"),
        ],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=60.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Screen results:")
        for col in result.schema.names[:3]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_bta(engine):
    """Test Technical Analysis (bta) - technical study data."""
    print("Testing: bta (Technical Analysis)")
    print("-" * 40)

    # Get dates for the study
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)

    # //blp/tasvc studyRequest with nested elements via dotted path notation
    params = {
        "service": "//blp/tasvc",
        "operation": "studyRequest",
        "extractor": "generic",
        "elements": [
            # priceSource sub-element
            ("priceSource.securityName", "AAPL US Equity"),
            # priceSource.dataRange.historical sub-element
            ("priceSource.dataRange.historical.startDate", start_date.strftime("%Y%m%d")),
            ("priceSource.dataRange.historical.endDate", end_date.strftime("%Y%m%d")),
            ("priceSource.dataRange.historical.periodicitySelection", "DAILY"),
            # studyAttributes.smavgStudyAttributes sub-element (Simple Moving Average)
            ("studyAttributes.smavgStudyAttributes.period", "20"),
            ("studyAttributes.smavgStudyAttributes.priceSourceClose", "PX_LAST"),
        ],
    }

    result = await asyncio.wait_for(engine.request(params), timeout=60.0)

    print(f"  Schema: {result.schema}")
    print(f"  Rows: {result.num_rows}")

    if result.num_rows > 0:
        print("\n  Technical Analysis results:")
        for col in result.schema.names[:5]:
            values = result[col].to_pylist()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_yas(engine):
    """Test Yield & Spread Analysis (yas) - bond yield calculations."""
    print("Testing: yas (Yield & Spread Analysis)")
    print("-" * 40)

    from xbbg import abdp

    # Get yield and duration for a Treasury bond
    # Using the generic on-the-run 10Y Treasury
    # yas() is a wrapper around bdp() with YAS override fields
    df = await abdp(
        "GT10 Govt",  # Generic 10-year Treasury (more reliable than CUSIP)
        ["YAS_BOND_YLD", "YAS_MOD_DUR", "YLD_YTM_MID"],
    )

    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")

    # Display results
    if len(df) > 0:
        print("\n  YAS Results:")
        for col in df.columns[:5]:
            values = df[col].to_list()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_etf_holdings(engine):
    """Test ETF Holdings (etf_holdings) - get ETF constituents via BQL."""
    print("Testing: etf_holdings (ETF Holdings)")
    print("-" * 40)

    from xbbg import abql

    # Get holdings for SPY ETF using BQL
    # etf_holdings() is a wrapper that builds this BQL query
    bql_query = "get(id_isin, weights, id().position) for(holdings('SPY US Equity'))"
    df = await abql(bql_query)

    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")

    # Display first few holdings
    if len(df) > 0:
        print("\n  Top 5 Holdings:")
        for col in df.columns[:4]:
            values = df[col].to_list()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_preferreds(engine):
    """Test Preferred Stocks (preferreds) - find preferreds via BQL."""
    print("Testing: preferreds (Preferred Stocks)")
    print("-" * 40)

    from xbbg import abql

    # Get preferred stocks for Bank of America using BQL
    # preferreds() is a wrapper that builds this BQL query
    bql_query = (
        "get(id, name) for(filter(debt(['BAC US Equity'], CONSOLIDATEDUPLICATES='N'), SRCH_ASSET_CLASS=='Preferreds'))"
    )
    df = await abql(bql_query)

    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")

    # Display results
    if len(df) > 0:
        print("\n  Preferred Stocks:")
        for col in df.columns[:3]:
            values = df[col].to_list()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_corporate_bonds(engine):
    """Test Corporate Bonds (corporate_bonds) - find bonds via BQL."""
    print("Testing: corporate_bonds (Corporate Bonds)")
    print("-" * 40)

    from xbbg import abql

    # Get active USD corporate bonds for Apple using BQL
    # corporate_bonds() is a wrapper that builds this BQL query
    bql_query = (
        "get(id) "
        "for(filter(bondsuniv('active', CONSOLIDATEDUPLICATES='N'), "
        "SRCH_ASSET_CLASS=='Corporates' AND TICKER=='AAPL' AND CRNCY=='USD'))"
    )
    df = await abql(bql_query)

    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}")

    # Display results
    if len(df) > 0:
        print("\n  Corporate Bonds:")
        for col in df.columns[:3]:
            values = df[col].to_list()[:5]
            print(f"    {col}: {values}")

    print()
    return True


async def test_ext_async(engine):
    """Test async extension functions (ayas, aetf_holdings, etc.)."""
    print("Testing: ext_async (Async Extension Functions)")
    print("-" * 40)

    from xbbg import ext

    # Test ayas - async yield & spread analysis
    print("  Testing ayas()...")
    try:
        df = await ext.ayas("GT10 Govt", ["YAS_BOND_YLD", "YAS_MOD_DUR"])
        print(f"    ayas: {len(df)} rows")
    except Exception as e:
        print(f"    ayas: Error - {e}")

    # Test aetf_holdings - async ETF holdings
    print("  Testing aetf_holdings()...")
    try:
        df = await ext.aetf_holdings("SPY US Equity")
        print(f"    aetf_holdings: {len(df)} rows")
    except Exception as e:
        print(f"    aetf_holdings: Error - {e}")

    # Test apreferreds - async find preferred stocks
    print("  Testing apreferreds()...")
    try:
        df = await ext.apreferreds("BAC US Equity")
        print(f"    apreferreds: {len(df)} rows")
    except Exception as e:
        print(f"    apreferreds: Error - {e}")

    # Test acorporate_bonds - async find corporate bonds
    print("  Testing acorporate_bonds()...")
    try:
        df = await ext.acorporate_bonds("AAPL")
        print(f"    acorporate_bonds: {len(df)} rows")
    except Exception as e:
        print(f"    acorporate_bonds: Error - {e}")

    # Test adividend - async dividend history
    print("  Testing adividend()...")
    try:
        df = await ext.adividend("AAPL US Equity", start_date="2024-01-01")
        print(f"    adividend: {len(df)} rows")
    except Exception as e:
        print(f"    adividend: Error - {e}")

    # Test afut_ticker - async futures ticker resolution
    print("  Testing afut_ticker()...")
    try:
        ticker = await ext.afut_ticker("ES1 Index", "2024-06-15")
        print(f"    afut_ticker: {ticker}")
    except Exception as e:
        print(f"    afut_ticker: Error - {e}")

    print()
    return True


# Test registry
TESTS = {
    "bdp": test_bdp,
    "bdh": test_bdh,
    "bdh_multi": test_bdh_multi,
    "bds": test_bds,
    "bdib": test_bdib,
    "bdtick": test_bdtick,
    "field_info": test_field_info,
    "schema": test_schema_introspection,
    "ext": test_ext_functions,
    "bql": test_bql,
    "bsrch": test_bsrch,
    "blkp": test_blkp,
    "bcurves": test_bcurves,
    "bgovts": test_bgovts,
    "beqs": test_beqs,
    "bta": test_bta,
    # Fixed income extensions
    "yas": test_yas,
    "etf_holdings": test_etf_holdings,
    "preferreds": test_preferreds,
    "corporate_bonds": test_corporate_bonds,
    # Async extension functions
    "ext_async": test_ext_async,
}


async def run_tests(test_names: list[str]):
    """Run selected tests."""
    engine = get_engine()

    passed = 0
    failed = 0
    skipped = 0

    for name in test_names:
        if name not in TESTS:
            print(f"Unknown test: {name}")
            skipped += 1
            continue

        try:
            print(f"\n{'=' * 50}")
            success = await TESTS[name](engine)
            if success:
                passed += 1
                print(f"PASSED: {name}")
            else:
                failed += 1
                print(f"FAILED: {name}")
        except asyncio.TimeoutError:
            failed += 1
            print(f"TIMEOUT: {name}")
        except Exception as e:
            failed += 1
            print(f"ERROR: {name} - {e}")

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 50}")

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Live Bloomberg API tests")
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
        for name, func in TESTS.items():
            doc = func.__doc__.split("\n")[0] if func.__doc__ else ""
            print(f"  {name:12} - {doc}")
        return 0

    print("=" * 50)
    print("XBBG Live Bloomberg API Tests")
    print("=" * 50)
    print(f"Running tests: {', '.join(args.tests)}")

    success = asyncio.run(run_tests(args.tests))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
