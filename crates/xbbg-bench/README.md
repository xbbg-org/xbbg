# xbbg-bench

Consolidated benchmarks for the xbbg workspace.

All performance tests, allocation profiling, and live Bloomberg benchmarks live here instead of being scattered across individual crates.

## Shared helpers (`src/lib.rs`)

| Helper | Purpose |
|--------|---------|
| `setup_session()` | Create & start a Bloomberg session (reads `BLP_HOST`/`BLP_PORT`) |
| `open_service(sess, uri)` | Open a service and wait for `ServiceStatus` |
| `FieldNames` | Pre-interned Bloomberg field names for hot-path benchmarks |
| `env_iterations(var, default)` | Read iteration count from env var |
| `write_json(path, json)` | Write results file, creating parent dirs |

## Supported benchmark suite

`xbbg-bench` now has one supported entrypoint:

```bash
cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
```

The suite runs together in one report:

1. Tiny live Bloomberg probes for BDP, BDH, BDTICK, and BQL.
2. Cached Bloomberg request-event replay through the real extractor states: BDP, BDH, BDS, BDTICK, and BQL.
3. A bounded live subscription throughput window.
4. Cached subscription-event replay through the real `SubscriptionState -> Arrow RecordBatch` path.
5. Offline generated BQL JSON extraction replay through `BqlState` for stable parser/Arrow benchmarks without Bloomberg usage.
6. Synthetic massive BDP, BDH, BDTICK, BQL, and subscription workloads.

Live probes and replay seed captures intentionally keep Bloomberg data usage low. Replay, offline BQL JSON extraction, and synthetic scale reuse cached SDK events or deterministic generated data instead of issuing repeated Bloomberg requests.

### Profiles

| Profile | Use | Live Bloomberg usage | Synthetic scale |
|---------|-----|----------------------|-----------------|
| `smoke` | quick validation | tiny live probes + 2s subscription | small |
| `standard` | default one-command benchmark | tiny live probes + 5s subscription | large |
| `stress` | manual capacity run | tiny live probes + 10s subscription by default | massive |

Examples:

```bash
BENCH_PROFILE=smoke cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
BENCH_PROFILE=standard cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
BENCH_PROFILE=stress cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
```

Override the live subscription collection window without increasing reference-data usage:

```bash
BENCH_PROFILE=stress BENCH_SUB_COLLECT_MS=30000 \
  cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
```

### Cached replay benchmarks

The suite includes cached SDK event replay benchmarks so performance changes in xbbg extraction code show up without hammering Bloomberg:

- `replay / bdp_refdata`: one BDP seed request, then repeated `RefDataState` extraction
- `replay / bdh_historical`: one BDH seed request, then repeated `HistDataState` extraction
- `replay / bds_bulk_late_fields`: one BDS-style bulk seed request, then repeated `BulkDataState` extraction with dynamic sub-field discovery
- `replay / bdtick_optional_fields`: one BDTICK seed request with condition/exchange code options, then repeated `IntradayTickState` extraction
- `replay / bql_response`: one BQL seed query, then repeated `BqlState` extraction


Offline BQL JSON extraction benchmarks are generated fixtures that run through the real `BqlState` JSON parser and Arrow materialization path, so parser/extractor changes move the benchmark without requiring repeated Bloomberg BQL requests:
- `bql_json / json_simple_1x1`: one row, one requested value field plus ticker/date/currency columns
- `bql_json / json_wide_1x5`: one row, five requested value fields plus shared secondary columns
- `bql_json / json_rows_1000x2`: 1,000 rows, two requested value fields plus shared secondary columns

Subscription replay captures a short real subscription window once, then replays cached messages through `SubscriptionState` cases: requested fields, `allFields`, high message count, and high topic count. Each cached SDK message is replayed multiple times when necessary so the measurement emphasizes `SubscriptionState -> Arrow RecordBatch` throughput rather than repeatedly constructing Bloomberg `MessageIterator`s.

Examples:

```bash
BENCH_ONLY=bdp_refdata cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
BENCH_ONLY=subscription_replay cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
BENCH_ONLY=bql_json BENCH_PROFILE_MODE=detail cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
```

### Detail profiling

Use the single benchmark-local profiling approach when you need optimization data over time:

```bash
BENCH_PROFILE_MODE=detail BENCH_ONLY=synthetic_bdh \
  cargo bench --package xbbg-bench --bench xbbg_benchmark_suite
```

`BENCH_PROFILE_MODE=detail` records structured profiling data in the normal JSON/Markdown reports:

- phase timings per scenario, such as generation, Arrow batch construction, and total time
- benchmark-local allocation counters
- allocation bytes and allocation counts per row/value

This profiling is implemented in the benchmark executable. The only production-crate surface used by these offline extractor benchmarks is the `xbbg-async/bench-internals` feature, which `xbbg-bench` enables explicitly and normal production builds do not enable.

Use `BENCH_ONLY=<substring>` to profile a single scenario or suite without running unrelated live probes. For example, `BENCH_ONLY=synthetic` runs only synthetic workloads, and `BENCH_ONLY=synthetic_subscriptions` runs only the synthetic subscription workload.

For subscription-path diagnosis, run `BENCH_ONLY=subscription_components BENCH_PROFILE_MODE=detail`. This benchmark-only suite emits `subscription_components / requested_fields` and `subscription_components / all_fields` records with component phases for message iteration, element access, requested-field lookup, allFields child traversal, datatype filtering, name-key caching, value getters, Arrow append/null padding, flush schema/arrays, and channel send overhead.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BLP_HOST` | `127.0.0.1` | Bloomberg host for live probes |
| `BLP_PORT` | `8194` | Bloomberg port for live probes |
| `BENCH_PROFILE` | `standard` | `smoke`, `standard`, or `stress` |
| `BENCH_PROFILE_MODE` | `none` | Set to `detail` for phase timings and benchmark-local allocation counters |
| `BENCH_ONLY` | unset | Run scenarios whose suite or scenario name contains this substring |
| `BENCH_SUB_COLLECT_MS` | profile-dependent | live subscription collection window |
| `BENCH_REPLAY_ITERATIONS` | profile-dependent | request-event replay iterations per seeded response |
| `BENCH_BQL_JSON_ITERATIONS` | profile-dependent | offline BQL JSON extraction iterations for one-row cases; row-heavy cases use a scaled-down count |
| `BENCH_SUB_REPLAY_MESSAGES` | profile-dependent | cached subscription messages processed in replay benchmarks |
| `BENCH_SUB_REPLAY_TOPICS` | profile-dependent | synthetic topic count for high-topic subscription replay |

### Results

The suite writes both timestamped and `latest` reports under the crate directory (`crates/xbbg-bench/benchmarks/results`), independent of the shell's current working directory:

```text
crates/xbbg-bench/benchmarks/results/xbbg_benchmark_suite_<timestamp>.json
crates/xbbg-bench/benchmarks/results/xbbg_benchmark_suite_latest.json
crates/xbbg-bench/benchmarks/results/xbbg_benchmark_suite_<timestamp>.md
crates/xbbg-bench/benchmarks/results/xbbg_benchmark_suite_latest.md
```

## Removed legacy benchmarks

The old standalone micro/experimental benchmark entrypoints were removed from `benches/` in favor of the single supported workflow suite. Use `xbbg_benchmark_suite` for all benchmark runs so live Bloomberg usage remains bounded and synthetic scale is reported consistently.