<!-- markdownlint-disable MD013 MD031 MD032 MD033 MD036 MD041 MD051 MD060 -->
<div align="center">

<a href="https://github.com/alpha-xone/xbbg"><img src="https://raw.githubusercontent.com/alpha-xone/xbbg/main/docs/xbbg.png" alt="xbbg logo" width="150"></a>

<!-- markdownlint-disable MD036 -->
**xbbg: An intuitive Bloomberg API for Python**
<!-- markdownlint-enable MD036 -->

[![PyPI version](https://img.shields.io/pypi/v/xbbg.svg)](https://pypi.org/project/xbbg/)
[![Python versions](https://img.shields.io/pypi/pyversions/xbbg.svg)](https://pypi.org/project/xbbg/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/xbbg)](https://pypistats.org/packages/xbbg)
[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/fUUy2nfzxM)

<a href="https://www.buymeacoffee.com/Lntx29Oof"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-1E3A8A?style=plastic&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>

**Quick Links:** [Discord](https://discord.gg/fUUy2nfzxM) • [Documentation](https://xbbg.readthedocs.io/) • [Installation](#installation) • [Quickstart](#quickstart) • [Examples](#examples) • [Contributing](CONTRIBUTING.md) • [Changelog](CHANGELOG.md)

</div>
<!-- markdownlint-enable MD033 MD041 -->

---

<!-- xbbg:latest-release-start -->
Latest release: xbbg==0.12.0b1 (release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.12.0b1))
<!-- xbbg:latest-release-end -->

## Table of Contents

- [Overview](#overview)
- [Why Choose xbbg?](#why-choose-xbbg)
- [Supported Functionality](#supported-functionality)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
  - [Basic Usage](#basic-usage)
  - [Common Use Cases](#common-use-cases)
  - [Connection Options](#connection-options)
  - [Async Functions](#async-functions)
  - [Multi-Backend Support](#multi-backend-support)
- [Examples](#examples)
  - [📊 Reference Data](#-reference-data)
  - [📈 Historical Data](#-historical-data)
  - [⏱️ Intraday Data](#️-intraday-data)
  - [🔍 Screening & Queries](#-screening--queries)
  - [📡 Real-time](#-real-time)
  - [🔧 Utilities](#-utilities)
- [Data Storage](#data-storage)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [Getting Help](#getting-help)
- [Links](#links)
- [License](#license)

## Overview

xbbg is a comprehensive Bloomberg API wrapper for Python, providing a clean, Pythonic interface to Bloomberg's data services. Designed for quantitative researchers, portfolio managers, and financial engineers, xbbg simplifies data access while maintaining full API functionality.

### Key Features

<table>
<tr>
<td width="50%">

**Complete API Coverage**
- Reference data (BDP/BDS)
- Historical time series (BDH)
- Intraday bars and tick data
- Real-time subscriptions
- BQL, BEQS, and BSRCH queries
- Technical analysis (BTA)

</td>
<td width="50%">

**Production-Grade Features**
- Parquet caching for intraday bars
- Async/await support for non-blocking operations
- **Multi-backend output** (pandas, Polars, PyArrow, DuckDB)
- Full type hints for IDE integration
- Comprehensive error handling
- Exchange-aware market hours

</td>
</tr>
<tr>
<td width="50%">

**Excel Compatibility**
- Familiar Bloomberg Excel syntax
- Same field names and date formats
- Minimal learning curve for Excel users
- Direct migration path from Excel workflows

</td>
<td width="50%">

**Developer Experience**
- Consistent, intuitive API design
- Extensive documentation and examples
- Active community support (Discord)
- Regular updates and maintenance
- Semantic versioning

</td>
</tr>
</table>

### Quick Example

```python
from xbbg import blp

# Reference data
prices = blp.bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST')

# Historical data
hist = blp.bdh('SPX Index', 'PX_LAST', '2024-01-01', '2024-12-31')

# Intraday bars with sub-minute precision
intraday = blp.bdib('TSLA US Equity', dt='2024-01-15', interval=10, intervalHasSeconds=True)
```

See [`examples/xbbg_jupyter_examples.ipynb`](examples/xbbg_jupyter_examples.ipynb) for comprehensive tutorials and examples.

## Why Choose xbbg?

xbbg is the **most complete and production-ready** Bloomberg API wrapper for Python, trusted by quantitative researchers and financial engineers worldwide. Here's what sets it apart:

### 🎯 Unmatched Feature Coverage

xbbg is the **only Python library** that provides:
- **Complete Bloomberg API access**: All major services (Reference, Historical, Intraday, Real-time, BQL, BEQS, BSRCH)
- **Sub-second precision**: Down to 10-second intraday bars (unique to xbbg)
- **Real-time streaming**: Live market data with async support
- **Advanced utilities**: Futures/CDX contract resolution, currency conversion, market hours

### 📊 Production-Grade Features

- **Intraday caching**: Automatic Parquet storage for `bdib()` bar data
- **Async/await support**: Non-blocking operations for modern Python applications
- **Exchange-aware sessions**: Precise market hour handling for 50+ global exchanges
- **Type safety**: Full type hints for IDE autocomplete and static analysis
- **Comprehensive error handling**: Clear, actionable error messages

### 💡 Developer Experience

- **Excel-compatible**: Use familiar Bloomberg Excel syntax - zero learning curve
- **Pythonic API**: Consistent, intuitive function names (`bdp`, `bdh`, `bdib`)
- **Rich documentation**: 100+ examples, Jupyter notebooks, comprehensive guides
- **Active community**: Discord support, regular updates, responsive maintainers

### 🚀 Performance & Reliability

- **Battle-tested**: Used in production by hedge funds, asset managers, and research teams
- **Modern Python**: Supports Python 3.10-3.14 with latest language features
- **CI/CD pipeline**: Automated testing across multiple Python versions and platforms
- **Semantic versioning**: Predictable releases with clear upgrade paths

### Comparison with Alternatives

| Feature | xbbg | pdblp | blp | polars-bloomberg |
|---------|------|-------|-----|------------------|
| **Data Services** | | | | |
| Reference Data (BDP/BDS) | ✅ | ✅ | ✅ | ✅ |
| Historical Data (BDH) | ✅ | ✅ | ✅ | ✅ |
| Intraday Bars (BDIB) | ✅ | ❌ | ❌ | ✅ |
| Tick-by-Tick Data | ✅ | ❌ | ❌ | ❌ |
| Real-time Subscriptions | ✅ | ❌ | ❌ | ❌ |
| **Advanced Features** | | | | |
| Equity Screening (BEQS) | ✅ | ❌ | ❌ | ❌ |
| Query Language (BQL) | ✅ | ❌ | ❌ | ✅ |
| Quote Request (BQR) | ✅ | ❌ | ❌ | ❌ |
| Search (BSRCH) | ✅ | ❌ | ❌ | ✅ |
| Technical Analysis (BTA) | ✅ | ❌ | ❌ | ❌ |
| Yield & Spread Analysis (YAS) | ✅ | ❌ | ❌ | ❌ |
| **Developer Features** | | | | |
| Excel-compatible syntax | ✅ | ❌ | ❌ | ❌ |
| Sub-minute intervals (10s bars) | ✅ | ❌ | ❌ | ❌ |
| Async/await support | ✅ | ❌ | ❌ | ❌ |
| Intraday bar caching (Parquet) | ✅ | ❌ | ❌ | ❌ |
| Multi-backend output | ✅ | ❌ | ❌ | ❌ |
| **Utilities** | | | | |
| Currency conversion | ✅ | ❌ | ❌ | ❌ |
| Futures contract resolution | ✅ | ❌ | ❌ | ❌ |
| CDX index resolution | ✅ | ❌ | ❌ | ❌ |
| Exchange market hours | ✅ | ❌ | ❌ | ❌ |
| **Project Health** | | | | |
| Active development | ✅ | ❌[^1] | ✅ | ✅ |
| Python version support | 3.10-3.14 | 3.8+ | 3.8+ | 3.12+ |
| DataFrame library | **Multi-backend** | pandas | pandas | Polars |
| Type hints | ✅ Full | ❌ | Partial | ✅ Full |
| CI/CD testing | ✅ | ❌ | ✅ | ✅ |

[^1]: pdblp has been superseded by blp and is no longer under active development.

**Bottom line**: If you need comprehensive Bloomberg API access with production-grade features, xbbg is the clear choice.

## Complete API Reference

### Reference Data - Point-in-Time Snapshots

| Function | Description | Key Features |
|----------|--------------|-------------|
| **`bdp()`** | Get current/reference data | Multiple tickers & fields<br>Excel-style overrides<br>ISIN/CUSIP/SEDOL support |
| **`bds()`** | Bulk/multi-row data | Portfolio holdings<br>Fixed income cash flows<br>Corporate actions |
| **`abdp()`** | Async reference data | Non-blocking operations<br>Concurrent requests<br>Web application friendly |
| **`abds()`** | Async bulk data | Parallel bulk queries<br>Same API as `bds()` |
| **`fieldInfo()`** | Field metadata lookup | Data types & descriptions<br>Discover available fields |
| **`fieldSearch()`** | Search Bloomberg fields | Find fields by keyword<br>Explore data catalog |
| **`lookupSecurity()`** | Find tickers by name | Company name search<br>Asset class filtering |
| **`getPortfolio()`** | Portfolio data queries | Dedicated portfolio API<br>Holdings & weights |

### Fixed Income Analytics

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`yas()`** | Yield & Spread Analysis | YAS calculator wrapper<br>YTM/YTC yield types<br>Price↔yield conversion<br>Spread calculations |

### Historical Data - Time Series Analysis

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`bdh()`** | End-of-day historical data | Flexible date ranges<br>Multiple frequencies<br>Dividend/split adjustments |
| **`abdh()`** | Async historical data | Non-blocking time series<br>Batch historical queries |
| **`dividend()`** | Dividend & split history | All dividend types<br>Projected dividends<br>Date range filtering |
| **`earning()`** | Corporate earnings | Geographic breakdowns<br>Product segments<br>Fiscal period analysis |
| **`turnover()`** | Trading volume & turnover | Multi-currency support<br>Automatic FX conversion |

### Intraday Data - High-Frequency Analysis

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`bdib()`** | Intraday bar data | Sub-minute bars (10s intervals)<br>Session filtering (open/close)<br>Exchange-aware timing |
| **`bdtick()`** | Tick-by-tick data | Trade & quote events<br>Condition codes<br>Exchange/broker details |

### Screening & Advanced Queries

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`beqs()`** | Bloomberg Equity Screening | Custom screening criteria<br>Private & public screens |
| **`bql()`** | Bloomberg Query Language | SQL-like syntax<br>Complex transformations<br>Options chain analysis |
| **`bqr()`** | Bloomberg Quote Request | Tick-level dealer quotes<br>Broker attribution codes<br>Date offset support (-2d, -1w) |
| **`bsrch()`** | SRCH (Search) queries | Fixed income searches<br>Commodity screens<br>Weather data |
| **`bta()`** | Technical Analysis | 50+ technical indicators<br>Custom studies |
| **`etf_holdings()`** | ETF holdings via BQL | Complete holdings list<br>Weights & positions |

### Real-Time - Live Market Data

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`live()`** | Real-time streaming | Async context manager<br>Auto-reconnection<br>Field-level updates |
| **`subscribe()`** | Real-time subscriptions | Event callbacks<br>Custom intervals<br>Multiple tickers |
| **`stream()`** | Async streaming | Modern async/await<br>Non-blocking updates |

### Utilities

| Function | Description | Key Features |
|----------|-------------|--------------|
| **`adjust_ccy()`** | Currency conversion | Multi-currency DataFrames<br>Historical FX rates<br>Automatic alignment |
| **`fut_ticker()`** | Futures contract resolution | Generic to specific mapping<br>Date-aware selection |
| **`active_futures()`** | Active futures selection | Volume-based logic<br>Roll date handling |
| **`cdx_ticker()`** | CDX index resolution | Series mapping<br>Index family support |
| **`active_cdx()`** | Active CDX selection | On-the-run detection<br>Lookback windows |

### Additional Features

- **Intraday Caching**: Automatic Parquet storage for `bdib()` bar data
- **Timezone Support**: Exchange-aware market hours for 50+ global exchanges
- **Configurable Logging**: Debug mode for troubleshooting
- **Batch Processing**: Efficient multi-ticker queries
- **Standardized Output**: Consistent DataFrame column naming

## Requirements

- **Bloomberg C++ SDK** version 3.12.1 or higher:
  - Visit [Bloomberg API Library](https://www.bloomberg.com/professional/support/api-library/) and download C++ Supported Release
  - In the `bin` folder of downloaded zip file, copy `blpapi3_32.dll` and `blpapi3_64.dll` to Bloomberg `BLPAPI_ROOT` folder (usually `blp/DAPI`)

- **Bloomberg official Python API**:

```cmd
pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
```

- **Python dependencies**: `numpy`, `pandas`, `narwhals`, `ruamel.yaml` and `pyarrow` (automatically installed)

- **Optional backends** (install separately if needed):
  - `polars` - For Polars DataFrame output
  - `duckdb` - For DuckDB relation output

## Installation

```cmd
pip install xbbg
```

Supported Python versions: **3.10 – 3.14** (universal wheel).

## Quickstart

### Basic Usage

```python
from xbbg import blp

# Get current stock prices
prices = blp.bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST')
print(prices)
```

### Common Workflows

<details>
<summary><b>📊 Get Reference Data (Current Snapshot)</b></summary>

```python
# Single ticker, multiple fields
info = blp.bdp('NVDA US Equity', ['Security_Name', 'GICS_Sector_Name', 'PX_LAST'])

# Multiple tickers, single field
prices = blp.bdp(['AAPL US Equity', 'MSFT US Equity', 'GOOGL US Equity'], 'PX_LAST')

# With overrides (e.g., VWAP for specific date)
vwap = blp.bdp('AAPL US Equity', 'Eqy_Weighted_Avg_Px', VWAP_Dt='20240115')
```

</details>

<details>
<summary><b>📈 Get Historical Data (Time Series)</b></summary>

```python
# Simple historical query
hist = blp.bdh('SPX Index', 'PX_LAST', '2024-01-01', '2024-12-31')

# Multiple fields
ohlc = blp.bdh('AAPL US Equity', ['open', 'high', 'low', 'close'], '2024-01-01', '2024-01-31')

# With dividend/split adjustments
adjusted = blp.bdh('AAPL US Equity', 'px_last', '2024-01-01', '2024-12-31', adjust='all')

# Weekly data with forward fill
weekly = blp.bdh('SPX Index', 'PX_LAST', '2024-01-01', '2024-12-31', Per='W', Fill='P')
```

</details>

<details>
<summary><b>⏱️ Get Intraday Data (High Frequency)</b></summary>

```python
# 5-minute bars
bars_5m = blp.bdib('SPY US Equity', dt='2024-01-15', interval=5)

# 1-minute bars (default)
bars_1m = blp.bdib('TSLA US Equity', dt='2024-01-15')

# Sub-minute bars (10-second intervals) - UNIQUE TO XBBG!
bars_10s = blp.bdib('AAPL US Equity', dt='2024-01-15', interval=10, intervalHasSeconds=True)

# Session filtering (e.g., first 30 minutes)
opening = blp.bdib('SPY US Equity', dt='2024-01-15', session='day_open_30')
```

</details>

<details>
<summary><b>🔍 Advanced Queries (BQL, Screening)</b></summary>

```python
# Bloomberg Query Language
result = blp.bql("get(px_last) for('AAPL US Equity')")

# Equity screening
screen_results = blp.beqs(screen='MyScreen', asof='2024-01-01')

# ETF holdings
holdings = blp.etf_holdings('SPY US Equity')

# Search queries
bonds = blp.bsrch("FI:MYSEARCH")

# Dealer quotes with broker codes (BQR)
quotes = blp.bqr("XYZ 4.5 01/15/30@MSG1 Corp", date_offset="-2d")
```

</details>

<details>
<summary><b>🔧 Utilities (Futures, Currency, etc.)</b></summary>

```python
# Resolve futures contract
contract = blp.fut_ticker('ES1 Index', '2024-01-15', freq='ME')  # → 'ESH24 Index'

# Get active futures
active = blp.active_futures('ESA Index', '2024-01-15')

# Currency conversion
hist_usd = blp.bdh('BMW GR Equity', 'PX_LAST', '2024-01-01', '2024-01-31')
hist_eur = blp.adjust_ccy(hist_usd, ccy='EUR')

# Dividend history
divs = blp.dividend('AAPL US Equity', start_date='2024-01-01', end_date='2024-12-31')
```

</details>

### Best Practices

- **Excel users**: Use the same field names and date formats as Bloomberg Excel
- **Performance**: `bdib()` caches intraday bars as Parquet files automatically (see [Data Storage](#data-storage))
- **Async operations**: Use `abdp()`, `abdh()`, `abds()` for non-blocking requests
- **Debugging**: Set `logging.getLogger('xbbg').setLevel(logging.DEBUG)` for detailed logs

### Connection Options

By default, xbbg connects to `localhost` on port `8194`. To connect to a remote Bloomberg server, use the `server` and `port` parameters:

```python
from xbbg import blp

# Connect to a remote Bloomberg server
kwargs = {'server': '192.168.1.100', 'port': 18194}
blp.bdp(tickers='NVDA US Equity', flds=['Security_Name'], **kwargs)
```

The `server` parameter (or `server_host`) can be passed through any function that accepts kwargs, just like the `port` parameter.

### Async Functions

Every sync function has an async counterpart prefixed with `a` — for example `bdp()` → `abdp()`, `bdh()` → `abdh()`, `bdib()` → `abdib()`. The async versions are the real implementations; the sync functions are thin wrappers.

#### In scripts (no existing event loop)

```python
import asyncio
from xbbg import blp

async def get_data():
    df = await blp.abdp(tickers='AAPL US Equity', flds=['PX_LAST', 'VOLUME'])
    return df

async def get_multiple():
    # Concurrent requests — runs in parallel on a single thread
    results = await asyncio.gather(
        blp.abdp(tickers='AAPL US Equity', flds=['PX_LAST']),
        blp.abdp(tickers='MSFT US Equity', flds=['PX_LAST']),
        blp.abdh(tickers='GOOGL US Equity', start_date='2024-01-01'),
    )
    return results

data = asyncio.run(get_data())
multiple = asyncio.run(get_multiple())
```

#### In Jupyter notebooks

Jupyter already runs an event loop, so `asyncio.run()` will raise `RuntimeError: asyncio.run() cannot be called from a running event loop`. Use `await` directly in notebook cells instead:

```python
from xbbg import blp

# Just await directly — Jupyter cells are already async
df = await blp.abdp(tickers='AAPL US Equity', flds=['PX_LAST', 'VOLUME'])

# Concurrent requests work the same way
import asyncio
results = await asyncio.gather(
    blp.abdp(tickers='AAPL US Equity', flds=['PX_LAST']),
    blp.abdp(tickers='MSFT US Equity', flds=['PX_LAST']),
)
```

> **Tip:** If you don't need async, the sync functions (`bdp`, `bdh`, `bdib`, etc.) work everywhere — scripts, notebooks, and async contexts — without any special handling.

**Benefits:**
- Non-blocking: doesn't block the event loop
- Concurrent: use `asyncio.gather()` for parallel requests
- Compatible: works with async web frameworks, Jupyter, and async codebases
- Same API: identical parameters to sync versions (`bdp`, `bds`, `bdh`)

### Multi-Backend Support

Starting with v0.11.0, xbbg is **DataFrame-library agnostic**. You can get output in your preferred format:

#### Supported Backends

| Backend | Type | Output | Best For |
|---------|------|--------|----------|
| **Eager Backends** ||||
| `pandas` | Eager | `pd.DataFrame` | Traditional workflows, compatibility |
| `polars` | Eager | `pl.DataFrame` | High performance, large datasets |
| `pyarrow` | Eager | `pa.Table` | Zero-copy interop, memory efficiency |
| `narwhals` | Eager | Narwhals DataFrame | Library-agnostic code |
| `modin` | Eager | Modin DataFrame | Pandas API with parallel execution |
| `cudf` | Eager | cuDF DataFrame | GPU-accelerated processing (NVIDIA) |
| **Lazy Backends** ||||
| `polars_lazy` | Lazy | `pl.LazyFrame` | Deferred execution, query optimization |
| `narwhals_lazy` | Lazy | Narwhals LazyFrame | Library-agnostic lazy evaluation |
| `duckdb` | Lazy | DuckDB relation | SQL analytics, OLAP queries |
| `dask` | Lazy | Dask DataFrame | Out-of-core and distributed computing |
| `ibis` | Lazy | Ibis Table | Unified interface to many backends |
| `pyspark` | Lazy | Spark DataFrame | Big data processing (requires Java) |
| `sqlframe` | Lazy | SQLFrame DataFrame | SQL-first DataFrame operations |

**Note:** Lazy backends only support `LONG` and `SEMI_LONG` output formats (not `WIDE`).

#### Check Backend Availability

```python
from xbbg import get_available_backends, print_backend_status, is_backend_available

# List installed backends
print(get_available_backends())  # ['pandas', 'polars', 'pyarrow', ...]

# Check if a specific backend is available
if is_backend_available('polars'):
    print("Polars is installed!")

# Print detailed status of all backends
print_backend_status()
```

#### Usage

```python
from xbbg import blp, Backend, Format

# Get data as Polars DataFrame
df_polars = blp.bdp('AAPL US Equity', 'PX_LAST', backend=Backend.POLARS)

# Get data as PyArrow Table
table = blp.bdh('SPX Index', 'PX_LAST', '2024-01-01', '2024-12-31', backend=Backend.PYARROW)

# Get data as pandas (default)
df_pandas = blp.bdp('MSFT US Equity', 'PX_LAST', backend=Backend.PANDAS)
```

#### Output Formats

Control the shape of your data with the `format` parameter:

| Format | Description | Use Case |
|--------|-------------|----------|
| `long` | Tidy format with ticker, field, value columns | Analysis, joins, aggregations |
| `semi_long` | One row per ticker, fields as columns | Quick inspection |
| `wide` | Tickers as columns (pandas only) | Time series alignment, Excel-like |

```python
from xbbg import blp, Format

# Long format (tidy data)
df_long = blp.bdp(['AAPL US Equity', 'MSFT US Equity'], ['PX_LAST', 'VOLUME'], format=Format.LONG)

# Wide format (Excel-like)
df_wide = blp.bdh('SPX Index', 'PX_LAST', '2024-01-01', '2024-12-31', format=Format.WIDE)
```

#### Global Configuration

Set defaults for your entire session:

```python
from xbbg import set_backend, set_format, Backend, Format

# Set Polars as default backend
set_backend(Backend.POLARS)

# Set long format as default
set_format(Format.LONG)

# All subsequent calls use these defaults
df = blp.bdp('AAPL US Equity', 'PX_LAST')  # Returns Polars DataFrame in long format
```

#### Why Multi-Backend?

- **Performance**: Polars and PyArrow can be 10-100x faster for large datasets
- **Memory**: Arrow-based backends use zero-copy and columnar storage
- **Interoperability**: Direct integration with DuckDB, Spark, and other Arrow-compatible tools
- **Future-proof**: Write library-agnostic code with narwhals backend

## Examples

### 📊 Reference Data

#### Equity and Index Securities

```python
from xbbg import blp

# Single point-in-time data (BDP)
blp.bdp(tickers='NVDA US Equity', flds=['Security_Name', 'GICS_Sector_Name'])
```

```pydocstring
Out[2]:
               security_name        gics_sector_name
NVDA US Equity   NVIDIA Corp  Information Technology
```

```python
# With field overrides
blp.bdp('AAPL US Equity', 'Eqy_Weighted_Avg_Px', VWAP_Dt='20181224')
```

```pydocstring
Out[3]:
                eqy_weighted_avg_px
AAPL US Equity               148.75
```

```python
# Multiple tickers and fields
blp.bdp(
    tickers=['AAPL US Equity', 'MSFT US Equity', 'GOOGL US Equity'],
    flds=['Security_Name', 'GICS_Sector_Name', 'PX_LAST']
)
```

```pydocstring
Out[3a]:
                  security_name        gics_sector_name px_last
AAPL US Equity        Company A  Information Technology  150.25
GOOGL US Equity    Company B  Communication Services  165.30
MSFT US Equity   Company C  Information Technology  180.45
```

```python
# Bulk/block data (BDS) - multi-row per ticker
blp.bds('AAPL US Equity', 'DVD_Hist_All', DVD_Start_Dt='20180101', DVD_End_Dt='20180531')
```

```pydocstring
Out[8]:
               declared_date     ex_date record_date payable_date  dividend_amount dividend_frequency dividend_type
AAPL US Equity    2018-05-01  2018-05-11  2018-05-14   2018-05-17             0.73            Quarter  Regular Cash
AAPL US Equity    2018-02-01  2018-02-09  2018-02-12   2018-02-15             0.63            Quarter  Regular Cash
```

#### Fixed Income Securities

xbbg supports fixed income securities using standard security identifiers (ISIN, CUSIP, SEDOL). Use the `/isin/{isin}`, `/cusip/{cusip}`, or `/sedol/{sedol}` format as the ticker:

```python
# Reference data using ISIN
blp.bdp(tickers='/isin/US1234567890', flds=['SECURITY_NAME', 'MATURITY', 'COUPON', 'PX_LAST'])
```

```pydocstring
Out[9]:
                       security_name    maturity coupon    px_last
/isin/US1234567890  US Treasury Note  2035-05-15   4.25  101.25
```

```python
# Cash flow schedule using ISIN
blp.bds(tickers='/isin/US1234567890', flds='DES_CASH_FLOW')
```

```pydocstring
Out[10]:
                   payment_date  coupon_amount  principal_amount
/isin/US1234567890   2026-05-15        21250.0               0.0
/isin/US1234567890   2026-11-15        21250.0               0.0
/isin/US1234567890   2027-05-15        21250.0               0.0
```

**Note:** Fixed income securities work with `bdp()`, `bds()`, and `bdh()` functions. The identifier format (`/isin/`, `/cusip/`, `/sedol/`) is automatically passed to blpapi.

#### Yield & Spread Analysis (YAS)

The `yas()` function provides a convenient wrapper for Bloomberg's YAS calculator:

```python
from xbbg import blp
from xbbg.api.fixed_income import YieldType

# Get yield to maturity
blp.yas('T 4.5 05/15/38 Govt')
```

```pydocstring
Out[11]:
                     YAS_BOND_YLD
ticker
T 4.5 05/15/38 Govt         4.348
```

```python
# Calculate yield from price
blp.yas('T 4.5 05/15/38 Govt', price=95.0)
```

```pydocstring
Out[12]:
                     YAS_BOND_YLD
ticker
T 4.5 05/15/38 Govt          5.05
```

```python
# Calculate price from yield
blp.yas('T 4.5 05/15/38 Govt', flds='YAS_BOND_PX', yield_=4.8)
```

```pydocstring
Out[13]:
                     YAS_BOND_PX
ticker
T 4.5 05/15/38 Govt    97.229553
```

```python
# Yield to call for callable bonds
blp.yas('AAPL 2.65 05/11/50 Corp', yield_type=YieldType.YTC)
```

```pydocstring
Out[14]:
                          YAS_BOND_YLD
ticker
AAPL 2.65 05/11/50 Corp          5.431
```

```python
# Multiple YAS analytics
blp.yas('T 4.5 05/15/38 Govt', ['YAS_BOND_YLD', 'YAS_MOD_DUR', 'YAS_ASW_SPREAD'])
```

```pydocstring
Out[15]:
                     YAS_ASW_SPREAD  YAS_BOND_YLD  YAS_MOD_DUR
ticker
T 4.5 05/15/38 Govt       33.093531         4.348     9.324928
```

**Available parameters:**
- `settle_dt`: Settlement date (YYYYMMDD or datetime)
- `yield_type`: `YieldType.YTM` (default) or `YieldType.YTC`
- `price`: Input price to calculate yield
- `yield_`: Input yield to calculate price
- `spread`: Spread to benchmark in basis points
- `benchmark`: Benchmark bond ticker for spread calculations

#### Field Information and Search

```python
# Get metadata about fields
blp.fieldInfo(['PX_LAST', 'VOLUME'])
```

```python
# Search for fields by name or description
blp.fieldSearch('vwap')
```

#### Security Lookup

```python
# Look up securities by company name
blp.lookupSecurity('IBM', max_results=10)
```

```python
# Lookup with asset class filter
blp.lookupSecurity('Apple', yellowkey='eqty', max_results=20)
```

#### Portfolio Data

```python
# Get portfolio data (dedicated function)
blp.getPortfolio('PORTFOLIO_NAME', 'PORTFOLIO_MWEIGHT')
```

### 📈 Historical Data

```python
# End-of-day historical data (BDH)
blp.bdh(
    tickers='SPX Index', flds=['high', 'low', 'last_price'],
    start_date='2018-10-10', end_date='2018-10-20',
)
```

```pydocstring
Out[4]:
           SPX Index
                high      low last_price
2018-10-10  2,874.02 2,784.86   2,785.68
2018-10-11  2,795.14 2,710.51   2,728.37
2018-10-12  2,775.77 2,729.44   2,767.13
2018-10-15  2,775.99 2,749.03   2,750.79
2018-10-16  2,813.46 2,766.91   2,809.92
2018-10-17  2,816.94 2,781.81   2,809.21
2018-10-18  2,806.04 2,755.18   2,768.78
2018-10-19  2,797.77 2,760.27   2,767.78
```

```python
# Multiple tickers and fields
blp.bdh(
    tickers=['AAPL US Equity', 'MSFT US Equity'],
    flds=['px_last', 'volume'],
    start_date='2024-01-01', end_date='2024-01-10',
)
```

```pydocstring
Out[4a]:
           AAPL US Equity             MSFT US Equity            
                  px_last      volume        px_last      volume
2024-01-02         150.25  45000000.0         180.45  25000000.0
2024-01-03         151.30  42000000.0         181.20  23000000.0
2024-01-04         149.80  48000000.0         179.90  24000000.0
2024-01-05         150.10  44000000.0         180.15  22000000.0
2024-01-08         151.50  46000000.0         181.80  26000000.0
```

```python
# Excel-compatible inputs with periodicity
blp.bdh(
    tickers='SHCOMP Index', flds=['high', 'low', 'last_price'],
    start_date='2018-09-26', end_date='2018-10-20',
    Per='W', Fill='P', Days='A',
)
```

```pydocstring
Out[5]:
           SHCOMP Index
                   high      low last_price
2018-09-28     2,827.34 2,771.16   2,821.35
2018-10-05     2,827.34 2,771.16   2,821.35
2018-10-12     2,771.94 2,536.66   2,606.91
2018-10-19     2,611.97 2,449.20   2,550.47
```

```python
# Dividend/split adjustments
blp.bdh('AAPL US Equity', 'px_last', '20140606', '20140609', adjust='all')
```

```pydocstring
Out[15]:
           AAPL US Equity
                  px_last
2014-06-06          85.22
2014-06-09          86.58
```

```python
# Dividend history
blp.dividend(['C US Equity', 'MS US Equity'], start_date='2018-01-01', end_date='2018-05-01')
```

```pydocstring
Out[13]:
                dec_date     ex_date    rec_date    pay_date  dvd_amt dvd_freq      dvd_type
C US Equity   2018-01-18  2018-02-02  2018-02-05  2018-02-23     0.32  Quarter  Regular Cash
MS US Equity  2018-04-18  2018-04-27  2018-04-30  2018-05-15     0.25  Quarter  Regular Cash
MS US Equity  2018-01-18  2018-01-30  2018-01-31  2018-02-15     0.25  Quarter  Regular Cash
```

```python
# Earnings breakdowns
blp.earning('AMD US Equity', by='Geo', Eqy_Fund_Year=2017, Number_Of_Periods=1)
```

```pydocstring
Out[12]:
                 level    fy2017  fy2017_pct
Asia-Pacific      1.00  3,540.00       66.43
    China         2.00  1,747.00       49.35
    Japan         2.00  1,242.00       35.08
    Singapore     2.00    551.00       15.56
United States     1.00  1,364.00       25.60
Europe            1.00    263.00        4.94
Other Countries   1.00    162.00        3.04
```

### ⏱️ Intraday Data

```python
# Intraday bars (1-minute default)
blp.bdib(ticker='BHP AU Equity', dt='2018-10-17').tail()
```

```pydocstring
Out[9]:
                          BHP AU Equity
                                   open  high   low close   volume num_trds
2018-10-17 15:56:00+11:00         33.62 33.65 33.62 33.64    16660      126
2018-10-17 15:57:00+11:00         33.65 33.65 33.63 33.64    13875      156
2018-10-17 15:58:00+11:00         33.64 33.65 33.62 33.63    16244      159
2018-10-17 15:59:00+11:00         33.63 33.63 33.61 33.62    16507      167
2018-10-17 16:10:00+11:00         33.66 33.66 33.66 33.66  1115523      216
```

**Selecting bar intervals:**

- **Minute-based intervals** (default): Use the `interval` parameter to specify minutes.
  By default, `interval=1` (1-minute bars). Common intervals:
  - `interval=5` → 5-minute bars
  - `interval=15` → 15-minute bars
  - `interval=30` → 30-minute bars
  - `interval=60` → 1-hour bars

```python
# 5-minute bars
blp.bdib(ticker='AAPL US Equity', dt='2025-11-12', interval=5).head()

# 15-minute bars
blp.bdib(ticker='AAPL US Equity', dt='2025-11-12', interval=15).head()
```

- **Sub-minute intervals** (seconds): Set `intervalHasSeconds=True` and specify seconds:

```python
# 10-second bars
blp.bdib(ticker='AAPL US Equity', dt='2025-11-12', interval=10, intervalHasSeconds=True).head()
```

```pydocstring
Out[9a]:
                          AAPL US Equity
                                   open    high     low   close volume num_trds
2025-11-12 09:31:00-05:00        150.25  150.35  150.20  150.30  25000      150
2025-11-12 09:31:10-05:00        150.30  150.40  150.25  150.35  18000      120
2025-11-12 09:31:20-05:00        150.35  150.45  150.30  150.40  22000      135
```

**Note:** By default, `interval` is interpreted as **minutes**. Set `intervalHasSeconds=True` to use seconds-based intervals.

```python
# Market session filtering
blp.bdib(ticker='7974 JT Equity', dt='2018-10-17', session='am_open_30').tail()
```

```pydocstring
Out[11]:
                          7974 JT Equity
                                    open      high       low     close volume num_trds
2018-10-17 09:27:00+09:00      39,970.00 40,020.00 39,970.00 39,990.00  10800       44
2018-10-17 09:28:00+09:00      39,990.00 40,020.00 39,980.00 39,980.00   6300       33
2018-10-17 09:29:00+09:00      39,970.00 40,000.00 39,960.00 39,970.00   3300       21
2018-10-17 09:30:00+09:00      39,960.00 40,010.00 39,950.00 40,000.00   3100       19
2018-10-17 09:31:00+09:00      39,990.00 40,000.00 39,980.00 39,990.00   2000       15
```

#### How the `session` parameter works

The `session` parameter is resolved by `xbbg.core.config.intervals.get_interval()`
and `xbbg.core.process.time_range()` using exchange metadata from
`xbbg/markets/config/exch.yml`:

- **Base sessions** (no underscores) map directly to session windows defined
  for the ticker's exchange in `exch.yml`:
  - `allday` - Full trading day including pre/post market (e.g., `[400, 2000]` for US equities)
  - `day` - Regular trading hours (e.g., `[0930, 1600]` for US equities)
  - `am` - Morning session (e.g., `[901, 1130]` for Japanese equities)
  - `pm` - Afternoon session (e.g., `[1230, 1458]` for Japanese equities)
  - `pre` - Pre-market session (e.g., `[400, 0930]` for US equities)
  - `post` - Post-market session (e.g., `[1601, 2000]` for US equities)
  - `night` - Night trading session (e.g., `[1710, 700]` for Australian futures)
  
  Not all exchanges define all sessions. For example, `GBP Curncy` uses
  `CurrencyGeneric` which defines `allday` and `day` only.

- **Compound sessions** (with underscores) allow finer control by combining
  a base session with modifiers (`open`, `close`, `normal`, `exact`):
  - **Open windows** (first N minutes of a session):
    - `day_open_30` → first 30 minutes of the `day` session
    - `am_open_30` → first 30 minutes of the `am` session
    - Note: `open` is not a base session; use `day_open_30`, not `open_30`
  - **Close windows** (last N minutes of a session):
    - `day_close_20` → last 20 minutes of the `day` session
    - `am_close_30` → last 30 minutes of the `am` session
    - Note: `close` is not a base session; use `day_close_20`, not `close_20`
  - **Normal windows** (skip open/close buffers):
    - `day_normal_30_20` → skips first 30 min and last 20 min of `day`
    - `am_normal_30_30` → skips first 30 min and last 30 min of `am`
  - **Exact clock times** (exchange-local HHMM format):
    - `day_exact_2130_2230` → [21:30, 22:30] local time (marker session)
    - `allday_exact_2130_2230` → [21:30, 22:30] local time (actual window)
    - `allday_exact_2130_0230` → [21:30, 02:30 next day] local time

- **Resolution order and fallbacks**:
  - `blp.bdib` / `blp.bdtick` call `time_range()`, which:
    1. Uses `exch.yml` + `get_interval()` and `const.exch_info()` to resolve
       local session times and exchange timezone.
    2. Converts that window to UTC and then to your requested `tz` argument
       (e.g., `'UTC'`, `'NY'`, `'Europe/London'`).
    3. If exchange metadata is missing for `session` and the asset, it may
       fall back to pandas‑market‑calendars (PMC) for simple sessions
       (`'day'` / `'allday'`), based on the exchange code.

- **Errors and diagnostics**:
  - If a `session` name is not defined for the ticker's exchange,
    `get_interval()` raises a `ValueError` listing the available sessions
    for that exchange and points to `xbbg/markets/exch.yml`.
  - For compound sessions whose base session doesn't exist (e.g. mis-typed
    `am_open_30` for an exchange that has no `am` section), `get_interval()`
    returns `SessNA` and `time_range()` will then try the PMC fallback or
    ultimately raise a clear `ValueError`.

In practice:

- Use simple names like `session='day'` or `session='allday'` when you just
  want the main trading hours.
- Use compound names like `session='day_open_30'` or `session='am_normal_30_30'`
  when you need to focus on opening/closing auctions or to exclude "micro"
  windows (e.g. the first X minutes).
- If you add or customize sessions, update `exch.yml` and rely on
  `get_interval()` to pick them up automatically.

```python
# Using reference exchange for market hours
blp.bdib(ticker='ESM0 Index', dt='2020-03-20', ref='ES1 Index').tail()
```

```pydocstring
out[10]:
                          ESM0 Index
                                open     high      low    close volume num_trds        value
2020-03-20 16:55:00-04:00   2,260.75 2,262.25 2,260.50 2,262.00    412      157   931,767.00
2020-03-20 16:56:00-04:00   2,262.25 2,267.00 2,261.50 2,266.75    812      209 1,838,823.50
2020-03-20 16:57:00-04:00   2,266.75 2,270.00 2,264.50 2,269.00   1136      340 2,576,590.25
2020-03-20 16:58:00-04:00   2,269.25 2,269.50 2,261.25 2,265.75   1077      408 2,439,276.00
2020-03-20 16:59:00-04:00   2,265.25 2,272.00 2,265.00 2,266.50   1271      378 2,882,978.25
```

```python
# Tick-by-tick data with event types and condition codes
blp.bdtick(ticker='XYZ US Equity', dt='2024-10-15', session='day', types=['TRADE']).head()
```

```pydocstring
Out[12]:
                          XYZ US Equity
                                   volume    typ   cond exch            trd_time
2024-10-15 09:30:15-04:00           1500  TRADE     @  NYSE  2024-10-15 09:30:15
2024-10-15 09:30:23-04:00            800  TRADE     @  NYSE  2024-10-15 09:30:23
2024-10-15 09:30:31-04:00           2200  TRADE     @  NYSE  2024-10-15 09:30:31
```

```python
# Tick data with timeout (useful for large requests)
blp.bdtick(ticker='XYZ US Equity', dt='2024-10-15', session='day', timeout=1000)
```

Note: `bdtick` requests can take longer to respond. Use `timeout` parameter (in milliseconds) if you encounter empty DataFrames due to timeout.

```python
# Trading volume & turnover (currency-adjusted, in millions)
blp.turnover(['ABC US Equity', 'DEF US Equity'], start_date='2024-01-01', end_date='2024-01-10', ccy='USD')
```

```pydocstring
Out[13]:
            ABC US Equity  DEF US Equity
2024-01-02        15,304        8,920
2024-01-03        18,450       12,340
2024-01-04        14,890        9,560
2024-01-05        16,720       11,230
2024-01-08        10,905        7,890
```

```python
# Currency conversion for historical data
hist = blp.bdh(['GHI US Equity'], ['px_last'], '2024-01-01', '2024-01-10')
blp.adjust_ccy(hist, ccy='EUR')
```

```pydocstring
Out[14]:
            GHI US Equity
2024-01-02        169.66
2024-01-03        171.23
2024-01-04        170.45
2024-01-05        172.10
2024-01-08        169.46
```

### 🔍 Screening & Queries

```python
# Bloomberg Query Language (BQL)
# IMPORTANT: The 'for' clause must be OUTSIDE get(), not inside
# Correct: get(px_last) for('AAPL US Equity')
# Incorrect: get(px_last for('AAPL US Equity'))
# blp.bql("get(px_last) for('AAPL US Equity')")  # doctest: +SKIP

# BQL Options query example - sum open interest
# blp.bql("get(sum(group(open_int))) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))")  # doctest: +SKIP

# BQL Options metadata - get available expiries
# blp.bql("get(expire_dt) for(options('INDEX Ticker'))")  # doctest: +SKIP

# BQL Options metadata - get option tickers for an underlying
# blp.bql("get(id) for(options('INDEX Ticker'))")  # doctest: +SKIP

# BQL Options metadata - get option chain (expiry, strike, put/call)
# blp.bql("get(id, expire_dt, strike_px, PUT_CALL) for(filter(options('INDEX Ticker'), expire_dt=='YYYY-MM-DD'))")  # doctest: +SKIP

# ETF Holdings (BQL)
# blp.etf_holdings('SPY US Equity')  # doctest: +SKIP
# Returns:
#               holding       id_isin SOURCE POSITION_TYPE  weights  position
# 0     MSFT US Equity  US5949181045    ETF             L   0.0725   123456.0
# 1     AAPL US Equity  US0378331005    ETF             L   0.0685   112233.0
# 2     NVDA US Equity  US67066G1040    ETF             L   0.0450    88776.0

# Bloomberg Equity Screening (BEQS)
# blp.beqs(screen='MyScreen', asof='2023-01-01')  # doctest: +SKIP

# SRCH (Search) - Fixed Income example
# blp.bsrch("FI:YOURSRCH")  # doctest: +SKIP
```

```pydocstring
Out[16]:
              id
0  !!ABC123 Mtge
1  !!DEF456 Mtge
2  !!GHI789 Mtge
3  !!JKL012 Mtge
4  !!MNO345 Mtge
```

```python
# SRCH - Weather data with parameters
blp.bsrch(  # doctest: +SKIP
    "comdty:weather",
    overrides={
        "provider": "wsi",
        "location": "US_XX",
        "model": "ACTUALS",
        "frequency": "DAILY",
        "target_start_date": "2021-01-01",
        "target_end_date": "2021-01-05",
        "location_time": "false",
        "fields": "WIND_SPEED|TEMPERATURE|HDD_65F|CDD_65F|HDD_18C|CDD_18C|PRECIPITATION_24HR|CLOUD_COVER|FEELS_LIKE_TEMPERATURE|MSL_PRESSURE|TEMPERATURE_MAX_24HR|TEMPERATURE_MIN_24HR"
    }
)
```

```pydocstring
Out[17]:
              Reported Time  Wind Speed (m/s)  Temperature (°C)  Heating Degree Days (°F)  Cooling Degree Days (°F)
0 2021-01-01 06:00:00+00:00              3.45              -2.15                   38.25                     0.0
1 2021-01-02 06:00:00+00:00              2.10              -1.85                   36.50                     0.0
2 2021-01-03 06:00:00+00:00              1.95              -2.30                   37.80                     0.0
3 2021-01-04 06:00:00+00:00              2.40              -2.65                   38.10                     0.0
4 2021-01-05 06:00:00+00:00              2.15              -1.20                   35.75                     0.0
```

**Note:** The `bsrch()` function uses the blpapi Excel service (`//blp/exrsvc`) and supports user-defined SRCH screens, commodity screens, and blpapi example screens. For weather data and other specialized searches, use the `overrides` parameter to pass search-specific parameters.

```python
# Bloomberg Quote Request (BQR) - Dealer quotes with broker codes
# Emulates Excel =BQR() function for fixed income dealer quotes

# Get quotes from last 2 days with broker attribution
# blp.bqr("XYZ 4.5 01/15/30@MSG1 Corp", date_offset="-2d")  # doctest: +SKIP

# Using ISIN with MSG1 pricing source
# blp.bqr("/isin/US123456789@MSG1", date_offset="-2d")  # doctest: +SKIP

# With explicit date range
# blp.bqr("XYZ 4.5 01/15/30@MSG1 Corp", start_date="2024-01-15", end_date="2024-01-17")  # doctest: +SKIP

# Get only trade events
# blp.bqr("XYZ 4.5 01/15/30@MSG1 Corp", date_offset="-1d", event_types=["TRADE"])  # doctest: +SKIP
```

```pydocstring
Out[18]:
                              ticker                 time event_type   price   size broker_buy broker_sell
0  XYZ 4.5 01/15/30@MSG1 Corp  2024-01-15 10:30:00        BID   98.75  10000       DLRA         NaN
1  XYZ 4.5 01/15/30@MSG1 Corp  2024-01-15 10:30:05        ASK   99.00   5000        NaN        DLRB
2  XYZ 4.5 01/15/30@MSG1 Corp  2024-01-15 11:45:00      TRADE   98.85   2500       DLRC        DLRC
```

**Note:** The `bqr()` function emulates Bloomberg Excel's `=BQR()` formula. Use the `@MSG1` pricing source suffix to get dealer-level quote attribution. The `broker_buy` and `broker_sell` columns identify the contributing dealers (4-character codes).

### 📡 Real-time

```python
# Real-time market data streaming
# with blp.live(['AAPL US Equity'], ['LAST_PRICE']) as stream:  # doctest: +SKIP
#     for update in stream:  # doctest: +SKIP
#         print(update)  # doctest: +SKIP

# Real-time subscriptions
# blp.subscribe(['AAPL US Equity'], ['LAST_PRICE'], callback=my_handler)  # doctest: +SKIP

# Subscribe with 10-second update interval
# blp.subscribe(['AAPL US Equity'], interval=10)  # doctest: +SKIP
```

### 🔧 Utilities

```python
# Futures ticker resolution (generic to specific contract)
blp.fut_ticker('ES1 Index', '2024-01-15', freq='ME')
```

```pydocstring
Out[15]:
'ESH24 Index'
```

```python
# Active futures contract selection (volume-based)
blp.active_futures('ESA Index', '2024-01-15')
```

```pydocstring
Out[16]:
'ESH24 Index'
```

```python
# CDX index ticker resolution (series mapping)
blp.cdx_ticker('CDX IG CDSI GEN 5Y Corp', '2024-01-15')
```

```pydocstring
Out[17]:
'CDX IG CDSI S45 5Y Corp'
```

```python
# Active CDX contract selection
blp.active_cdx('CDX IG CDSI GEN 5Y Corp', '2024-01-15', lookback_days=10)
```

```pydocstring
Out[18]:
'CDX IG CDSI S45 5Y Corp'
```

## Data Storage

### What gets cached

Currently, only **`bdib()` intraday bar data** is cached as local Parquet files. Other functions (`bdp`, `bds`, `bdh`, `bql`, `beqs`, `bsrch`, `bta`, `bqr`) always make live Bloomberg API calls — they are not cached.

When `bdib()` fetches intraday bars, it will:

1. **Check the cache first** — if a Parquet file exists for that ticker/date/interval, return it instead of calling Bloomberg.
2. **Save results to cache** — after a successful Bloomberg fetch, save the bars as a Parquet file (only once the trading session has ended, to avoid saving incomplete data).

Exchange metadata (timezone, session hours) is also cached locally to avoid repeated lookups.

### Cache location

By default, xbbg uses a platform-specific cache directory:

| Platform | Default location |
|----------|-----------------|
| Windows | `%APPDATA%\xbbg` |
| Linux/macOS | `~/.cache/xbbg` or `~/.xbbg` |

To use a custom location, set `BBG_ROOT` before importing xbbg:

```python
import os
os.environ['BBG_ROOT'] = '/path/to/your/cache/directory'
```

### Cache structure

Intraday bar files are organized as:

```
{BBG_ROOT}/{asset_class}/{ticker}/{event_type}/{interval}/{date}.parq
```

For example, 1-minute TRADE bars for AAPL on 2024-01-15:

```
/path/to/cache/Equity/AAPL US Equity/TRADE/1m/2024-01-15.parq
```

### Controlling cache behavior

```python
# Disable cache for a specific call (always fetch from Bloomberg)
blp.bdib('AAPL US Equity', dt='2024-01-15', cache=False)

# Force reload (fetch from Bloomberg even if cached, then overwrite cache)
blp.bdib('AAPL US Equity', dt='2024-01-15', reload=True)
```

### Bloomberg data license compliance

Local data usage must be compliant with the Bloomberg Datafeed Addendum (see `DAPI<GO>`):

> To access Bloomberg data via the API (and use that data in Microsoft Excel), your company must sign the 'Datafeed Addendum' to the Bloomberg Agreement. This legally binding contract describes the terms and conditions of your use of the data and information available via the API (the "Data"). The most fundamental requirement regarding your use of Data is that it cannot leave the local PC you use to access the BLOOMBERG PROFESSIONAL service.

## 🔧 Troubleshooting

<details>
<summary><b>❌ Empty DataFrame Returned</b></summary>

**Possible causes:**
- ✅ Bloomberg Terminal not running → Start Bloomberg Terminal
- ✅ Wrong ticker format → Use `'AAPL US Equity'` not `'AAPL'`
- ✅ Data not available for date/time → Check Bloomberg Terminal
- ✅ Timeout too short → Increase: `blp.bdtick(..., timeout=1000)`

**Quick fix:**
```python
# Verify ticker exists
blp.lookupSecurity('Apple', yellowkey='eqty')

# Check field availability
blp.fieldSearch('price')
```

</details>

<details>
<summary><b>🔌 Connection Errors</b></summary>

**Checklist:**
- ✅ Bloomberg Terminal is running and logged in
- ✅ Default connection is `localhost:8194`
- ✅ For remote: `blp.bdp(..., server='192.168.1.100', port=18194)`
- ✅ Bloomberg API (blpapi) is installed

**Test connection:**
```python
from xbbg import blp
blp.bdp('AAPL US Equity', 'PX_LAST')  # Should return data
```

</details>

<details>
<summary><b>⏱️ Timeout Errors</b></summary>

**Solutions:**
```python
# Increase timeout (milliseconds)
blp.bdtick('AAPL US Equity', dt='2024-01-15', timeout=5000)

# Break large requests into chunks
dates = pd.date_range('2024-01-01', '2024-12-31', freq='MS')
chunks = [blp.bdh('SPX Index', 'PX_LAST', start, end) for start, end in zip(dates[:-1], dates[1:])]
result = pd.concat(chunks)
```

</details>

<details>
<summary><b>🔍 Field Not Found</b></summary>

**Find the right field:**
```python
# Search for fields
blp.fieldSearch('vwap')  # Find VWAP-related fields

# Get field info
blp.fieldInfo(['PX_LAST', 'VOLUME'])  # See data types & descriptions

# Check in Bloomberg Terminal
# Type FLDS<GO> to browse all fields
```

</details>

<details>
<summary><b>🐛 Still Stuck?</b></summary>

**Get help fast:**
- 💬 **Discord**: [Join our community](https://discord.gg/fUUy2nfzxM) - Usually get answers within hours
- 🐛 **GitHub Issues**: [Report bugs](https://github.com/alpha-xone/xbbg/issues) - Include error messages & code
- 📚 **Documentation**: [ReadTheDocs](https://xbbg.readthedocs.io/) - Comprehensive guides
- 📓 **Examples**: [`xbbg_jupyter_examples.ipynb`](examples/xbbg_jupyter_examples.ipynb) - 100+ working examples

**When reporting issues, include:**
1. xbbg version: `import xbbg; print(xbbg.__version__)`
2. Python version: `python --version`
3. Error message (full traceback)
4. Minimal code to reproduce

</details>

## Development

### Setup

Create venv and install dependencies:

```cmd
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync --locked --extra dev --extra test
```

### Adding Dependencies

```cmd
uv add <package>
```

### Running Tests and Linting

```cmd
uv run ruff check xbbg
uv run pytest --doctest-modules --cov -v xbbg
```

### Building

```cmd
uv run python -m build
```

Publishing is handled via GitHub Actions using PyPI Trusted Publishing (OIDC).

### Documentation

```cmd
uv sync --locked --extra docs
uv run sphinx-build -b html docs docs/_build/html
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Setting up your development environment
- Code style and standards
- Testing requirements
- Pull request process
- Community guidelines

Quick start for contributors:

```cmd
# Fork and clone the repository
git clone https://github.com/YOUR-USERNAME/xbbg.git
cd xbbg

# Set up development environment
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync --locked --extra dev --extra test

# Run tests and linting
uv run ruff check xbbg
uv run pytest --doctest-modules -q
```

## Getting Help

### Community Support

- **Discord**: [Join our community](https://discord.gg/fUUy2nfzxM) for discussions, questions, and help
- **GitHub Issues**: [Report bugs or request features](https://github.com/alpha-xone/xbbg/issues)
- **GitHub Discussions**: Share ideas and ask questions

### Resources

- **Documentation**: [ReadTheDocs](https://xbbg.readthedocs.io/)
- **Examples**: [`examples/xbbg_jupyter_examples.ipynb`](examples/xbbg_jupyter_examples.ipynb)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Security**: [SECURITY.md](SECURITY.md)

## Links

- [PyPI Package](https://pypi.org/project/xbbg/)
- [Documentation](https://xbbg.readthedocs.io/)
- [Source Code](https://github.com/alpha-xone/xbbg)
- [Issue Tracker](https://github.com/alpha-xone/xbbg/issues)
- [Discord Community](https://discord.gg/fUUy2nfzxM)
- [Changelog](CHANGELOG.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=alpha-xone/xbbg&type=Date)](https://star-history.com/#alpha-xone/xbbg&Date)

## Project Status

| Category       | Badge                                                                                                                                    |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Docs           | [![Documentation Status](https://readthedocs.org/projects/xbbg/badge/?version=latest)](https://xbbg.readthedocs.io/)                    |
| Build          | [![Actions Status](https://github.com/alpha-xone/xbbg/workflows/Auto%20CI/badge.svg)](https://github.com/alpha-xone/xbbg/actions)       |
| Coverage       | [![codecov](https://codecov.io/gh/alpha-xone/xbbg/branch/main/graph/badge.svg)](https://codecov.io/gh/alpha-xone/xbbg)                  |
| Quality        | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/daec9f52ba344e3ea116c15f1fc6d541)](https://www.codacy.com/gh/alpha-xone/xbbg/) |
|                | [![CodeFactor](https://www.codefactor.io/repository/github/alpha-xone/xbbg/badge)](https://www.codefactor.io/repository/github/alpha-xone/xbbg) |
| License        | [![GitHub license](https://img.shields.io/github/license/alpha-xone/xbbg.svg)](https://github.com/alpha-xone/xbbg/blob/main/LICENSE)   |

_0.11.0b1_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b1)

## v0.11.0b1 - Beta Release

### Highlights

- **Arrow-first pipeline**: Complete rewrite of data processing using PyArrow internally

- **Multi-backend support**: New Backend enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb

- **Output format control**: New Format enum with long, semi_long, wide options

- **Bloomberg Technical Analysis (BTA)**: New `bta()` function for technical indicators

- **v1.0 migration infrastructure**: Deprecation warnings and forward-compatible APIs

### Added

- `Backend` and `Format` enums for output control

- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` functions

- `bta()` function for Bloomberg Technical Analysis

- `get_sdk_info()` as replacement for `getBlpapiVersion()`

- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, etc.)

- `EngineConfig` dataclass and `configure()` function

- `Service` and `Operation` enums for Bloomberg services

### Changed

- All API functions now support `backend` and `format` parameters

- Internal pipeline uses PyArrow tables with narwhals transformations

- Removed pytz dependency (using stdlib datetime.timezone)

### Deprecated

- `connect()` / `disconnect()` - engine auto-initializes in v1.0

- `getBlpapiVersion()` - use `get_sdk_info()`

- `lookupSecurity()` - will become `blkp()` in v1.0

- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0

This is a **beta release** for testing the new Arrow-first architecture before v1.0.

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0b1

_0.11.0b3_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b3)

v0.11.0b3

- bqr(): New Bloomberg Quote Request function emulating Excel =BQR() for dealer quote data with broker attribution (#22)

- Slow Bloomberg fields no longer timeout prematurely - TIMEOUT events handled correctly (#193)

- Pipeline data types: Preserve original data types in pipeline output instead of converting to strings (#191)

_0.11.0b4_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b4)

### Added

- **yas()**: New Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics
  - Provides convenient interface to Bloomberg's YAS calculator via `bdp()` overrides
  - `YieldType` enum for yield calculation type (`YTM=1`, `YTC=2`)
  - Supports settlement date, spread, yield, price, and benchmark overrides
  - Parameter mapping: `settle_dt` → `SETTLE_DT`, `yield_type` → `YAS_YLD_FLAG`, etc.
  - Available via `blp.yas()` or `from xbbg.api.fixed_income import yas, YieldType`

- **Treasury & SOFR futures support**: Added TY, ZN, ZB, ZF, ZT, UB, TN (Treasury), SFR, SR1, SR3 (SOFR), and ED (Eurodollar) futures to assets.yml (#198)

### Fixed

- **stream() field values**: Subscribed field values are now always included in output dict (#199)
  - Previously, fields not in `const.LIVE_INFO` (like `RT_BN_SURVEY_MEDIAN`) were filtered out
  - Output would show `FIELD='RT_BN_SURVEY_MEDIAN'` but contain `LAST_PRICE` value instead
  - Fix ensures the subscribed field's value is always present regardless of info filter

- **Futures symbol parsing for bdib**: Fixed `market_info()` to correctly parse futures symbols like `TYH6` → `TY` (#198)
  - Previously failed to identify root symbol when ticker had single-digit year suffix

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.0b3...v0.11.0b4

_0.11.0b5_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0b5)

### Fixed

- **Import without blpapi installed**: Fixed `AttributeError` when importing xbbg without blpapi installed (#200)
  - Added `from __future__ import annotations` to defer type annotation evaluation in `conn.py`
  - Guarded `blpapi.Name()` constants with `is_available()` check in `process.py`

- **Japan/non-US timezone fix for bdib**: Fixed timezone conversion for non-US exchanges (#198)
  - Bloomberg returns `TRADING_DAY_START_TIME_EOD` and `TRADING_DAY_END_TIME_EOD` in EST (America/New_York)
  - These are now correctly converted to the exchange's local timezone (e.g., Asia/Tokyo for Japanese equities)
  - Previously, Tokyo's 09:00-15:45 trading hours appeared as 19:00-01:45 (EST times misinterpreted as local)
  - `FUT_TRADING_HRS` is not converted (already in exchange local time)

- **get_tz() no longer triggers Bloomberg lookup for timezone strings**: Direct timezone strings like `"America/New_York"` or `"UTC"` are now recognized without calling Bloomberg API

### Removed

- **Trials mechanism removed**: Eliminated the retry-blocking system that caused silent failures
  - The trials system tracked failed API requests and blocked future attempts after 2 failures
  - This caused issues when bugs were fixed (stale entries still blocked requests)
  - Users had to manually clear SQLite database entries to retry
  - Pipeline caching already handles "don't re-fetch" use case properly
  - Deleted `xbbg/core/utils/trials.py` and related test files

- **pandas-market-calendars dependency removed**: Simplified exchange metadata resolution
  - Removed `PmcCalendarResolver` from resolver chain
  - Exchange information now sourced exclusively from Bloomberg API with local caching
  - Removed `pmc_extended` context option (no longer needed)
  - Reduces package dependencies and improves consistency

### Changed

- **Internal class renames** (backward compatible aliases provided):
  - `YamlMarketInfoProvider` → `MetadataProvider`
  - `ExchangeYamlResolver` → `ExchangeMetadataResolver`

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0b5

_0.11.0_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.0)

### Highlights

- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow for improved performance

- **Multi-backend support**: Output to pandas, Polars, PyArrow, DuckDB, or narwhals with the new `Backend` enum

- **New API functions**: `bta()` for technical analysis, `bqr()` for dealer quotes, `yas()` for fixed income analytics

- **BQL helpers**: `preferreds()` and `corporate_bonds()` convenience functions

- **Dependency cleanup**: Removed pandas-market-calendars and the trials mechanism for a leaner install

- **v1.0 migration path**: Deprecation warnings and forward-compatible APIs prepare for the upcoming v1.0 release

### Added

- **Arrow-first pipeline**: Complete rewrite of internal data processing using PyArrow

- **Multi-backend support**: New `Backend` enum supporting narwhals, pandas, polars, polars_lazy, pyarrow, duckdb

- **Output format control**: New `Format` enum with long, semi_long, wide options

- **bta()**: Bloomberg Technical Analysis function for 50+ technical indicators (#175)

- **bqr()**: Bloomberg Quote Request function emulating Excel `=BQR()` for dealer quote data with broker attribution (#22)

- **yas()**: Bloomberg YAS (Yield Analysis) wrapper for fixed income analytics with `YieldType` enum

- **preferreds()**: BQL convenience function to find preferred stocks for an equity ticker

- **corporate_bonds()**: BQL convenience function to find active corporate bonds for a ticker

- `set_backend()`, `get_backend()`, `set_format()`, `get_format()` configuration functions

- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`

- v1.0-compatible exception classes (`BlpError`, `BlpSessionError`, `BlpRequestError`, etc.)

- `EngineConfig` dataclass and `configure()` function for engine configuration

- `Service` and `Operation` enums for Bloomberg service URIs

- Treasury & SOFR futures support: TY, ZN, ZB, ZF, ZT, UB, TN, SFR, SR1, SR3, ED futures (#198)

- Comprehensive logging improvements across critical paths with better error traceability

- CONTRIBUTING.md and CODE_OF_CONDUCT.md for community standards

### Changed

- All API functions now accept `backend` and `format` parameters

- Internal pipeline uses PyArrow tables with narwhals transformations

- Removed pytz dependency (using stdlib `datetime.timezone`)

- **Intraday cache now includes interval in path** (#80) - different bar intervals cached separately (**breaking**: existing cache will miss)

- Internal class renames with backward compatible aliases (`YamlMarketInfoProvider` → `MetadataProvider`)

- Logging level adjustments: `BBG_ROOT not set` promoted to WARNING, cache timing demoted to DEBUG

### Deprecated

- `connect()` / `disconnect()` - engine auto-initializes in v1.0

- `getBlpapiVersion()` - use `get_sdk_info()` instead

- `lookupSecurity()` - will become `blkp()` in v1.0

- `fieldInfo()` / `fieldSearch()` - will merge into `bfld()` in v1.0

- `bta_studies()` - renamed to `ta_studies()` in v1.0

- `getPortfolio()` - renamed to `bport()` in v1.0

- Helper functions (`dividend()`, `earning()`, `turnover()`, `adjust_ccy()`) moving to `xbbg.ext` in v1.0

- Futures/CDX utilities (`fut_ticker()`, `active_futures()`, `cdx_ticker()`, `active_cdx()`) moving to `xbbg.ext` in v1.0

### Removed

- **Trials mechanism**: Eliminated retry-blocking system that caused silent failures after 2 failed attempts

- **pandas-market-calendars dependency**: Exchange info now sourced exclusively from Bloomberg API with local caching

### Fixed

- **Import without blpapi installed**: Fixed `AttributeError` when importing xbbg without blpapi (#200)

- **Japan/non-US timezone fix for bdib**: Trading hours now correctly converted to exchange's local timezone (#198)

- **stream() field values**: Subscribed field values now always included in output dict (#199)

- **Slow Bloomberg fields**: TIMEOUT events handled correctly; requests wait for response with `slow_warn_seconds` warning (#193)

- **Pipeline data types**: Preserve original data types instead of converting to strings (#191)

- **Futures symbol parsing**: Fixed `market_info()` to correctly parse symbols like `TYH6` → `TY` (#198)

- **get_tz() optimization**: Direct timezone strings recognized without Bloomberg API call

- **bdtick timezone fix**: Pass exchange timezone to fix blank results for non-UTC exchanges (#185)

- **bdtick timeout**: Increased from 10s to 2 minutes for tick data requests

- Extended BDS test date range to 120 days for quarterly dividends

- Helper functions now work correctly with LONG format output

- Logging format compliance fixes (G004, G201)

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.10.3...v0.11.0

_0.11.1_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.1)

### Fixed

- **Field names now lowercase**: Restored v0.10.x behavior where `bdp()`, `bdh()`, and `bds()` return field/column names as lowercase (#206)

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.0...v0.11.1

_0.11.2_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.2)

### Added

- **Extended multi-backend support**: Added 6 new backends matching narwhals' full backend support:
  - **Eager backends**: `cudf` (GPU-accelerated via NVIDIA RAPIDS), `modin` (distributed pandas)
  - **Lazy backends**: `dask` (parallel computing), `ibis` (portable DataFrame expressions), `pyspark` (Apache Spark), `sqlframe` (SQL-based DataFrames)
  - Total: 13 backends (6 eager + 7 lazy)

- **Backend availability checking**: New functions to check and validate backend availability with helpful error messages:
  - `is_backend_available(backend)` - Check if a backend package is installed
  - `check_backend(backend)` - Check availability with version validation, raises helpful errors
  - `get_available_backends()` - List all currently available backends
  - `print_backend_status()` - Diagnostic function showing all backend statuses

- **Format compatibility checking**: New functions to validate format support per backend:
  - `is_format_supported(backend, format)` - Check if a format works with a backend
  - `get_supported_formats(backend)` - Get set of supported formats for a backend
  - `check_format_compatibility(backend, format)` - Validate with helpful errors
  - `validate_backend_format(backend, format)` - Combined validation for API functions

- **`xbbg.ext` module**: New extension module for v1.0 migration containing helper functions that will be removed from `blp` namespace
  - `xbbg.ext.currency` - `adjust_ccy()` for currency conversion
  - `xbbg.ext.dividends` - `dividend()` for dividend history
  - `xbbg.ext.earnings` - `earning()` for earnings breakdowns
  - `xbbg.ext.turnover` - `turnover()` for trading volume
  - `xbbg.ext.holdings` - `etf_holdings()`, `preferreds()`, `corporate_bonds()` BQL helpers
  - `xbbg.ext.futures` - `fut_ticker()`, `active_futures()` for futures resolution
  - `xbbg.ext.cdx` - `cdx_ticker()`, `active_cdx()` for CDX index resolution
  - `xbbg.ext.yas` - `yas()`, `YieldType` for fixed income analytics

- New v1.0-compatible import path: `from xbbg.ext import dividend, fut_ticker, ...` (no deprecation warnings)

- **Pandas removed as required dependency**: `xbbg.ext` modules now use only stdlib datetime and narwhals, making pandas fully optional

### Changed

- **Backend enum reorganized**: Backends now categorized as eager (full API) vs lazy (deferred execution)

- **Format restrictions**: WIDE format only available for eager backends (pandas, polars, pyarrow, narwhals, cudf, modin); lazy backends limited to LONG and SEMI_LONG

- **Version requirements updated**: Minimum versions now match narwhals requirements (duckdb>=1.0, dask>=2024.1)

- `xbbg/markets/resolvers.py` now re-exports from `xbbg.ext.futures` and `xbbg.ext.cdx` for backwards compatibility

- Internal implementations moved to `xbbg/ext/` module; old import paths still work with deprecation warnings

### Fixed

- **ibis backend**: Updated to use `ibis.memtable()` instead of deprecated `con.read_in_memory()`

- **sqlframe backend**: Fixed import path to use `sqlframe.duckdb.DuckDBSession`

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.1...v0.11.2

_0.11.3_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.3)

### Fixed

- **Duplicate `port` keyword argument**: `bbg_service()` and `bbg_session()` used `.get()` to extract `port` then forwarded `**kwargs` still containing it, causing `TypeError: got multiple values for keyword argument 'port'` on non-default ports (e.g., B-Pipe connections) (#212)

- **Session resource leak**: `clear_default_session()` set `_default_session = None` without calling `session.stop()`, leaking OS file descriptors over repeated connect/disconnect cycles (#211)

- **Wrong session removed on retry**: `send_request()` retry path called `remove_session(port=port)` without `server_host`, always targeting `//localhost:{port}` even for remote hosts

- **Inconsistent `server_host` extraction**: `get_session()` / `get_service()` checked `server_host` before `server`, but `connect_bbg()` did the opposite, causing different code paths to resolve different hosts when both keys were present

- **Resource leak on start failure**: `connect_bbg()` did not stop the session before raising `ConnectionError` when `.start()` failed, leaking C++ resources allocated by the `Session()` constructor

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.2...v0.11.3

_0.11.4_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.11.4)

### Fixed

- **`bdtick` Arrow conversion failure**: Object columns containing `blpapi.Name` instances caused `pa.Table.from_pandas()` to fail; now stringified before conversion

- **`adjust_ccy` field name mismatch**: Looked for `"Last_Price"` but `bdh` returns lowercase `"last_price"` since v0.11.1, causing `KeyError`

- **`active_futures` two failures**: Used `nw.coalesce()` with a column (`last_tradeable_dt`) not present in SEMI_LONG format, and called `.height` (not valid on narwhals DataFrame) instead of `.shape[0]`

- **Live test assertions**: Updated 10 tests in `test_live_endpoints.py` to match WIDE format default (active since v0.7.x)

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.3...v0.11.4

_0.12.0b1_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.12.0b1)

### Changed

- **Async-first architecture**: All Bloomberg API functions (`bdp`, `bds`, `bdh`, `bdib`, `bdtick`, `bql`, `beqs`, `bsrch`, `bqr`, `bta`) now have async counterparts (`abdp`, `abds`, `abdh`, etc.) as the source of truth; sync wrappers delegate via `_run_sync()` (#218)

- **Unified I/O layer**: All Bloomberg requests now flow through a single `arequest()` async entry point in `conn.py`, replacing scattered session/service management across modules (#218)

- **Pipeline and process modules**: Adapted `pipeline_core`, `process`, and `request_builder` to work with the async `arequest()` foundation (#218)

- **Top-level async exports**: All async API variants (`abdp`, `abds`, `abdh`, `abdib`, `abdtick`, `abql`, `abeqs`, `absrch`, `abqr`, `abta`) exported from `xbbg.blp` (#218)

- **IO module cleanup**: Removed dead code and fixed type annotations across `xbbg/io/` (#218)

- **Test coverage expanded**: 571 tests total (up from 543), covering all connection-related GitHub issues and all previously untested paths in `conn.py`

### Fixed

- **Mock session leak in tests**: Added autouse `_reset_session_manager` fixture in `conftest.py` to prevent `MagicMock` sessions from persisting in the `SessionManager` singleton across test modules, which caused infinite `__getattr__` → `_get_child_mock` recursion and stack overflow on Windows (#213)

- **`interval` parameter leaked as Bloomberg override**: `interval` was not in `PRSV_COLS`, causing it to be sent to Bloomberg as an override field instead of being used locally for bar sizing (#145)

- **README Data Storage section**: Clarified that only `bdib()` (intraday bars) has caching via `BarCacheAdapter`; all other functions always make live Bloomberg API calls (#215)

- **README async example for Jupyter**: Fixed `asyncio.run()` example that fails in notebooks (which already have a running event loop) by adding `await`-based and `nest_asyncio` alternatives (#216)

- **Unused imports in tests**: Removed `import os` from `test_intraday_api.py` and `import pytest` from `test_logging.py` that caused Ruff F401 lint failures in CI

### Removed

- **`xbbg/io/db.py`**: SQLite database helper module (zero imports across codebase) (#218)

- **`xbbg/io/param.py`**: Legacy parameter/configuration module (zero imports across codebase) (#218)

- **`xbbg/io/files.py`**: File path utility module (zero imports after replacing 6 usages in `cache.py` and `const.py` with `pathlib.Path`) (#218)

- **`xbbg/tests/test_param.py`**: Tests for deleted `param` module (7 tests) (#218)

- **`xbbg/markets/cached/pmc_cache.json`**: Stale pandas-market-calendars cache file (pmc dependency removed in v0.11.0) (#218)

- **`xbbg/tests/__init__.py`**, **`examples/feeds/__init__.py`**: Empty `__init__` files (#218)

- **`xbbg/tests/xone.db`**: Stale SQLite test database (#218)

- **`regression_testing/`**: Standalone v0.7.7 regression test directory (6 files); all 9 test scenarios already covered by `xbbg/tests/test_live_endpoints.py` with stricter assertions (#218)

### Security

- **Bump `cryptography` from 46.0.4 to 46.0.5**: Fixes CVE-2026-26007 — subgroup attack due to missing validation for SECT binary elliptic curves (#217)

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.11.4...v0.12.0b1
