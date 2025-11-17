#!/usr/bin/env python3
"""Test script to verify xbbg 0.7.7 behavior and structure.

This script:
1. Verifies the installed xbbg version
2. Makes a simple BDH request
3. Shows the structure of the returned DataFrame
"""

from datetime import date, datetime, timedelta
import os
import sys

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Ensure we use the installed xbbg, not the local one
# Remove current directory from path if we're in the xbbg repo
# But be careful not to remove venv site-packages directories
if os.path.exists('xbbg') and os.path.exists('pyproject.toml'):
    # We're in the xbbg repo directory - remove it from sys.path
    current_dir = os.path.abspath('.').lower()
    original_path = sys.path.copy()

    # Filter out paths that are the current directory or subdirectories of it
    # But keep venv site-packages even if they're in a subdirectory
    filtered_path = []
    for p in original_path:
        p_abs = os.path.abspath(p).lower()
        # Skip if it's exactly the current directory
        if p_abs == current_dir:
            continue
        # Skip if it's a subdirectory of current directory (but not if it's a venv)
        if p_abs.startswith(current_dir + os.sep):
            # Keep venv site-packages directories
            if 'site-packages' in p_abs or 'venv' in p_abs.lower():
                filtered_path.append(p)
            # Skip other subdirectories
            continue
        # Keep everything else
        filtered_path.append(p)

    sys.path = filtered_path

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
            elif isinstance(first_val, date):
                print(f"  [OK] {test_name} - Index is regular Index with datetime.date objects")
            elif isinstance(first_val, (pd.Timestamp, datetime)):
                print(f"  [OK] {test_name} - Index is regular Index with date objects")
            else:
                print(f"  [WARN] {test_name} - Index is regular Index with unexpected type: {type(first_val)}")
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

# Check xbbg version BEFORE importing xbbg to ensure we're checking the right one
def check_xbbg_version():
    """Check installed xbbg version using importlib.metadata or pkg_resources."""
    try:
        import importlib.metadata
        version = importlib.metadata.version('xbbg')
    except ImportError:
        try:
            import pkg_resources
            version = pkg_resources.get_distribution('xbbg').version
        except ImportError:
            print("ERROR: Cannot determine xbbg version")
            return None
    return version

# Verify version BEFORE importing xbbg
installed_version_before_import = check_xbbg_version()
if not installed_version_before_import:
    sys.exit(1)

print("=" * 80)
print("xbbg Version Check")
print("=" * 80)
print(f"Installed version (before import): {installed_version_before_import}")
print("Expected version: 0.7.7")
if installed_version_before_import.split('+')[0].split('-')[0] != '0.7.7':
    print(f"ERROR: Version mismatch! Expected 0.7.7, got {installed_version_before_import}")
    print("This script should be run in a virtual environment with xbbg==0.7.7 installed.")
    print(f"Current sys.path: {sys.path[:5]}...")  # Show first 5 entries
    sys.exit(1)
else:
    print("[OK] Version matches expected 0.7.7")
print()

# Import xbbg AFTER version check
try:
    from xbbg import blp
except ImportError as e:
    print(f"ERROR: Cannot import xbbg: {e}")
    sys.exit(1)

# Verify version again AFTER import to make sure we didn't import the wrong one
try:
    import importlib.metadata
    installed_version_after_import = importlib.metadata.version('xbbg')
except ImportError:
    try:
        import pkg_resources
        installed_version_after_import = pkg_resources.get_distribution('xbbg').version
    except ImportError:
        installed_version_after_import = "unknown"

if installed_version_after_import != installed_version_before_import:
    print("WARNING: Version changed after import!")
    print(f"  Before import: {installed_version_before_import}")
    print(f"  After import: {installed_version_after_import}")
    print("  This suggests we imported from a different location.")
    print(f"  xbbg module location: {blp.__file__ if hasattr(blp, '__file__') else 'unknown'}")
    print()

# Make historical data requests
print("=" * 80)
print("Making Historical Data Requests")
print("=" * 80)

# Use a small date range (last 5 days)
end_date = datetime.now()
start_date = end_date - timedelta(days=5)

print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print()


def _run_bdh_and_related_tests(blp, start_date: datetime, end_date: datetime) -> None:
    """Run the suite of BDH/turnover/dividend/adjust_ccy structure checks."""
    # Test 1: Single ticker BDH
    print("\n" + "=" * 80)
    print("TEST 1: BDH - Single Ticker")
    print("=" * 80)
    result = blp.bdh(
        tickers='AAPL US Equity',
        flds=['PX_LAST'],
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
    )

    print(f"\nDataFrame Shape: {result.shape}")
    print(f"\nIndex Type: {type(result.index)}")
    print(f"Index dtype: {result.index.dtype}")
    print(f"Is DatetimeIndex: {isinstance(result.index, pd.DatetimeIndex)}")
    print(f"Is datetime64 dtype: {pd.api.types.is_datetime64_any_dtype(result.index)}")

    if len(result.index) > 0:
        print(f"\nFirst index value: {result.index[0]}")
        print(f"First index value type: {type(result.index[0])}")
        print(f"First index value repr: {repr(result.index[0])}")

    print(f"\nColumn Type: {type(result.columns)}")
    print(f"Is MultiIndex: {isinstance(result.columns, pd.MultiIndex)}")
    print(f"Column levels: {result.columns.nlevels if isinstance(result.columns, pd.MultiIndex) else 1}")
    print(f"Columns: {list(result.columns)}")

    print("\nDataFrame (first 3 rows):")
    print(result.head(3))

    # Analyze structure
    print("\nStructure Analysis:")
    analyze_structure(result, "BDH Single Ticker")

    # Test 2: Multiple tickers BDH
    print("\n" + "=" * 80)
    print("TEST 2: BDH - Multiple Tickers")
    print("=" * 80)
    result_multi = blp.bdh(
        tickers=['AAPL US Equity', 'MSFT US Equity'],
        flds=['PX_LAST'],
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
    )

    print(f"\nDataFrame Shape: {result_multi.shape}")
    print(f"\nIndex Type: {type(result_multi.index)}")
    print(f"Index dtype: {result_multi.index.dtype}")

    if len(result_multi.index) > 0:
        print(f"\nFirst index value: {result_multi.index[0]}")
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

    # Test 3: Turnover (uses BDH internally)
    print("\n" + "=" * 80)
    print("TEST 3: turnover() - Historical Trading Volume")
    print("=" * 80)
    try:
        result_turnover = blp.turnover(
            tickers='AAPL US Equity',
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            ccy='USD',
        )

        if not result_turnover.empty:
            print(f"\nDataFrame Shape: {result_turnover.shape}")
            print(f"\nIndex Type: {type(result_turnover.index)}")
            print(f"Index dtype: {result_turnover.index.dtype}")
            if len(result_turnover.index) > 0:
                print(f"First index value type: {type(result_turnover.index[0])}")
            print(f"\nColumn Type: {type(result_turnover.columns)}")
            print(f"Is MultiIndex: {isinstance(result_turnover.columns, pd.MultiIndex)}")
            print(f"Columns: {list(result_turnover.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_turnover.head(3))
            analyze_structure(result_turnover, "turnover()")
        else:
            print("[WARN] turnover() returned empty DataFrame")
    except Exception as e:
        print(f"[WARN] turnover() test failed: {e}")

    # Test 3a: Turnover - Multiple tickers
    print("\n" + "=" * 80)
    print("TEST 3a: turnover() - Multiple Tickers")
    print("=" * 80)
    try:
        result_turnover_multi = blp.turnover(
            tickers=['AAPL US Equity', 'MSFT US Equity'],
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            ccy='USD',
        )

        if not result_turnover_multi.empty:
            print(f"\nDataFrame Shape: {result_turnover_multi.shape}")
            print(f"\nIndex Type: {type(result_turnover_multi.index)}")
            print(f"Index dtype: {result_turnover_multi.index.dtype}")
            if len(result_turnover_multi.index) > 0:
                print(f"First index value type: {type(result_turnover_multi.index[0])}")
            print(f"\nColumn Type: {type(result_turnover_multi.columns)}")
            print(f"Is MultiIndex: {isinstance(result_turnover_multi.columns, pd.MultiIndex)}")
            print(f"Columns: {list(result_turnover_multi.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_turnover_multi.head(3))
            analyze_structure(result_turnover_multi, "turnover() Multiple Tickers")
        else:
            print("[WARN] turnover() with multiple tickers returned empty DataFrame")
    except Exception as e:
        print(f"[WARN] turnover() multiple tickers test failed: {e}")

    # Test 4: BDH with periodicity (weekly)
    print("\n" + "=" * 80)
    print("TEST 4: BDH - Periodicity (Weekly)")
    print("=" * 80)
    try:
        weekly_start = (end_date - timedelta(days=14)).strftime('%Y-%m-%d')
        result_weekly = blp.bdh(
            tickers='AAPL US Equity',
            flds=['PX_LAST'],
            start_date=weekly_start,
            end_date=end_date.strftime('%Y-%m-%d'),
            Per='W',  # Weekly periodicity
            Fill='P',
            Days='A',
        )

        if not result_weekly.empty:
            print(f"\nDataFrame Shape: {result_weekly.shape}")
            print(f"\nIndex Type: {type(result_weekly.index)}")
            print(f"Index dtype: {result_weekly.index.dtype}")
            if len(result_weekly.index) > 0:
                print(f"First index value: {result_weekly.index[0]}")
                print(f"First index value type: {type(result_weekly.index[0])}")
                print(f"First index value repr: {repr(result_weekly.index[0])}")
            print(f"\nColumn Type: {type(result_weekly.columns)}")
            print(f"Is MultiIndex: {isinstance(result_weekly.columns, pd.MultiIndex)}")
            if isinstance(result_weekly.columns, pd.MultiIndex):
                print(f"Column levels: {result_weekly.columns.nlevels}")
            print(f"Columns: {list(result_weekly.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_weekly.head(3))
            analyze_structure(result_weekly, "BDH Weekly Periodicity")
        else:
            print("[WARN] BDH weekly returned empty DataFrame")
    except Exception as e:
        print(f"[WARN] BDH weekly test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 5: BDH with adjustments
    print("\n" + "=" * 80)
    print("TEST 5: BDH - Adjustments")
    print("=" * 80)
    try:
        adjust_start = (end_date - timedelta(days=2)).strftime('%Y-%m-%d')
        result_adjust = blp.bdh(
            tickers='AAPL US Equity',
            flds=['PX_LAST'],
            start_date=adjust_start,
            end_date=end_date.strftime('%Y-%m-%d'),
            adjust='all',  # Adjust for all dividends and splits
        )

        if not result_adjust.empty:
            print(f"\nDataFrame Shape: {result_adjust.shape}")
            print(f"\nIndex Type: {type(result_adjust.index)}")
            print(f"Index dtype: {result_adjust.index.dtype}")
            if len(result_adjust.index) > 0:
                print(f"First index value: {result_adjust.index[0]}")
                print(f"First index value type: {type(result_adjust.index[0])}")
                print(f"First index value repr: {repr(result_adjust.index[0])}")
            print(f"\nColumn Type: {type(result_adjust.columns)}")
            print(f"Is MultiIndex: {isinstance(result_adjust.columns, pd.MultiIndex)}")
            if isinstance(result_adjust.columns, pd.MultiIndex):
                print(f"Column levels: {result_adjust.columns.nlevels}")
            print(f"Columns: {list(result_adjust.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_adjust.head(3))
            analyze_structure(result_adjust, "BDH With Adjustments")
        else:
            print("[WARN] BDH with adjustments returned empty DataFrame")
    except Exception as e:
        print(f"[WARN] BDH adjustments test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 6: Dividend history
    print("\n" + "=" * 80)
    print("TEST 6: dividend() - Dividend History")
    print("=" * 80)
    try:
        # Use a longer range to increase chance of finding dividends
        dividend_start = (end_date - timedelta(days=90)).strftime('%Y-%m-%d')
        result_dividend = blp.dividend(
            tickers='AAPL US Equity',
            start_date=dividend_start,
            end_date=end_date.strftime('%Y-%m-%d'),
        )

        if not result_dividend.empty:
            print(f"\nDataFrame Shape: {result_dividend.shape}")
            print(f"\nIndex Type: {type(result_dividend.index)}")
            print(f"Index dtype: {result_dividend.index.dtype}")
            if len(result_dividend.index) > 0:
                print(f"First index value: {result_dividend.index[0]}")
                print(f"First index value type: {type(result_dividend.index[0])}")
            print(f"\nColumn Type: {type(result_dividend.columns)}")
            print(f"Is MultiIndex: {isinstance(result_dividend.columns, pd.MultiIndex)}")
            print(f"Columns: {list(result_dividend.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_dividend.head(3))
            analyze_structure(result_dividend, "dividend()")
        else:
            print("[INFO] dividend() returned empty DataFrame (no dividends in date range)")
    except Exception as e:
        print(f"[WARN] dividend() test failed: {e}")

    # Test 6a: Dividend history - Multiple tickers
    print("\n" + "=" * 80)
    print("TEST 6a: dividend() - Multiple Tickers")
    print("=" * 80)
    try:
        # Use a longer range to increase chance of finding dividends
        dividend_start = (end_date - timedelta(days=90)).strftime('%Y-%m-%d')
        result_dividend_multi = blp.dividend(
            tickers=['AAPL US Equity', 'MSFT US Equity'],
            start_date=dividend_start,
            end_date=end_date.strftime('%Y-%m-%d'),
        )

        if not result_dividend_multi.empty:
            print(f"\nDataFrame Shape: {result_dividend_multi.shape}")
            print(f"\nIndex Type: {type(result_dividend_multi.index)}")
            print(f"Index dtype: {result_dividend_multi.index.dtype}")
            if len(result_dividend_multi.index) > 0:
                print(f"First index value: {result_dividend_multi.index[0]}")
                print(f"First index value type: {type(result_dividend_multi.index[0])}")
                print(f"Unique tickers in index: {list(result_dividend_multi.index.unique())}")
            print(f"\nColumn Type: {type(result_dividend_multi.columns)}")
            print(f"Is MultiIndex: {isinstance(result_dividend_multi.columns, pd.MultiIndex)}")
            print(f"Columns: {list(result_dividend_multi.columns)}")
            print("\nDataFrame (first 3 rows):")
            print(result_dividend_multi.head(3))
            analyze_structure(result_dividend_multi, "dividend() Multiple Tickers")
        else:
            print("[INFO] dividend() with multiple tickers returned empty DataFrame (no dividends in date range)")
    except Exception as e:
        print(f"[WARN] dividend() multiple tickers test failed: {e}")

    # Test 7: adjust_ccy() - Currency conversion
    print("\n" + "=" * 80)
    print("TEST 7: adjust_ccy() - Currency Conversion")
    print("=" * 80)
    try:
        # First get some historical data with MultiIndex columns
        hist_data = blp.bdh(
            tickers='AAPL US Equity',
            flds=['PX_LAST'],
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
        )

        if not hist_data.empty:
            print(f"\nOriginal Data Shape: {hist_data.shape}")
            print(f"Original Index Type: {type(hist_data.index)}")
            print(f"Original Column Type: {type(hist_data.columns)}")
            print(f"Original Is MultiIndex: {isinstance(hist_data.columns, pd.MultiIndex)}")
            if isinstance(hist_data.columns, pd.MultiIndex):
                print(f"Original Column levels: {hist_data.columns.nlevels}")
                print(f"Original Columns: {list(hist_data.columns)}")
            else:
                print(f"Original Columns: {list(hist_data.columns)}")

            # Convert to EUR
            result_ccy = blp.adjust_ccy(hist_data, ccy='EUR')

            if not result_ccy.empty:
                print(f"\nConverted Data Shape: {result_ccy.shape}")
                print(f"Converted Index Type: {type(result_ccy.index)}")
                print(f"Converted Column Type: {type(result_ccy.columns)}")
                print(f"Converted Is MultiIndex: {isinstance(result_ccy.columns, pd.MultiIndex)}")
                if isinstance(result_ccy.columns, pd.MultiIndex):
                    print(f"Converted Column levels: {result_ccy.columns.nlevels}")
                    print(f"Converted Columns: {list(result_ccy.columns)}")
                else:
                    print(f"Converted Columns: {list(result_ccy.columns)}")

                print(f"\nShape preserved: {result_ccy.shape == hist_data.shape}")
                # Check if index types match (both are same type)
                index_type_match = type(result_ccy.index).__name__ == type(hist_data.index).__name__
                print(f"Index type preserved: {index_type_match}")
                # Check if column types match (both are same type)
                col_type_match = type(result_ccy.columns).__name__ == type(hist_data.columns).__name__
                print(f"Column type preserved: {col_type_match}")

                if isinstance(hist_data.columns, pd.MultiIndex):
                    print(f"MultiIndex preserved: {isinstance(result_ccy.columns, pd.MultiIndex)}")
                    if isinstance(result_ccy.columns, pd.MultiIndex):
                        print(f"MultiIndex equals: {result_ccy.columns.equals(hist_data.columns)}")
                        print(f"MultiIndex levels match: {result_ccy.columns.nlevels == hist_data.columns.nlevels}")
                else:
                    print(f"Single-level preserved: {not isinstance(result_ccy.columns, pd.MultiIndex)}")
                    if not isinstance(result_ccy.columns, pd.MultiIndex):
                        print(f"Column names match: {list(result_ccy.columns) == list(hist_data.columns)}")

                print("\nOriginal Data (first 3 rows):")
                print(hist_data.head(3))
                print("\nConverted Data (first 3 rows):")
                print(result_ccy.head(3))

                analyze_structure(result_ccy, "adjust_ccy()")
            else:
                print("[WARN] adjust_ccy() returned empty DataFrame")
        else:
            print("[WARN] Cannot test adjust_ccy() - historical data is empty")
    except Exception as e:
        print(f"[WARN] adjust_ccy() test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("All Tests Complete")
    print("=" * 80)


try:
    _run_bdh_and_related_tests(blp=blp, start_date=start_date, end_date=end_date)
except Exception as e:
    print(f"\nERROR: Bloomberg request failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

