# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Subscription field exposure** (#265): `all_fields` on `asubscribe`, `astream`, and `stream` (and `PyEngine.subscribe` / `subscribe_with_options`). When `False` (default), batches include only requested fields plus `MKTDATA_EVENT_TYPE` and `MKTDATA_EVENT_SUBTYPE`. When `True`, each batch includes every top-level scalar field Bloomberg sends (e.g. full `SUMMARY`/`INITPAINT` snapshots), with the schema growing as new fields appear. The same flag is available on `avwap`, `amktbar`, `adepth`, and `achains` for consistency across streaming services.

## [1.0.0rc1] - 2026-03-23

### Added

- **Intraday timezone controls (`request_tz` / `output_tz`)**: `abdib`/`bdib`, `abdtick`/`bdtick`, `arequest`, and Rust `RequestParams` accept optional `request_tz` (interpret naive `start_datetime`/`end_datetime` before Bloomberg) and `output_tz` (relabel Arrow `time` to an IANA zone). Supported labels include `UTC`, `local`, `exchange`, `NY`/`LN`/`TK`/`HK`, reference tickers, and explicit IANA names. Implemented in `xbbg-async` (`chrono-tz`, `iana-time-zone`) with nested RefData calls routed through `request_without_intraday_transform` to avoid recursion.
- **Pixi environment management**: Added `pixi.toml` with 11 environments (default, test, lint, benchmark, docs, py310–py314), 21 tasks, and conda-forge deps for Rust, libclang, and pyarrow. Single `pixi install && pixi run install` replaces manual toolchain setup.
- **mimalloc allocator**: PyO3 extension now uses mimalloc by default (feature-gated) for improved Rust-side allocation performance.
- **`ty` type checking**: Lint environment includes Astral's `ty` type checker alongside ruff; CI lint job now runs type checking automatically.
- **SOCKS5 proxy support** (#180): Route Bloomberg connections through a SOCKS5 proxy via `socks5_host` and `socks5_port` kwargs on `configure()` and `Engine()`. Uses the Bloomberg SDK's `Socks5Config` API (no auth, hostname + port only).
- **Enterprise-friendly request middleware context**: `RequestContext` now carries a read-only `RequestEnvironment` snapshot so middleware can inspect engine source, host/port, server list, auth method, app/user context, and validation mode without reaching into private globals.

### Changed

- **Workspace default build scope**: Root `Cargo.toml` sets `[workspace].default-members` to exclude `crates/datamock` and `crates/datamock-sys`, so plain `cargo build` / `cargo test` at the repo root does not compile the C++ mock stack. Use `cargo test -p datamock` or `cargo build --workspace` when working on mocks. The `mock` Cargo feature on `xbbg-sys` and downstream crates remains optional and off by default.
- **Standardised on `BLPAPI_ROOT`**: Removed `XBBG_DEV_SDK_ROOT` env var across the codebase (build.rs, scripts, docs). SDK discovery now uses `BLPAPI_ROOT` only (set by pixi activation or `.cargo/config.toml`). No hardcoded SDK version — build.rs scans versioned subdirs automatically.
- **Removed `BLPAPI_LINK_LIB_NAME`**: Library name is now always auto-detected by `detect_link_lib_name()` based on target platform.
- **Build profiles cleaned up**: Removed redundant `[profile.release.package.xbbg_core]`; added `[profile.dev.package."*"] opt-level = 2` so all deps are optimised in dev builds; `pixi run install` uses `target-cpu=native` for local builds.
- **Migrated from uv to pixi for dev tooling**: Removed `[dependency-groups]`, `[tool.uv.*]` from pyproject.toml; deleted `uv.lock`; pre-commit hooks use bare `ruff` instead of `uvx ruff`; README dev instructions updated to pixi commands.
- **Consolidated config files**: Merged `.coveragerc` into `pyproject.toml` `[tool.coverage.*]`; deleted `.env` (pixi activation replaces it); un-gitignored `.cargo/config.toml` (now contains only project-standard `BLPAPI_ROOT`).
- **CI lint job uses pixi**: `lint-python` job now uses `prefix-dev/setup-pixi` with the lightweight `lint` environment, replacing `uvx ruff`.
- **Request tracing is more consistent**: Python request middleware now sees the generated `request_id` in both `RequestContext.request_id` and `RequestContext.params_dict`, centralized request logs include the request ID, and the Rust request path forwards it as the Bloomberg request label for better audit/debug correlation.
- **Bindgen/libclang toolchain aligned**: All Rust FFI crates now use `bindgen 0.72.1` with runtime loading, and the pixi environment now requires `libclang >=22`. This fixes incorrect Bloomberg SDK `blpapi_ManagedPtr_t_` generation under newer libclang releases and removes the need for correlation-ID layout workarounds.

### Removed

- **`XBBG_DEV_SDK_ROOT` env var**: Use `BLPAPI_ROOT` instead. The `.env` file fallback in `blpapi-sys/build.rs` has been removed.
- **`BLPAPI_LINK_LIB_NAME` env var**: Auto-detection covers all platforms.
- **`uv.lock`**: Replaced by `pixi.lock`.
- **`.coveragerc`**: Configuration moved to `pyproject.toml`.

### Fixed

- **datamock C API** (`datamock_c_api.cpp`): `datamock_Message_typeString` and `datamock_Element_nameString` returned `const char*` into temporaries (`Name` destroyed at end of full-expression). Pointers are now stable via thread-local string copies before returning.
- **datamock tests**: C API integration tests moved to `crates/datamock/tests/c_api.rs`; message/field strings decoded with lossy UTF-8 (mock data is not always valid UTF-8); tests serialized behind a mutex to avoid races on C++ global state; `build.rs` passes `-Wno-unused-parameter` for stub-heavy sources.
- **datamock C++ warnings**: Safer null/empty check in `Name` equality vs C string; `ServiceRefData` marks `name` / `createRequest` with `override`; `SchemaTypeDefinition` destructor matches throwing body with `noexcept(false)`.
- **De-duplicated Rust recipe helpers**: Extracted `array_value_as_string`, `date32_to_naive`, `as_string_col` into shared `xbbg-recipes/src/utils.rs`.
- **De-duplicated Python code**: Consolidated `_to_pandas_wide` (was in both `info.py` and `bloomberg.py`); unified `_FUTURES_MONTH_CODES` to use Rust-sourced `ext_get_futures_months()`; extracted `_apply_settle_override` helper replacing 5 repeated blocks in `bonds.py`.

## [1.0.0b7] - 2026-03-18

### Added

- **Python type stubs** for `xbbg._core` via `pyo3-stub-gen`: auto-generated `.pyi` files provide full IDE autocompletion and type-checker support for `EngineConfig`, `Engine`, `Subscription`, and all Rust-backed functions. Includes `py.typed` PEP 561 marker.
- **macOS ARM64 wheel builds** in CI and release workflows. Wheels are now built and tested for Linux x86_64, Windows x86_64, and macOS ARM64 across Python 3.10–3.14.
- **CI auto-regeneration of type stubs**: stubs are regenerated and auto-committed after all CI checks pass, ensuring `.pyi` files stay in sync with Rust annotations.
- **`Engine` class** for non-global multi-engine routing. Create independent engine instances and scope them via `with engine:` (sync) or `async with engine:` (async). The global `configure()` + `blp.bdp()` API is unchanged — `Engine` is fully opt-in.
- **TLS support** for encrypted B-PIPE connections: `tls_client_credentials`, `tls_trust_material`, `tls_handshake_timeout_ms` on `EngineConfig` and `configure()`.
- **Identity lifecycle FFI**: `Session.generate_token()`, `Session.send_authorization_request()`, `Session.subscribe_with_identity()` for multi-user entitlement flows.
- **Runtime SDK version**: `get_sdk_info()` now includes `runtime_version` field reporting the linked Bloomberg C SDK version via `blpapi_getVersionInfo()` (e.g., `"3.26.2.1"`). Also available as `xbbg._core.sdk_version()` → `(major, minor, patch, build)` tuple.
- **Async request cancellation**: cancelling the Python task for any async Bloomberg request now propagates to the Bloomberg SDK via `Session::cancel(correlationId)`. The worker drops local request state immediately after a successful cancel and remains usable for subsequent requests.
- **Reconnect resilience (Phases 1–3)** for the Rust engine (#245):
  - **Fail-fast on session death**: request workers now immediately drain all in-flight requests with an error on `SessionTerminated`/`SessionConnectionDown` instead of letting callers hang indefinitely. Workers are marked `Dead` and restored to `Healthy` on `SessionConnectionUp`.
  - **Service re-open before re-subscribe**: `recover_active_subscriptions()` now re-opens all previously opened services before re-issuing subscriptions after reconnect, fixing a critical gap where recovery could silently fail.
  - **Health-aware dispatch**: request pool round-robin skips `Dead` workers; returns `AllWorkersDown` immediately if the entire pool is dead.
  - **Retry with exponential backoff**: `RetryPolicy` on `EngineConfig` (`retry_max_retries`, `retry_initial_delay_ms`, `retry_backoff_factor`, `retry_max_delay_ms`) enables automatic retry of transient request failures.
  - **Recovery limits**: `max_recovery_attempts` and `recovery_timeout_ms` cap subscription recovery to prevent infinite loops.
  - **Lifecycle events**: `ConnectionLost`, `Reconnected`, and `RecoveryFailed` events emitted to subscription status for observability.
  - **New error variants**: `BlpAsyncError::SessionLost` and `AllWorkersDown` mapped to Python `BlpSessionError`.
  - **Python surface**: all new config fields exposed in `EngineConfig`, `configure()`, and `Engine()`; `engine.worker_health()` returns per-worker health status.
- **Multi-server failover** via `servers` kwarg (#250). Pass a list of `(host, port)` tuples for automatic Bloomberg SDK failover using `setServerAddress(host, port, index)`. Existing `host`/`port` kwargs unchanged for single-server use.
- **ZFP over leased lines** via `zfp_remote` kwarg (#255). Set to `"8194"` or `"8196"` with TLS credentials to connect via Bloomberg Zero Footprint without a local Terminal. Uses `ZfpUtil::getOptionsForLeasedLines` from the SDK.
- **Identity entitlement checking** (#252): `Identity.is_authorized(service)`, `Identity.has_entitlements(service, eids)`, and `Identity.seat_type()` for B-PIPE multi-user entitlement verification.
- **Bloomberg SDK logging bridge** (#253): `enable_sdk_logging(level)` and `EngineConfig.sdk_log_level` route native BLPAPI internal logs into `xbbg-log` tracing target `xbbg.sdk`. Default is **off**; registration happens before session start when enabled.

### Changed

- **Engine Architecture & EngineConfig documentation**: README now includes a full reference for all 20+ `EngineConfig` fields (worker pools, subscription tuning, buffers, validation, auth), an ASCII architecture diagram, and auth mode examples.
- **API surface updated to v1**: README function tables, examples, and Connection Options section now reflect v1 names (`blkp`, `bport`, `earnings`, `convert_ccy`, `configure()`, `subscribe`/`stream`, etc.) and remove stale v0.x references (`lookupSecurity`, `exchange_tz`, `set_format`, `Format` enum).
- **Dev setup and contributing guides** updated for v1 project structure (`py-xbbg/src` paths, Astro docs, `uv sync` dependency-groups).

### Fixed

- **cargo-deny advisory ignores** for unmaintained `unic-*` crates (transitive deps of `rustpython-parser` via `pyo3-stub-gen`, build-time only).

## [1.0.0b6] - 2026-03-16

### Changed

- **Internal correlation ID dispatch overhaul**: The async engine no longer uses raw Bloomberg integer correlation IDs as direct slab indexes. All request and session dispatch now routes through an explicit dispatch-key layer at the session boundary, preventing ID collisions between auth subscriptions and user requests and aligning lifecycle tracking with Bloomberg SDK semantics.
- **Logging levels better match the quiet-by-default workflow**: Request roundtrip telemetry and Python subscription lifecycle messages now emit at `DEBUG` instead of `INFO`, while exchange metadata fetch failures that cleanly fall back now emit at `WARNING` instead of `ERROR`, keeping normal control-flow noise out of default logs without hiding real request telemetry.

### Fixed

- **SAPI authentication fails with `BLPAPI_ERROR_DUPLICATE_CORRELATIONID`** ([#248](https://github.com/alpha-xone/xbbg/issues/248)): `CorrelationId::default()` returned `Int(0)`, which is a valid explicit correlation ID. When `setSessionIdentityOptions` registered `Int(0)` for the auth flow, subsequent `sendRequest` calls with the same default ID were rejected as duplicates (rc=131077). The default is now `CorrelationId::Unset` (maps to `BLPAPI_CORRELATION_TYPE_UNSET` in the FFI struct), matching the official Python `blpapi` behavior where the SDK auto-generates unique IDs. Affects all SAPI authentication modes (`app`, `user`, `userapp`, `dir`, `token`).

## [1.0.0b5] - 2026-03-12

### Added

- **Rust-backed Bloomberg session authentication for v1**: Added structured auth support across the Rust core, async engine, and PyO3 bindings for `user`, `app`, `userapp`, `dir`, `manual`, and `token` auth modes, enabling SAPI/B-PIPE session configuration from the v1 Python API.
- **Request middleware chain for telemetry and wrappers**: Added `RequestContext` plus middleware registration helpers around `arequest()` so callers can layer centralized request instrumentation, logging, caching, and wrapper behavior without patching individual endpoint functions.

### Changed

- **`configure()` is now the canonical engine/session setup surface**: Connection/auth setup now flows through `configure()` with support for legacy aliases such as `server_host`, `server_port`, `max_attempt`, and `auto_restart`, while the temporary `connect()` / `disconnect()` wrappers were removed before release.

### Fixed

- **Auth/session startup failures now propagate with context**: Request and subscription workers now wait for Bloomberg startup/auth events before proceeding, so failed authentication and session-start problems surface as actionable errors instead of being swallowed or masked by later service-open failures.
- **Rust/Python CI regressions in the new auth path**: Cleaned release-blocking lint and formatting issues in the new auth/middleware code paths so the full Linux/Windows CI matrix passes with the beta 5 changes.

## [1.0.0b4] - 2026-03-10

### Changed

- **Subscription failure isolation for mixed-topic streams**: Real-time subscriptions now treat Bloomberg `SubscriptionFailure` and unexpected `SubscriptionTerminated` events as per-ticker status instead of fatal stream errors when other topics remain healthy. Mixed subscriptions keep delivering data for valid tickers while exposing failed topics through subscription metadata.
- **Subscription lifecycle observability**: Real-time subscriptions now retain bounded status/event history for topic lifecycle transitions, session connectivity, service readiness, slow-consumer/data-loss signals, and reconnect recovery attempts so callers can inspect operational state without scraping logs.
- **Non-fatal disconnect handling with opt-in recovery**: `SessionConnectionDown` no longer tears down healthy subscriptions by default. Callers can opt into `recovery_policy="resubscribe"` to issue reconnect-time recovery subscribes while tracking attempts, successes, and last recovery errors through subscription status metadata.

### Added

- **Subscription failure metadata**: Python subscriptions now expose `failed_tickers` and `failures` so callers can inspect which topics Bloomberg rejected or terminated, along with the reported reason and failure kind.
- **Subscription health/status surfaces**: Python subscriptions now expose `status`, `events`, `topic_states`, `session_status`, `admin_status`, `service_status`, `all_failed`, and expanded `stats` fields including data-loss counters, last-message timestamps, and effective overflow policy.

## [1.0.0b3] - 2026-03-06

### Added

- **Backend enum and availability checks** ([#234](https://github.com/alpha-xone/xbbg/issues/234)): Ported `Backend` enum and backend availability infrastructure from `release/0.x` into `py-xbbg/src/xbbg/backend.py`. The canonical `Backend` enum now has all 13 backends (added `CUDF`, `MODIN`, `DASK`, `IBIS`, `PYSPARK`, `SQLFRAME`). New public helpers: `is_backend_available()`, `check_backend()`, `get_available_backends()`, `print_backend_status()`, `validate_backend_format()`, `is_format_supported()`, `get_supported_formats()`, `check_format_compatibility()`. Includes `MIN_VERSIONS`, `PACKAGE_NAMES`, `MODULE_NAMES`, and `SUPPORTED_FORMATS` dicts for version validation and actionable install instructions.

### Changed

- **Subscription mutation synchronization**: Refactored subscription worker ownership to split the single-owner pool lease from a cloneable command handle, allowing subscription `add()`/`remove()` paths in both `xbbg-async` and PyO3 to drop metadata locks before awaiting Bloomberg command dispatch while still serializing mutations safely.

### Fixed

- **Additional GIL release coverage in PyO3 bindings**: Released the GIL around synchronous cache-save calls, Arrow pivot/format inspection helpers, and subscription metadata snapshots so Python threads are not blocked during disk I/O, pure Rust Arrow work, or waits on subscription state locks.
- **Reduced avoidable Arrow-path copies**: Removed intermediate string allocations for borrowed Bloomberg string/enum values and stopped cloning field-name/subfield-name vectors in `refdata`, `histdata`, and `bulkdata` extraction paths before the existing zero-copy PyArrow export boundary.
- **Removed unused `lief` dependency**: Dropped `lief>=0.17` from core `[project.dependencies]`; the package was never imported anywhere in the codebase.

## [1.0.0b2] - 2026-03-05

### Added

- **Field-validation toggle for refdata/histdata requests**: Added optional `validate_fields` request parameter in `request()`/`arequest()` and typed wrappers (`abdp`/`bdp`, `abdh`/`bdh`, `abds`/`bds`). This supports per-request strict validation override while still honoring engine-level `validation_mode` defaults.
- **Engine-side field-validation enforcement**: `xbbg-async` now validates requested fields for `ReferenceDataRequest` and `HistoricalDataRequest` before dispatch when validation is enabled, returning configuration errors for unknown Bloomberg fields in strict mode.
- **Live validation toggle smoke script**: Added `py-xbbg/tests/live/field_validation_toggle_smoke.py` to verify on/off behavior against a connected Bloomberg session.
- **Request-plumbing coverage for `validate_fields`**: Added `py-xbbg/tests/test_validate_fields_toggle.py` to verify Python parameter serialization and forwarding through async/sync wrappers.

### Changed

- **Canonical exception exports**: `xbbg.exceptions` now re-exports Rust `_core` exception classes (`BlpError`, `BlpRequestError`, etc.) as the single source of truth, with Python-only exceptions remaining additive.
- **Validation helper compatibility**: Preserved `BlpValidationError.from_rust_error(...)` by attaching the compatibility classmethod to the canonical Rust-backed validation exception.
- **Generated sync wrapper metadata**: `blp.py` generated sync wrappers now derive `__doc__` and `__annotations__` from async templates directly; remaining manual generated sync wrapper boilerplate was removed.
- **Integration logging expectations**: Updated logging integration assertions to match centralized `arequest` request logging (`bloomberg ... ReferenceDataRequest`) instead of deprecated endpoint-specific debug strings.
- **Optional pandas integration paths**: Updated pandas-dependent integration tests to use `pytest.importorskip("pandas")`, avoiding hard failures when pandas is not installed.

### Fixed

- **`except BlpError` catchability gap**: Runtime exceptions raised by Rust (for example `BlpRequestError`) are now catchable via `xbbg.exceptions.BlpError` import paths because both now point to the same canonical Rust exception hierarchy.

## [1.0.0b1] - 2026-03-03

### Added

- **Endpoint-factory regression tests**: Added focused coverage for generated `abflds`/`bflds` and `abqr`/`bqr` routing, validation, and reshape behavior in `py-xbbg/tests/test_endpoint_factory_bflds.py` and `py-xbbg/tests/test_endpoint_factory_bqr.py`

### Changed

- **Template endpoint generation in `blp.py`**: Migrated clean-fit wrappers to generated async/sync endpoints backed by `_GeneratedEndpointSpec` and `_EndpointPlan`, including `abdp`/`bdp`, `abdh`/`bdh`, `abds`/`bds`, `abdib`/`bdib`, `abdtick`/`bdtick`, `abql`/`bql`, `abqr`/`bqr`, `absrch`/`bsrch`, `abeqs`/`beqs`, `ablkp`/`blkp`, `abport`/`bport`, `abcurves`/`bcurves`, `abgovts`/`bgovts`, and `abflds`/`bflds`

### Fixed

- **`bqr` pandas dependency regression**: Removed unconditional `to_pandas()` conversion in BQR postprocessing; quote requests now use Arrow-native checks/reshape and run without requiring pandas for standard flows

## [1.0.0a3] - 2026-02-27

### Added

- **`bqr()`/`abqr()` Bloomberg Quote Request**: Tick-level dealer quotes with `date_offset` (`-2d`, `-1w`, `-3h`), `start_date`/`end_date` date ranges, and optional `include_broker_codes`, `include_spread_price`, `include_yield`, `include_condition_codes`, `include_exchange_codes` parameters. Generic extractor fallback reshaped via `_reshape_bqr_generic()`
- **`bflds()`/`abflds()` unified field metadata lookup**: Single function for both field info (`fields=[...]`) and keyword search (`search_spec='...'`). `bfld`/`abfld` provided as backward-compatible aliases. Convenience wrappers `fieldInfo()`/`fieldSearch()` preserved
- **`include_security_errors` option for `bdp()`/`arequest()`**: Optionally surface per-security failures as rows in the result DataFrame instead of silently dropping them
- **Extension modules (`xbbg.ext`)**: `bonds` (6 functions), `options` (6 functions + 5 enums), `cdx` (8 functions) for fixed income, equity options, and credit default swap index analytics
- **Streaming performance enhancements**: Per-subscription config (`flush_threshold`, `overflow_policy`, `stream_capacity`), observability metrics via shared atomics, `tick_mode` support
- **Live integration tests**: 69 tests across `test_ext_bonds.py` (21), `test_ext_options.py` (20), `test_ext_cdx.py` (22) covering all ext module functions
- **Streaming tests**: Tests for `tick_mode`, per-subscription config, and observability metrics
- **Rust exchange/session APIs**: Added low-level exchange resolution support with `ExchangeInfo` metadata, runtime exchange overrides, session timezone conversion utilities, and `market_timing` helpers in the Rust layer (`xbbg-ext`, `xbbg-async`, `pyo3-xbbg`)
- **Live exchange smoke test**: Added `py-xbbg/tests/live/test_exchange_resolution.py` covering override precedence, UTC session conversion, live `resolve_exchange`, `fetch_market_info`, and `market_timing`

### Changed

- **README**: Updated API reference tables with `bflds()`, expanded BQR section with spread/yield/broker parameters and examples
- **Futures resolver**: Aligned with `release/0.x` chain methodology (`FUT_CHAIN_LAST_TRADE_DATES`)
- **CDX resolver**: Aligned methodology with `release/0.x`

### Removed

- **Legacy `xbbg/` Python package directory**: Fully removed; all code now lives in `py-xbbg/src/xbbg/`

### Fixed

- **Empty `RecordBatch` construction**: Handle empty ordered RecordBatch in `xbbg-async` without panic
- **Security failure surfacing**: `refdata` extractor now properly surfaces per-security errors instead of silently dropping them
- **`FIELD_SEARCH` extractor**: Corrected to use `ExtractorHint.FIELD_INFO` instead of generic extractor
- **Unused `logging` import in `ext/options.py`**: Removed to pass ruff lint
- **Test imports**: `BlpInternalError` imported from `_core` (Rust) instead of `exceptions` (Python)
- **CI fixes**: Resolved 4 Python test failures, clippy warnings (`too_many_arguments`, `SubscriptionMetrics` re-export), ruff check/format violations, cargo fmt formatting, module path for `test_markets.py`, Linux test runtime setup
- **Exchange refdata parsing shape support**: `resolve_exchange` now handles both WIDE and LONG refdata responses by mapping `(field, value)` rows when Bloomberg returns long-shape metadata

## [1.0.0a2] - 2026-02-19

### Changed

- **README**: Comprehensive rewrite with full API reference tables, comparison matrix, multi-backend documentation, detailed intraday session guide, fixed income/options/CDX analytics examples, troubleshooting section, and data storage documentation

## [1.0.0a1] - 2026-02-19

### Added

- **Rust-powered engine**: Complete ground-up rewrite delivering up to **10x faster** data retrieval with zero-copy Arrow transfer between Rust and Python. The engine spans 11 purpose-built crates: safe FFI bindings with SIMD-accelerated parsing (`blpapi-sys`, `xbbg-core`), an async worker pool engine with state machines for every Bloomberg request type (`xbbg-async`), Rust ports of extension and recipe logic (`xbbg-ext`, `xbbg-recipes` -- all 12 recipes exposed via PyO3), zero-GIL tracing (`xbbg-log`), CI/test stubs (`xbbg-sys`), and PyO3 Python bindings (`pyo3-xbbg`)
- **New Python package (`py-xbbg/`)**: Complete v1 API powered by the Rust backend, replacing the pure-Python `xbbg/` package. Lazy-loaded via `__getattr__` for near-instant import
- **Streaming APIs**: `vwap()`/`avwap()` for VWAP streaming (`//blp/mktvwap`), `mktbar()`/`amktbar()` for market bar streaming, `depth()`/`adepth()` for market depth (B-PIPE), `chains()`/`achains()` for option/futures chain streaming (B-PIPE) -- all with async variants
- **New Bloomberg API functions**: `bcurves()`/`abcurves()` for yield curve lookup, `bgovts()`/`abgovts()` for government securities lookup, `bflds()`/`abflds()` for field search (replacing `fieldInfo`/`fieldSearch`)
- **Generic request API**: `request()`/`arequest()` -- direct access to any Bloomberg service and operation with schema-driven kwargs routing. Power users can hit any Bloomberg endpoint without a dedicated wrapper
- **Schema introspection**: `bops()`/`abops()` to list service operations, `bschema()`/`abschema()` for full service schema, `get_schema()`/`aget_schema()`, `list_operations()`/`alist_operations()`, `get_enum_values()`/`aget_enum_values()`, `list_valid_elements()`/`alist_valid_elements()` -- all with async variants. `generate_stubs()` and `configure_ide_stubs()` for IDE auto-completion generated from live Bloomberg schemas
- **Test without a Bloomberg Terminal**: `datamock` and `datamock-sys` crates -- a C++ BEmu port with C API and Rust FFI bindings for deterministic testing of reference, historical, intraday bar, intraday tick, and market data requests
- **Field type cache**: `FieldTypeCache`, `FieldInfo`, `resolve_field_types()`/`aresolve_field_types()`, `cache_field_types()`, `get_field_info()`, `clear_field_cache()` for caching and resolving Bloomberg field metadata
- **Engine lifecycle management**: `shutdown()`, `reset()`, `is_connected()` for explicit Rust engine control
- **`EngineConfig`**: Rust-native engine configuration (PyO3 `PyEngineConfig`) -- subscription pool size, request pool size, flush thresholds, auto-restart on disconnection
- **Auto-restart on disconnection**: Subscription sessions automatically reconnect after network interruptions via `setAutoRestartOnDisconnection`
- **`Time64Micros` value type**: Microsecond-precision time-of-day extraction from Bloomberg `Datetime` fields, with Arrow `Time64Micros` type support in generic, histdata, and refdata state handlers
- **`BlpBPipeError` exception**: New exception class for B-PIPE-specific errors, added to the existing exception hierarchy
- **Technical Analysis improvements**: `ta_study_params()` to inspect study parameters, `generate_ta_stubs()` for IDE auto-completion of TA study names
- **Logging control**: `set_log_level()`, `get_log_level()` to control Rust-side tracing verbosity without Python overhead
- **Bloomberg SDK message receive time**: `Message::receive_time()` for latency measurement and diagnostics
- **Service definitions**: `Service`, `Operation`, `OutputMode`, `RequestParams`, `ExtractorHint` enums for type-safe Bloomberg service configuration
- **Extension modules (`py-xbbg/src/xbbg/ext/`)**: `currency`, `fixed_income`, `futures`, `historical` -- ported to work with the Rust backend in LONG format
- **Markets module (`py-xbbg/src/xbbg/markets/`)**: `bloomberg`, `info`, `overrides`, `resolvers`, `sessions` -- exchange metadata, market timing, and override normalization
- **Data definition files**: `defs/bloomberg.toml` and `defs/exchanges.toml` for data-driven Bloomberg and exchange configuration
- **Starlight documentation site**: Full rewrite from Sphinx to Astro Starlight -- API reference (`blp.md`, `exceptions.md`, `schema.md`, `services.md`), getting started guides (`installation.mdx`, `introduction.mdx`, `quickstart.mdx`), async/streaming/migration/output-format guides, and configuration reference
- **Benchmark suites**: Rust benchmarks via Criterion (`xbbg-bench` -- allocation profiling, datetime/name micro-benchmarks, cached response parsing, live `bdp`/subscription benchmarks) and Python benchmarks (`benchmarks/` -- `bdp`, `bdh`, `bdib`, `bdtick`, `bql`, raw `blpapi` with version-based result tracking)
- **Comprehensive test suites**: `py-xbbg/tests/` with unit tests for imports, backends, blp API, backend conversion, currency conversion, exceptions, futures validation, integration, markets, and yield types. Live test suite (`py-xbbg/tests/live/`) for API, engine, subscription lifecycle, and subscription fixes
- **CI infrastructure**: `ci-rust.yml` for multi-platform Rust CI (clippy, rustfmt, unit tests, integration tests, `cargo-audit`, `cargo-deny`, semver-checks), `ci-docker.yml` for reusable container image builds, Docker containers for Rust CI and manylinux wheel builds
- **Codegen tool** (`codegen/generate.py`): Python code generator for service definitions, including `SEMI_LONG` output format support from `release/0.x`
- **SDK setup script** (`scripts/sdktool.ps1`): PowerShell script for Bloomberg SDK vendor layout management
- **`cargo-deny` configuration** (`deny.toml`): License and security policy for all Rust dependencies
- **Future language binding scaffolds**: `bindings/napi-xbbg/` (Node.js N-API), `bindings/dotnet-xbbg/` (.NET), `apps/xbbg-cli/` (CLI), `apps/xbbg-server/` (server), and `js-xbbg/` (npm package)
- **`vendor/blpapi-sdk/README.md`**: Instructions for vendoring the Bloomberg C++ SDK locally

### Changed

- **Build system**: Switched to `setuptools-rust` (PyO3) with `setuptools_scm` versioning. `pyproject.toml` now builds the Rust extension via `setuptools.build_meta`
- **Python package source location**: Moved from `xbbg/` (in-tree) to `py-xbbg/src/xbbg/` for the Rust-backed package layout. The native extension is compiled as `xbbg._core`
- **Runtime dependencies**: `pandas` is no longer required -- now only `narwhals>=1.30`, `pyarrow>=22.0.0`, `lief>=0.17`. Removed `blpapi`, `tomli`, and all other previous hard dependencies
- **Python version support**: Added Python 3.14 to classifiers (`>=3.10,<3.15`)
- **`pypi_upload.yml` workflow**: Completely rewritten for `setuptools-rust` wheel builds with Bloomberg SDK detection, replacing the pure-Python sdist/wheel workflow
- **`pre-commit-config.yaml`**: Updated hooks for the Rust+Python monorepo -- added `cargo fmt`, `cargo clippy`, and scoped ruff to `py-xbbg/` and `xbbg/`
- **`.gitignore`**: Expanded for Rust build artifacts (`target/`), native extension outputs, SDK vendor directory, benchmark results, and IDE files
- **README.md**: Rewritten for v1.0 -- concise project description, Rust-powered backend highlights, installation and quick start replacing the extensive v0.x documentation
- **CONTRIBUTING.md**: Rewritten for the Rust+Python development workflow
- **LICENSE**: Updated to Apache-2.0 with revised copyright
- **Maximum-performance release builds**: `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`, `strip = "symbols"` for production; `opt-level = 3` for `xbbg-core`, `opt-level = 2` for dev
- **Subscription pool default**: Reduced from 4 to 1 worker, consolidated into `EngineConfig`
- **Legacy `xbbg/` package**: Minor cleanups -- added `from __future__ import annotations` across all `__init__.py` files, normalized docstring quotes from single to double, removed `# noqa` lint suppression comments, replaced `lambda: []` with `list` in pipeline factory registry default resolvers

### Removed

- **`xbbg/__init__.py`**: Top-level package init replaced by `py-xbbg/src/xbbg/__init__.py` with Rust backend
- **`xbbg/blp.py`**: 178-line deprecation compatibility layer -- all functions now live in `py-xbbg/src/xbbg/blp.py` backed by Rust
- **`xbbg/const.py`**: 187-line constants module -- constants moved to Rust crates and `defs/*.toml`
- **`xbbg/core/__init__.py`**: 35-line core package init -- core functionality replaced by Rust engine
- **`xbbg/core/process.py`**: 787-line Bloomberg message processing module -- replaced by `xbbg-async` Rust engine state machines
- **`xbbg/utils/pipeline.py`**: 336-line pipeline utilities -- replaced by Rust engine pipeline
- **`xbbg/io/__init__.py`**: IO module init removed (module gutted in v0.12.0)
- **`xbbg/markets/__init__.py`**: 76-line markets package init -- replaced by `py-xbbg/src/xbbg/markets/`
- **`xbbg/markets/resolvers.py`**: Futures/CDX resolvers moved to `xbbg-ext` Rust crate
- **`examples/feeds/pub.py`** and **`examples/feeds/sub.py`**: Legacy feed examples
- **Sphinx documentation**: `docs/conf.py`, `docs/index.rst` (1,293 lines), `docs/Makefile`, `docs/make.bat`, `docs/docstring_style.rst` -- replaced by Starlight
- **`.readthedocs.yaml`**: ReadTheDocs configuration (docs now use Starlight)
- **`MANIFEST.in`**: No longer needed with the `setuptools-rust` build system
- **`SECURITY.md`**: Security policy document
- **`_config.yml`**: Jekyll configuration
- **`codecov.yml`**: Codecov configuration
- **9 CI workflows**: `auto_ci.yml`, `ci_docs.yml`, `codeql-analysis.yml`, `publish_docs.yml`, `publish_testpypi.yml`, `pypi_build_test.yml`, `release_assets.yml`, `update_index_on_release.yml`, `update_readme_on_release.yml` -- consolidated into `ci-rust.yml`, `ci-docker.yml`, and rewritten `pypi_upload.yml`

### Fixed

- **Clippy 1.93 lints**: Resolved `map_or` and doc indentation warnings across all Rust crates
- **Windows LLVM/`LIBCLANG_PATH` setup**: Fixed detection and configuration for `bindgen` on Windows CI
- **Linux `LIBCLANG_PATH` detection**: Fixed `libclang-dev` path resolution on Linux CI
- **Non-ASCII characters in comments**: Replaced em dashes with ASCII equivalents to pass CI source checks
- **Subscription slab key reuse race**: Prevented key reuse on subscription removal in `xbbg-async` that could cause events to route to wrong handlers
- **Subscription error propagation**: Subscription errors now propagate as Python exceptions via PyO3 instead of being silently swallowed
- **Subscription pipeline rewrite**: Multi-type support, error propagation, and event time tracking in `xbbg-async`
- **`Datetime` field zeroed date parts**: Added parts bitmask check to correctly handle Bloomberg `Datetime` fields with zeroed date components
- **DLL search path setup (Windows)**: Moved SDK DLL search path configuration to module level in `py-xbbg` to fix `from xbbg._core import X` failures
- **`Request::set_bool`**: Use `setElementString` for Bool elements in Bloomberg requests (Bloomberg API quirk)
- **TA study requests**: Wired through `elements` instead of unused `json_elements` path
- **`WIDE` format compatibility**: Produces 0.7.7-compatible DataFrame structure from the Rust backend
- **Backend double-conversion bug**: Fixed duplicate conversion when Rust backend returns data that is then converted again by Python

## [0.12.0] - 2026-02-18

### Added

- **Async-first architecture**: All Bloomberg API functions (`bdp`, `bds`, `bdh`, `bdib`, `bdtick`, `bql`, `beqs`, `bsrch`, `bqr`, `bta`) now have async counterparts (`abdp`, `abds`, `abdh`, etc.) as the source of truth; sync wrappers delegate via `_run_sync()` (#218)
- **Bond analytics module** (`xbbg.ext.bonds`): 6 new functions for fixed income analytics -- `bond_info` (reference metadata and ratings), `bond_risk` (duration, convexity, DV01), `bond_spreads` (OAS, Z-spread, I-spread, ASW), `bond_cashflows` (cash flow schedule), `bond_key_rates` (key rate durations and risks), `bond_curve` (multi-bond relative value comparison)
- **Options analytics module** (`xbbg.ext.options`): 6 new functions and 5 enums for equity option analytics -- `option_info` (contract metadata), `option_greeks` (Greeks and implied volatility), `option_pricing` (value decomposition and activity), `option_chain` (chain via `CHAIN_TICKERS` with overrides), `option_chain_bql` (chain via BQL with rich filtering), `option_screen` (multi-option comparison). Enums: `PutCall`, `ChainPeriodicity`, `StrikeRef`, `ExerciseType`, `ExpiryMatch`
- **CDX analytics** (`xbbg.ext.cdx`): 8 new functions for credit default swap index analytics -- `cdx_info`, `cdx_defaults`, `cdx_pricing`, `cdx_risk`, `cdx_basis`, `cdx_default_prob`, `cdx_cashflows`, `cdx_curve`. `cdx_pricing`/`cdx_risk` support `CDS_RR` recovery rate override
- **`YieldType` expanded**: Added `YTW` (Yield to Worst), `YTP` (Yield to Put), `CFY` (Cash Flow Yield) to `YieldType` enum
- **`workout_dt` parameter for `yas()`**: Workout date for yield-to-worst/call calculations, maps to `YAS_WORKOUT_DT` Bloomberg override. Accepts `str` (YYYYMMDD) or `datetime`
- **`tz` parameter for `bdib()`/`abdib()`**: Controls output timezone for intraday bar data. Defaults to `None` (exchange local timezone, matching v0.7.x behavior). Set `tz='UTC'` to keep UTC timestamps, or pass any IANA timezone string (e.g., `'Europe/London'`)
- **`exchange_tz()` helper**: Returns the IANA timezone string for any Bloomberg ticker (e.g., `blp.exchange_tz('AAPL US Equity')` -> `'America/New_York'`). Exported via `blp.exchange_tz()`
- **LONG_TYPED output format**: New `_to_long_typed()` function produces typed value columns (`value_f64`, `value_i64`, `value_str`, `value_bool`, `value_date`, `value_ts`) with exactly one populated per row based on the Arrow type of each field
- **LONG_WITH_METADATA output format**: New `_to_long_with_metadata()` function produces `(ticker, date, field, value, dtype)` where `value` is stringified and `dtype` contains the Arrow type name (e.g. `double`, `int64`, `string`)
- **CI non-ASCII source check**: New `auto_ci.yml` step rejects non-ASCII characters in Python source files (allows CJK for ticker tests)
- **Comprehensive test coverage**: 55+ new tests including bond analytics (7), CDX analytics (8), options analytics, timezone conversion (13), `ovrds` dict normalization (7), `_events_to_table()` (16), `bdtick` format variants (5), mixed-type BDP (2), and output format tests (12)

### Changed

- **Unified I/O layer**: All Bloomberg requests now flow through a single `arequest()` async entry point in `conn.py`, replacing scattered session/service management across modules (#218)
- **Futures resolution uses `FUT_CHAIN_LAST_TRADE_DATES`** (#223): Replaced manual candidate generation (`FUT_GEN_MONTH` + batch `bdp`) with Bloomberg-native `FUT_CHAIN_LAST_TRADE_DATES` via single `bds()` call. ~2x faster (0.25-0.30s vs 0.53-0.72s)
- **`sync_api` decorator**: Replaces 13 hand-written sync wrappers across API modules (`screening.py`, `historical.py`, `intraday.py`, etc.) with a single `sync_api(async_fn)` call
- **Table-driven deprecation wrappers**: 23 manual wrapper functions in `blp.py` replaced by dict + loop pattern; 24 `warn_*` functions in `deprecation.py` replaced by `_DEPRECATION_REGISTRY` + `get_warn_func()` lookup
- **Market session rules extracted to TOML** (`markets/config/sessions.toml`): All MIC and exchange code rules moved from `sessions.py` into data-driven TOML config, reducing `sessions.py` from 364 to 168 lines (54% reduction)
- **Pipeline factory registry** (`pipeline_factories.py`): Centralized factory dispatch replaces scattered conditionals
- **CDX ticker format corrected**: Version is now a separate space-delimited token (e.g., `CDX HY CDSI S45 V2 5Y Corp` instead of `S45V2`)
- **`tomli` conditional dependency added**: `tomli>=2.0.1` for Python < 3.11 (TOML parsing for `sessions.toml`)
- **Net reduction of ~1,346 lines** across 27 files from codegen and table-driven optimizations

### Removed

- **`xbbg/io/db.py`**: SQLite database helper module (zero imports across codebase) (#218)
- **`xbbg/io/param.py`**: Legacy parameter/configuration module (zero imports across codebase) (#218)
- **`xbbg/io/files.py`**: File path utility module (zero imports after replacing 6 usages in `cache.py` and `const.py` with `pathlib.Path`) (#218)
- **`regression_testing/`**: Standalone v0.7.7 regression test directory; all scenarios covered by `test_live_endpoints.py` (#218)
- **`MONTH_CODE_MAP` and futures candidate generation helpers**: Superseded by `FUT_CHAIN_LAST_TRADE_DATES` chain resolution (#223)
- Stale files: `pmc_cache.json`, `xone.db`, empty `__init__` files, `test_param.py` (#218)

### Fixed

- **`bdtick` format parameter was completely non-functional**: All five output formats (LONG, SEMI_LONG, WIDE, LONG_TYPED, LONG_WITH_METADATA) were broken due to MultiIndex column wrapping, killed index name, and mixed-type Arrow conversion errors
- **`bdib` timezone regression**: The Arrow pipeline rewrite (v0.11.0) dropped the UTC-to-exchange local timezone conversion that existed in v0.7.x. Restored with configurable `tz` parameter
- **`ArrowInvalid` on multi-field BDP calls**: Bloomberg returns different Python types for different fields. New `_events_to_table()` builds Arrow tables with automatic type coercion fallback (#219)
- **`create_request` crashed when `ovrds` passed as dict**: Now normalizes dict to list of tuples before iteration ([SO#79880156](https://stackoverflow.com/questions/79880156))
- **Case-sensitive `backend` and `format` parameters**: Added `_missing_` classmethod to `Backend` and `Format` enums for case-insensitive lookup (#221)
- **Mock session leak in tests**: Added autouse `_reset_session_manager` fixture to prevent `MagicMock` persistence across test modules (#213)
- **`interval` parameter leaked as Bloomberg override**: Added to `PRSV_COLS` so it stays local (#145)
- **`StrEnum` Python 3.10 compatibility**: Added polyfill for Python < 3.11
- **Non-ASCII characters in source**: Replaced with ASCII equivalents for CI compliance

### Security

- **Bump `cryptography` from 46.0.4 to 46.0.5**: Fixes CVE-2026-26007 (#217)

## [0.12.0b3] - 2026-02-16

### Added

- **Bond analytics module** (`xbbg.ext.bonds`): 6 new functions for fixed income analytics -- `bond_info` (reference metadata and ratings), `bond_risk` (duration, convexity, DV01), `bond_spreads` (OAS, Z-spread, I-spread, ASW), `bond_cashflows` (cash flow schedule), `bond_key_rates` (key rate durations and risks), `bond_curve` (multi-bond relative value comparison)
- **Options analytics module** (`xbbg.ext.options`): 6 new functions and 5 enums for equity option analytics -- `option_info` (contract metadata), `option_greeks` (Greeks and implied volatility), `option_pricing` (value decomposition and activity), `option_chain` (chain via `CHAIN_TICKERS` with overrides), `option_chain_bql` (chain via BQL with rich filtering), `option_screen` (multi-option comparison). Enums: `PutCall`, `ChainPeriodicity`, `StrikeRef`, `ExerciseType`, `ExpiryMatch`
- **CDX analytics** (`xbbg.ext.cdx`): 8 new functions for credit default swap index analytics -- `cdx_info`, `cdx_defaults`, `cdx_pricing`, `cdx_risk`, `cdx_basis`, `cdx_default_prob`, `cdx_cashflows`, `cdx_curve`. `cdx_pricing`/`cdx_risk` support `CDS_RR` recovery rate override
- **`YieldType` expanded**: Added `YTW` (Yield to Worst), `YTP` (Yield to Put), `CFY` (Cash Flow Yield) to `YieldType` enum
- **`workout_dt` parameter for `yas()`**: Workout date for yield-to-worst/call calculations, maps to `YAS_WORKOUT_DT` Bloomberg override. Accepts `str` (YYYYMMDD) or `datetime`
- **`tz` parameter for `bdib()`/`abdib()`**: Controls output timezone for intraday bar data. Defaults to `None` (exchange local timezone, matching v0.7.x behavior). Set `tz='UTC'` to keep UTC timestamps, or pass any IANA timezone string (e.g., `'Europe/London'`)
- **`exchange_tz()` helper**: Returns the IANA timezone string for any Bloomberg ticker (e.g., `blp.exchange_tz('AAPL US Equity')` -> `'America/New_York'`). Exported via `blp.exchange_tz()`
- **`tz` field on `DataRequest` and `RequestBuilder`**: Propagates timezone control through the pipeline. `RequestBuilder` gains `.tz()` builder method
- **CI non-ASCII source check**: New `auto_ci.yml` step rejects non-ASCII characters in Python source files (allows CJK for ticker tests)
- **Live endpoint tests**: 7 tests for bond analytics, 8 tests for CDX analytics, plus options analytics coverage in `test_live_endpoints.py`
- **13 unit tests for timezone conversion** (`test_intraday_timezone.py`): Covers default exchange tz, explicit UTC, explicit timezone, Japanese equities, empty exchange info, empty tables, column renaming, and DataRequest/RequestBuilder propagation
- **7 regression tests for `ovrds` dict normalization** (`test_overrides.py`): Covers dict crash, correct element setting, multiple overrides, list-of-tuples backward compat, and None/empty edge cases

### Changed

- **Futures resolution uses `FUT_CHAIN_LAST_TRADE_DATES`** (#223): Replaced manual candidate generation (`FUT_GEN_MONTH` + batch `bdp`) with Bloomberg-native `FUT_CHAIN_LAST_TRADE_DATES` via single `bds()` call. ~2x faster (0.25-0.30s vs 0.53-0.72s). Removed `MONTH_CODE_MAP`, `_get_cycle_months`, `_construct_contract_ticker`
- **`sync_api` decorator**: Replaces 13 hand-written sync wrappers across API modules (`screening.py`, `historical.py`, `intraday.py`, etc.) with a single `sync_api(async_fn)` call
- **Table-driven deprecation wrappers**: 23 manual wrapper functions in `blp.py` replaced by dict + loop pattern; 24 `warn_*` functions in `deprecation.py` replaced by `_DEPRECATION_REGISTRY` + `get_warn_func()` lookup
- **Market session rules extracted to TOML** (`markets/config/sessions.toml`): All MIC and exchange code rules moved from `sessions.py` into data-driven TOML config, reducing `sessions.py` from 364 to 168 lines (54% reduction)
- **Pipeline factory registry** (`pipeline_factories.py`): Centralized factory dispatch replaces scattered conditionals
- **Wildcard imports in `__init__.py` files**: 9 `__init__.py` files simplified to use wildcard imports with explicit `__all__` lists
- **CDX ticker format corrected**: Version is now a separate space-delimited token (e.g., `CDX HY CDSI S45 V2 5Y Corp` instead of `S45V2`)
- **`tomli` conditional dependency added**: `tomli>=2.0.1` for Python < 3.11 (TOML parsing for `sessions.toml`)
- **Net reduction of ~1,346 lines** across 27 files from codegen and table-driven optimizations

### Removed

- **`update_readme_on_release.yml` workflow**: Inline changelog in README replaced by link to `CHANGELOG.md`
- **`MONTH_CODE_MAP` and futures candidate generation helpers**: Superseded by `FUT_CHAIN_LAST_TRADE_DATES` chain resolution (#223)

### Fixed

- **`bdib` timezone regression**: The Arrow pipeline rewrite (v0.11.0) dropped the UTC-to-exchange local timezone conversion that existed in v0.7.x. Intraday bar timestamps were returned in UTC instead of exchange local time. Restored the conversion in `IntradayTransformer.transform()` with configurable `tz` parameter
- **`create_request` crashed when `ovrds` passed as dict**: `create_request(ovrds={"PRICING_SOURCE": "BGN"})` raised `ValueError: too many values to unpack` because iterating a dict yields keys (strings), not (key, value) tuples. Now normalizes dict to list of tuples before iteration. Also updated type annotation to accept `dict[str, Any]` ([SO#79880156](https://stackoverflow.com/questions/79880156))
- **Case-sensitive `backend` and `format` parameters**: `Backend("POLARS")` and `Format("WIDE")` raised `ValueError` because enum values are lowercase. Added `_missing_` classmethod to both `Backend` and `Format` enums for case-insensitive lookup (#221)
- **`StrEnum` Python 3.10 compatibility**: Added `StrEnum` polyfill in options module for Python < 3.11 where `enum.StrEnum` does not exist
- **Python 3.10 mock patching**: Fixed `patch.object()` usage for Python 3.10 compatible mock patching in tests by exposing submodules and patching at source
- **Non-ASCII characters in source**: Replaced checkmarks, em dashes, and arrows with ASCII equivalents across the codebase for CI compliance
- **Ruff lint errors**: Fixed import sorting (I001) and docstring formatting issues

## [0.12.0b2] - 2026-02-13

### Added

- **16 unit tests for `_events_to_table()`** (`test_events_to_table.py`): covers basic contract, mixed-type columns (float+str, int+str, float+date, kitchen sink), null handling, non-uniform dict keys, and pipeline integration (#219)
- **2 live regression tests for mixed-type BDP** (`test_live_endpoints.py`): `test_bdp_mixed_type_fields` and `test_bdp_mixed_type_multiple_tickers` exercise the exact bug scenario with `ES1 Index` / `NQ1 Index` using `FUT_CONT_SIZE` + `FUT_VAL_PT` (#219)

### Fixed

- **`ArrowInvalid` on multi-field BDP calls**: Bloomberg returns different Python types for different fields (e.g., `float` for `FUT_CONT_SIZE`, `str` for `FUT_VAL_PT`). When both land in the same Arrow value column, `pa.array()` raised `ArrowInvalid`. New `_events_to_table()` builds Arrow tables directly from event dicts with automatic type coercion fallback — stringify on `ArrowInvalid`/`ArrowTypeError`, preserving nulls (#219)
- **Post-transform `pa.Table.from_pandas()` mixed-type failure**: Protected the secondary Arrow conversion (after narwhals transform) with the same stringify fallback for object columns (#219)

## [0.12.0b1] - 2026-02-12

### Changed

- **Async-first architecture**: All Bloomberg API functions (`bdp`, `bds`, `bdh`, `bdib`, `bdtick`, `bql`, `beqs`, `bsrch`, `bqr`, `bta`) now have async counterparts (`abdp`, `abds`, `abdh`, etc.) as the source of truth; sync wrappers delegate via `_run_sync()` (#218)
- **Unified I/O layer**: All Bloomberg requests now flow through a single `arequest()` async entry point in `conn.py`, replacing scattered session/service management across modules (#218)
- **Pipeline and process modules**: Adapted `pipeline_core`, `process`, and `request_builder` to work with the async `arequest()` foundation (#218)
- **Top-level async exports**: All async API variants (`abdp`, `abds`, `abdh`, `abdib`, `abdtick`, `abql`, `abeqs`, `absrch`, `abqr`, `abta`) exported from `xbbg.blp` (#218)
- **IO module cleanup**: Removed dead code and fixed type annotations across `xbbg/io/` (#218)
- **Test coverage expanded**: 571 tests total (up from 543), covering all connection-related GitHub issues and all previously untested paths in `conn.py`

### Removed

- **`xbbg/io/db.py`**: SQLite database helper module (zero imports across codebase) (#218)
- **`xbbg/io/param.py`**: Legacy parameter/configuration module (zero imports across codebase) (#218)
- **`xbbg/io/files.py`**: File path utility module (zero imports after replacing 6 usages in `cache.py` and `const.py` with `pathlib.Path`) (#218)
- **`xbbg/tests/test_param.py`**: Tests for deleted `param` module (7 tests) (#218)
- **`xbbg/markets/cached/pmc_cache.json`**: Stale pandas-market-calendars cache file (pmc dependency removed in v0.11.0) (#218)
- **`xbbg/tests/__init__.py`**, **`examples/feeds/__init__.py`**: Empty `__init__` files (#218)
- **`xbbg/tests/xone.db`**: Stale SQLite test database (#218)
- **`regression_testing/`**: Standalone v0.7.7 regression test directory (6 files); all 9 test scenarios already covered by `xbbg/tests/test_live_endpoints.py` with stricter assertions (#218)

### Fixed

- **Mock session leak in tests**: Added autouse `_reset_session_manager` fixture in `conftest.py` to prevent `MagicMock` sessions from persisting in the `SessionManager` singleton across test modules, which caused infinite `__getattr__` → `_get_child_mock` recursion and stack overflow on Windows (#213)
- **`interval` parameter leaked as Bloomberg override**: `interval` was not in `PRSV_COLS`, causing it to be sent to Bloomberg as an override field instead of being used locally for bar sizing (#145)
- **README Data Storage section**: Clarified that only `bdib()` (intraday bars) has caching via `BarCacheAdapter`; all other functions always make live Bloomberg API calls (#215)
- **README async example for Jupyter**: Fixed `asyncio.run()` example that fails in notebooks (which already have a running event loop) by adding `await`-based and `nest_asyncio` alternatives (#216)
- **Unused imports in tests**: Removed `import os` from `test_intraday_api.py` and `import pytest` from `test_logging.py` that caused Ruff F401 lint failures in CI

### Security

- **Bump `cryptography` from 46.0.4 to 46.0.5**: Fixes CVE-2026-26007 — subgroup attack due to missing validation for SECT binary elliptic curves (#217)

## [0.11.4] - 2026-02-06

### Fixed

- **`bdtick` Arrow conversion failure**: Object columns containing `blpapi.Name` instances caused `pa.Table.from_pandas()` to fail; now stringified before conversion
- **`adjust_ccy` field name mismatch**: Looked for `"Last_Price"` but `bdh` returns lowercase `"last_price"` since v0.11.1, causing `KeyError`
- **`active_futures` two failures**: Used `nw.coalesce()` with a column (`last_tradeable_dt`) not present in SEMI_LONG format, and called `.height` (not valid on narwhals DataFrame) instead of `.shape[0]`
- **Live test assertions**: Updated 10 tests in `test_live_endpoints.py` to match WIDE format default (active since v0.7.x)

## [0.11.3] - 2026-02-06

### Fixed

- **Duplicate `port` keyword argument**: `bbg_service()` and `bbg_session()` used `.get()` to extract `port` then forwarded `**kwargs` still containing it, causing `TypeError: got multiple values for keyword argument 'port'` on non-default ports (e.g., B-Pipe connections) (#212)
- **Session resource leak**: `clear_default_session()` set `_default_session = None` without calling `session.stop()`, leaking OS file descriptors over repeated connect/disconnect cycles (#211)
- **Wrong session removed on retry**: `send_request()` retry path called `remove_session(port=port)` without `server_host`, always targeting `//localhost:{port}` even for remote hosts
- **Inconsistent `server_host` extraction**: `get_session()` / `get_service()` checked `server_host` before `server`, but `connect_bbg()` did the opposite, causing different code paths to resolve different hosts when both keys were present
- **Resource leak on start failure**: `connect_bbg()` did not stop the session before raising `ConnectionError` when `.start()` failed, leaking C++ resources allocated by the `Session()` constructor

## [0.11.2] - 2026-02-05

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

- **BDS output format**: Restored v0.10.x backward compatibility for `bds()` output format (#209)
  - Default `format='wide'` now returns single data column with ticker as index (pandas) or column (other backends)
  - Field column dropped for cleaner output matching v0.10.x behavior
  - Users can opt-in to new 3-column format with `format='long'`
- **ibis backend**: Updated to use `ibis.memtable()` instead of deprecated `con.read_in_memory()`
- **sqlframe backend**: Fixed import path to use `sqlframe.duckdb.DuckDBSession`

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

## [0.11.0b5] - 2026-01-25

### Changed

- Internal class renames with backward compatible aliases (`YamlMarketInfoProvider` -> `MetadataProvider`)

### Removed

- **Trials mechanism**: Eliminated retry-blocking system that caused silent failures after 2 failed attempts
- **pandas-market-calendars dependency**: Exchange info now sourced exclusively from Bloomberg API with local caching

### Fixed

- **Import without blpapi installed**: Fixed `AttributeError` when importing xbbg without blpapi (#200)
- **Japan/non-US timezone fix for bdib**: Bloomberg returns trading hours in EST; now correctly converted to exchange's local timezone (#198)
- **get_tz() improvement**: Direct timezone strings recognized without Bloomberg API call

## [0.11.0b4] - 2026-01-24

### Added

- **yas()**: Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics with `YieldType` enum (#202)
- **Treasury and SOFR futures support**: TY, ZN, ZB, ZF, ZT, UB, TN, SFR, SR1, SR3, ED futures (#198)

### Fixed

- **stream() field values**: Subscribed field values now always included in output dict (#199)
- **Futures symbol parsing**: Fixed `market_info()` to correctly parse symbols like `TYH6` -> `TY` (#198)

## [0.11.0b3] - 2026-01-21

### Added

- **bqr()**: Bloomberg Quote Request function emulating Excel `=BQR()` for dealer quote data with broker attribution (#22)

### Fixed

- **Slow Bloomberg fields**: TIMEOUT events handled correctly; requests wait for response with `slow_warn_seconds` warning (#193)
- **Pipeline data types**: Preserve original data types instead of converting to strings (#191)

## [0.11.0b2] - 2026-01-20

### Added

- **preferreds()**: BQL convenience function to find preferred stocks for an equity ticker
- **corporate_bonds()**: BQL convenience function to find active corporate bonds for a ticker

### Fixed

- **bdtick timezone fix**: Pass exchange timezone to fix blank results for non-UTC exchanges (#185)
- **bdtick timeout**: Increased from 10s to 2 minutes for tick data requests

## [0.11.0b1] - 2026-01-10

### Added

- **Arrow-first pipeline**: Complete rewrite of data processing using PyArrow internally
- **Multi-backend support**: New `Backend` enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb
- **Output format control**: New `Format` enum with long, semi_long, wide options
- **bta()**: Bloomberg Technical Analysis function for 50+ technical indicators
- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` configuration functions
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`
- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, etc.)
- `EngineConfig` dataclass and `configure()` function
- `Service` and `Operation` enums for Bloomberg service URIs

### Changed

- All API functions now support `backend` and `format` parameters
- Internal pipeline uses PyArrow tables with narwhals transformations
- Removed pytz dependency (using stdlib `datetime.timezone`)

### Deprecated

- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()`
- `lookupSecurity()` - will become `blkp()` in v1.0
- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0

## [0.10.3] - 2025-12-29

### Changed

- Re-enabled futures and CDX resolver tests
- Updated live endpoint tests for LONG format output
- Code style improvements using contextlib.suppress instead of try-except-pass

### Fixed

- Extended BDS test date range to 120 days for quarterly dividends
- Helper functions now work correctly with LONG format output

## [0.10.2] - 2025-12-29

### Changed

- CI/CD improvements with reusable workflows (workflow_call) for release automation
- Separated pypi_upload workflow for trusted publisher compatibility

## [0.10.1] - 2025-12-29

### Changed

- Trigger release workflows via release event instead of workflow_dispatch
- Removed Gitter badge (replaced by Discord)
- Added Discord community link and badge

### Fixed

- Persist blp.connect() session for subsequent API calls (#165)

## [0.10.0] - 2025-12-25

### Added

- Updated polars-bloomberg support for BQL, BDIB and BSRCH (#155)

### Fixed

- Add identifier type prefix to B-Pipe subscription topics (#156)
- Remove pandas version cap to support Python 3.14 (#161)
- Resolve RST formatting warning in index.rst (#162)
- Update Japan equity market hours for TSE trading extension (#163)

## [0.9.1] - 2025-12-11

### Changed

- Add blank lines around latest-release markers in index.rst
- Remove redundant release triggers from workflows
- Trigger release workflows explicitly from semantic_version

### Fixed

- Fix BQL returning only one row for multi-value results (#152)

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

## [0.8.0rc1] - 2025-11-17

### Changed

- Comprehensive codebase cleanup and restructuring (#144)

## [0.8.0b2] - 2025-11-14

### Fixed

- Fix BQL syntax documentation and error handling (#141, #142)

## [0.8.0b1] - 2025-11-14

### Added

- **BQL support**: Bloomberg Query Language with QueryRequest and result parsing
- **Sub-minute intervals for bdib**: 10-second bars via `intervalHasSeconds=True` flag
- **bsrch()**: Bloomberg SRCH queries for fixed income, commodities, and weather data (#137)
- **Fixed income securities support**: ISIN/CUSIP/SEDOL identifiers for bdib (#136)
- **Server host parameter**: Connect to remote Bloomberg servers via `server` parameter (#138)
- **Interval parameter for subscribe()/live()**: Configurable update intervals for real-time feeds
- Support for GY (Xetra), IM (Borsa Italiana), and SE (SIX) exchanges (#140)

### Changed

- Standardized Google-style docstrings across codebase
- Migrate to uv for development with PEP 621 pyproject.toml
- Improved logging with blpapi integration and performance optimizations (#135)
- Enhanced BEQS timeout handling with configurable `timeout` and `max_timeouts` parameters

### Fixed

- Remove 1-minute offset for bare session names in bdtick (#139)

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

### Changed

- Add exchanges support
- CI/CD configuration updates

### Fixed

- Corrected typo (thanks to @ShiyuanSchonfeld)
- Pin pandas version due to pd.to_datetime behaviour change in format_raw
- Fix TLS Options typo when creating a new connection

## [0.7.8a2] - 2022-12-03

### Added

- Additional exchanges support (#83)

### Changed

- CI/CD configuration improvements

## [0.7.7] - 2022-06-19

### Added

- Custom config usage in bdib (contributed by @hceh)
- Options in `blp.live` (contributed by @swiecki)

### Changed

- Pandas options handling in doctest
- CI/CD configuration updates

## [0.7.7a4] - 2022-05-25

### Changed

- Pandas options handling in doctest

## [0.7.7a3] - 2021-12-31

### Fixed

- Typo fix

## [0.7.7a2] - 2021-12-20

### Added

- Custom config and reference exchange support (contributed by @hceh)

## [0.7.7a1] - 2021-07-13

### Added

- Options in `blp.live` (contributed by @swiecki)

## [0.7.6] - 2021-07-05

### Added

- Log folder creation handling
- Alternative connection method support
- Custom session argument for Bloomberg connections
- `bdtick` with custom time range support

### Changed

- Update asset universe
- Exchange info corrections
- No manual conversion of timezones

### Fixed

- BDS fix for edge cases
- blpapi install URL correction

## [0.7.6a8] - 2021-04-17

### Fixed

- Log folder creation bug

## [0.7.6a7] - 2021-04-02

### Changed

- Update asset universe

## [0.7.6a6] - 2021-03-27

### Fixed

- Exchange info corrected

## [0.7.6a5] - 2021-03-05

### Changed

- No manual conversion of timezones

## [0.7.6a4] - 2021-03-05

### Added

- `bdtick` with custom time range support

## [0.7.6a3] - 2021-02-10

### Fixed

- Bug fixes for BDS and blpapi install URL

## [0.7.6a2] - 2021-02-07

### Added

- Alternative connection method

## [0.7.6a1] - 2021-02-03

### Added

- Add `sess` as argument for custom Bloomberg session

## [0.7.5] - 2021-01-31

### Added

- Currency adjusted turnover function
- Useful fields for live feeds
- More examples in documentation

### Changed

- Standardize IO operations
- Log levels adjustment
- Replace `os.path` with pathlib
- Performance function improvements
- Default args of live feeds

### Fixed

- CCY adjust fix
- Bug in finding exchange info

## [0.7.5b2] - 2021-01-30

### Changed

- Log levels adjustment

## [0.7.5b1] - 2021-01-13

### Added

- New methods included in `__all__`

### Fixed

- CCY adjust fix

## [0.7.5a9] - 2021-01-12

### Added

- Currency adjusted turnover function

## [0.7.5a09] - 2021-01-12

### Added

- Currency adjusted turnover function

## [0.7.5a8] - 2021-01-11

### Fixed

- Fix bug in finding exchange info

## [0.7.5a7] - 2021-01-07

### Changed

- Default args of live feeds

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

[Unreleased]: https://github.com/alpha-xone/xbbg/compare/v1.0.0rc1...HEAD
[1.0.0rc1]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b7...v1.0.0rc1
[1.0.0b7]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b6...v1.0.0b7
[1.0.0b6]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b5...v1.0.0b6
[1.0.0b5]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b4...v1.0.0b5
[1.0.0b4]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b3...v1.0.0b4
[1.0.0b3]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b2...v1.0.0b3
[1.0.0b2]: https://github.com/alpha-xone/xbbg/compare/v1.0.0b1...v1.0.0b2
[1.0.0b1]: https://github.com/alpha-xone/xbbg/compare/v1.0.0a3...v1.0.0b1
[1.0.0a3]: https://github.com/alpha-xone/xbbg/compare/v1.0.0a2...v1.0.0a3
[1.0.0a2]: https://github.com/alpha-xone/xbbg/compare/v1.0.0a1...v1.0.0a2
[1.0.0a1]: https://github.com/alpha-xone/xbbg/compare/v0.12.1...v1.0.0a1
[0.12.0]: https://github.com/alpha-xone/xbbg/compare/v0.12.0b3...v0.12.0
[0.12.0b3]: https://github.com/alpha-xone/xbbg/compare/v0.12.0b2...v0.12.0b3
[0.12.0b2]: https://github.com/alpha-xone/xbbg/compare/v0.12.0b1...v0.12.0b2
[0.12.0b1]: https://github.com/alpha-xone/xbbg/compare/v0.11.4...v0.12.0b1
[0.11.4]: https://github.com/alpha-xone/xbbg/compare/v0.11.3...v0.11.4
[0.11.3]: https://github.com/alpha-xone/xbbg/compare/v0.11.2...v0.11.3
[0.11.2]: https://github.com/alpha-xone/xbbg/compare/v0.11.1...v0.11.2
[0.11.1]: https://github.com/alpha-xone/xbbg/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b5...v0.11.0
[0.11.0b5]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b4...v0.11.0b5
[0.11.0b4]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b3...v0.11.0b4
[0.11.0b3]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b2...v0.11.0b3
[0.11.0b2]: https://github.com/alpha-xone/xbbg/compare/v0.11.0b1...v0.11.0b2
[0.11.0b1]: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0b1
[0.10.3]: https://github.com/alpha-xone/xbbg/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/alpha-xone/xbbg/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/alpha-xone/xbbg/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/alpha-xone/xbbg/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/alpha-xone/xbbg/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/alpha-xone/xbbg/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/alpha-xone/xbbg/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/alpha-xone/xbbg/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/alpha-xone/xbbg/compare/v0.8.0rc1...v0.8.0
[0.8.0rc1]: https://github.com/alpha-xone/xbbg/compare/v0.8.0b2...v0.8.0rc1
[0.8.0b2]: https://github.com/alpha-xone/xbbg/compare/v0.8.0b1...v0.8.0b2
[0.8.0b1]: https://github.com/alpha-xone/xbbg/compare/v0.7.11...v0.8.0b1
[0.7.11]: https://github.com/alpha-xone/xbbg/compare/v0.7.10...v0.7.11
[0.7.10]: https://github.com/alpha-xone/xbbg/compare/v0.7.9...v0.7.10
[0.7.9]: https://github.com/alpha-xone/xbbg/compare/v0.7.8a2...v0.7.9
[0.7.8a2]: https://github.com/alpha-xone/xbbg/compare/v0.7.7...v0.7.8a2
[0.7.7]: https://github.com/alpha-xone/xbbg/compare/v0.7.7a4...v0.7.7
[0.7.7a4]: https://github.com/alpha-xone/xbbg/compare/v0.7.7a3...v0.7.7a4
[0.7.7a3]: https://github.com/alpha-xone/xbbg/compare/v0.7.7a2...v0.7.7a3
[0.7.7a2]: https://github.com/alpha-xone/xbbg/compare/v0.7.7a1...v0.7.7a2
[0.7.7a1]: https://github.com/alpha-xone/xbbg/compare/v0.7.6...v0.7.7a1
[0.7.6]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a8...v0.7.6
[0.7.6a8]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a7...v0.7.6a8
[0.7.6a7]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a6...v0.7.6a7
[0.7.6a6]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a5...v0.7.6a6
[0.7.6a5]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a4...v0.7.6a5
[0.7.6a4]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a3...v0.7.6a4
[0.7.6a3]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a2...v0.7.6a3
[0.7.6a2]: https://github.com/alpha-xone/xbbg/compare/v0.7.6a1...v0.7.6a2
[0.7.6a1]: https://github.com/alpha-xone/xbbg/compare/v0.7.5...v0.7.6a1
[0.7.5]: https://github.com/alpha-xone/xbbg/compare/v0.7.5b2...v0.7.5
[0.7.5b2]: https://github.com/alpha-xone/xbbg/compare/v0.7.5b1...v0.7.5b2
[0.7.5b1]: https://github.com/alpha-xone/xbbg/compare/v0.7.5a9...v0.7.5b1
[0.7.5a9]: https://github.com/alpha-xone/xbbg/compare/v0.7.5a09...v0.7.5a9
[0.7.5a09]: https://github.com/alpha-xone/xbbg/compare/v0.7.5a8...v0.7.5a09
[0.7.5a8]: https://github.com/alpha-xone/xbbg/compare/v0.7.5a7...v0.7.5a8
[0.7.5a7]: https://github.com/alpha-xone/xbbg/compare/v0.7.2...v0.7.5a7
[0.7.2]: https://github.com/alpha-xone/xbbg/compare/v0.7.0...v0.7.2
[0.7.0]: https://github.com/alpha-xone/xbbg/compare/v0.6.7...v0.7.0
[0.6.7]: https://github.com/alpha-xone/xbbg/compare/v0.6.0...v0.6.7
[0.6.0]: https://github.com/alpha-xone/xbbg/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/alpha-xone/xbbg/compare/v0.1.22...v0.5.0
[0.1.22]: https://github.com/alpha-xone/xbbg/compare/v0.1.17...v0.1.22
[0.1.17]: https://github.com/alpha-xone/xbbg/releases/tag/v0.1.17
