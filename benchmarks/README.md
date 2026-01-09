# xbbg Benchmarks

Comprehensive benchmark suite comparing xbbg (Rust) against competing Bloomberg API packages.

## ⚠️ Bloomberg Data Usage

**These benchmarks use live Bloomberg data.** Each full benchmark run queries:
- **BDP**: ~10-20 data points
- **BDH**: ~15-30 historical points
- **BDIB**: ~50-100 intraday bars
- **BDTICK**: ~100-200 tick data points

**Total per run: ~200-350 data points**

Run benchmarks locally and control frequency to manage Bloomberg data limits.

---

## Competing Packages

| Package | Version | Status | Notes |
|---------|---------|--------|-------|
| **xbbg (Rust)** | 1.0.0+ | Current | This version (Rust rewrite) |
| **xbbg (legacy)** | 0.10.3 | Baseline | Pure Python version |
| **blpapi** | 3.25.11 | Official | Raw Bloomberg API |
| **bbg-fetch** | 1.1.2 | Active | Modern alternative |
| **pdblp** | 0.1.8 | Legacy | Historical comparison |

See [../BLOOMBERG_PACKAGES_BENCHMARK.md](../BLOOMBERG_PACKAGES_BENCHMARK.md) for full package details.

---

## Quick Start

### 1. Install Dependencies

```bash
# Install all competing packages
pip install xbbg==0.10.3  # Legacy version for comparison
pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
pip install bbg-fetch
pip install pdblp

# Install benchmark dependencies
pip install pytest-benchmark tabulate pandas polars
```

### 2. Run Benchmarks

```bash
# Run all benchmarks
python benchmarks/run_all.py

# Run specific benchmark
python benchmarks/bench_bdp.py
python benchmarks/bench_bdh.py
python benchmarks/bench_bdib.py

# Generate report
python benchmarks/generate_report.py
```

---

## Benchmark Scripts

| Script | Operations | Data Points |
|--------|-----------|-------------|
| `bench_bdp.py` | Reference data (bdp) | ~10-20 |
| `bench_bdh.py` | Historical data (bdh) | ~15-30 |
| `bench_bdib.py` | Intraday bars (bdib) | ~50-100 |
| `bench_bdtick.py` | Tick data (bdtick) | ~100-200 |
| `bench_bql.py` | BQL queries | ~10-20 |
| `run_all.py` | All benchmarks | ~200-350 |

---

## Benchmark Configuration

Edit `config.py` to customize:

```python
# Test data configuration
TICKERS = ["IBM US Equity", "AAPL US Equity"]
FIELDS = ["PX_LAST", "VOLUME"]
DATE_RANGE = ("2025-01-02", "2025-01-06")

# Benchmark settings
ITERATIONS = 5  # Repetitions per test
WARMUP_ITERATIONS = 2  # Warm-up runs

# Packages to compare
PACKAGES = ["xbbg-rust", "xbbg-legacy", "blpapi", "bbg-fetch", "pdblp"]
```

---

## Output Format

Results are saved to `results/`:

```
results/
├── benchmark_YYYYMMDD_HHMMSS.json    # Raw data
├── benchmark_YYYYMMDD_HHMMSS.md      # Markdown report
└── latest.json                        # Symlink to latest run
```

### Example Output

```
┌─────────────────┬──────────┬─────────────┬──────────────┬──────────┐
│ Package         │ BDP (ms) │ BDH (ms)    │ Memory (MB)  │ Winner   │
├─────────────────┼──────────┼─────────────┼──────────────┼──────────┤
│ xbbg (Rust)     │  12 ✅   │  145 ✅     │  8.2 ✅      │ 🏆       │
│ xbbg (legacy)   │ 120      │ 1200        │ 45.1         │          │
│ blpapi          │  35      │  380        │ 22.3         │          │
│ bbg-fetch       │  95      │  920        │ 38.7         │          │
│ pdblp           │  85      │  890        │ 32.4         │          │
└─────────────────┴──────────┴─────────────┴──────────────┴──────────┘

Speedup vs legacy xbbg: 10.0x faster, 5.5x less memory
Speedup vs pdblp:       7.1x faster, 3.9x less memory
```

---

## Metrics Tracked

| Metric | Description |
|--------|-------------|
| **Latency** | Time to complete request (p50, p95, p99) |
| **Throughput** | Requests per second |
| **Memory** | Peak memory usage |
| **Cold Start** | First request (includes setup) |
| **Warm** | Subsequent requests (cached) |
| **Data Shape** | Result size validation |

---

## CI Integration (Planned)

`.github/workflows/benchmark.yml` will:
- Run benchmarks on PR
- Compare against main branch
- Post results as PR comment
- Store historical data in GitHub Pages
- Fail if performance regresses >10%

---

## Notes

- **Bloomberg connection required**: Tests need active Bloomberg terminal or BPIPE
- **Data limits**: Be mindful of Bloomberg data limits when running frequently
- **Timing variability**: Network latency affects results; run multiple iterations
- **Package versions**: Results are version-specific; document versions used
- **Historical tracking**: Save results to track performance over time
