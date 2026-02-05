# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Extended multi-backend support**: Added 6 new backends matching narwhals' full backend support:
  - **Eager backends**: `cudf` (GPU-accelerated via NVIDIA RAPIDS), `modin` (distributed pandas)
  - **Lazy backends**: `dask` (parallel computing), `ibis` (portable DataFrame expressions), `pyspark` (Apache Spark), `sqlframe` (SQL-based DataFrames)
  - Total: 13 backends (6 eager + 7 lazy)
- **Backend availability checking**: New functions to check and validate backend availability with helpful error messages:
  - `is_backend_available(backend)` - Check if a backend package is installed
  - `check_backend(backend)` - Check availability with version validation, raises helpful errors
  - `get_available_backends()` - List all currently available backends
  - `print_backend_status()` - Diagnostic function showing all backend statuses
- **Format compatibility checking**: New functions to validate format support per backend:
  - `is_format_supported(backend, format)` - Check if a format works with a backend
  - `get_supported_formats(backend)` - Get set of supported formats for a backend
  - `check_format_compatibility(backend, format)` - Validate with helpful errors
  - `validate_backend_format(backend, format)` - Combined validation for API functions
- **`xbbg.ext` module**: New extension module for v1.0 migration containing helper functions that will be removed from `blp` namespace
  - `xbbg.ext.currency` - `adjust_ccy()` for currency conversion
  - `xbbg.ext.dividends` - `dividend()` for dividend history
  - `xbbg.ext.earnings` - `earning()` for earnings breakdowns
  - `xbbg.ext.turnover` - `turnover()` for trading volume
  - `xbbg.ext.holdings` - `etf_holdings()`, `preferreds()`, `corporate_bonds()` BQL helpers
  - `xbbg.ext.futures` - `fut_ticker()`, `active_futures()` for futures resolution
  - `xbbg.ext.cdx` - `cdx_ticker()`, `active_cdx()` for CDX index resolution
  - `xbbg.ext.yas` - `yas()`, `YieldType` for fixed income analytics
- New v1.0-compatible import path: `from xbbg.ext import dividend, fut_ticker, ...` (no deprecation warnings)
- **Pandas removed as required dependency**: `xbbg.ext` modules now use only stdlib datetime and narwhals, making pandas fully optional

### Changed

- **Backend enum reorganized**: Backends now categorized as eager (full API) vs lazy (deferred execution)
- **Format restrictions**: WIDE format only available for eager backends (pandas, polars, pyarrow, narwhals, cudf, modin); lazy backends limited to LONG and SEMI_LONG
- **Version requirements updated**: Minimum versions now match narwhals requirements (duckdb>=1.0, dask>=2024.1)
- `xbbg/markets/resolvers.py` now re-exports from `xbbg.ext.futures` and `xbbg.ext.cdx` for backwards compatibility
- Internal implementations moved to `xbbg/ext/` module; old import paths still work with deprecation warnings

### Fixed

- **ibis backend**: Updated to use `ibis.memtable()` instead of deprecated `con.read_in_memory()`
- **sqlframe backend**: Fixed import path to use `sqlframe.duckdb.DuckDBSession`

## [0.11.2] - 2026-02-05

### Fixed

- **BDS output format**: Restored v0.10.x backward compatibility for `bds()` output format (#209)
  - Default `format='wide'` now returns single data column with ticker as index (pandas) or column (other backends)
  - Field column dropped for cleaner output matching v0.10.x behavior
  - Users can opt-in to new 3-column format with `format='long'`

## [0.11.1] - 2026-02-05

### Fixed

- **Field names now lowercase**: Restored v0.10.x behavior where `bdp()`, `bdh()`, and `bds()` return field/column names as lowercase (#206)

## [0.11.0] - 2026-02-02

### Added

- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow for improved performance
- **Multi-backend support**: New `Backend` enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb
- **Output format control**: New `Format` enum with long, semi_long, wide options
- **bta()**: Bloomberg Technical Analysis function for 50+ technical indicators (#175)
- **bqr()**: Bloomberg Quote Request function emulating Excel `=BQR()` for dealer quote data with broker attribution (#22)
- **yas()**: Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics with `YieldType` enum
- **preferreds()**: BQL convenience function to find preferred stocks for an equity ticker
- **corporate_bonds()**: BQL convenience function to find active corporate bonds for a ticker
- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` configuration functions
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`
- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, `BlpRequestError`, etc.)
- `EngineConfig` dataclass and `configure()` function for engine configuration
- `Service` and `Operation` enums for Bloomberg service URIs
- Treasury & SOFR futures support: TY, ZN, ZB, ZF, ZT, UB, TN, SFR, SR1, SR3, ED futures (#198)
- Comprehensive logging improvements across critical paths with better error traceability
- CONTRIBUTING.md and CODE_OF_CONDUCT.md for community standards

### Changed

- All API functions now accept `backend` and `format` parameters
- Internal pipeline uses PyArrow tables with narwhals transformations
- Removed pytz dependency (using stdlib `datetime.timezone`)
- **Intraday cache now includes interval in path** (#80) - different bar intervals cached separately (**breaking**: existing cache will miss)
- Internal class renames with backward compatible aliases (`YamlMarketInfoProvider` → `MetadataProvider`)
- Logging level adjustments: `BBG_ROOT not set` promoted to WARNING, cache timing demoted to DEBUG

### Deprecated

- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()` instead
- `lookupSecurity()` - will become `blkp()` in v1.0
- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0
- `bta_studies()` - renamed to `ta_studies()` in v1.0
- `getPortfolio()` - renamed to `bport()` in v1.0
- Helper functions (`dividend()`, `earning()`, `turnover()`, `adjust_ccy()`) moving to `xbbg.ext` in v1.0
- Futures/CDX utilities (`fut_ticker()`, `active_futures()`, `cdx_ticker()`, `active_cdx()`) moving to `xbbg.ext` in v1.0

### Removed

- **Trials mechanism**: Eliminated retry-blocking system that caused silent failures after 2 failed attempts
- **pandas-market-calendars dependency**: Exchange info now sourced exclusively from Bloomberg API with local caching

### Fixed

- **Import without blpapi installed**: Fixed `AttributeError` when importing xbbg without blpapi (#200)
- **Japan/non-US timezone fix for bdib**: Trading hours now correctly converted to exchange's local timezone (#198)
- **stream() field values**: Subscribed field values now always included in output dict (#199)
- **Slow Bloomberg fields**: TIMEOUT events handled correctly; requests wait for response with `slow_warn_seconds` warning (#193)
- **Pipeline data types**: Preserve original data types instead of converting to strings (#191)
- **Futures symbol parsing**: Fixed `market_info()` to correctly parse symbols like `TYH6` → `TY` (#198)
- **get_tz() optimization**: Direct timezone strings recognized without Bloomberg API call
- **bdtick timezone fix**: Pass exchange timezone to fix blank results for non-UTC exchanges (#185)
- **bdtick timeout**: Increased from 10s to 2 minutes for tick data requests
- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output
- Logging format compliance fixes (G004, G201)

## [0.10.3] - 2025-12-29

### Fixed

- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output

### Changed

- Re-enabled futures and CDX resolver tests
- Updated live endpoint tests for LONG format output
- Code style improvements using contextlib.suppress instead of try-except-pass

## [0.10.2] - 2025-12-29

### Changed

- CI/CD improvements with reusable workflows (workflow_call) for release automation
- Separated pypi_upload workflow for trusted publisher compatibility

## [0.10.1] - 2025-12-29

### Fixed

- Persist blp.connect() session for subsequent API calls (#165)

### Changed

- Trigger release workflows via release event instead of workflow_dispatch
- Removed Gitter badge (replaced by Discord)
- Added Discord community link and badge

## [0.10.0] - 2025-12-25

### Added

- Updated polars-bloomberg support for BQL, BDIB and BSRCH (#155)

### Fixed

- Add identifier type prefix to B-Pipe subscription topics (#156)
- Remove pandas version cap to support Python 3.14 (#161)
- Resolve RST formatting warning in index.rst (#162)
- Update Japan equity market hours for TSE trading extension (#163)

## [0.9.1] - 2025-12-11

### Fixed

- Fix BQL returning only one row for multi-value results (#152)

### Changed

- Add blank lines around latest-release markers in index.rst
- Remove redundant release triggers from workflows
- Trigger release workflows explicitly from semantic_version

## [0.9.0] - 2025-12-02

### Added

- Add etf_holdings() function for retrieving ETF holdings via BQL (#147)
- Add multi-day support to bdib() (#148)
- Add multi-day cache support for bdib() (#149)

### Fixed

- Resolve RST duplicate link targets and Sphinx build warnings

## [0.8.2] - 2025-11-19

### Fixed

- Fix BQL options chain metadata issues (#146)

## [0.8.1] - 2025-11-17

### Changed

- CI/CD workflow improvements for trusted publisher compatibility

## [0.8.0] - 2025-11-16

### Added

- **bsrch()**: Bloomberg SRCH queries for fixed income, commodities, and weather data (#137)
- **Fixed income securities support**: ISIN/CUSIP/SEDOL identifiers for bdib (#136)
- **Server host parameter**: Connect to remote Bloomberg servers via `server` parameter (#138)
- **Interval parameter for subscribe()/live()**: Configurable update intervals for real-time feeds
- Semantic versioning workflow for automated releases
- Support for GY (Xetra), IM (Borsa Italiana), and SE (SIX) exchanges (#140)
- Comprehensive bar interval selection guide for bdib function

### Changed

- Comprehensive codebase cleanup and restructuring (#144)
- Improved logging with blpapi integration and performance optimizations (#135)
- Enhanced BEQS timeout handling with configurable `timeout` and `max_timeouts` parameters
- Updated README with comparison table, quickstart guide, and examples

### Fixed

- Fix BQL syntax documentation and error handling (#141, #142)
- Remove 1-minute offset for bare session names in bdtick (#139)
- Resolve Sphinx build errors and RST formatting issues

## [0.7.11] - 2025-11-12

### Added

- **BQL support**: Bloomberg Query Language with QueryRequest and result parsing
- **Sub-minute intervals for bdib**: 10-second bars via `intervalHasSeconds=True` flag
- pandas-market-calendars integration for exchange session resolution

### Changed

- Standardized Google-style docstrings across codebase
- Migrate to uv for development with PEP 621 pyproject.toml
- Switch to PyPI Trusted Publishing (OIDC)
- Exclude tests from wheel and sdist distributions

### Fixed

- Fix BQL to use correct service name and handle JSON response format
- Normalize UX* Index symbols; fix pandas 'M' deprecation to 'ME' in fut_ticker

## [0.7.10] - 2025-11-05

### Added

- Enhanced Bloomberg connection handling with alternative connection methods
- Market resolvers for active futures and CDX tickers

### Changed

- Replace flake8 with ruff for linting
- Update Python version requirements and dependencies
- Clean up CI workflows and documentation

## [0.7.9] - 2025-04-15

### Fixed

- Corrected typo (thanks to @ShiyuanSchonfeld)
- Pin pandas version due to pd.to_datetime behaviour change in format_raw
- Fix TLS Options typo when creating a new connection

### Changed

- Add exchanges support
- CI/CD configuration updates

## [0.7.2] - 2020-12-16

### Added

- Logo image for project branding

### Changed

- Use `async` for live data feeds
- Speed up by caching files
- Change logic of exchange lookup and market timing
- Push all values from live subscription
- Support for Python 3.8

### Fixed

- Proper caching implementation

## [0.7.0] - 2020-08-02

### Changed

- `bdh` preserves column orders (both tickers and flds)
- `timeout` argument is available for all queries
- `bdtick` usually takes longer to respond - can use `timeout=1000` for example if keep getting empty DataFrame

## [0.6.7] - 2020-05-17

### Added

- Add flexibility to use reference exchange as market hour definition
- No longer necessary to add `.yml` for new tickers, provided that the exchange was defined in `/xbbg/markets/exch.yml`

### Changed

- Switch CI from Travis to GitHub Actions

## [0.6.0] - 2020-01-23

### Added

- Tick data availability via bdtick()

### Changed

- Speed improvements by removing intermediate layer of generator for processing Bloomberg responses

## [0.5.0] - 2020-01-08

### Changed

- Rewritten library to add subscription, BEQS, simplify interface and remove dependency of `pdblp`

## [0.1.22] - 2019-09-15

### Security

- Remove PyYAML dependency due to security vulnerability

## [0.1.17] - 2019-07-01

### Added

- Add `adjust` argument in `bdh` for easier dividend / split adjustments

---

[Unreleased]: https://github.com/alpha-xone/xbbg/compare/v0.11.1...HEAD
[0.11.1]: https://github.com/alpha-xone/xbbg/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0
[0.10.3]: https://github.com/alpha-xone/xbbg/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/alpha-xone/xbbg/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/alpha-xone/xbbg/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/alpha-xone/xbbg/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/alpha-xone/xbbg/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/alpha-xone/xbbg/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/alpha-xone/xbbg/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/alpha-xone/xbbg/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/alpha-xone/xbbg/compare/v0.7.11...v0.8.0
[0.7.11]: https://github.com/alpha-xone/xbbg/compare/v0.7.10...v0.7.11
[0.7.10]: https://github.com/alpha-xone/xbbg/compare/v0.7.9...v0.7.10
[0.7.9]: https://github.com/alpha-xone/xbbg/compare/v0.7.2...v0.7.9
[0.7.2]: https://github.com/alpha-xone/xbbg/compare/v0.7.0...v0.7.2
[0.7.0]: https://github.com/alpha-xone/xbbg/compare/v0.6.7...v0.7.0
[0.6.7]: https://github.com/alpha-xone/xbbg/compare/v0.6.0...v0.6.7
[0.6.0]: https://github.com/alpha-xone/xbbg/compare/v0.5.1...v0.6.0
[0.5.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.5.1
[0.1.22]: https://github.com/alpha-xone/xbbg/releases/tag/v0.1.22
[0.1.17]: https://github.com/alpha-xone/xbbg/releases/tag/v0.1.17
