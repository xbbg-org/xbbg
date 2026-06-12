# xbbg Benchmark Results

**Version:** 1.2.6
**Generated:** 2026-06-11 20:25:50

---

## BDP - Reference Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 171.02 | 195.46 | 31.33 | 45.59 | (1, 3) |
| xbbg-legacy | 0.55 | 0.40 | 0.03 | 0.00 | (1,) |
| pdblp ✅ | 0.39 | 0.39 | 0.01 | 0.00 | (1,) |
| xbbg-rust | 424.81 | 389.38 | 18.49 | 0.03 | (9, 3) |
| xbbg-legacy | 0.56 | 0.40 | 0.01 | 0.00 | (1,) |
| pdblp ✅ | 0.40 | 0.38 | 0.01 | 0.00 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## BDH - Historical Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 264.73 | 254.74 | 37.69 | 0.05 | (3, 4) |
| xbbg-legacy | 0.45 | 0.40 | 0.01 | 0.00 | (1,) |
| pdblp ✅ | 0.40 | 0.39 | 0.01 | 0.00 | (1,) |
| xbbg-rust | 544.14 | 654.44 | 93.79 | 0.05 | (27, 4) |
| xbbg-legacy | 0.43 | 0.44 | 0.06 | 0.00 | (1,) |
| pdblp ✅ | 0.41 | 0.38 | 0.01 | 0.00 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## BDIB - Intraday Bars

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-legacy ✅ | 0.40 | 0.39 | 0.02 | 0.00 | (1,) |
| pdblp | 0.40 | 0.42 | 0.07 | 0.00 | (1,) |

---

## BDTICK - Tick Data

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-legacy ✅ | 0.41 | 0.39 | 0.02 | 0.00 | (1,) |
| pdblp ✅ | 0.41 | 0.38 | 0.01 | 0.00 | (1,) |
| xbbg-legacy ✅ | 0.39 | 0.38 | 0.01 | 0.00 | (1,) |
| pdblp ✅ | 0.39 | 0.39 | 0.01 | 0.00 | (1,) |
| xbbg-legacy ✅ | 0.38 | 0.38 | 0.01 | 0.00 | (1,) |
| pdblp ✅ | 0.52 | 0.39 | 0.01 | 0.00 | (1,) |

---

## BQL - Query Language

| Package | Cold Start (ms) | Warm Mean (ms) | Warm Std (ms) | Memory (MB) | Shape |
|---------|-----------------|----------------|---------------|-------------|-------|
| xbbg-rust | 195.66 | 260.12 | 163.64 | 0.03 | (1, 4) |
| xbbg-legacy | 0.44 | 0.45 | 0.06 | 0.00 | (1,) |
| xbbg-legacy ✅ | 0.46 | 0.43 | 0.04 | 0.02 | (1,) |

**Speedup vs legacy:** 0.00x faster

---

## Summary

**Total execution time (warm):**

- xbbg (Rust): 1754.13ms
- xbbg (legacy): 4.05ms (0.00x slower)
- pdblp: 3.12ms (0.00x slower)

