#!/usr/bin/env python3
"""Test script to verify xbbg latest (Rust backend) behavior and structure.

This script mirrors test_xbbg_0.7.7.py to compare output structures.
Run both tests and compare results to ensure backwards compatibility.
"""

from datetime import datetime, timedelta
import sys

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is not installed")
    sys.exit(1)


# Helper function to analyze DataFrame structure
def analyze_structure(df, test_name):
    """Analyze and print DataFrame structure."""
    # Analyze index
    if pd.api.types.is_datetime64_any_dtype(df.index):
        print(f"  [OK] {test_name} - Index is DatetimeIndex (datetime64 dtype)")
    elif isinstance(df.index, pd.Index):
        if len(df.index) > 0:
            first_val = df.index[0]
            if isinstance(first_val, str):
                print(f"  [OK] {test_name} - Index is regular Index with date strings")
            elif hasattr(first_val, "date"):
                print(f"  [OK] {test_name} - Index is regular Index with date objects")
            else:
                print(f"  [INFO] {test_name} - Index type: {type(first_val)}")
        else:
            print(f"  [WARN] {test_name} - Index is empty")
    else:
        print(f"  [WARN] {test_name} - Unexpected index type: {type(df.index)}")

    # Analyze columns
    if isinstance(df.columns, pd.MultiIndex):
        print(f"  [OK] {test_name} - Columns are MultiIndex with {df.columns.nlevels} levels")
        print(f"    Level 0 (tickers): {list(df.columns.get_level_values(0).unique())}")
        print(f"    Level 1 (fields): {list(df.columns.get_level_values(1).unique())}")
    else:
        print(f"  [OK] {test_name} - Columns are single-level: {list(df.columns)}")


def check_xbbg_version():
    """Check installed xbbg version."""
    try:
        import importlib.metadata

        version = importlib.metadata.version("xbbg")
    except Exception:
        version = "unknown"
    return version


print("=" * 80)
print("xbbg Version Check (Latest/Rust Backend)")
print("=" * 80)
version = check_xbbg_version()
print(f"Installed version: {version}")
print()

# Import xbbg - the new Rust backend
try:
    import xbbg

    # Configure to use pandas backend for comparison with 0.7.7
    xbbg.set_backend("pandas")
    print(f"[OK] xbbg imported successfully")
    print(f"[OK] Backend set to: pandas")
except ImportError as e:
    print(f"ERROR: Cannot import xbbg: {e}")
    sys.exit(1)

# Date range for tests
end_date = datetime.now()
start_date = end_date - timedelta(days=5)

print("=" * 80)
print("Making Historical Data Requests")
print("=" * 80)
print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print()


def run_tests():
    """Run all regression tests."""

    # Test 1: BDP - Single Ticker
    print("\n" + "=" * 80)
    print("TEST 1: BDP - Single Ticker")
    print("=" * 80)
    try:
        result = xbbg.bdp(
            tickers="AAPL US Equity",
            flds=["PX_LAST", "NAME"],
        )
        print(f"\nDataFrame Shape: {result.shape}")
        print(f"Index Type: {type(result.index)}")
        print(f"Column Type: {type(result.columns)}")
        print(f"Columns: {list(result.columns)}")
        print("\nDataFrame:")
        print(result)
        analyze_structure(result, "BDP Single Ticker")
    except Exception as e:
        print(f"[ERROR] BDP test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 2: BDH - Single Ticker
    print("\n" + "=" * 80)
    print("TEST 2: BDH - Single Ticker")
    print("=" * 80)
    try:
        result = xbbg.bdh(
            tickers="AAPL US Equity",
            flds=["PX_LAST"],
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        print(f"\nDataFrame Shape: {result.shape}")
        print(f"Index Type: {type(result.index)}")
        print(f"Index dtype: {result.index.dtype}")
        print(f"Is DatetimeIndex: {isinstance(result.index, pd.DatetimeIndex)}")

        if len(result.index) > 0:
            print(f"First index value: {result.index[0]}")
            print(f"First index value type: {type(result.index[0])}")

        print(f"\nColumn Type: {type(result.columns)}")
        print(f"Is MultiIndex: {isinstance(result.columns, pd.MultiIndex)}")
        print(f"Columns: {list(result.columns)}")
        print("\nDataFrame (first 3 rows):")
        print(result.head(3))
        analyze_structure(result, "BDH Single Ticker")
    except Exception as e:
        print(f"[ERROR] BDH single ticker test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 3: BDH - Multiple Tickers
    print("\n" + "=" * 80)
    print("TEST 3: BDH - Multiple Tickers")
    print("=" * 80)
    try:
        result_multi = xbbg.bdh(
            tickers=["AAPL US Equity", "MSFT US Equity"],
            flds=["PX_LAST"],
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        print(f"\nDataFrame Shape: {result_multi.shape}")
        print(f"Index Type: {type(result_multi.index)}")
        print(f"Index dtype: {result_multi.index.dtype}")

        if len(result_multi.index) > 0:
            print(f"First index value: {result_multi.index[0]}")
            print(f"First index value type: {type(result_multi.index[0])}")

        print(f"\nColumn Type: {type(result_multi.columns)}")
        print(f"Is MultiIndex: {isinstance(result_multi.columns, pd.MultiIndex)}")
        if isinstance(result_multi.columns, pd.MultiIndex):
            print(f"Column levels: {result_multi.columns.nlevels}")
            print(f"Level 0 (tickers): {list(result_multi.columns.get_level_values(0).unique())}")
            print(f"Level 1 (fields): {list(result_multi.columns.get_level_values(1).unique())}")
        print(f"Columns: {list(result_multi.columns)}")
        print("\nDataFrame (first 3 rows):")
        print(result_multi.head(3))
        analyze_structure(result_multi, "BDH Multiple Tickers")
    except Exception as e:
        print(f"[ERROR] BDH multiple tickers test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 4: BDS - Bulk Data
    print("\n" + "=" * 80)
    print("TEST 4: BDS - Bulk Data (Index Members)")
    print("=" * 80)
    try:
        result_bds = xbbg.bds(
            tickers="SPX Index",
            flds="INDX_MEMBERS",
        )
        print(f"\nDataFrame Shape: {result_bds.shape}")
        print(f"Index Type: {type(result_bds.index)}")
        print(f"Column Type: {type(result_bds.columns)}")
        print(f"Columns: {list(result_bds.columns)}")
        print("\nDataFrame (first 5 rows):")
        print(result_bds.head(5))
        analyze_structure(result_bds, "BDS Bulk Data")
    except Exception as e:
        print(f"[ERROR] BDS test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 5: BDIB - Intraday Bars
    print("\n" + "=" * 80)
    print("TEST 5: BDIB - Intraday Bars")
    print("=" * 80)
    try:
        # Use yesterday for intraday data
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result_bdib = xbbg.bdib(
            ticker="AAPL US Equity",
            dt=yesterday,
            interval=60,  # 60-minute bars
        )
        print(f"\nDataFrame Shape: {result_bdib.shape}")
        print(f"Index Type: {type(result_bdib.index)}")
        print(f"Column Type: {type(result_bdib.columns)}")
        print(f"Columns: {list(result_bdib.columns)}")
        print("\nDataFrame (first 5 rows):")
        print(result_bdib.head(5))
        analyze_structure(result_bdib, "BDIB Intraday Bars")
    except Exception as e:
        print(f"[ERROR] BDIB test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 6: BQL - Bloomberg Query Language
    print("\n" + "=" * 80)
    print("TEST 6: BQL - Bloomberg Query Language")
    print("=" * 80)
    try:
        result_bql = xbbg.bql("get(px_last) for('AAPL US Equity')")
        print(f"\nDataFrame Shape: {result_bql.shape}")
        print(f"Index Type: {type(result_bql.index)}")
        print(f"Column Type: {type(result_bql.columns)}")
        print(f"Columns: {list(result_bql.columns)}")
        print("\nDataFrame:")
        print(result_bql)
        analyze_structure(result_bql, "BQL Query")
    except Exception as e:
        print(f"[ERROR] BQL test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 7: Extension - Dividend History
    print("\n" + "=" * 80)
    print("TEST 7: EXT - Dividend History")
    print("=" * 80)
    try:
        from xbbg.ext import dividend

        dividend_start = (end_date - timedelta(days=365)).strftime("%Y-%m-%d")
        result_div = dividend(
            tickers="AAPL US Equity",
            start_date=dividend_start,
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        print(f"\nDataFrame Shape: {result_div.shape}")
        print(f"Index Type: {type(result_div.index)}")
        print(f"Column Type: {type(result_div.columns)}")
        print(f"Columns: {list(result_div.columns)}")
        print("\nDataFrame (first 5 rows):")
        print(result_div.head(5))
        analyze_structure(result_div, "Dividend History")
    except Exception as e:
        print(f"[ERROR] Dividend test failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 8: Extension - Futures
    print("\n" + "=" * 80)
    print("TEST 8: EXT - Futures Active Contract")
    print("=" * 80)
    try:
        from xbbg.ext import fut_ticker

        # fut_ticker(gen_ticker, dt, freq='M') - gen_ticker should be like "ES1 Index"
        today = datetime.now().strftime("%Y-%m-%d")
        result_fut = fut_ticker("ES1 Index", today)
        print(f"\nActive contract: {result_fut}")
    except Exception as e:
        print(f"[ERROR] Futures test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("All Tests Complete")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\nERROR: Test suite failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
