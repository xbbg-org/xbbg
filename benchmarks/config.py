"""Benchmark configuration for xbbg performance testing."""

from __future__ import annotations

# ============================================================================
# Test Data Configuration
# ============================================================================

# Tickers to use for benchmarks (minimal set to limit data usage)
TICKERS_SINGLE = ["IBM US Equity"]
TICKERS_MULTI = ["IBM US Equity", "AAPL US Equity", "MSFT US Equity"]

# Fields for reference data
FIELDS_SINGLE = ["PX_LAST"]
FIELDS_MULTI = ["PX_LAST", "VOLUME", "TRADING_DT_REALTIME"]

# Historical data range (keep short to minimize data usage)
BDH_START = "2025-01-02"
BDH_END = "2025-01-06"  # ~3-4 trading days

# Intraday data
BDIB_DATE = "2025-01-06"
BDIB_START_TIME = "09:30"
BDIB_END_TIME = "10:00"  # 30 minutes
BDIB_INTERVAL = 5  # 5-minute bars

# Tick data
BDTICK_DATE = "2025-01-06"
BDTICK_START_TIME = "09:30:00"
BDTICK_END_TIME = "09:35:00"  # 5 minutes

# BQL query
BQL_SIMPLE = "get(px_last) for(['IBM US Equity'])"
BQL_MULTI = "get(px_last, volume) for(['IBM US Equity', 'AAPL US Equity'])"

# ============================================================================
# Benchmark Settings
# ============================================================================

# Number of iterations per benchmark (first is cold, rest are warm)
ITERATIONS = 5

# Warmup iterations (discarded from results)
WARMUP_ITERATIONS = 1

# Time limit per benchmark (seconds)
TIMEOUT = 60

# ============================================================================
# Packages to Compare
# ============================================================================

PACKAGES = {
    "xbbg-rust": {
        "name": "xbbg (Rust 1.0+)",
        "enabled": True,
        "import": "xbbg",
        "version_check": lambda: __import__("xbbg").__version__,
    },
    "xbbg-legacy": {
        "name": "xbbg (Python <1.0)",
        "enabled": True,
        "import": "xbbg_legacy",  # Install xbbg==0.10.3 as xbbg_legacy
        "version_check": lambda: __import__("xbbg_legacy").__version__,
        "install_cmd": "pip install xbbg==0.10.3",
    },
    "blpapi": {
        "name": "blpapi (Official)",
        "enabled": True,
        "import": "blpapi",
        "version_check": lambda: __import__("blpapi").version,
        "install_cmd": "pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi",
        "requires_wrapper": True,  # Needs custom wrapper for consistent API
    },
    "bbg-fetch": {
        "name": "bbg-fetch",
        "enabled": True,
        "import": "bbg_fetch",
        "version_check": lambda: __import__("bbg_fetch").__version__,
        "install_cmd": "pip install bbg-fetch",
    },
    "pdblp": {
        "name": "pdblp",
        "enabled": True,
        "import": "pdblp",
        "version_check": lambda: __import__("pdblp").__version__,
        "install_cmd": "pip install pdblp",
    },
}

# ============================================================================
# Output Configuration
# ============================================================================

RESULTS_DIR = "benchmarks/results"
RESULTS_FORMAT = "json"  # json, csv, markdown

# Report options
GENERATE_MARKDOWN = True
GENERATE_CSV = True
GENERATE_JSON = True
GENERATE_HTML = False

# ============================================================================
# Metrics to Track
# ============================================================================

METRICS = [
    "cold_start_ms",  # First call time
    "warm_mean_ms",  # Average of warm calls
    "warm_median_ms",  # Median of warm calls
    "warm_p95_ms",  # 95th percentile
    "warm_p99_ms",  # 99th percentile
    "warm_std_ms",  # Standard deviation
    "memory_peak_mb",  # Peak memory usage
    "data_shape",  # Result shape validation
]

# ============================================================================
# Performance Thresholds
# ============================================================================

# Acceptable regression from main branch (for CI)
REGRESSION_THRESHOLD_PERCENT = 10  # Fail if >10% slower

# Expected speedup vs legacy (for reporting)
EXPECTED_SPEEDUP_VS_LEGACY = 5.0  # Target: 5x faster
EXPECTED_SPEEDUP_VS_PDBLP = 3.0  # Target: 3x faster

# ============================================================================
# CI Configuration (for GitHub Actions)
# ============================================================================

CI_ENABLED = True
CI_PR_COMMENT = True  # Post results as PR comment
CI_FAIL_ON_REGRESSION = True  # Fail CI if performance regresses
CI_STORE_RESULTS = True  # Upload results to GitHub Pages
