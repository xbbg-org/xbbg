# Quick Start Guide - Benchmark with Versioning

## TL;DR

```bash
# 1. Install xbbg (the version you want to benchmark)
maturin develop --release

# 2. Run benchmarks (requires Bloomberg terminal/BPIPE)
cd benchmarks
python run_all.py

# 3. Results are auto-saved with version
# - benchmark_v{version}.json (official, overwrites)
# - benchmark_v{version}_{timestamp}.json (archive, keeps)

# 4. Commit to git
git add results/benchmark_v*.json results/benchmark_v*.md
git commit -m "chore: add benchmark results for v1.0.0"
```

---

## File Naming Explained

After running benchmarks for v1.0.0, you'll see:

```
results/
├── benchmark_v1.0.0.json              ← Official v1.0.0 results (OVERWRITES)
├── benchmark_v1.0.0.md
├── benchmark_v1.0.0_20260108_153045.json  ← Archive from this run (KEEPS)
├── benchmark_v1.0.0_20260108_153045.md
├── latest.json                        ← Symlink (DON'T COMMIT)
└── latest.md
```

### What to Commit

✅ `benchmark_v*.json` - All version files
✅ `benchmark_v*.md` - All markdown reports  
❌ `latest.*` - Auto-generated, ignore

---

## Why This Design?

### Version Files (Overwrites)
**Purpose:** Official benchmark for each release

**Example:** "xbbg v1.0.0 is 10x faster than v0.10.3" ← Use these numbers in marketing/docs

**When:** Re-running benchmarks for same version overwrites → always shows current best performance

### Timestamped Archives (Never Overwrites)
**Purpose:** Historical record of all runs

**Example:** Compare v1.0.0 performance on different machines/times

**When:** Debugging performance variations, identifying environmental factors

---

## Typical Workflows

### Scenario 1: New Release

```bash
# Build v1.0.0
git checkout v1.0.0
maturin develop --release

# Run benchmarks
python benchmarks/run_all.py
# Creates: benchmark_v1.0.0.json
#          benchmark_v1.0.0_20260108_153045.json

# Commit
git add results/benchmark_v1.0.0.*
git commit -m "chore: add benchmark results for v1.0.0"
git push
```

### Scenario 2: Performance Optimization

```bash
# Made code faster in v1.0.0, want to update benchmarks
maturin develop --release

# Run again
python benchmarks/run_all.py
# OVERWRITES: benchmark_v1.0.0.json (updated official)
# CREATES: benchmark_v1.0.0_20260110_091230.json (new archive)

# Commit updated official benchmark
git add results/benchmark_v1.0.0.json results/benchmark_v1.0.0.md
git add results/benchmark_v1.0.0_20260110_091230.*
git commit -m "chore: update v1.0.0 benchmarks (post-optimization)"
```

### Scenario 3: Compare Versions

```bash
# See performance improvement from v0.10.3 to v1.0.0
diff results/benchmark_v0.10.3.md results/benchmark_v1.0.0.md

# Or use jq for JSON
jq '.benchmarks."BDP - Reference Data"' results/benchmark_v1.0.0.json
```

---

## Requirements

**Must have:**
- Bloomberg Terminal or B-PIPE connection
- Active market data access
- `xbbg` installed (the version you want to benchmark)
- Competing packages installed (optional):
  ```bash
  pip install xbbg==0.10.3  # legacy version
  pip install pdblp
  pip install bbg-fetch
  ```

**Bloomberg data usage:** ~200-350 data points per full benchmark run

---

## Troubleshooting

### "Version shows as 'unknown'"

**Fix:** Ensure xbbg is installed:
```bash
pip show xbbg
# or
python -c "import xbbg; print(xbbg.__version__)"
```

### "Bloomberg connection failed"

**Check:**
- Bloomberg terminal is running
- BLPAPI_ROOT environment variable is set
- Can connect via `blpapi` package:
  ```python
  import blpapi
  session = blpapi.Session()
  session.start()
  ```

### "Competing package missing"

**Expected:** Not all competing packages need to be installed. The benchmark will skip missing packages.

**To install:**
```bash
pip install pdblp
pip install xbbg==0.10.3
```

---

## Results Location

After running benchmarks:

1. **View latest:** `cat results/latest.md`
2. **View specific version:** `cat results/benchmark_v1.0.0.md`
3. **View historical run:** `cat results/benchmark_v1.0.0_20260108_153045.md`

---

## See Also

- [README.md](README.md) - Full benchmark documentation
- [VERSIONING.md](VERSIONING.md) - Detailed versioning strategy
- [results/README.md](results/README.md) - Results directory guide
- [config.py](config.py) - Customize benchmark parameters
