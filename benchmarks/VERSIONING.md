# Benchmark Versioning Strategy

## Overview

Benchmark results are automatically saved per xbbg version with both:
1. **Version-specific files** (overwrites for same version)
2. **Timestamped archives** (never overwrites)

This allows tracking performance across versions while keeping historical snapshots.

---

## File Structure

```
results/
├── benchmark_v1.0.0.json              # Official v1.0.0 results (overwrites)
├── benchmark_v1.0.0.md
├── benchmark_v1.0.0_20260108_153045.json  # Jan 8 run (archived)
├── benchmark_v1.0.0_20260108_153045.md
├── benchmark_v1.0.0_20260110_091230.json  # Jan 10 run (archived)
├── benchmark_v1.0.0_20260110_091230.md
├── benchmark_v1.0.1.json              # Official v1.0.1 results
├── benchmark_v1.0.1.md
├── latest.json                        # Symlink to latest version
└── latest.md
```

---

## Automatic Versioning

The benchmark script automatically:

1. **Detects xbbg version** from installed package
2. **Generates version-specific filename**
3. **Overwrites existing version file** (if re-running same version)
4. **Creates timestamped archive** (never overwrites)
5. **Updates latest symlinks**

### Example Run

```bash
$ python run_all.py

======================================================================
xbbg Comprehensive Benchmark Suite
======================================================================

xbbg version: 1.0.0

Running benchmarks with live Bloomberg data...
Estimated data usage: ~200-350 data points

...

======================================================================
Generating Reports
======================================================================

✓ Version JSON: results/benchmark_v1.0.0.json
✓ Version MD:   results/benchmark_v1.0.0.md
✓ Archive JSON: results/benchmark_v1.0.0_20260108_153045.json
✓ Archive MD:   results/benchmark_v1.0.0_20260108_153045.md
✓ Latest symlinks updated

======================================================================
Benchmarks Complete!
======================================================================

Results saved:
  - Version-specific (overwrites): results/benchmark_v1.0.0.md
  - Timestamped archive (keeps):   results/benchmark_v1.0.0_20260108_153045.md
  - Latest:                        latest.md

Commit these files to git for version tracking.
```

---

## Use Cases

### 1. Official Version Benchmarks

**Scenario:** You release v1.0.0 and want official benchmark results.

```bash
# Build and install v1.0.0
maturin develop --release

# Run benchmarks
python benchmarks/run_all.py
# Creates: benchmark_v1.0.0.json (official)
#          benchmark_v1.0.0_20260108_153045.json (archive)

# Commit official results
git add results/benchmark_v1.0.0.*
git commit -m "chore: add benchmark results for v1.0.0"
```

**Result:** `benchmark_v1.0.0.json` is the official benchmark for this version.

---

### 2. Re-running Benchmarks (Overwrites)

**Scenario:** You fix a bug in v1.0.0, want to update benchmarks.

```bash
# Make changes, rebuild
maturin develop --release

# Run benchmarks again
python benchmarks/run_all.py
# OVERWRITES: benchmark_v1.0.0.json (updated official)
# CREATES:    benchmark_v1.0.0_20260110_091230.json (new archive)
```

**Result:** Official v1.0.0 benchmark is updated, but old run is archived.

---

### 3. Comparing Versions

**Scenario:** You want to compare v1.0.1 vs v1.0.0 performance.

```bash
# After running benchmarks for both versions
diff results/benchmark_v1.0.0.md results/benchmark_v1.0.1.md

# Or use jq for JSON comparison
jq '.benchmarks' results/benchmark_v1.0.0.json > v1.0.0_summary.txt
jq '.benchmarks' results/benchmark_v1.0.1.json > v1.0.1_summary.txt
diff v1.0.0_summary.txt v1.0.1_summary.txt
```

---

### 4. Historical Tracking

**Scenario:** You want to see how v1.0.0 performed across different runs.

```bash
# List all v1.0.0 runs
ls results/benchmark_v1.0.0_*.md

# results/benchmark_v1.0.0_20260108_153045.md  (Desktop, morning)
# results/benchmark_v1.0.0_20260108_203012.md  (Desktop, evening)
# results/benchmark_v1.0.0_20260109_104521.md  (Laptop, office)

# Compare morning vs evening performance
diff results/benchmark_v1.0.0_20260108_153045.md \
     results/benchmark_v1.0.0_20260108_203012.md
```

**Insight:** Identify performance variations due to:
- Network conditions
- Bloomberg server load
- Hardware differences
- Background processes

---

## Git Workflow

### What to Commit

✅ **Commit:**
- `benchmark_v{version}.json` - Official version benchmarks
- `benchmark_v{version}.md`
- `benchmark_v{version}_{timestamp}.json` - Historical archives
- `benchmark_v{version}_{timestamp}.md`

❌ **Do NOT commit:**
- `latest.json` - Generated file
- `latest.md`

### Commit Messages

```bash
# New version benchmark
git commit -m "chore: add benchmark results for v1.0.0"

# Updated benchmark
git commit -m "chore: update benchmark results for v1.0.0 (post-fix)"

# Multiple versions
git commit -m "chore: add benchmarks for v1.0.0, v1.0.1"
```

---

## Configuration

### Changing Version Detection

If automatic version detection fails, you can manually specify version:

```python
# In run_all.py
def main():
    # Force a specific version
    version = "1.0.0-rc.1"  # Override automatic detection
    # Or: version = get_xbbg_version()
```

### Disabling Timestamped Archives

If you only want version-specific files (no archives):

```python
# In run_all.py, comment out archive generation:
# archive_json = RESULTS_DIR / f"benchmark_v{version}_{timestamp_short}.json"
# archive_md = RESULTS_DIR / f"benchmark_v{version}_{timestamp_short}.md"
# shutil.copy(version_json, archive_json)
# shutil.copy(version_md, archive_md)
```

---

## FAQ

### Q: Why overwrite version-specific files?

**A:** Official benchmarks should represent the "current truth" for a version. If you improve performance in v1.0.0 through optimization, the official benchmark should reflect that improvement. Historical runs are preserved in timestamped archives.

### Q: Why keep timestamped archives?

**A:** Performance can vary due to:
- Network conditions
- Bloomberg server load
- Hardware differences
- Background processes

Timestamped archives help identify if performance regressions are real or environmental.

### Q: Can I delete old archives?

**A:** Yes, but not recommended. Archives are small text files and provide valuable historical context. If needed, delete archives older than 6-12 months.

### Q: What if version detection fails?

**A:** The script falls back to "unknown" version. You can manually edit the generated filenames or fix version detection in `get_xbbg_version()`.

### Q: How do I compare against competitors?

**A:** Competitor results are included in the same benchmark files:

```json
{
  "version": "1.0.0",
  "benchmarks": {
    "BDP - Reference Data": [
      {"package": "xbbg-rust", "warm_mean_ms": 12.3},
      {"package": "xbbg-legacy", "warm_mean_ms": 120.7},
      {"package": "pdblp", "warm_mean_ms": 85.2}
    ]
  }
}
```

Compare the same benchmark file to see xbbg vs competitors.

---

## Related

- [README.md](README.md) - Main benchmark documentation
- [results/README.md](results/README.md) - Results directory guide
- [config.py](config.py) - Benchmark configuration
