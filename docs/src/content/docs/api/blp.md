---
title: Bloomberg Data API
description: Core API functions for Bloomberg data (bdp, bdh, bds, bdib, bdtick)
---

<a id="xbbg.blp"></a>

# xbbg.blp

High-level Bloomberg data API: reference, historical, intraday.

This module provides the xbbg-compatible API using the Rust backend,
with support for multiple DataFrame backends via narwhals.

API Design:
- Async-first: Core implementation uses async/await (abdp, abdh, etc.)
- Sync wrappers: Convenience functions (bdp, bdh, etc.) wrap async with asyncio.run()
- Generic API: arequest() and request() for power users and arbitrary Bloomberg requests
- Users can use either style based on their needs

<a id="xbbg.blp.Backend"></a>

## Backend Objects

```python
class Backend(str, Enum)
```

DataFrame backend options for xbbg functions.

**Attributes**:

- `NARWHALS` - Return narwhals DataFrame (default). Convert with .to_pandas(), .to_polars(), etc.
- `NARWHALS_LAZY` - Return narwhals LazyFrame. Call .collect() to materialize.
- `PANDAS` - Return pandas DataFrame directly.
- `POLARS` - Return polars DataFrame directly.
- `POLARS_LAZY` - Return polars LazyFrame directly. Call .collect() to materialize.
- `PYARROW` - Return pyarrow Table directly.
- `DUCKDB` - Return DuckDB relation (lazy). Call .df() or .arrow() to materialize.

<a id="xbbg.blp.EngineConfig"></a>

## EngineConfig Objects

```python
@dataclass
class EngineConfig()
```

Configuration for the xbbg Engine.

All settings have sensible defaults - you only need to specify what you want to change.

**Attributes**:

- `host` - Bloomberg server host (default: "localhost")
- `port` - Bloomberg server port (default: 8194)
- `request_pool_size` - Number of pre-warmed request workers (default: 2)
- `subscription_pool_size` - Number of pre-warmed subscription sessions (default: 4)
  
  Example::
  
  from xbbg import configure, EngineConfig
  
  # Configure before first request
  configure(EngineConfig(
  request_pool_size=4,
  subscription_pool_size=8,
  ))
  
  # Or use configure() with keyword arguments
  configure(request_pool_size=4, subscription_pool_size=8)

<a id="xbbg.blp.configure"></a>

#### configure

```python
def configure(config: EngineConfig | None = None,
              *,
              host: str | None = None,
              port: int | None = None,
              request_pool_size: int | None = None,
              subscription_pool_size: int | None = None) -> None
```

Configure the xbbg engine before first use.

This function must be called before any Bloomberg request is made.
If called after the engine has started, a RuntimeError is raised.

Can be called with either an EngineConfig object or keyword arguments.

**Arguments**:

- `config` - An EngineConfig object with all settings.
- `host` - Bloomberg server host (default: "localhost")
- `port` - Bloomberg server port (default: 8194)
- `request_pool_size` - Number of pre-warmed request workers (default: 2)
- `subscription_pool_size` - Number of pre-warmed subscription sessions (default: 4)
  

**Raises**:

- `RuntimeError` - If called after the engine has already started.
  
  Example::
  
  import xbbg
  
  # Option 1: Using keyword arguments
  xbbg.configure(request_pool_size=4, subscription_pool_size=8)
  
  # Option 2: Using EngineConfig object
  from xbbg import EngineConfig
  xbbg.configure(EngineConfig(request_pool_size=4))
  
  # Now make requests - configuration takes effect
  df = xbbg.bdp("AAPL US Equity", "PX_LAST")

<a id="xbbg.blp.set_backend"></a>

#### set\_backend

```python
def set_backend(backend: Backend | str | None) -> None
```

Set the default DataFrame backend for all xbbg functions.

**Arguments**:

- `backend` - The backend to use. Can be a Backend enum or string:
  - Backend.NARWHALS / "narwhals": Return narwhals DataFrame (default)
  - Backend.NARWHALS_LAZY / "narwhals_lazy": Return narwhals LazyFrame
  - Backend.PANDAS / "pandas": Return pandas DataFrame
  - Backend.POLARS / "polars": Return polars DataFrame
  - Backend.POLARS_LAZY / "polars_lazy": Return polars LazyFrame
  - Backend.PYARROW / "pyarrow": Return pyarrow Table
  - Backend.DUCKDB / "duckdb": Return DuckDB relation (lazy)
  - None: Same as Backend.NARWHALS
  
  Example::
  
  import xbbg
  from xbbg import Backend
  
  xbbg.set_backend(Backend.POLARS)
  df = xbbg.bdh("AAPL US Equity", "PX_LAST")  # Returns polars.DataFrame
  
  # Use lazy evaluation for deferred computation
  xbbg.set_backend(Backend.POLARS_LAZY)
  lf = xbbg.bdh("AAPL US Equity", "PX_LAST")  # Returns polars.LazyFrame
  df = lf.collect()  # Materialize when ready
  
  # String also works
  xbbg.set_backend("pandas")

<a id="xbbg.blp.get_backend"></a>

#### get\_backend

```python
def get_backend() -> Backend | None
```

Get the current default DataFrame backend.

<a id="xbbg.blp.arequest"></a>

#### arequest

```python
async def arequest(
        service: str | Service,
        operation: str | Operation,
        *,
        securities: str | Sequence[str] | None = None,
        security: str | None = None,
        fields: str | Sequence[str] | None = None,
        overrides: dict[str, Any] | Sequence[tuple[str, str]] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        event_type: str | None = None,
        interval: int | None = None,
        options: dict[str, Any] | Sequence[tuple[str, str]] | None = None,
        field_types: dict[str, str] | None = None,
        output: OutputMode | str = OutputMode.ARROW,
        extractor: ExtractorHint | str | None = None,
        format: Format | str | None = None,
        backend: Backend | str | None = None,
        request_tz: str | None = None,
        output_tz: str | None = None)
```

Async generic Bloomberg request.

This is the low-level API for power users who need to:
- Send requests to arbitrary Bloomberg services
- Use operations not covered by the typed convenience functions
- Get raw JSON responses for debugging

For common use cases, prefer the typed functions: abdp, abdh, abds, abdib, abdtick.

**Arguments**:

- `service` - Bloomberg service URI (e.g., Service.REFDATA or "//blp/refdata").
- `operation` - Request operation name (e.g., Operation.REFERENCE_DATA).
- `securities` - List of security identifiers (for multi-security requests).
- `security` - Single security identifier (for intraday requests).
- `fields` - List of field names to retrieve.
- `overrides` - Field overrides as dict or list of (name, value) tuples.
- `start_date` - Start date for historical requests (YYYYMMDD format).
- `end_date` - End date for historical requests (YYYYMMDD format).
- `start_datetime` - Start datetime for intraday requests (ISO format).
- `end_datetime` - End datetime for intraday requests (ISO format).
- `event_type` - Event type for intraday bars (TRADE, BID, ASK, etc.).
- `interval` - Bar interval in minutes for intraday bars.
- `options` - Additional Bloomberg options as dict or list of (key, value) tuples.
- `field_types` - Manual type overrides for fields (for future type resolution).
- `output` - Output format: OutputMode.ARROW (default) or OutputMode.JSON.
- `extractor` - Override the auto-detected extractor. Use ExtractorHint.BULK for
  bulk data fields. If None, auto-detected from operation.
- `format` - Output format hint for result structure.
- `backend` - DataFrame backend to return. If None, uses global default.
- `request_tz` - Optional intraday: naive datetime interpretation (Rust engine).
- `output_tz` - Optional intraday: `time` column relabel (Rust engine).
  

**Returns**:

  DataFrame/Table in the requested format.
  
  Example::
  
  # Query field metadata (//blp/apiflds service)
  df = await arequest(
  Service.APIFLDS,
  Operation.FIELD_INFO,
  fields=['PX_LAST', 'VOLUME'],
  )
  
  # Get raw JSON for debugging
  json_table = await arequest(
  Service.REFDATA,
  Operation.REFERENCE_DATA,
  securities=['AAPL US Equity'],
  fields=['PX_LAST'],
  output=OutputMode.JSON,
  )
  
  # Custom Bloomberg request (power user)
  df = await arequest(
  "//blp/refdata",
  "ReferenceDataRequest",
  securities=['AAPL US Equity'],
  fields=['PX_LAST'],
  )

<a id="xbbg.blp.request"></a>

#### request

```python
def request(service: str | Service,
            operation: str | Operation,
            *,
            securities: str | Sequence[str] | None = None,
            security: str | None = None,
            fields: str | Sequence[str] | None = None,
            overrides: dict[str, Any] | Sequence[tuple[str, str]]
            | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
            start_datetime: str | None = None,
            end_datetime: str | None = None,
            event_type: str | None = None,
            interval: int | None = None,
            options: dict[str, Any] | Sequence[tuple[str, str]] | None = None,
            field_types: dict[str, str] | None = None,
            output: OutputMode | str = OutputMode.ARROW,
            extractor: ExtractorHint | str | None = None,
            backend: Backend | str | None = None)
```

Generic Bloomberg request (sync wrapper).

Sync wrapper around arequest(). For async usage, use arequest() directly.

See arequest() for full documentation.

Example::

# Query field metadata
df = request(
Service.APIFLDS,
Operation.FIELD_INFO,
fields=['PX_LAST', 'VOLUME'],
)

<a id="xbbg.blp.abdp"></a>

#### abdp

```python
async def abdp(tickers: str | Sequence[str],
               flds: str | Sequence[str] | None = None,
               *,
               backend: Backend | str | None = None,
               format: Format | str | None = None,
               field_types: dict[str, str] | None = None,
               **kwargs)
```

Async Bloomberg reference data (BDP).

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field or list of fields to query.
- `backend` - DataFrame backend to return. If None, uses global default.
  Supports lazy backends: 'polars_lazy', 'narwhals_lazy', 'duckdb'.
- `format` - Output format. Options:
  - Format.LONG (default): ticker, field, value (strings)
  - Format.LONG_TYPED: ticker, field, value_f64, value_i64, etc.
  - Format.LONG_WITH_METADATA: ticker, field, value, dtype
  - Format.SEMI_LONG: one row per ticker with fields as columns
- `field_types` - Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
  If None, types are auto-resolved from Bloomberg field metadata.
- `**kwargs` - Bloomberg overrides and infrastructure options.
  

**Returns**:

  DataFrame in long format with columns: ticker, field, value.
  For lazy backends, returns LazyFrame that must be collected.
  
  Example::
  
  # Async usage
  df = await abdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
  
  # Concurrent requests
  dfs = await asyncio.gather(
  abdp('AAPL US Equity', 'PX_LAST'),
  abdp('MSFT US Equity', 'PX_LAST'),
  )

<a id="xbbg.blp.abdh"></a>

#### abdh

```python
async def abdh(tickers: str | Sequence[str],
               flds: str | Sequence[str] | None = None,
               start_date: str | None = None,
               end_date: str = "today",
               *,
               backend: Backend | str | None = None,
               format: Format | str | None = None,
               field_types: dict[str, str] | None = None,
               **kwargs)
```

Async Bloomberg historical data (BDH).

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field or list of fields. Defaults to ['PX_LAST'].
- `start_date` - Start date. Defaults to 8 weeks before end_date.
- `end_date` - End date. Defaults to 'today'.
- `backend` - DataFrame backend to return. If None, uses global default.
  Supports lazy backends: 'polars_lazy', 'narwhals_lazy', 'duckdb'.
- `format` - Output format. Options:
  - Format.LONG (default): ticker, date, field, value (strings)
  - Format.LONG_TYPED: ticker, date, field, value_f64, value_i64, etc.
  - Format.LONG_WITH_METADATA: ticker, date, field, value, dtype
  - Format.SEMI_LONG: one row per security/date with fields as columns
- `field_types` - Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
  If None, types are auto-resolved from Bloomberg field metadata.
- `**kwargs` - Additional overrides and infrastructure options.
- `adjust` - Adjustment type ('all', 'dvd', 'split', '-', None).
  

**Returns**:

  DataFrame in long format with columns: ticker, date, field, value.
  For lazy backends, returns LazyFrame that must be collected.
  
  Example::
  
  # Async usage
  df = await abdh('AAPL US Equity', 'PX_LAST', start_date='2024-01-01')
  
  # Concurrent requests
  dfs = await asyncio.gather(
  abdh('AAPL US Equity', 'PX_LAST'),
  abdh('MSFT US Equity', 'PX_LAST'),
  )

<a id="xbbg.blp.abds"></a>

#### abds

```python
async def abds(tickers: str | Sequence[str],
               flds: str,
               *,
               backend: Backend | str | None = None,
               **kwargs)
```

Async Bloomberg bulk data (BDS).

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field name (bulk fields return multiple rows).
- `backend` - DataFrame backend to return. If None, uses global default.
- `**kwargs` - Bloomberg overrides and infrastructure options.
  

**Returns**:

  DataFrame with bulk data, multiple rows per ticker.
  
  Example::
  
  df = await abds('AAPL US Equity', 'DVD_Hist_All')
  df = await abds('SPX Index', 'INDX_MEMBERS', backend='polars')

<a id="xbbg.blp.abdib"></a>

#### abdib

```python
async def abdib(ticker: str,
                dt: str | None = None,
                session: str = "allday",
                typ: str = "TRADE",
                *,
                start_datetime: str | None = None,
                end_datetime: str | None = None,
                interval: int = 1,
                backend: Backend | str | None = None,
                request_tz: str | None = None,
                output_tz: str | None = None,
                **kwargs)
```

Async Bloomberg intraday bar data (BDIB).

**Arguments**:

- `ticker` - Ticker name.
- `dt` - Date to download (for single-day requests).
- `session` - Trading session name. Ignored when start_datetime/end_datetime provided.
- `typ` - Event type (TRADE, BID, ASK, etc.).
- `start_datetime` - Explicit start datetime for multi-day requests.
- `end_datetime` - Explicit end datetime for multi-day requests.
- `interval` - Bar interval in minutes (default: 1).
- `backend` - DataFrame backend to return. If None, uses global default.
- `request_tz` - Optional. How naive datetimes are interpreted before the Bloomberg call (`UTC`, `local`, `exchange`, `NY`/`LN`/…, reference ticker, or IANA). Resolved and converted to UTC in the Rust engine.
- `output_tz` - Optional. Relabel the `time` column to this IANA zone (same instants; Rust engine).
- `**kwargs` - Additional options.
  

**Returns**:

  DataFrame with intraday bar data.
  
  Example::
  
  df = await abdib('AAPL US Equity', dt='2024-12-01')
  df = await abdib('AAPL US Equity', start_datetime='2024-12-01 09:30',
  end_datetime='2024-12-01 16:00', interval=5, backend='polars')

<a id="xbbg.blp.abdtick"></a>

#### abdtick

```python
async def abdtick(ticker: str,
                  start_datetime: str,
                  end_datetime: str,
                  *,
                  event_types: Sequence[str] | None = None,
                  backend: Backend | str | None = None,
                  request_tz: str | None = None,
                  output_tz: str | None = None,
                  **kwargs)
```

Async Bloomberg tick data (BDTICK).

**Arguments**:

- `ticker` - Ticker name.
- `start_datetime` - Start datetime.
- `end_datetime` - End datetime.
- `event_types` - Event types (default TRADE).
- `backend` - DataFrame backend to return. If None, uses global default.
- `request_tz` - Optional. Same semantics as `abdib` (Rust engine).
- `output_tz` - Optional. Same semantics as `abdib` (Rust engine).
- `**kwargs` - Additional options.
  

**Returns**:

  DataFrame with tick data.
  
  Example::
  
  df = await abdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00')
  df = await abdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00', backend='polars')

<a id="xbbg.blp.bdp"></a>

#### bdp

```python
def bdp(tickers: str | Sequence[str],
        flds: str | Sequence[str] | None = None,
        *,
        backend: Backend | str | None = None,
        format: Format | str | None = None,
        field_types: dict[str, str] | None = None,
        **kwargs)
```

Bloomberg reference data (BDP).

Sync wrapper around abdp(). For async usage, use abdp() directly.

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field or list of fields to query.
- `backend` - DataFrame backend to return. If None, uses global default.
- `format` - Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, SEMI_LONG).
- `field_types` - Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
- `**kwargs` - Bloomberg overrides and infrastructure options.
  

**Returns**:

  DataFrame in long format with columns: ticker, field, value
  
  Example::
  
  df = bdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
  df = bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST', backend='polars')

<a id="xbbg.blp.bdh"></a>

#### bdh

```python
def bdh(tickers: str | Sequence[str],
        flds: str | Sequence[str] | None = None,
        start_date: str | None = None,
        end_date: str = "today",
        *,
        backend: Backend | str | None = None,
        format: Format | str | None = None,
        field_types: dict[str, str] | None = None,
        **kwargs)
```

Bloomberg historical data (BDH).

Sync wrapper around abdh(). For async usage, use abdh() directly.

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field or list of fields. Defaults to ['PX_LAST'].
- `start_date` - Start date. Defaults to 8 weeks before end_date.
- `end_date` - End date. Defaults to 'today'.
- `backend` - DataFrame backend to return. If None, uses global default.
- `format` - Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, SEMI_LONG).
- `field_types` - Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
- `**kwargs` - Additional overrides and infrastructure options.
  

**Returns**:

  DataFrame in long format with columns: ticker, date, field, value
  
  Example::
  
  df = bdh('AAPL US Equity', 'PX_LAST', start_date='2024-01-01')
  df = bdh(['AAPL', 'MSFT'], ['PX_LAST', 'VOLUME'], backend='polars')

<a id="xbbg.blp.bds"></a>

#### bds

```python
def bds(tickers: str | Sequence[str],
        flds: str,
        *,
        backend: Backend | str | None = None,
        **kwargs)
```

Bloomberg bulk data (BDS).

Sync wrapper around abds(). For async usage, use abds() directly.

**Arguments**:

- `tickers` - Single ticker or list of tickers.
- `flds` - Single field name (bulk fields return multiple rows).
- `backend` - DataFrame backend to return. If None, uses global default.
- `**kwargs` - Bloomberg overrides and infrastructure options.
  

**Returns**:

  DataFrame with bulk data, multiple rows per ticker.
  
  Example::
  
  df = bds('AAPL US Equity', 'DVD_Hist_All')
  df = bds('SPX Index', 'INDX_MEMBERS', backend='polars')

<a id="xbbg.blp.bdib"></a>

#### bdib

```python
def bdib(ticker: str,
         dt: str | None = None,
         session: str = "allday",
         typ: str = "TRADE",
         *,
         start_datetime: str | None = None,
         end_datetime: str | None = None,
         interval: int = 1,
         backend: Backend | str | None = None,
         request_tz: str | None = None,
         output_tz: str | None = None,
         **kwargs)
```

Bloomberg intraday bar data (BDIB).

Sync wrapper around abdib(). For async usage, use abdib() directly.

**Arguments**:

- `ticker` - Ticker name.
- `dt` - Date to download (for single-day requests).
- `session` - Trading session name.
- `typ` - Event type (TRADE, BID, ASK, etc.).
- `start_datetime` - Explicit start datetime for multi-day requests.
- `end_datetime` - Explicit end datetime for multi-day requests.
- `interval` - Bar interval in minutes (default: 1).
- `backend` - DataFrame backend to return. If None, uses global default.
- `request_tz` - Optional. Same as `abdib`.
- `output_tz` - Optional. Same as `abdib`.
- `**kwargs` - Additional options.
  

**Returns**:

  DataFrame with intraday bar data.
  
  Example::
  
  df = bdib('AAPL US Equity', dt='2024-12-01')
  df = bdib('AAPL US Equity', start_datetime='2024-12-01 09:30',
  end_datetime='2024-12-01 16:00', interval=5, backend='polars')

<a id="xbbg.blp.bdtick"></a>

#### bdtick

```python
def bdtick(ticker: str,
           start_datetime: str,
           end_datetime: str,
           *,
           event_types: Sequence[str] | None = None,
           backend: Backend | str | None = None,
           request_tz: str | None = None,
           output_tz: str | None = None,
           **kwargs)
```

Bloomberg tick data (BDTICK).

Sync wrapper around abdtick(). For async usage, use abdtick() directly.

**Arguments**:

- `ticker` - Ticker name.
- `start_datetime` - Start datetime.
- `end_datetime` - End datetime.
- `event_types` - Event types (default TRADE).
- `backend` - DataFrame backend to return. If None, uses global default.
- `request_tz` - Optional. Same as `abdib`.
- `output_tz` - Optional. Same as `abdib`.
- `**kwargs` - Additional options.
  

**Returns**:

  DataFrame with tick data.
  
  Example::
  
  df = bdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00')
  df = bdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00', backend='polars')

<a id="xbbg.blp.Tick"></a>

## Tick Objects

```python
@dataclass
class Tick()
```

Single tick data point from a subscription.

**Attributes**:

- `ticker` - Security identifier
- `field` - Bloomberg field name
- `value` - Field value (type depends on field)
- `timestamp` - Time the tick was received

<a id="xbbg.blp.Subscription"></a>

## Subscription Objects

```python
class Subscription()
```

Subscription handle with async iteration and dynamic control.

Supports:
- Async iteration: `async for tick in sub`
- Dynamic add/remove: `await sub.add(['MSFT US Equity'])`
- Context manager: `async with xbbg.asubscribe(...) as sub:`
- Explicit unsubscribe: `await sub.unsubscribe(drain=True)`

Example::

sub = await xbbg.asubscribe(['AAPL US Equity'], ['LAST_PRICE', 'BID'])

async for batch in sub:
# batch is pyarrow.RecordBatch
print(batch.to_pandas())

if should_add_msft:
await sub.add(['MSFT US Equity'])

await sub.unsubscribe()

<a id="xbbg.blp.Subscription.__init__"></a>

#### \_\_init\_\_

```python
def __init__(py_sub, raw: bool, backend: Backend | None)
```

Initialize subscription wrapper.

**Arguments**:

- `py_sub` - The underlying PySubscription from Rust
- `raw` - If True, yield raw Arrow batches
- `backend` - DataFrame backend for conversion (if not raw)

<a id="xbbg.blp.Subscription.__anext__"></a>

#### \_\_anext\_\_

```python
async def __anext__() -> pa.RecordBatch | nw.DataFrame
```

Get next batch of data.

<a id="xbbg.blp.Subscription.add"></a>

#### add

```python
async def add(tickers: str | list[str]) -> None
```

Add tickers to subscription dynamically.

**Arguments**:

- `tickers` - Single ticker or list of tickers to add

<a id="xbbg.blp.Subscription.remove"></a>

#### remove

```python
async def remove(tickers: str | list[str]) -> None
```

Remove tickers from subscription dynamically.

**Arguments**:

- `tickers` - Single ticker or list of tickers to remove

<a id="xbbg.blp.Subscription.tickers"></a>

#### tickers

```python
@property
def tickers() -> list[str]
```

Currently subscribed tickers.

<a id="xbbg.blp.Subscription.fields"></a>

#### fields

```python
@property
def fields() -> list[str]
```

Subscribed fields.

<a id="xbbg.blp.Subscription.is_active"></a>

#### is\_active

```python
@property
def is_active() -> bool
```

Whether the subscription is still active.

<a id="xbbg.blp.Subscription.unsubscribe"></a>

#### unsubscribe

```python
async def unsubscribe(drain: bool = False) -> list[pa.RecordBatch] | None
```

Close subscription and optionally drain remaining data.

**Arguments**:

- `drain` - If True, return any remaining buffered batches
  

**Returns**:

  List of remaining batches if drain=True, else None

<a id="xbbg.blp.asubscribe"></a>

#### asubscribe

```python
async def asubscribe(tickers: str | list[str],
                     fields: str | list[str],
                     *,
                     raw: bool = False,
                     backend: Backend | str | None = None) -> Subscription
```

Create an async subscription to real-time market data.

This is the low-level subscription API with full control over
the subscription lifecycle, including dynamic add/remove.

**Arguments**:

- `tickers` - Securities to subscribe to
- `fields` - Fields to subscribe to (e.g., 'LAST_PRICE', 'BID', 'ASK')
- `raw` - If True, yield raw Arrow RecordBatches for max performance
- `backend` - DataFrame backend for batch conversion (ignored if raw=True)
  

**Returns**:

  Subscription handle for iteration and control
  
  Example::
  
  # Basic usage
  sub = await xbbg.asubscribe(['AAPL US Equity'], ['LAST_PRICE', 'BID'])
  async for batch in sub:
  print(batch)
  await sub.unsubscribe()
  
  # With context manager
  async with xbbg.asubscribe(['AAPL US Equity'], ['LAST_PRICE']) as sub:
  count = 0
  async for batch in sub:
  print(batch)
  count += 1
  if count >= 10:
  break
  
  # Dynamic add/remove
  sub = await xbbg.asubscribe(['AAPL US Equity'], ['LAST_PRICE'])
  async for batch in sub:
  if should_add_msft:
  await sub.add(['MSFT US Equity'])
  if should_remove_aapl:
  await sub.remove(['AAPL US Equity'])

<a id="xbbg.blp.subscribe"></a>

#### subscribe

```python
def subscribe(tickers: str | list[str],
              fields: str | list[str],
              *,
              raw: bool = False,
              backend: Backend | str | None = None) -> Subscription
```

Create a subscription to real-time market data (sync version).

Note: This returns an async Subscription. Use in an async context
or call methods with asyncio.run().

For simple sync iteration, use stream() instead.

See asubscribe() for full documentation.

<a id="xbbg.blp.astream"></a>

#### astream

```python
async def astream(tickers: str | list[str],
                  fields: str | list[str],
                  *,
                  raw: bool = False,
                  backend: Backend | str | None = None)
```

High-level async streaming - simple iteration.

This is the simple API for streaming data. For dynamic add/remove,
use asubscribe() instead.

**Arguments**:

- `tickers` - Securities to subscribe to
- `fields` - Fields to subscribe to
- `raw` - If True, yield raw Arrow RecordBatches
- `backend` - DataFrame backend for batch conversion
  

**Yields**:

  Batches of market data (RecordBatch or DataFrame)
  
  Example::
  
  async for batch in xbbg.astream(['AAPL US Equity'], ['LAST_PRICE']):
  print(batch)
  if done:
  break

<a id="xbbg.blp.stream"></a>

#### stream

```python
def stream(tickers: str | list[str],
           fields: str | list[str],
           *,
           raw: bool = False,
           backend: Backend | str | None = None)
```

High-level sync streaming using a background thread.

Note: This is a generator that runs the async stream in a background
thread. Use astream() for async contexts.

**Arguments**:

- `tickers` - Securities to subscribe to
- `fields` - Fields to subscribe to
- `raw` - If True, yield raw Arrow RecordBatches
- `backend` - DataFrame backend for batch conversion
  

**Yields**:

  Batches of market data
  
  Example::
  
  for batch in xbbg.stream(['AAPL US Equity'], ['LAST_PRICE']):
  print(batch)
  if done:
  break

<a id="xbbg.blp.abql"></a>

#### abql

```python
async def abql(expression: str,
               *,
               backend: Backend | str | None = None) -> nw.DataFrame
```

Async Bloomberg Query Language (BQL) request.

BQL is Bloomberg's powerful query language for financial analytics.
It allows you to query data across universes of securities with
complex filters, calculations, and time series operations.

**Arguments**:

- `expression` - BQL expression string.
- `backend` - DataFrame backend to return. If None, uses global default.
  

**Returns**:

  DataFrame with columns: id, <field1>, <field2>, ...
  Where 'id' is the security identifier from the BQL universe.
  
  Example::
  
  # Get price for a single security
  df = await abql("get(px_last) for('AAPL US Equity')")
  
  # Get multiple fields
  df = await abql("get(px_last, volume) for('AAPL US Equity')")
  
  # Holdings of an ETF
  df = await abql("get(id_isin, weights) for(holdings('SPY US Equity'))")
  
  # Index members
  df = await abql("get(px_last) for(members('SPX Index'))")
  
  # With filters
  df = await abql("get(px_last, pe_ratio) for(members('SPX Index')) with(pe_ratio > 20)")
  
  # Time series
  df = await abql("get(px_last) for('AAPL US Equity') with(dates=range(-5d, 0d))")

<a id="xbbg.blp.bql"></a>

#### bql

```python
def bql(expression: str,
        *,
        backend: Backend | str | None = None) -> nw.DataFrame
```

Bloomberg Query Language (BQL) request.

Sync wrapper around abql(). For async usage, use abql() directly.

BQL is Bloomberg's powerful query language for financial analytics.
It allows you to query data across universes of securities with
complex filters, calculations, and time series operations.

**Arguments**:

- `expression` - BQL expression string.
- `backend` - DataFrame backend to return. If None, uses global default.
  

**Returns**:

  DataFrame with columns: id, <field1>, <field2>, ...
  Where 'id' is the security identifier from the BQL universe.
  
  Example::
  
  # Get price for a single security
  df = bql("get(px_last) for('AAPL US Equity')")
  
  # Holdings of an ETF
  df = bql("get(id_isin, weights) for(holdings('SPY US Equity'))")
  
  # Index members with filter
  df = bql("get(px_last, pe_ratio) for(members('SPX Index')) with(pe_ratio > 20)")

<a id="xbbg.blp.absrch"></a>

#### absrch

```python
async def absrch(domain: str,
                 *,
                 backend: Backend | str | None = None,
                 **kwargs) -> nw.DataFrame
```

Async Bloomberg Search (BSRCH) request.

BSRCH executes saved Bloomberg searches and returns matching securities.

**Arguments**:

- `domain` - The saved search domain/name (e.g., "FI:SOVR", "COMDTY:PRECIOUS").
- `backend` - DataFrame backend to return. If None, uses global default.
- `**kwargs` - Additional search parameters passed as request elements.
  

**Returns**:

  DataFrame with columns from the saved search results.
  
  Example::
  
  # Sovereign bonds
  df = await absrch("FI:SOVR")
  
  # With additional parameters
  df = await absrch("COMDTY:WEATHER", LOCATION="NYC", MODEL="GFS")

<a id="xbbg.blp.bsrch"></a>

#### bsrch

```python
def bsrch(domain: str,
          *,
          backend: Backend | str | None = None,
          **kwargs) -> nw.DataFrame
```

Bloomberg Search (BSRCH) request.

Sync wrapper around absrch(). For async usage, use absrch() directly.

BSRCH executes saved Bloomberg searches and returns matching securities.

**Arguments**:

- `domain` - The saved search domain/name (e.g., "FI:SOVR", "COMDTY:PRECIOUS").
- `backend` - DataFrame backend to return. If None, uses global default.
- `**kwargs` - Additional search parameters passed as request elements.
  

**Returns**:

  DataFrame with columns from the saved search results.
  
  Example::
  
  # Sovereign bonds
  df = bsrch("FI:SOVR")
  
  # With additional parameters
  df = bsrch("COMDTY:WEATHER", LOCATION="NYC", MODEL="GFS")

<a id="xbbg.blp.abfld"></a>

#### abfld

```python
async def abfld(fields: str | Sequence[str],
                *,
                backend: Backend | str | None = None) -> nw.DataFrame
```

Async Bloomberg Field Info (BFLD) request.

Get metadata about specific Bloomberg fields including description,
data type, and category.

**Arguments**:

- `fields` - Field name or list of field names (e.g., "PX_LAST", ["PX_LAST", "VOLUME"]).
- `backend` - DataFrame backend to return. If None, uses global default.
  

**Returns**:

  DataFrame with columns: field, datatype, description, category, etc.
  
  Example::
  
  # Get info for a single field
  df = await abfld("PX_LAST")
  
  # Get info for multiple fields
  df = await abfld(["PX_LAST", "VOLUME", "NAME"])

<a id="xbbg.blp.bfld"></a>

#### bfld

```python
def bfld(fields: str | Sequence[str],
         *,
         backend: Backend | str | None = None) -> nw.DataFrame
```

Bloomberg Field Info (BFLD) request.

Sync wrapper around abfld(). For async usage, use abfld() directly.

Get metadata about specific Bloomberg fields including description,
data type, and category.

**Arguments**:

- `fields` - Field name or list of field names (e.g., "PX_LAST", ["PX_LAST", "VOLUME"]).
- `backend` - DataFrame backend to return. If None, uses global default.
  

**Returns**:

  DataFrame with columns: field, datatype, description, category, etc.
  
  Example::
  
  # Get info for a single field
  df = bfld("PX_LAST")
  
  # Get info for multiple fields
  df = bfld(["PX_LAST", "VOLUME", "NAME"])

<a id="xbbg.blp.abops"></a>

#### abops

```python
async def abops(service: str | Service = Service.REFDATA) -> list[str]
```

List available operations for a Bloomberg service (async).

**Arguments**:

- `service` - Service URI or Service enum (default: //blp/refdata)
  

**Returns**:

  List of operation names.
  
  Example::
  
  >>> ops = await abops()
  >>> print(ops)
  ['ReferenceDataRequest', 'HistoricalDataRequest', ...]
  
  >>> ops = await abops("//blp/instruments")
  >>> print(ops)
  ['InstrumentListRequest', ...]

<a id="xbbg.blp.bops"></a>

#### bops

```python
def bops(service: str | Service = Service.REFDATA) -> list[str]
```

List available operations for a Bloomberg service.

Sync wrapper around abops(). For async usage, use abops() directly.

**Arguments**:

- `service` - Service URI or Service enum (default: //blp/refdata)
  

**Returns**:

  List of operation names.
  
  Example::
  
  >>> bops()
  ['ReferenceDataRequest', 'HistoricalDataRequest', ...]
  
  >>> bops("//blp/instruments")
  ['InstrumentListRequest', ...]

<a id="xbbg.blp.abschema"></a>

#### abschema

```python
async def abschema(service: str | Service = Service.REFDATA,
                   operation: str | Operation | None = None) -> dict
```

Get Bloomberg service or operation schema (async).

Returns introspected schema with element definitions, types, and enum values.
Schemas are cached locally (~/.xbbg/schemas/) for fast subsequent access.

**Arguments**:

- `service` - Service URI or Service enum (default: //blp/refdata)
- `operation` - Optional operation name. If None, returns full service schema.
  

**Returns**:

  Dictionary with schema information:
  - If operation is None: Full service schema with all operations
  - If operation is specified: Just that operation's request/response schema
  
  Example::
  
  >>> # Get full service schema
  >>> schema = await abschema()
  >>> print(schema['operations'][0]['name'])
  'ReferenceDataRequest'
  
  >>> # Get specific operation schema
  >>> op_schema = await abschema(operation="ReferenceDataRequest")
  >>> print(op_schema['request']['children'][0]['name'])
  'securities'
  
  >>> # Get enum values for an element
  >>> op = await abschema(operation="HistoricalDataRequest")
  >>> for child in op['request']['children']:
  ...     if child.get('enum_values'):
  ...         print(f"{child['name']}: {child['enum_values']}")

<a id="xbbg.blp.bschema"></a>

#### bschema

```python
def bschema(service: str | Service = Service.REFDATA,
            operation: str | Operation | None = None) -> dict
```

Get Bloomberg service or operation schema.

Sync wrapper around abschema(). For async usage, use abschema() directly.

Returns introspected schema with element definitions, types, and enum values.
Schemas are cached locally (~/.xbbg/schemas/) for fast subsequent access.

**Arguments**:

- `service` - Service URI or Service enum (default: //blp/refdata)
- `operation` - Optional operation name. If None, returns full service schema.
  

**Returns**:

  Dictionary with schema information.
  
  Example::
  
  >>> # List operations
  >>> schema = bschema()
  >>> [op['name'] for op in schema['operations']]
  ['ReferenceDataRequest', 'HistoricalDataRequest', ...]
  
  >>> # Get operation details
  >>> op = bschema(operation="ReferenceDataRequest")
  >>> [c['name'] for c in op['request']['children']]
  ['securities', 'fields', 'overrides', ...]
