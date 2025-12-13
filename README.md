<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<a href="https://github.com/alpha-xone/xbbg"><img src="https://raw.githubusercontent.com/alpha-xone/xbbg/main/docs/xbbg.png" alt="xbbg logo" width="150"></a>

<!-- markdownlint-disable MD036 -->
**xbbg: An intuitive Bloomberg API for Python**
<!-- markdownlint-enable MD036 -->

[![PyPI version](https://img.shields.io/pypi/v/xbbg.svg)](https://pypi.org/project/xbbg/)
[![Python versions](https://img.shields.io/pypi/pyversions/xbbg.svg)](https://pypi.org/project/xbbg/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/xbbg)](https://pypistats.org/packages/xbbg)
[![Gitter](https://badges.gitter.im/xbbg/community.svg)](https://gitter.im/xbbg/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

<a href="https://www.buymeacoffee.com/Lntx29Oof"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-1E3A8A?style=plastic&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>

**Quick Links:** [Documentation](https://xbbg.readthedocs.io/) • [Installation](#installation) • [Quickstart](#quickstart) • [Examples](#examples) • [Source](https://github.com/alpha-xone/xbbg) • [Issues](https://github.com/alpha-xone/xbbg/issues)

</div>
<!-- markdownlint-enable MD033 MD041 -->

---

<!-- xbbg:latest-release-start -->
Latest release: xbbg==0.9.1 (release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.9.1))
<!-- xbbg:latest-release-end -->

## Overview

xbbg is the **most comprehensive and intuitive blpapi wrapper for Python**, providing a Pythonic interface with Excel-compatible inputs, straightforward intraday bar requests, and real-time subscriptions. All functions return pandas DataFrames for seamless integration with your data workflow.

**Why xbbg?**

- 🎯 **Complete API Coverage**: Reference, historical, intraday bars, tick data, real-time subscriptions, equity screening (BEQS), BQL support, and SRCH queries
- 📊 **Excel-Compatible**: Use familiar Excel date formats and field names - no learning curve
- ⚡ **Built-in Caching**: Automatic Parquet-based local storage reduces API calls and speeds up workflows
- 🔧 **Rich Utilities**: Currency conversion, futures/CDX resolvers, exchange-aware market hours, and more
- 🚀 **Modern & Active**: Python 3.10+ support with regular updates and active maintenance
- 💡 **Intuitive Design**: Simple, consistent API (`bdp`, `bdh`, `bdib`, etc.) that feels natural to use

See [`examples/xbbg_jupyter_examples.ipynb`](examples/xbbg_jupyter_examples.ipynb) for interactive tutorials and examples.

## Why Choose xbbg?

xbbg stands out as the most comprehensive and user-friendly blpapi wrapper for Python. Here's how it compares to alternatives:

| Feature | xbbg | pdblp | blp | polars-bloomberg |
|---------|------|-------|-----|------------------|
| Reference Data (BDP/BDS) | ✅ | ✅ | ✅ | ✅ |
| Historical Data (BDH) | ✅ | ✅ | ✅ | ✅ |
| Intraday Bars (BDIB) | ✅ | ❌ | ❌ | ✅ |
| Tick Data | ✅ | ❌ | ❌ | ❌ |
| Real-time Subscriptions | ✅ | ❌ | ❌ | ❌ |
| Equity Screening (BEQS) | ✅ | ❌ | ❌ | ❌ |
| Query Language (BQL) | ✅ | ❌ | ❌ | ✅ |
| Search (BSRCH) | ✅ | ❌ | ❌ | ✅ |
| Excel-compatible inputs | ✅ | ❌ | ❌ | ❌ |
| Sub-minute intervals | ✅ | ❌ | ❌ | ❌ |
| Local Parquet caching | ✅ | ❌ | ❌ | ❌ |
| Currency conversion | ✅ | ❌ | ❌ | ❌ |
| Futures/CDX resolvers | ✅ | ❌ | ❌ | ❌ |
| Active development | ✅ | ❌[^1] | ✅ | ✅ |
| Modern Python (3.10+) | ✅ | ✅ | ✅ | 3.12+ |
| DataFrame Library | pandas | pandas | pandas | Polars |

[^1]: pdblp has been superseded by blp and is no longer under active development.

## Supported Functionality

| Function | Description | Key Features |
|----------|-------------|--------------|
| 📊 **Reference Data** | | |
| `bdp()` | Single point-in-time reference data | Multiple tickers/fields, Excel dates, overrides, **ISIN/CUSIP/SEDOL support** |
| `bds()` | Bulk/block data (multi-row) | Portfolio data, date filtering, nested structures, **Fixed income cash flows** |
| `abdp()` | Async reference data | Non-blocking, concurrent requests, same API as `bdp()` |
| `abds()` | Async block data | Non-blocking, concurrent requests, same API as `bds()` |
| `fieldInfo()` | Field metadata | Data types, descriptions, field information |
| `fieldSearch()` | Field search | Search fields by name/description |
| `lookupSecurity()` | Security lookup | Find tickers by company name, asset class filtering |
| `getPortfolio()` | Portfolio data | Dedicated portfolio query function |
| 📈 **Historical Data** | | |
| `bdh()` | End-of-day historical data | Date ranges, frequencies, dividend/split adjustments |
| `abdh()` | Async historical data | Non-blocking, concurrent requests, same API as `bdh()` |
| `dividend()` | Dividend & split history | Multiple types, date ranges, projected dividends |
| `earning()` | Corporate earnings breakdowns | Geographic/product breakdowns, fiscal periods |
| `turnover()` | Trading volume & turnover | Currency conversion, multi-currency support |
| ⏱️ **Intraday Data** | | |
| `bdib()` | Intraday bar data | Minute/second intervals, sub-minute bars, sessions |
| `bdtick()` | Tick-by-tick data | Event types, condition codes, exchange/broker codes |
| 🔍 **Screening & Queries** | | |
| `beqs()` | Bloomberg Equity Screening | Custom criteria, private/public screens |
| `bql()` | Bloomberg Query Language | SQL-like syntax, complex transformations |
| `bsrch()` | SRCH (Search) | User-defined searches, commodity screens, weather data |
| 📡 **Real-time** | | |
| `live()` | Real-time market data | Async updates, context manager support |
| `subscribe()` | Real-time subscriptions | Field-level subscriptions, event callbacks |
| 🔧 **Utilities** | | |
| `adjust_ccy()` | Currency conversion | Multi-currency, historical FX rates |
| `active_futures()` | Active futures contracts | Volume-based selection, date-aware resolution |
| `fut_ticker()` | Futures ticker resolution | Generic to specific contract mapping |
| `cdx_ticker()` | CDX index ticker resolution | Index series mapping |
| `active_cdx()` | Active CDX contracts | Series resolution, volume-based selection |

**Additional Features**: Local caching (Parquet), configurable logging, timezone support, exchange-aware market hours, batch processing, standardized column mapping

## Requirements

- Bloomberg C++ SDK version 3.12.1 or higher:

  - Visit [Bloomberg API Library](https://www.bloomberg.com/professional/support/api-library/) and download C++ Supported Release

  - In the `bin` folder of downloaded zip file, copy `blpapi3_32.dll` and `blpapi3_64.dll` to Bloomberg `BLPAPI_ROOT` folder (usually `blp/DAPI`)

- Bloomberg official Python API:

```cmd
pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
```

- `numpy`, `pandas`, `ruamel.yaml` and `pyarrow`

## Installation

```cmd
pip install xbbg
```

Supported Python versions: 3.10 – 3.14 (universal wheel).

## Quickstart

```python
from xbbg import blp

# Reference data (BDP)
ref = blp.bdp(tickers='AAPL US Equity', flds=['Security_Name', 'GICS_Sector_Name'])
print(ref)

# Historical data (BDH)
hist = blp.bdh('SPX Index', ['high', 'low', 'last_price'], '2021-01-01', '2021-01-05')
print(hist.tail())
```

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

xbbg provides async versions of reference and historical data functions for non-blocking, concurrent requests. Use `abdp()`, `abds()`, and `abdh()` in async contexts:

```python
import asyncio
from xbbg import blp

# Single async request
async def get_data():
    df = await blp.abdp(tickers='TICKER US Equity', flds=['PX_LAST', 'VOLUME'])
    return df

# Concurrent requests for multiple tickers
async def get_multiple():
    results = await asyncio.gather(
        blp.abdp(tickers='TICKER1 US Equity', flds=['PX_LAST']),
        blp.abdp(tickers='TICKER2 US Equity', flds=['PX_LAST']),
        blp.abdh(tickers='TICKER3 US Equity', start_date='2024-01-01'),
    )
    return results

# Run async functions
data = asyncio.run(get_data())
multiple = asyncio.run(get_multiple())
```

**Benefits:**
- Non-blocking: doesn't block the event loop
- Concurrent: use `asyncio.gather()` for parallel requests
- Compatible: works with async web frameworks and async codebases
- Same API: identical parameters to sync versions (`bdp`, `bds`, `bdh`)

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
  - If a `session` name is not defined for the ticker’s exchange,
    `get_interval()` raises a `ValueError` listing the available sessions
    for that exchange and points to `xbbg/markets/exch.yml`.
  - For compound sessions whose base session doesn’t exist (e.g. mis-typed
    `am_open_30` for an exchange that has no `am` section), `get_interval()`
    returns `SessNA` and `time_range()` will then try the PMC fallback or
    ultimately raise a clear `ValueError`.

In practice:

- Use simple names like `session='day'` or `session='allday'` when you just
  want the main trading hours.
- Use compound names like `session='day_open_30'` or `session='am_normal_30_30'`
  when you need to focus on opening/closing auctions or to exclude “micro”
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

If `BBG_ROOT` is provided in `os.environ`, data can be saved locally in Parquet format. By default, local storage is preferred over blpapi for all queries.

**Setup**:

```python
import os
os.environ['BBG_ROOT'] = '/path/to/your/data/directory'
```

Once configured, xbbg will automatically save and retrieve data from local Parquet files, reducing blpapi calls and improving performance.

**Important**: Local data usage must be compliant with Bloomberg Datafeed Addendum (full description in `DAPI<GO>`):

> To access Bloomberg data via the API (and use that data in Microsoft Excel), your company must sign the 'Datafeed Addendum' to the Bloomberg Agreement. This legally binding contract describes the terms and conditions of your use of the data and information available via the API (the "Data"). The most fundamental requirement regarding your use of Data is that it cannot leave the local PC you use to access the BLOOMBERG PROFESSIONAL service.

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

- Issues and feature requests: please open an issue on the repository.
- Pull requests welcome. Run lint and tests locally:

```cmd
uv sync --locked --extra dev --extra test
uv run ruff check xbbg
uv run pytest --doctest-modules -q
```

## Links

- [PyPI](https://pypi.org/project/xbbg/)
- [Documentation](https://xbbg.readthedocs.io/)
- [Source](https://github.com/alpha-xone/xbbg)
- Security policy: see `SECURITY.md`

## What's New

<!-- xbbg:changelog-start -->

_0.9.1_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.9.1)

## What's Changed

- fix: Fix BQL returning only one row for multi-value results by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/152

- fix(docs): add blank lines around latest-release markers in index.rst

- ci: remove redundant release triggers from workflows

- ci: trigger release workflows explicitly from semantic_version

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.9.0...v0.9.1


_0.9.0_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.9.0)

## What's Changed

- feat: Add etf_holdings() function for retrieving ETF holdings via BQL by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/147

- feat: Add multi-day support to bdib() by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/148

- feat: Add multi-day cache support for bdib() by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/149

- fix: resolve RST duplicate link targets and Sphinx build warnings

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.2...v0.9.0

_0.8.2_ - see release: [notes](https://github.com/alpha-xone/xbbg/releases/tag/v0.8.2)
<!-- xbbg:changelog-end -->

_0.7.2_ - Use `async` for live data feeds

_0.7.0_ - `bdh` preserves columns orders (both tickers and flds).
`timeout` argument is available for all queries - `bdtick` usually takes longer to respond -
can use `timeout=1000` for example if keep getting empty DataFrame.

_0.6.6_ - Add flexibility to use reference exchange as market hour definition
(so that it's not necessary to add `.yml` for new tickers, provided that the exchange was defined
in `/xbbg/markets/exch.yml`). See example of `bdib` below for more details.

_0.6.0_ - Speed improvements and tick data availablity

_0.5.0_ - Rewritten library to add subscription, BEQS, simplify interface and remove dependency of `pdblp`

_0.1.22_ - Remove PyYAML dependency due to security vulnerability

_0.1.17_ - Add `adjust` argument in `bdh` for easier dividend / split adjustments

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=alpha-xone/xbbg&type=Date)](https://star-history.com/#alpha-xone/xbbg&Date)

| Category       | Badge                                                                                                                                    |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Docs           | [![Documentation Status](https://readthedocs.org/projects/xbbg/badge/?version=latest)](https://xbbg.readthedocs.io/)                    |
| Build          | [![Actions Status](https://github.com/alpha-xone/xbbg/workflows/Auto%20CI/badge.svg)](https://github.com/alpha-xone/xbbg/actions)       |
| Coverage       | [![codecov](https://codecov.io/gh/alpha-xone/xbbg/branch/main/graph/badge.svg)](https://codecov.io/gh/alpha-xone/xbbg)                  |
| Quality        | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/daec9f52ba344e3ea116c15f1fc6d541)](https://www.codacy.com/gh/alpha-xone/xbbg/) |
|                | [![CodeFactor](https://www.codefactor.io/repository/github/alpha-xone/xbbg/badge)](https://www.codefactor.io/repository/github/alpha-xone/xbbg) |
| License        | [![GitHub license](https://img.shields.io/github/license/alpha-xone/xbbg.svg)](https://github.com/alpha-xone/xbbg/blob/main/LICENSE)   |
