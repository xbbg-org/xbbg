"""Core Bloomberg API processing and connection utilities.

This package contains internal core functionality:
- conn: Bloomberg session connection management
- process: Request creation and message processing
- helpers: Common helper functions (normalize_tickers, normalize_flds, etc.)
- intervals: Trading session interval resolution
- overrides: Bloomberg override and element option processing
- timezone: Timezone utilities and conversion
- utils: General utility functions (flatten, fmt_dt, etc.)
- trials: Retry tracking for missing data
- blpapi_logging: Optional Bloomberg API logging configuration
"""

