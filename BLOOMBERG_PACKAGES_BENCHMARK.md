# Bloomberg API Python Packages - Comprehensive Benchmark List

**Generated:** January 8, 2026  
**Purpose:** Competitive analysis for xbbg 1.0.0 Rust rewrite benchmarks (Issue #171)

---

## 1. Official Bloomberg API

### **blpapi** (Official Bloomberg SDK)
- **Latest Version:** 3.25.11 (as of Jan 2025)
- **PyPI URL:** https://pypi.org/project/blpapi/
- **GitHub:** https://github.com/msitt/blpapi-python
- **Installation:** `python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi`
- **Description:** Official Bloomberg Python SDK wrapper around C++ BLPAPI
- **Approach:** Low-level, event-driven, synchronous
- **Key Features:**
  - Direct C++ SDK binding
  - Session management, event handling
  - Request/response pattern
  - Supports Python 3.8-3.12 (32/64-bit)
  - Cross-platform (Windows, macOS, Linux)
  - Pre-built wheels bundled with C++ API
- **Last Update:** Jan 1, 2025 (documentation)
- **License:** Bloomberg proprietary
- **Documentation:** https://bloomberg.github.io/blpapi-docs/python/3.25.11/

---

## 2. Pandas-Based Wrappers

### **pdblp** (Pandas Bloomberg)
- **Latest Version:** 0.1.8
- **PyPI URL:** https://pypi.org/project/pdblp/
- **GitHub:** https://github.com/matthewgilbert/pdblp
- **Installation:** `pip install pdblp`
- **Description:** Pandas wrapper for Bloomberg Open API
- **Approach:** Synchronous, pandas-centric
- **Key Features:**
  - Wraps blpapi responses into pandas DataFrames
  - Historical data (bdh), reference data (bds)
  - Bloomberg SRCH data support
  - Caching with joblib
  - Context manager support (bopen)
- **Last Update:** June 21, 2015 (last commit)
- **Status:** ⚠️ **SUPERSEDED** - No longer under active development
- **Successor:** `blp` (see below)
- **License:** MIT
- **GitHub Stats:** 252 stars, 72 forks

### **blp** (Next-Gen Pythonic Interface)
- **Latest Version:** 0.0.3
- **PyPI URL:** https://pypi.org/project/blp/
- **GitHub:** https://github.com/matthewgilbert/blp
- **Installation:** `pip install blp` or `conda install -c conda-forge blp`
- **Description:** Pythonic interface for Bloomberg Open API (successor to pdblp)
- **Approach:** Synchronous, Pythonic, explicit session management
- **Key Features:**
  - Explicit separation of session management, event parsing, event aggregation
  - Extensible design
  - Better error handling than pdblp
  - Modern Python patterns
- **Last Update:** Oct 22, 2023
- **Status:** ⚠️ **INACTIVE** - Last release over 1 year ago
- **License:** MIT
- **Requires:** Python >=3.6

### **pdblpi** (Enhanced pdblp)
- **Latest Version:** Unknown (GitHub only)
- **PyPI URL:** Not on PyPI
- **GitHub:** https://github.com/ME-64/pdblpi
- **Description:** Enhanced Python wrapper for Bloomberg API based on pdblp
- **Approach:** Synchronous, pandas-based enhancement
- **Status:** ⚠️ **MINIMAL ACTIVITY** - Last update Sept 27, 2021
- **GitHub Stats:** 2 stars, 1 fork

---

## 3. Toolkit Packages

### **tia** (Toolkit for Integration and Analysis)
- **Latest Version:** 0.3.0
- **PyPI URL:** https://pypi.org/project/tia/
- **GitHub:** https://github.com/bpsmith/tia
- **Installation:** `pip install tia`
- **Description:** Toolkit for integration and analysis with Bloomberg support
- **Approach:** Synchronous, reference data focused
- **Key Features:**
  - LocalTerminal API for reference data
  - Support for multiple fields per security
  - Response as DataFrame or dict
  - v3api direct access
- **Last Update:** Dec 2, 2015
- **Status:** ⚠️ **ABANDONED** - No updates in 10+ years
- **License:** Unknown
- **GitHub Stats:** Limited activity

---

## 4. Modern Alternatives

### **xbbg** (Intuitive Bloomberg API)
- **Latest Version:** 0.10.3
- **PyPI URL:** https://pypi.org/project/xbbg/
- **GitHub:** https://github.com/alpha-xone/xbbg
- **Installation:** `pip install xbbg`
- **Description:** Intuitive Bloomberg data API with modern design
- **Approach:** Synchronous, pandas-native, Excel-compatible
- **Key Features:**
  - Excel-compatible inputs
  - Straightforward intraday bar requests
  - Subscriptions support
  - Pandas DataFrames as primary output
  - Requires Bloomberg C++ SDK 3.12.1+
- **Last Update:** Dec 29, 2025 (VERY RECENT)
- **Status:** ✅ **ACTIVELY MAINTAINED**
- **License:** Apache-2.0
- **Requires:** Python <3.15, >=3.10
- **Documentation:** https://xbbg.readthedocs.io/
- **GitHub Stats:** Active development

### **bbg-fetch** (Bloomberg Data Fetcher)
- **Latest Version:** 1.1.2
- **PyPI URL:** https://pypi.org/project/bbg-fetch/
- **GitHub:** https://github.com/ArturSepp/BloombergFetch
- **Installation:** `pip install bbg-fetch`
- **Description:** Python functionality for getting different data from Bloomberg
- **Approach:** Synchronous, data-focused
- **Key Features:**
  - Prices, implied volatilities, fundamentals
  - Credit data, equities, futures, options, bonds, FX
  - Quantitative finance focused
  - Requires Python >=3.8
- **Last Update:** Aug 7, 2025
- **Status:** ✅ **ACTIVELY MAINTAINED**
- **License:** GPLv3+
- **Tags:** bloomberg, bloomberg-api, bloomberg-terminal, financial-data, market-data, xbbg, blpapi
- **GitHub Stats:** Active development

---

## 5. Type Stubs & Utilities

### **blpapi-stubs**
- **Latest Version:** Unknown
- **PyPI URL:** https://pypi.org/project/blpapi-stubs/
- **Description:** Type stubs for blpapi (for IDE support)
- **Last Update:** March 16, 2022
- **Status:** ⚠️ **INACTIVE**
- **Purpose:** Type hints for blpapi package

---

## Summary Table

| Package | Version | Last Update | Status | Approach | GitHub Stars |
|---------|---------|-------------|--------|----------|--------------|
| **blpapi** | 3.25.11 | Jan 2025 | ✅ Active | Low-level, event-driven | Official |
| **xbbg** | 0.10.3 | Dec 2025 | ✅ Active | Pandas-native, modern | Active |
| **bbg-fetch** | 1.1.2 | Aug 2025 | ✅ Active | Data-focused | Active |
| **blp** | 0.0.3 | Oct 2023 | ⚠️ Inactive | Pythonic wrapper | ~50 |
| **pdblp** | 0.1.8 | Jun 2015 | ⚠️ Superseded | Pandas wrapper | 252 |
| **tia** | 0.3.0 | Dec 2015 | ⚠️ Abandoned | Toolkit | Limited |
| **pdblpi** | Unknown | Sep 2021 | ⚠️ Minimal | Enhanced pdblp | 2 |
| **blpapi-stubs** | Unknown | Mar 2022 | ⚠️ Inactive | Type stubs | N/A |

---

## Key Findings for Benchmarking

### Active Competitors (for xbbg 1.0.0 Rust rewrite):
1. **blpapi** - Official SDK (baseline, low-level)
2. **xbbg** - Current Python implementation (direct competitor)
3. **bbg-fetch** - Modern alternative (data-focused)

### Legacy/Inactive (for historical context):
- **pdblp** - Pioneering pandas wrapper (superseded by blp)
- **blp** - Attempted modernization (stalled)
- **tia** - Early toolkit (abandoned)

### Benchmark Strategy:
- Compare **xbbg Rust** vs **xbbg Python** (0.10.3) for performance
- Compare vs **blpapi** (3.25.11) for raw API performance
- Compare vs **bbg-fetch** (1.1.2) for feature parity
- Show improvements over legacy **pdblp** (0.1.8) for historical context

---

## Installation Commands Reference

```bash
# Official Bloomberg API
python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

# Active alternatives
pip install xbbg          # Current Python implementation
pip install bbg-fetch     # Modern alternative
pip install blp           # Pythonic wrapper (inactive)

# Legacy packages
pip install pdblp         # Original pandas wrapper (superseded)
pip install tia           # Toolkit (abandoned)
```

---

## Notes for Issue #171

- **xbbg** is the primary competitor to benchmark against (same author, Python version)
- **blpapi** provides the baseline for raw API performance
- **bbg-fetch** shows modern design patterns in Python
- Most packages are synchronous; async support is minimal in Python ecosystem
- Pandas integration is standard across all modern packages
- Performance gains in Rust rewrite should be significant due to:
  - No GIL limitations
  - Direct C++ binding (vs Python wrapper overhead)
  - Async/await support
  - Memory efficiency

