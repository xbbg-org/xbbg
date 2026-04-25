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
cargo bench --package xbbg-bench --bench arrow_builder_append
cargo bench --package xbbg-bench --bench async_subscription_replay
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
cargo bench --package xbbg-bench --bench cached_subscription_arrow
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
| `ARROW_BENCH_ROWS` | `100000` | `arrow_builder_append` |
| `ARROW_BENCH_ITERATIONS` | `5` | `arrow_builder_append` |
| `SUB_REPLAY_ROWS` | `100000` | `async_subscription_replay` |
| `SUB_REPLAY_FLUSH` | `1024` | `async_subscription_replay` |
| `SUB_REPLAY_ITERATIONS` | `5` | `async_subscription_replay` |
| `CACHED_SUB_TICKER` | `XBTUSD Curncy` | `cached_subscription_arrow` |
| `CACHED_SUB_FIELDS` | `LAST_PRICE,BID,ASK` | `cached_subscription_arrow` |
| `CACHED_SUB_CAPTURE_MESSAGES` | `25` | `cached_subscription_arrow` |
| `CACHED_SUB_CAPTURE_TIMEOUT_MS` | `15000` | `cached_subscription_arrow` |
| `CACHED_SUB_REPLAY_LOOPS` | `1000` | `cached_subscription_arrow` |
| `CACHED_SUB_FLUSH` | `1024` | `cached_subscription_arrow` |
| `CACHED_SUB_CHANNEL_CAPACITY` | `16384` | `cached_subscription_arrow` |
| `CACHED_SUB_ITERATIONS` | `5` | `cached_subscription_arrow` |
| `CACHED_SUB_ALL_FIELDS` | `false` | `cached_subscription_arrow` |

## Benchmark inventory

| Benchmark | Framework | What it measures |
|-----------|-----------|------------------|
| `datetime` | Criterion | `HighPrecisionDatetime::to_micros/to_nanos` conversion |
| `name` | Criterion | `Name` comparison and `as_str()` |
| `alloc_criterion` | Criterion + custom allocator | Allocation counts for datetime, name, field operations |
| `arrow_builder_append` | Manual timing | Offline Arrow/TypedBuilder append, null, late-column, and RecordBatch finalization paths |
| `async_subscription_replay` | Manual timing | Offline synthetic xbbg-async subscription-shaped Arrow replay; no Bloomberg/datamock |
| `cached_subscription_arrow` | Manual timing | One bounded live subscription capture replayed through real `SubscriptionState` into Arrow batches |
| `live_bdp` | Manual timing | End-to-end BDP round-trip (cold/warm, min/max/std) |
| `live_bdp_profiled` | Manual timing | Per-phase BDP breakdown (get_service → parse_response) |
| `live_subscription` | Manual timing | Subscription setup, time-to-first-tick, throughput |
| `parse_cached` | Manual timing | 6 parsing strategies compared (baseline → minimal FFI) |
| `alloc_profile` | dhat | Heap allocation profiling per operation phase |
