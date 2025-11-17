# Testing xbbg Versions with uv

This directory contains scripts to test xbbg 0.7.7 and latest version,
and verify the structure of returned DataFrames.

## Files

- `test_xbbg_0.7.7.py` - Test script for xbbg 0.7.7 that makes a BDH
  request and analyzes the structure
- `test_xbbg_latest.py` - Test script for latest xbbg version
- `run_xbbg_0.7.7_test.ps1` - PowerShell script to run the 0.7.7 test
  with uv (Windows)
- `run_xbbg_latest_test.ps1` - PowerShell script to run the latest
  version test with uv (Windows)
- `run_both_tests.ps1` - PowerShell script to run both tests for
  comparison
- `run_xbbg_0.7.7_test.sh` - Bash script to run the test with uv
  (Linux/Mac)

## Quick Start (Windows PowerShell)

```powershell
# Test xbbg 0.7.7
.\run_xbbg_0.7.7_test.ps1

# Test latest xbbg version
.\run_xbbg_latest_test.ps1

# Run both tests for comparison
.\run_both_tests.ps1
```

## Quick Start (Linux/Mac)

```bash
# Make script executable
chmod +x run_xbbg_0.7.7_test.sh

# Run the script
./run_xbbg_0.7.7_test.sh
```

## Manual Steps

If you prefer to run manually:

```powershell
# 1. Create virtual environment
uv venv .venv_xbbg_0.7.7

# 2. Activate it
.\.venv_xbbg_0.7.7\Scripts\Activate.ps1  # Windows
# or
source .venv_xbbg_0.7.7/bin/activate  # Linux/Mac

# 3. Install xbbg 0.7.7
uv pip install xbbg==0.7.7 pandas

# 4. Verify version
python -c "import importlib.metadata; print(importlib.metadata.version('xbbg'))"

# 5. Run test script
python test_xbbg_0.7.7.py

# 6. Cleanup
deactivate
rm -rf .venv_xbbg_0.7.7  # or Remove-Item -Recurse -Force .venv_xbbg_0.7.7 on Windows
```

## What the Test Does

1. **Version Verification**: Checks the installed xbbg version
2. **BDH Request**: Makes a simple historical data request for AAPL US Equity
3. **Structure Analysis**: Analyzes and displays:
   - Index type (DatetimeIndex vs regular Index)
   - Index dtype and values (date strings, datetime.date objects, or Timestamp)
   - Column structure (MultiIndex vs single-level)
   - Full DataFrame output

## Test Results Summary

### xbbg 0.7.7

- **Index**: Regular `Index` with `datetime.date` objects (not
  DatetimeIndex)
- **Index dtype**: `object`
- **Columns**: **MultiIndex** with 2 levels (even for single ticker)
  - Level 0: tickers
  - Level 1: fields

### xbbg 0.7.11 (Latest)

- **Index**: Regular `Index` with `datetime.date` objects (not
  DatetimeIndex)
- **Index dtype**: `object`
- **Columns**: **MultiIndex** with 2 levels (even for single ticker)
  - Level 0: tickers
  - Level 1: fields

### Key Finding

Both versions have **identical structure**:

- Both use regular Index with `datetime.date` objects (not strings, not
  DatetimeIndex)
- Both return MultiIndex columns even for single ticker requests
- This means tests need to handle `datetime.date` objects in the index
  and expect MultiIndex columns for all BDH requests
