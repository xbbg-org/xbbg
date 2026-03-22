# xbbg Edge Cases from Closed Issues

A comprehensive list of edge case requests discovered through real-world usage of xbbg.

---

## Symbology & Ticker Parsing

### Issue #198 - Treasury/SOFR Futures Missing Exchange Info
```python
blp.bdib(ticker='TYH6 Comdty', dt='2025-11-12', interval=15)
blp.bdib(ticker='SFRH7 Comdty', dt='2025-11-12', interval=15)
```
**Error:** `KeyError: 'Cannot find exchange info for ___'`

**Root Cause:** Symbol parsing extracted `TYH` instead of `TY`, and Treasury/SOFR futures missing from default config.

---

### Issue #25 - Generic Futures Beyond 9th Contract
```python
blp.bdtick('SB11 Comdty', '2020-12-04')
```
**Error:** `AttributeError: 'Series' object has no attribute 'tz'`

**Workaround:**
```python
blp.bdtick('SB11 Comdty', '2020-12-04', ref='SB1 Comdty')
```

---

### Issue #8 - Tickers with Whitespaces
```python
blp.bdib('C 1 Comdty', dt='2021-01-15')  # Corn
blp.bdib('S 1 Comdty', dt='2021-01-15')  # Soybeans
```
**Error:** `required exchange info cannot be found in S 1 Comdty`

**Problem:** YAML parsing ignores trailing whitespace in ticker lists.

---

### Issue #52 - Commodity Futures Intraday
```python
blp.bdib('GCZ1 Comdty', dt='2021-02-19', typ='TRADE')
```
**Result:** Returns empty data.

---

### Issue #32 - ES1 Index Missing Exchange Info
```python
blp.bdib(ticker='ES1 Index', dt='2021-02-19')
```
**Error:** `KeyError: 'Cannot find exchange info for ES1 Index'`

---

## Timeout & Slow Fields

### Issue #193 - Slow Bloomberg Fields Timeout
```python
from xbbg import blp

tickers = ['SECURITY1 Pfd', 'SECURITY2 Pfd', 'SECURITY3 Pfd', 'SECURITY4 Pfd']
fields = ['STOCHASTIC_OAS_MID_MOD_DUR']

df = blp.bdp(tickers, fields)
print(df.empty)  # True - times out after 10 seconds
```
**Problem:** Fields like `STOCHASTIC_OAS_MID_MOD_DUR` take >10s to compute; `TIMEOUT` events treated as fatal.

---

### Issue #157 - bdib Timeout Argument Ineffective
```python
blp.bdib(ticker="SPY US EQUITY", dt="2025-07-07", typ="ASK", timeout=100000)
```
**Problem:** `timeout` argument has no effect.

---

## Session & Time Handling

### Issue #160 - Japan Market Hours Changed
```python
# Japan equity close moved from 3:00 PM to 3:30 PM local time (Nov 2024)
blp.bdib('7203 JP Equity', dt='2024-11-15', session='day')
```
**Problem:** `bdib` misses the final 30 minutes of data.

**Request:** Need way to override `markets/exch.yaml` sessions.

---

### Issue #49 - Tick Data Starts 1 Minute Late
```python
from datetime import datetime
from xbbg import blp

df = blp.bdtick('ESZ1 Index', datetime(2021,8,17), session='day', types=['BID','ASK'], ref='CME')
print(df.head())
```
**Output:** Data starts at `08:01:00` instead of `08:00:00`.

---

### Issue #145 - Invalid Override Field: interval
```python
from datetime import date
from xbbg import blp

df = blp.bdib(
    ticker="SPY US Equity",
    dt=date(2025, 11, 12),
    interval=5,
    session="open",
    typ="TRADE"
)
```
**Warning:** `Invalid override field: interval`

**Problem:** `interval` parameter incorrectly passed to session resolution API.

---

### Issue #59 - Pre/Post Market Returns Empty
```python
blp.bdib('QQQ US Equity', dt='2021-08-10', session='pre')   # Empty
blp.bdib('QQQ US Equity', dt='2021-08-10', session='post')  # Empty
blp.bdib('QQQ US Equity', dt='2021-08-10', session='allday') # Empty
blp.bdib('QQQ US Equity', dt='2021-08-10', session='day')   # Works
```

---

### Issue #33 - A50 Future Singapore Day Session Empty
```python
blp.bdib("XU1 Index", dt="2021-03-24", session="day", ref="FuturesSingapore")
```
**Result:** Returns nothing for day session (9am-16:35pm), only returns night session.

---

## Field & Override Quirks

### Issue #122 - Historical Fundamentals via bdp
```python
from xbbg import blp

FIELD_MAP = {
    'pe': 'PE_RATIO',
    'pb': 'PX_TO_BOOK_RATIO',
    'eps': 'BEST_EPS',
    # ... more fields
}

# This works (most recent data):
data = blp.bdp(tickers='AAPL US Equity', flds=list(FIELD_MAP.values()))

# This returns empty (historical date):
data = blp.bdp(
    tickers='AAPL US Equity',
    flds=list(FIELD_MAP.values()),
    overrides=[('REFERENCE_DATE', '20240101')],
)
```

---

### Issue #71 - bds Ignores CURVE_DATE Override
```python
from xbbg import blp

# This ignores CURVE_DATE and returns most recent data:
blp.bds('YCSW0045 Index', "PAR_CURVE", CURVE_DATE='20160625')
```
**Problem:** Bloomberg requires `REFERENCE_DATE` instead of `CURVE_DATE` for this index.

---

### Issue #93 - CDR Calendar Override Ignored
```python
# All of these return identical results (260 rows):
t1 = blp.bdh("EURUSD Curncy", "PX_LAST", "20220101", "20221231", "CDR=TE")   # Germany
t2 = blp.bdh("EURUSD Curncy", "PX_LAST", "20220101", "20221231", "CDR=ID")   # Indonesia
t3 = blp.bdh("EURUSD Curncy", "PX_LAST", "20220101", "20221231", "CDR=TE&ID") # Intersection
t4 = blp.bdh("EURUSD Curncy", "PX_LAST", "20220101", "20221231", "CDR=SK")   # South Korea
```
**Problem:** CDR override not implemented in bdh.

---

### Issue #35 - Custom Overrides Not Supported
```python
blp.bdh(tickers="SPX Index", flds='BID', start_date="2021-03-30", end_date="2021-03-31", IntrRw=True)
```
**Result:** Empty DataFrame. Adding `IntrRw` to `ELEM_KEYS` causes different error.

---

### Issue #51 - Currency Override Not Working for Market Cap
```python
for index, row in dataset.iterrows():
    row['Mkt Cap'] = blp.bds((row[key_column] + " Equity"), flds=["CUR_MKT_CAP", "CRNCY=USD"])
```
**Problem:** Market cap returned in local currency, not USD.

---

### Issue #50 - Currency-Adjusted Price Returns Empty
```python
value = blp.bdp(ticker + " Equity", "CRNCY_ADJ_PX_LAST", kwargs="EQY_FUND_CRNCY=USD")
```
**Result:** Empty DataFrame.

---

## Data Type & Array Fields

### Issue #21 - Array/Bulk Fields Cause ValueError
```python
blp.bdp('TYA Index', 'FUT_CHAIN')
```
**Error:** `ValueError: Index contains duplicate entries, cannot reshape`

**Note:** Fields with "Show Bulk Data" in Bloomberg FLDS should use `bds`, not `bdp`.

---

### Issue #45 - Index Members Returns Duplicate Entries
```python
blp.bdp('RAY Index', 'INDX_MEMBERS')
```
**Error:** `ValueError: Index contains duplicate entries, cannot reshape`

---

## Intraday & Caching

### Issue #80 & #96 - Cache Collision for Different Intervals
```python
# First call - caches 5-minute bars:
blp.bdib('EUR Curncy', dt='2023-1-23', typ='TRADE', interval=5, session='allday')

# Second call - returns 5-minute bars instead of 60-minute:
blp.bdib('EUR Curncy', dt='2023-1-23', typ='TRADE', interval=60, session='allday')
```
**Problem:** Cache path doesn't include interval, causing collisions.

---

### Issue #70 - Multi-Day Intraday Bars Not Supported
```python
# Want to pass start and end dates:
blp.bdib('ES1 Index', dt_from='2021-03-01', dt_to='2021-03-05')  # Not supported
```
**Workaround:** Loop over dates individually.

---

### Issue #92 - Sub-Minute Bars Not Supported
```python
# Want 10-second bars:
blp.bdib('AAPL US Equity', dt='2022-10-17', session='day', interval=1)  # Only minutes supported
```
**Request:** Support `interval` in seconds via `intervalHasSeconds=True`.

---

## Exchange & Asset Mapping

### Issue #68 - Missing European Exchanges
```python
blp.bdtick('SAP GY Equity', dt='2021-06-15')  # GY = Xetra
blp.bdtick('ENI IM Equity', dt='2021-06-15')  # IM = Borsa Italiana
blp.bdtick('NESN SE Equity', dt='2021-06-15') # SE = SIX
```
**Problem:** Exchange codes GY, IM, SE missing from `assets.yml` and `exch.yml`.

---

## BQL Specific

### Issue #189 - Economic Calendar Missing Ticker Column
```python
from xbbg import blp

df = blp.bql("for(['US Country', 'CN Country', 'JP Country']) get(calendar(dates=range(2026-01-21, 2026-02-21),type='ECONOMIC_RELEASES'))")
```
**Problem:** Returns NaN in ticker column instead of actual tickers.

---

### Issue #150 - BQL Returns Only One Row
```python
from xbbg import blp

blp.bql("get(eco_calendar) for ('US Country')")
```
**Result:** Only 1 row returned instead of 50+ calendar events.

---

### Issue #141 - BQL Options Query Returns Nothing
```python
blp.bql("filter(options('SPX Index'), expire_dt=='2025-11-21'), sum(group(open_int))", mode="cached")
```
**Result:** Empty or no data returned.

---

## Connection & B-Pipe

### Issue #154 - B-Pipe Symbology Requirements
```python
# Standard xbbg calls return BAD_SEC on B-Pipe:
blp.bdp('IBM US Equity', 'PX_LAST')
```
**Problem:** From Dec 31, 2025, Bloomberg enforces prefix symbology:
- Wrong: `//blp/mktdata/IBM US Equity`
- Correct: `//blp/mktdata/TICKER/IBM US Equity`

---

### Issue #164 - blp.connect Not Taking Effect
```python
from xbbg import blp

# First call (fails - no local terminal):
px = blp.bdp("SPX Index", "PX_LAST")

# Connect to B-Pipe:
blp.connect(
    auth_method="app",
    server_host="<your bpipe server>",
    server_port=8194,
    app_name="<app name>",
)

# Second call (still tries localhost:8194):
px = blp.bdp("SPX Index", "PX_LAST")
```
**Problem:** `blp.connect` configuration not persisted.

---

## Discontinued/Stopped Tickers

### Issue #112 (referenced) - Discontinued Tickers Return Empty
```python
# LIBOR stopped publishing - this returns empty:
blp.bdh('US0003M Index', 'PX_LAST', start_date='2020-01-01', end_date='2024-01-01')
```
**Workaround:** Omit `end_date` to get last available data.

---

### Issue #38 - Different Results With/Without end_date
```python
fut_sym = "HC1 Index"

# With end_date:
df1 = blp.bdh(fut_sym, "PX_LAST", start_date="2019-01-01", end_date="2019-12-31")
# Returns: 9710.851, 9739.567, ...

# Without end_date:
df2 = blp.bdh(fut_sym, "PX_LAST", start_date="2019-01-01")
# Returns: 9410.969, 9438.798, ...  (DIFFERENT VALUES!)
```

---

## Subscription & Live Data

### Issue #65 - No Interval Option for Subscriptions
```python
# Want to set 10-second interval:
blp.subscribe(topics, flds)  # No interval parameter available
```
**Workaround:** Modify `blp.py` line 532:
```python
sub_list.add(topic, flds, correlationId=cid, options='interval=10')
```

---

### Issue #60 - Async Live Feed Not Working
```python
async def live_data():
    async for snap in blp.live(['ESA Index', 'NQA Index'], max_cnt=2):
        print(snap)

def run_data():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(live_data())
    loop.close()

run_data()  # Doesn't work
```

---

## Miscellaneous Edge Cases

### Issue #81 - Some Indexes Not Recognized
```python
df = blp.bdh(
    tickers=['JPEIDIVR Index', 'JCMDCOMP Index', 'JGENVUUG Index'],
    flds=['px_last'],
    start_date='2018-10-31',
    end_date='2018-11-30',
    Per="M"
)
# Only returns JPEIDIVR, others not recognized
```

---

### Issue #67 - Risk Data Intermittently Empty
```python
# Sometimes returns data, sometimes empty:
blp.bdp(tickers, ['SW566', 'SW031', 'KEY_RATE_RISK_3M'])
```
**Problem:** Risk fields for interest rate swaps (pv01, dv01) intermittently fail.

---

### Issue #75 - bds with Empty Field
```python
blp.bds('TSLA US Equity', flds='')
```
**Result:** Empty DataFrame (need valid field like `INDX_MWEIGHT`).

---

### Issue #29 - bds Produces Duplicated Results
```python
blp.bds(['AAPL US Equity', 'IBM US Equity', 'T US Equity', 'F US Equity'], flds=['EQY_DVD_ADJUST_FACT'])
```
**Problem:** Duplicated output for same ticker due to request accumulation in map function.

---

### Issue #98 - Duplicate Index Entries in bdh
```python
tickers = ['AAPL US Equity', 'MSFT US Equity']
fields = ['PX_LAST', 'VOLUME']

df = blp.bdh(tickers=tickers, flds=fields, start_date='2023-01-01', end_date='2023-01-31', currency='USD')
```
**Error:** `ValueError: Index contains duplicate entries, cannot reshape`

---

### Issue #53 - Cannot Specify Server IP
```python
# Only port works, not server IP:
blp.bdp(tickers='NVDA US Equity', flds=['Security_Name'], server_port=18194)

# Want to specify IP:
blp.bdp(tickers='NVDA US Equity', flds=['Security_Name'], server='192.168.1.100', server_port=18194)
```
**Problem:** `conn.py` hardcodes `localhost`.

---

### Issue #82 - Typo in connect()
```python
# In conn.py line ~91:
sess_opts.setServerPort(serverPort=kwargs['server_post'])  # Should be 'server_port'
```

---

### Issue #121 - Typo in createWithLogonName
```python
# In xbbg/core/conn.py:
user = blpapi.AuthUser.createWithLogonName()  # Missing parentheses in some code paths
```

---

## Summary by Category

| Category | Count | Key Issues |
|----------|-------|------------|
| Symbology/Parsing | 5 | #198, #25, #8, #52, #32 |
| Timeout/Slow Fields | 2 | #193, #157 |
| Session/Time | 5 | #160, #49, #145, #59, #33 |
| Field/Override | 6 | #122, #71, #93, #35, #51, #50 |
| Data Types | 2 | #21, #45 |
| Caching | 3 | #80, #96, #70, #92 |
| Exchange Mapping | 1 | #68 |
| BQL | 3 | #189, #150, #141 |
| Connection/B-Pipe | 2 | #154, #164 |
| Discontinued Tickers | 2 | #112, #38 |
| Subscriptions | 2 | #65, #60 |
| Misc | 8 | #81, #67, #75, #29, #98, #53, #82, #121 |
