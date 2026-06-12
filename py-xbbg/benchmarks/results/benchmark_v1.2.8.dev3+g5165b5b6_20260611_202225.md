# xbbg Benchmark Results

**Version:** 1.2.8.dev3+g5165b5b6
**Generated:** 2026-06-11 20:22:25

---

## BDP - Reference Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 171.30 | 174.13 | 23.73 | 52.36 | (1, 3) |
| xbbg-legacy | 0.54 | 0.58 | 0.18 | 0.00 | (1,) |
| pdblp | 0.45 | 0.40 | 0.01 | 0.00 | (1,) |
| xbbg-rust | 447.47 | 491.93 | 235.79 | 0.54 | (9, 3) |
| xbbg-legacy | 0.49 | 0.37 | 0.02 | 0.00 | (1,) |
| pdblp ✅ | 0.37 | 0.35 | 0.02 | 0.00 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## BDH - Historical Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 239.36 | 244.74 | 26.46 | 0.56 | (3, 4) |
| xbbg-legacy | 0.49 | 0.36 | 0.02 | 0.00 | (1,) |
| pdblp ✅ | 0.35 | 0.35 | 0.00 | 0.00 | (1,) |
| xbbg-rust | 534.91 | 554.44 | 83.43 | 0.54 | (27, 4) |
| xbbg-legacy | 0.44 | 0.42 | 0.06 | 0.00 | (1,) |
| pdblp ✅ | 0.36 | 0.35 | 0.01 | 0.00 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## BDIB - Intraday Bars

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-legacy ✅ | 0.49 | 0.39 | 0.03 | 0.00 | (1,) |
| pdblp | 0.69 | 0.48 | 0.06 | 0.00 | (1,) |

---

## BDTICK - Tick Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-legacy | 0.39 | 0.37 | 0.02 | 0.00 | (1,) |
| pdblp | 0.39 | 0.53 | 0.14 | 0.00 | (1,) |
| xbbg-legacy | 0.37 | 0.35 | 0.02 | 0.00 | (1,) |
| pdblp ✅ | 0.36 | 0.34 | 0.01 | 0.00 | (1,) |
| xbbg-legacy ✅ | 0.35 | 0.34 | 0.01 | 0.00 | (1,) |
| pdblp ✅ | 0.34 | 0.35 | 0.01 | 0.00 | (1,) |

---

## BQL - Query Language

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 201.88 | 158.23 | 31.81 | 0.54 | (1, 4) |
| xbbg-legacy ✅ | 0.51 | 0.42 | 0.06 | 0.00 | (1,) |
| xbbg-legacy ✅ | 0.42 | 0.41 | 0.07 | 0.53 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## Summary

**Total execution time (warm):**

- xbbg (Rust): 1623.47ms
- xbbg (legacy): 4.02ms (0.00x slower)
- pdblp: 3.14ms (0.00x slower)

