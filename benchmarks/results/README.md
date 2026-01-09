# Benchmark Results

This directory contains historical benchmark results for xbbg performance tracking.

## File Naming Convention

### Version-Specific Files (Overwrites)
```
benchmark_v{version}.json
benchmark_v{version}.md
```

**Example:** `benchmark_v1.0.0.json`, `benchmark_v1.0.1.md`

- **Purpose:** Current benchmark for each version
- **Behavior:** OVERWRITES when you re-run benchmarks for the same version
- **Commit:** YES - These are the "official" benchmark results per version

### Timestamped Archives (Never Overwrites)
```
benchmark_v{version}_{YYYYMMDD_HHMMSS}.json
benchmark_v{version}_{YYYYMMDD_HHMMSS}.md
```

**Example:** `benchmark_v1.0.0_20260108_153045.json`

- **Purpose:** Historical snapshots of benchmark runs
- **Behavior:** NEVER overwrites - each run creates a new file
- **Commit:** YES - Keeps full history of all benchmark runs
- **Use case:** Track performance changes across different machines, Bloomberg connections, etc.

### Latest Files (Symlinks/Copies)
```
latest.json
latest.md
```

- **Purpose:** Quick access to most recent benchmark
- **Behavior:** Always points to/copies the latest version
- **Commit:** NO - These are generated, ignore in git

## Workflow

### Running Benchmarks Locally

```bash
# Must have Bloomberg terminal/BPIPE access
cd benchmarks
python run_all.py
```

**Output:**
```
results/
├── benchmark_v1.0.0.json           # Version file (overwrites)
├── benchmark_v1.0.0.md
├── benchmark_v1.0.0_20260108_153045.json  # Timestamped archive (keeps)
├── benchmark_v1.0.0_20260108_153045.md
├── latest.json                     # Symlink/copy (ignored)
└── latest.md
```

### After Running Benchmarks

1. **Review results:**
   ```bash
   cat results/benchmark_v1.0.0.md
   ```

2. **Commit to git:**
   ```bash
   git add results/benchmark_v*.json
   git add results/benchmark_v*.md
   git commit -m "chore: add benchmark results for v1.0.0"
   ```

3. **Compare versions:**
   ```bash
   # Compare current vs previous version
   diff results/benchmark_v0.10.3.md results/benchmark_v1.0.0.md
   ```

## Version History

| Version | Date | Key Results | Notes |
|---------|------|-------------|-------|
| 1.0.0 | TBD | TBD | First Rust release |
| 0.10.3 | TBD | TBD | Legacy Python (baseline) |

## Why This Structure?

### ✅ Version-Specific Files
- **Marketing**: "v1.0.0 is 10x faster than v0.10.3" (official comparison)
- **Documentation**: Include in release notes
- **Reproducibility**: Re-run benchmarks, overwrite if needed

### ✅ Timestamped Archives
- **Historical tracking**: See how performance evolved
- **Environment differences**: Compare results across different machines/connections
- **Debugging**: "Why was v1.0.0 faster on Jan 8 than Jan 5?"

### ❌ Latest Files (Not Committed)
- **Convenience**: Quick access for local dev
- **Generated**: Can always be recreated
- **No history value**: Already captured in version/timestamped files

## Data Integrity

**All benchmark files are committed to git** (except `latest.*`) because:
- ✅ Small file sizes (JSON/MD are text, compress well)
- ✅ Performance claims need evidence
- ✅ Historical tracking is valuable
- ✅ Results are expensive to generate (require Bloomberg access)

## CI/CD Note

**Benchmarks do NOT run in CI** because they require:
- ❌ Bloomberg Terminal or B-PIPE access
- ❌ Live market data connection
- ❌ Data usage limits management

**Benchmarks run LOCALLY only**, then results are committed.

## Interpreting Results

### Key Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| **Cold Start** | First request (includes setup) | Baseline |
| **Warm Mean** | Average of subsequent requests | Primary comparison |
| **Warm P95** | 95th percentile latency | Consistency indicator |
| **Memory Peak** | Peak memory usage | Lower is better |
| **Speedup** | Ratio vs baseline | Higher is better |

### Example Comparison

```markdown
## BDP - Reference Data

| Package         | Warm Mean (ms) | Memory (MB) |
|-----------------|----------------|-------------|
| xbbg v1.0.0 ✅  |  12.3          |  8.2        |
| xbbg v0.10.3    | 120.7          | 45.1        |

**Speedup:** 9.8x faster, 5.5x less memory
```

**This means:** Rust version completes BDP requests in 1/10th the time using 1/5th the memory.

## Questions?

See [../README.md](../README.md) for full benchmark suite documentation.
