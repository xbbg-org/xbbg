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

## Benchmarks

### Pure Rust (no Bloomberg connection)

```bash
cargo bench --package xbbg-bench --bench datetime
cargo bench --package xbbg-bench --bench alloc_criterion
```

### Require Bloomberg DLL

```bash
cargo bench --package xbbg-bench --bench name
```

### Require live Bloomberg connection

```bash
cargo bench --package xbbg-bench --bench live_bdp
cargo bench --package xbbg-bench --bench live_bdp_profiled
cargo bench --package xbbg-bench --bench live_subscription
cargo bench --package xbbg-bench --bench parse_cached
cargo bench --package xbbg-bench --bench alloc_profile
```

### Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| `BLP_HOST` | `127.0.0.1` | All live benchmarks |
| `BLP_PORT` | `8194` | All live benchmarks |
| `BENCH_ITERATIONS` | varies | `parse_cached`, `live_bdp`, `live_bdp_profiled` |
| `BENCH_WARMUP` | `2` | `live_bdp` |
| `BENCH_COLLECT_MS` | `5000` | `live_subscription` |
| `ALLOC_ITERATIONS` | `100` | `alloc_profile` |

## Benchmark inventory

| Benchmark | Framework | What it measures |
|-----------|-----------|------------------|
| `datetime` | Criterion | `HighPrecisionDatetime::to_micros/to_nanos` conversion |
| `name` | Criterion | `Name` comparison and `as_str()` |
| `alloc_criterion` | Criterion + custom allocator | Allocation counts for datetime, name, field operations |
| `live_bdp` | Manual timing | End-to-end BDP round-trip (cold/warm, min/max/std) |
| `live_bdp_profiled` | Manual timing | Per-phase BDP breakdown (get_service → parse_response) |
| `live_subscription` | Manual timing | Subscription setup, time-to-first-tick, throughput |
| `parse_cached` | Manual timing | 6 parsing strategies compared (baseline → minimal FFI) |
| `alloc_profile` | dhat | Heap allocation profiling per operation phase |
