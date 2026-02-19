---
title: Services and Enums  
description: Bloomberg service definitions, operations, and enums
---

  xbbg.services.RequestParams: 168
<a id="xbbg.services"></a>

# xbbg.services

Bloomberg service definitions and request parameters.

This module defines the Bloomberg services, operations, and request parameters
used by the xbbg API. These definitions are the authoritative source for
service/operation names - the Rust layer accepts these as strings.

**Example**:

  from xbbg import Service, Operation, RequestParams
  
  params = RequestParams(
  service=Service.REFDATA,
  operation=Operation.REFERENCE_DATA,
  securities=['AAPL US Equity'],
  fields=['PX_LAST'],
  )

<a id="xbbg.services.Service"></a>

## Service Objects

```python
class Service(str, Enum)
```

Bloomberg service URIs.

These are the standard Bloomberg API services. Power users can also
use raw service URI strings for services not listed here.

<a id="xbbg.services.Service.REFDATA"></a>

#### REFDATA

Reference data service for bdp, bdh, bds, bdib, bdtick requests.

<a id="xbbg.services.Service.MKTDATA"></a>

#### MKTDATA

Real-time market data subscriptions.

<a id="xbbg.services.Service.APIFLDS"></a>

#### APIFLDS

Field metadata service for field info and search.

<a id="xbbg.services.Operation"></a>

## Operation Objects

```python
class Operation(str, Enum)
```

Bloomberg request operation names.

These correspond to Bloomberg API request types. Power users can also
use raw operation name strings for operations not listed here.

<a id="xbbg.services.Operation.REFERENCE_DATA"></a>

#### REFERENCE\_DATA

Single point-in-time data (bdp, bds).

<a id="xbbg.services.Operation.HISTORICAL_DATA"></a>

#### HISTORICAL\_DATA

Historical time series data (bdh).

<a id="xbbg.services.Operation.INTRADAY_BAR"></a>

#### INTRADAY\_BAR

Intraday OHLCV bars (bdib).

<a id="xbbg.services.Operation.INTRADAY_TICK"></a>

#### INTRADAY\_TICK

Intraday tick data (bdtick).

<a id="xbbg.services.Operation.FIELD_INFO"></a>

#### FIELD\_INFO

Get field metadata (type, description).

<a id="xbbg.services.Operation.FIELD_SEARCH"></a>

#### FIELD\_SEARCH

Search for fields by keyword.

<a id="xbbg.services.OutputMode"></a>

## OutputMode Objects

```python
class OutputMode(str, Enum)
```

Output format for generic requests.

Controls how Bloomberg responses are converted before returning to Python.

<a id="xbbg.services.OutputMode.ARROW"></a>

#### ARROW

Convert to Arrow RecordBatch using appropriate extractor.

For known operations (bdp, bdh, etc.), uses optimized extractors.
For unknown operations, uses a generic flattener.

<a id="xbbg.services.OutputMode.JSON"></a>

#### JSON

Return raw JSON as a single-column Arrow table.

Useful for debugging or when you need the full Bloomberg response structure.

<a id="xbbg.services.ExtractorHint"></a>

## ExtractorHint Objects

```python
class ExtractorHint(str, Enum)
```

Hint for which Arrow extractor to use.

This is typically auto-detected from the operation, but can be
overridden for custom use cases.

<a id="xbbg.services.ExtractorHint.REFDATA"></a>

#### REFDATA

Reference data extractor: [ticker, field, value, ...]

<a id="xbbg.services.ExtractorHint.HISTDATA"></a>

#### HISTDATA

Historical data extractor: [ticker, date, field, value, ...]

<a id="xbbg.services.ExtractorHint.BULK"></a>

#### BULK

Bulk data extractor: [ticker, field, row_idx, col1, col2, ...]

<a id="xbbg.services.ExtractorHint.INTRADAY_BAR"></a>

#### INTRADAY\_BAR

Intraday bar extractor: [ticker, time, open, high, low, close, volume, ...]

<a id="xbbg.services.ExtractorHint.INTRADAY_TICK"></a>

#### INTRADAY\_TICK

Intraday tick extractor: [ticker, time, type, value, size, ...]

<a id="xbbg.services.ExtractorHint.GENERIC"></a>

#### GENERIC

Generic flattener: [path, type, value_str, value_num, value_date]

<a id="xbbg.services.ExtractorHint.RAW_JSON"></a>

#### RAW\_JSON

Raw JSON output: [json]

<a id="xbbg.services.ExtractorHint.FIELD_INFO"></a>

#### FIELD\_INFO

Field info extractor: [field, type, description, category]

<a id="xbbg.services.Format"></a>

## Format Objects

```python
class Format(str, Enum)
```

Output format for reference data (bdp/bdh).

Controls the shape and typing of the output DataFrame.

<a id="xbbg.services.Format.LONG"></a>

#### LONG

Long format with all values as strings (default, backwards-compatible).

Columns: ticker, field, value

<a id="xbbg.services.Format.LONG_TYPED"></a>

#### LONG\_TYPED

Long format with typed value columns.

Columns: ticker, field, value_f64, value_i64, value_str, value_bool, value_date, value_ts
Each row populates one value column based on the field's data type.

<a id="xbbg.services.Format.LONG_WITH_METADATA"></a>

#### LONG\_WITH\_METADATA

Long format with string values and dtype metadata column.

Columns: ticker, field, value, dtype
The dtype column contains the Arrow type name (float64, int64, string, etc.)

<a id="xbbg.services.Format.WIDE"></a>

#### WIDE

Wide format with fields as columns (DEPRECATED).

Use df.pivot(on='field', index='ticker', values='value') instead.

<a id="xbbg.services.RequestParams"></a>

## RequestParams Objects

```python
@dataclass
class RequestParams()
```

Validated request parameters for the Bloomberg API.

This dataclass holds all possible parameters for Bloomberg requests.
Not all parameters are used for all request types - the Python layer
validates that required parameters are present for each operation.

Parameters are validated before being sent to the Rust layer.

**Attributes**:

- `service` - Bloomberg service URI (e.g., "//blp/refdata").
- `operation` - Request operation name (e.g., "ReferenceDataRequest").
- `securities` - List of security identifiers (for multi-security requests).
- `security` - Single security identifier (for intraday requests).
- `fields` - List of field names to retrieve.
- `overrides` - List of (field, value) tuples for field overrides.
- `elements` - List of (name, value) tuples for generic request elements (BQL, bsrch).
- `start_date` - Start date for historical requests (YYYYMMDD format).
- `end_date` - End date for historical requests (YYYYMMDD format).
- `start_datetime` - Start datetime for intraday requests (ISO format).
- `end_datetime` - End datetime for intraday requests (ISO format).
- `event_type` - Event type for intraday bars (TRADE, BID, ASK, etc.).
- `interval` - Bar interval in minutes for intraday bars.
- `options` - Additional Bloomberg options as (key, value) tuples.
- `field_types` - Manual type overrides for fields (for issue `168`).
- `output` - Output format (arrow or json).
- `extractor` - Override the auto-detected extractor hint.
- `format` - Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, WIDE).

<a id="xbbg.services.RequestParams.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__() -> None
```

Convert enums to strings and set defaults.

<a id="xbbg.services.RequestParams.validate"></a>

#### validate

```python
def validate() -> None
```

Validate parameters for the given operation.

**Raises**:

- `BlpValidationError` - If required parameters are missing or invalid.

<a id="xbbg.services.RequestParams.to_dict"></a>

#### to\_dict

```python
def to_dict() -> dict
```

Convert to dictionary for passing to Rust.

**Returns**:

  Dictionary with only non-None values, suitable for Rust consumption.

