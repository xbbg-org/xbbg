# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0b4] - 2026-01-24

### Added
- **yas()**: New Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics
  - Provides convenient interface to Bloomberg's YAS calculator via `bdp()` overrides
  - `YieldType` enum for yield calculation type (`YTM=1`, `YTC=2`)
  - Supports settlement date, spread, yield, price, and benchmark overrides
  - Parameter mapping: `settle_dt` → `SETTLE_DT`, `yield_type` → `YAS_YLD_FLAG`, etc.
  - Available via `blp.yas()` or `from xbbg.api.fixed_income import yas, YieldType`
- **Treasury & SOFR futures support**: Added TY, ZN, ZB, ZF, ZT, UB, TN (Treasury), SFR, SR1, SR3 (SOFR), and ED (Eurodollar) futures to assets.yml (#198)

### Fixed
- **stream() field values**: Subscribed field values are now always included in output dict (#199)
  - Previously, fields not in `const.LIVE_INFO` (like `RT_BN_SURVEY_MEDIAN`) were filtered out
  - Output would show `FIELD='RT_BN_SURVEY_MEDIAN'` but contain `LAST_PRICE` value instead
  - Fix ensures the subscribed field's value is always present regardless of info filter
- **Futures symbol parsing for bdib**: Fixed `market_info()` to correctly parse futures symbols like `TYH6` → `TY` (#198)
  - Previously failed to identify root symbol when ticker had single-digit year suffix

## [0.11.0b3] - 2026-01-21

### Added
- **bqr()**: New Bloomberg Quote Request function emulating Excel `=BQR()` for dealer quote data (#22)
  - Retrieves tick-level quotes with broker/dealer attribution from MSG1 pricing sources
  - Supports date offsets (`-2d`, `-1w`) and explicit date ranges
  - Includes broker codes (`broker_buy`, `broker_sell`) for dealer identification
  - Works with Bloomberg tickers and ISINs (e.g., `/isin/US037833BA77@MSG1`)
  - Full multi-backend support (pandas, polars, pyarrow, duckdb)

### Fixed
- **Slow Bloomberg fields no longer timeout prematurely** (#193)
  - Bloomberg TIMEOUT events are now handled correctly - they indicate the request is still processing, not an error
  - Removed `max_timeouts` limit that caused requests to fail after ~10 seconds
  - Added `slow_warn_seconds` parameter (default: 15s) to warn about slow requests without aborting them
  - Requests will now wait indefinitely for Bloomberg response (or until connection lost)
  - Fields like `STOCHASTIC_OAS_MID_MOD_DUR` that take 10+ seconds now work correctly
- **Pipeline data types**: Preserve original data types in pipeline output instead of converting to strings (#191)
- **Backend/format attributes**: Preserve backend/format attributes in DataRequest pipeline helpers

- **Intraday cache now includes interval in path** (#80)
  - Different bar intervals (1m, 5m, 10s, etc.) are now cached separately
  - Previously, requesting 1-min bars then 5-min bars for the same ticker/date would return cached 1-min data
  - Cache path format: `{BBG_ROOT}/{asset}/{ticker}/{typ}/{interval}/{date}.parq`
  - Example: `Equity/AAPL US Equity/TRADE/5m/2025-01-15.parq`
  - **Breaking change**: Existing cached data without interval folder will be cache misses (first request will re-fetch)

## [0.11.0b2] - 2026-01-19

### Added
- **preferreds()**: New BQL convenience function to find preferred stocks for an equity ticker (e.g., `blp.preferreds('BAC')`)
- **corporate_bonds()**: New BQL convenience function to find active corporate bonds for a ticker (e.g., `blp.corporate_bonds('AAPL')`)

### Fixed
- **bdtick timezone fix**: Pass exchange timezone to `time_range()` to fix blank results for non-UTC exchanges like HK, Tokyo (#185)
- **bdtick timeout defaults**: Increase timeout from 10s to 2 minutes for tick data requests to prevent empty results
- **CI pre-release publishing**: Fix workflow to include pre-releases when publishing via workflow_dispatch

## [0.11.0b1] - 2026-01-10

### Added
- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow
- **Multi-backend support**: New `Backend` enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb
- **Output format control**: New `Format` enum with long, semi_long, wide options
- **Bloomberg Technical Analysis**: New `bta()` function for technical indicators (#175)
- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` configuration functions
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`
- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, `BlpRequestError`, etc.)
- `EngineConfig` dataclass and `configure()` function for engine configuration
- `Service` and `Operation` enums for Bloomberg service URIs
- CONTRIBUTING.md with comprehensive contribution guidelines
- CODE_OF_CONDUCT.md for community standards

### Changed
- All API functions now accept `backend` and `format` parameters
- Internal pipeline uses PyArrow tables with narwhals transformations
- Removed pytz dependency (using stdlib `datetime.timezone`)
- Updated SECURITY.md to reference current supported versions

### Deprecated
- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()` instead
- `lookupSecurity()` - will become `blkp()` in v1.0
- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0
- `bta_studies()` - renamed to `ta_studies()` in v1.0
- `getPortfolio()` - renamed to `bport()` in v1.0
- Helper functions (`dividend()`, `earning()`, `turnover()`, `adjust_ccy()`) moving to `xbbg.ext` in v1.0
- Futures/CDX utilities (`fut_ticker()`, `active_futures()`, `cdx_ticker()`, `active_cdx()`) moving to `xbbg.ext` in v1.0

### Fixed
- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output
- String concatenation in WIDE format conversion using `concat_str`

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0b1

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

[Unreleased]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b4...HEAD
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
