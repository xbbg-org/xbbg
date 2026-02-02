# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Highlights

**v0.11.0** is a major release featuring a complete rewrite of the internal data pipeline using PyArrow, multi-backend output support, and several new API functions for fixed income and technical analysis.

- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow for improved performance
- **Multi-backend support**: Output to pandas, Polars, PyArrow, DuckDB, or narwhals with the new `Backend` enum
- **New API functions**: `bta()` for technical analysis, `bqr()` for dealer quotes, `yas()` for fixed income analytics
- **BQL helpers**: `preferreds()` and `corporate_bonds()` convenience functions
- **Dependency cleanup**: Removed pandas-market-calendars and the trials mechanism for a leaner install
- **v1.0 migration path**: Deprecation warnings and forward-compatible APIs prepare for the upcoming v1.0 release

### Added

#### Core Architecture
- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow
- **Multi-backend support**: New `Backend` enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb
- **Output format control**: New `Format` enum with long, semi_long, wide options
- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` configuration functions
- All API functions now accept `backend` and `format` parameters

#### New API Functions
- **bta()**: Bloomberg Technical Analysis function for 50+ technical indicators (#175)
- **bqr()**: Bloomberg Quote Request function emulating Excel `=BQR()` for dealer quote data (#22)
  - Retrieves tick-level quotes with broker/dealer attribution from MSG1 pricing sources
  - Supports date offsets (`-2d`, `-1w`) and explicit date ranges
  - Includes broker codes (`broker_buy`, `broker_sell`) for dealer identification
- **yas()**: Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics
  - `YieldType` enum for yield calculation type (`YTM=1`, `YTC=2`)
  - Supports settlement date, spread, yield, price, and benchmark overrides
- **preferreds()**: BQL convenience function to find preferred stocks for an equity ticker
- **corporate_bonds()**: BQL convenience function to find active corporate bonds for a ticker

#### Infrastructure & Configuration
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`
- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, `BlpRequestError`, etc.)
- `EngineConfig` dataclass and `configure()` function for engine configuration
- `Service` and `Operation` enums for Bloomberg service URIs
- **Treasury & SOFR futures support**: Added TY, ZN, ZB, ZF, ZT, UB, TN (Treasury), SFR, SR1, SR3 (SOFR), and ED (Eurodollar) futures to assets.yml (#198)

#### Logging & Observability
- Comprehensive logging audit and enhancements across critical paths
- Added `logger.error()` before raising exceptions in `process.py` for better error traceability
- Added INFO logging for stale session/service handle removal in `conn.py`
- Added DEBUG logging for Bloomberg service lifecycle events
- Added ERROR logging with re-raise for directory creation failures in `files.py`
- New `xbbg/tests/test_logging.py` with 9 tests covering critical logging paths

#### Documentation
- CONTRIBUTING.md with comprehensive contribution guidelines
- CODE_OF_CONDUCT.md for community standards

### Changed

#### Breaking Changes
- **Intraday cache now includes interval in path** (#80)
  - Different bar intervals (1m, 5m, 10s, etc.) are now cached separately
  - Cache path format: `{BBG_ROOT}/{asset}/{ticker}/{typ}/{interval}/{date}.parq`
  - Existing cached data without interval folder will be cache misses (first request will re-fetch)

#### Internal Changes
- Internal pipeline uses PyArrow tables with narwhals transformations
- Removed pytz dependency (using stdlib `datetime.timezone`)
- Updated SECURITY.md to reference current supported versions
- Internal class renames with backward compatible aliases:
  - `YamlMarketInfoProvider` → `MetadataProvider`
  - `ExchangeYamlResolver` → `ExchangeMetadataResolver`

#### Logging Adjustments
- `BBG_ROOT not set` message promoted from INFO → WARNING (meaningful configuration issue)
- Cache save "skipping due to market timing" demoted from INFO → DEBUG (internal policy decision)
- Cache load failures for corrupt files now log WARNING (previously DEBUG)

### Deprecated

The following functions will be renamed or reorganized in v1.0:
- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()` instead
- `lookupSecurity()` - will become `blkp()` in v1.0
- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0
- `bta_studies()` - renamed to `ta_studies()` in v1.0
- `getPortfolio()` - renamed to `bport()` in v1.0
- Helper functions (`dividend()`, `earning()`, `turnover()`, `adjust_ccy()`) moving to `xbbg.ext` in v1.0
- Futures/CDX utilities (`fut_ticker()`, `active_futures()`, `cdx_ticker()`, `active_cdx()`) moving to `xbbg.ext` in v1.0

### Removed
- **Trials mechanism**: Eliminated the retry-blocking system that caused silent failures
  - The trials system tracked failed API requests and blocked future attempts after 2 failures
  - This caused issues when bugs were fixed (stale entries still blocked requests)
  - Pipeline caching already handles "don't re-fetch" use case properly
  - Deleted `xbbg/core/utils/trials.py` and related test files
- **pandas-market-calendars dependency**: Simplified exchange metadata resolution
  - Removed `PmcCalendarResolver` from resolver chain
  - Exchange information now sourced exclusively from Bloomberg API with local caching
  - Removed `pmc_extended` context option (no longer needed)

### Fixed

#### Critical Fixes
- **Import without blpapi installed**: Fixed `AttributeError` when importing xbbg without blpapi installed (#200)
- **Japan/non-US timezone fix for bdib**: Fixed timezone conversion for non-US exchanges (#198)
  - Bloomberg returns trading hours in EST; now correctly converted to exchange's local timezone
- **stream() field values**: Subscribed field values are now always included in output dict (#199)
  - Previously, fields not in `const.LIVE_INFO` were filtered out incorrectly
- **Slow Bloomberg fields no longer timeout prematurely** (#193)
  - Bloomberg TIMEOUT events now handled correctly; requests wait for response
  - Added `slow_warn_seconds` parameter (default: 15s) to warn without aborting

#### Data & Pipeline Fixes
- **Pipeline data types**: Preserve original data types in pipeline output instead of converting to strings (#191)
- **Backend/format attributes**: Preserve backend/format attributes in DataRequest pipeline helpers
- **Futures symbol parsing for bdib**: Fixed `market_info()` to correctly parse futures symbols like `TYH6` → `TY` (#198)
- **get_tz() optimization**: Direct timezone strings like `"America/New_York"` or `"UTC"` are now recognized without calling Bloomberg API

#### Tick Data Fixes
- **bdtick timezone fix**: Pass exchange timezone to `time_range()` to fix blank results for non-UTC exchanges (#185)
- **bdtick timeout defaults**: Increased timeout from 10s to 2 minutes for tick data requests

#### Other Fixes
- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output
- String concatenation in WIDE format conversion using `concat_str`
- Fixed 10 f-string logging statements to use %-formatting (G004 compliance)
- Changed `.error(..., exc_info=True)` to `.exception()` in `process.py` (G201 compliance)

### Developer
- **CI logging enforcement**: Added `LOG` (flake8-logging) and `G` (flake8-logging-format) rules to ruff configuration

---

## Beta Release History

The following beta releases were made during v0.11.0 development:

- **v0.11.0b5** (2026-01-25): Import fix without blpapi, timezone fixes, removed trials/PMC
- **v0.11.0b4** (2026-01-24): Added yas(), Treasury/SOFR futures, stream() fix (#199)
- **v0.11.0b3** (2026-01-21): Added bqr(), timeout handling, cache interval fix (#80)
- **v0.11.0b2** (2026-01-19): Added preferreds()/corporate_bonds(), bdtick fixes
- **v0.11.0b1** (2026-01-10): Arrow-first pipeline, multi-backend support, bta()

## [0.10.3] - 2024-01-07

### Fixed
- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output

### Changed
- Re-enabled futures and CDX resolver tests
- Updated live endpoint tests for LONG format output

### Improved
- Code style improvements using contextlib.suppress instead of try-except-pass

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.2...v0.10.3

## [0.10.2] - 2024-01-06

### Changed
- CI/CD improvements with reusable workflows (workflow_call) for release automation
- Separated pypi_upload workflow for trusted publisher compatibility

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.1...v0.10.2

## [0.10.1] - 2024-01-05

### Fixed
- Persist blp.connect() session for subsequent API calls (#165)

### Changed
- Trigger release workflows via release event instead of workflow_dispatch

### Documentation
- Removed Gitter badge (replaced by Discord)
- Added Discord community link and badge

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.0...v0.10.1

## [0.10.0] - 2024-01-04

### Added
- Updated polars-bloomberg support for BQL, BDIB and BSRCH (#155)

### Fixed
- Add identifier type prefix to B-Pipe subscription topics (#156)
- Remove pandas version cap to support Python 3.14 (#161)
- Resolve RST formatting warning in index.rst (#162)
- Update Japan equity market hours for TSE trading extension (#163)

### Contributors
- @MarekOzana made their first contribution in #155

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.9.1...v0.10.0

## [0.9.1] - 2023-12-15

### Fixed
- Fix BQL returning only one row for multi-value results (#152)

### Documentation
- Add blank lines around latest-release markers in index.rst

### CI/CD
- Remove redundant release triggers from workflows
- Trigger release workflows explicitly from semantic_version

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.9.0...v0.9.1

## [0.9.0] - 2023-12-10

### Added
- Add etf_holdings() function for retrieving ETF holdings via BQL (#147)
- Add multi-day support to bdib() (#148)
- Add multi-day cache support for bdib() (#149)

### Fixed
- Resolve RST duplicate link targets and Sphinx build warnings

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.2...v0.9.0

## [0.8.2] - 2023-11-20

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.2

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.1...v0.8.2

## [0.8.1] - 2023-11-15

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.1

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.0...v0.8.1

## [0.8.0] - 2023-11-10

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.0

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.7.11...v0.8.0

## [0.7.11] - 2023-10-20

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.11

## [0.7.10] - 2023-10-15

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.10

## [0.7.9] - 2023-10-10

See release notes: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.9

## [0.7.2] - 2023-08-15

### Changed
- Use `async` for live data feeds

## [0.7.0] - 2023-08-01

### Changed
- `bdh` preserves column orders (both tickers and flds)
- `timeout` argument is available for all queries
- `bdtick` usually takes longer to respond - can use `timeout=1000` for example if keep getting empty DataFrame

## [0.6.6] - 2023-07-15

### Added
- Add flexibility to use reference exchange as market hour definition
- No longer necessary to add `.yml` for new tickers, provided that the exchange was defined in `/xbbg/markets/exch.yml`

## [0.6.0] - 2023-06-01

### Added
- Tick data availability

### Improved
- Speed improvements

## [0.5.0] - 2023-04-01

### Changed
- Rewritten library to add subscription, BEQS, simplify interface and remove dependency of `pdblp`

## [0.1.22] - 2022-12-01

### Security
- Remove PyYAML dependency due to security vulnerability

## [0.1.17] - 2022-10-01

### Added
- Add `adjust` argument in `bdh` for easier dividend / split adjustments

---

[Unreleased]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b5...HEAD
[0.11.0b5]: https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b5
[0.11.0b4]: https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b4
[0.11.0b3]: https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b3
[0.11.0b2]: https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b2
[0.11.0b1]: https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b1
[0.10.3]: https://github.com/alpha-xone/xbbg/releases/tag/v0.10.3
[0.10.2]: https://github.com/alpha-xone/xbbg/releases/tag/v0.10.2
[0.10.1]: https://github.com/alpha-xone/xbbg/releases/tag/v0.10.1
[0.10.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.10.0
[0.9.1]: https://github.com/alpha-xone/xbbg/releases/tag/v0.9.1
[0.9.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.9.0
[0.8.2]: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.2
[0.8.1]: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.1
[0.8.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.8.0
[0.7.11]: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.11
[0.7.10]: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.10
[0.7.9]: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.9
[0.7.2]: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.2
[0.7.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.7.0
[0.6.6]: https://github.com/alpha-xone/xbbg/releases/tag/v0.6.6
[0.6.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.6.0
[0.5.0]: https://github.com/alpha-xone/xbbg/releases/tag/v0.5.0
[0.1.22]: https://github.com/alpha-xone/xbbg/releases/tag/v0.1.22
[0.1.17]: https://github.com/alpha-xone/xbbg/releases/tag/v0.1.17
