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
2. A bounded live subscription throughput window.
3. Synthetic massive BDP, BDH, BDTICK, BQL, and subscription workloads.

Live probes intentionally keep Bloomberg data usage low. Scale comes from the synthetic workloads, which use deterministic generated data and do not issue Bloomberg requests.

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

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BLP_HOST` | `127.0.0.1` | Bloomberg host for live probes |
| `BLP_PORT` | `8194` | Bloomberg port for live probes |
| `BENCH_PROFILE` | `standard` | `smoke`, `standard`, or `stress` |
| `BENCH_SUB_COLLECT_MS` | profile-dependent | live subscription collection window |

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