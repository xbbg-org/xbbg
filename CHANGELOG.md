# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CONTRIBUTING.md with comprehensive contribution guidelines
- CODE_OF_CONDUCT.md for community standards
- CHANGELOG.md for tracking version history

### Changed
- Updated SECURITY.md to reference current supported versions (0.10.x and 0.9.x)

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

[Unreleased]: https://github.com/alpha-xone/xbbg/compare/v0.10.3...HEAD
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
