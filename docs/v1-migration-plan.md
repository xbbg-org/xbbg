# xbbg v1.0 Migration Plan

## Overview

This document outlines the plan to migrate xbbg from pandas-only output to a
backend-agnostic architecture using Arrow internally and narwhals for output
conversion.

**Important**: This plan must be compatible with the Rust v1 branch API, which
already implements backend selection. The pure Python version should mirror
that API so users have a consistent experience.

## Goals

1. **Internal refactor**: Use Arrow as the internal data format
2. **Multi-backend support**: Return pandas, polars, arrow, or narwhals
3. **Multiple formats**: Support semi-long (default), long, and wide (pandas only)
4. **Backward compatibility**: Current behavior preserved with explicit options
5. **Smooth migration**: Warnings guide users to new defaults
6. **API compatibility**: Match the Rust v1 branch backend API

## Rust v1 Branch Reference

The Rust branch (py-xbbg/src/xbbg/blp.py) already implements:

```python
class Backend(str, Enum):
    NARWHALS = "narwhals"       # Default in v1
    PANDAS = "pandas"
    POLARS = "polars"
    POLARS_LAZY = "polars_lazy"
    PYARROW = "pyarrow"
    DUCKDB = "duckdb"

# Global default
set_backend(Backend.POLARS)

# Per-call override
df = bdp('AAPL US Equity', 'PX_LAST', backend=Backend.PANDAS)
```

**Data flow in Rust v1:**
```
User call → PyEngine.abdp() returns PyArrow Table
         → narwhals wraps it
         → _convert_backend() converts to requested format
```

We need to mirror this in pure Python so the API is identical.

## Release Timeline

| Version | Milestone |
|---------|-----------|
| 0.11    | Add options, refactor internals to Arrow, no warnings |
| 0.12    | Add deprecation warnings for implicit defaults |
| 1.0     | Flip defaults to `backend=Backend.NARWHALS`, `format=Format.LONG` |

---

## Phase 1: v0.11 — Foundation

### 1.1 Dependencies

- [x] Remove unused dependencies (pytest, python-stdnum from runtime)
- [x] Replace pytz with stdlib datetime.timezone
- [ ] Add narwhals as dependency
- [ ] Keep pyarrow (already present)

### 1.2 Add Backend Enum (matching Rust v1)

Create `xbbg/backend.py`:

```python
from enum import Enum

class Backend(str, Enum):
    """DataFrame backend for xbbg output.

    Matches the Rust v1 branch API for compatibility.
    """
    NARWHALS = "narwhals"
    PANDAS = "pandas"
    POLARS = "polars"
    POLARS_LAZY = "polars_lazy"
    PYARROW = "pyarrow"
    DUCKDB = "duckdb"

class Format(str, Enum):
    """Output format for xbbg data."""
    LONG = "long"             # Default in v1: ticker, date, field, value (tidy data)
    SEMI_LONG = "semi-long"   # ticker, date, field1, field2, ... (fields as columns)
    WIDE = "wide"             # Pandas only: MultiIndex columns (ticker, field)
```

### 1.3 Add Configuration System (matching Rust v1 API)

Create `xbbg/options.py`:

```python
from xbbg.backend import Backend, Format

# Module-level state (matching Rust v1 pattern)
_default_backend: Backend = Backend.PANDAS  # 0.x default, will flip to NARWHALS in 1.0
_default_format: Format = Format.WIDE       # 0.x default, will flip to LONG in 1.0

def get_backend() -> Backend:
    """Get the current default backend."""
    return _default_backend

def set_backend(backend: Backend | str) -> None:
    """Set the global default backend.

    Args:
        backend: Backend enum or string ('pandas', 'polars', etc.)

    Example:
        >>> import xbbg
        >>> xbbg.set_backend(Backend.POLARS)
        >>> xbbg.set_backend('polars')  # Also works
    """
    global _default_backend
    if isinstance(backend, str):
        backend = Backend(backend)
    _default_backend = backend

def get_format() -> Format:
    """Get the current default format."""
    return _default_format

def set_format(fmt: Format | str) -> None:
    """Set the global default output format.

    Args:
        fmt: Format enum or string ('semi-long', 'long', 'wide')
    """
    global _default_format
    if isinstance(fmt, str):
        fmt = Format(fmt)
    _default_format = fmt
```

### 1.3 Add Warning Infrastructure

Create `xbbg/deprecation.py`:

```python
import warnings

class XbbgFutureWarning(FutureWarning):
    """Warnings for xbbg 1.0 migration."""
    pass

_warned_defaults = False

def warn_defaults_changing():
    """Warn once per session about changing defaults."""
    global _warned_defaults
    if _warned_defaults:
        return
    _warned_defaults = True
    warnings.warn(
        "xbbg 1.0 will change defaults: backend='narwhals', format='semi-long'. "
        "Current: backend='pandas', format='wide'. "
        "Set explicitly to silence this warning. "
        "See https://github.com/alpha-xone/xbbg/issues/166",
        XbbgFutureWarning,
        stacklevel=4  # adjust based on call depth
    )
```

### 1.4 Add Output Conversion Layer (matching Rust v1 pattern)

Create `xbbg/io/convert.py`:

This mirrors the `_convert_backend()` function from the Rust v1 branch.

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import narwhals as nw
import pyarrow as pa

from xbbg.backend import Backend, Format

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


def _convert_backend(
    nw_frame: nw.DataFrame,
    backend: Backend,
) -> Any:
    """Convert narwhals DataFrame to requested backend.

    Mirrors the Rust v1 branch _convert_backend() function.

    Args:
        nw_frame: narwhals DataFrame (wrapping Arrow table)
        backend: Target backend

    Returns:
        DataFrame in requested backend format
    """
    match backend:
        case Backend.NARWHALS:
            return nw_frame
        case Backend.PANDAS:
            return nw_frame.to_pandas()
        case Backend.POLARS:
            return nw_frame.to_polars()
        case Backend.POLARS_LAZY:
            return nw_frame.to_polars().lazy()
        case Backend.PYARROW:
            return nw.to_native(nw_frame)
        case Backend.DUCKDB:
            import duckdb
            arrow_table = nw.to_native(nw_frame)
            return duckdb.from_arrow(arrow_table)
        case _:
            raise ValueError(f"Unknown backend: {backend}")


def to_output(
    arrow_table: pa.Table,
    backend: Backend = Backend.NARWHALS,
    format: Format = Format.LONG,
    ticker_col: str = 'ticker',
    date_col: str = 'date',
    field_cols: list[str] | None = None,
) -> Any:
    """Convert Arrow table to requested backend and format.

    Data flow (matching Rust v1):
        PyArrow Table → narwhals → format transform → _convert_backend()

    Args:
        arrow_table: Source data as PyArrow Table (in semi-long format internally)
        backend: Target backend (Backend enum)
        format: Output format (Format enum)
        ticker_col: Name of ticker column
        date_col: Name of date column
        field_cols: Field column names (for pivoting)

    Returns:
        DataFrame in requested backend and format
    """
    # Wrap in narwhals (same as Rust v1 pattern)
    df = nw.from_native(arrow_table)

    # Apply format transformation
    # Internal Arrow table is semi-long: ticker, date, field1, field2, ...
    if format == Format.LONG:
        # Unpivot field columns to true tidy/long format
        df = df.unpivot(
            on=field_cols,
            index=[ticker_col, date_col],
            variable_name='field',
            value_name='value'
        )
    elif format == Format.SEMI_LONG:
        # No transformation needed (this is what Arrow naturally produces)
        pass
    elif format == Format.WIDE:
        if backend != Backend.PANDAS:
            raise ValueError("format='wide' requires backend='pandas' (MultiIndex not supported elsewhere)")
        # Wide with MultiIndex (pandas only)
        pdf = df.to_pandas()
        return _apply_multiindex(pdf, ticker_col, date_col, field_cols)

    # Convert to requested backend
    return _convert_backend(df, backend)


def _apply_multiindex(
    df: pd.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str] | None,
) -> pd.DataFrame:
    """Convert semi-long pandas DataFrame to wide with MultiIndex columns.

    This preserves backward compatibility with current xbbg output format.
    """
    import pandas as pd

    # Pivot: date as index, (ticker, field) as MultiIndex columns
    result = df.pivot(index=date_col, columns=ticker_col, values=field_cols)

    # Reorder levels to (ticker, field)
    if isinstance(result.columns, pd.MultiIndex):
        result = result.swaplevel(axis=1).sort_index(axis=1)

    return result
```

### 1.5 Lower-Level Refactor (Arrow-First)

Instead of modifying each API function individually, we modify the pipeline layer.
All API functions automatically inherit backend/format support.

**Data flow:**
```
Bloomberg events → Arrow Table → narwhals transform → to_output()
```

#### Step 1: Add backend/format to DataRequest

`xbbg/core/domain/contracts.py`:

```python
from xbbg.backend import Backend, Format

@dataclass(frozen=True)
class DataRequest:
    # ... existing fields ...
    ticker: str
    dt: str | pd.Timestamp
    # ... etc ...

    # NEW: Output configuration
    backend: Backend | None = None
    format: Format | None = None
```

#### Step 2: Build Arrow in _fetch_from_bloomberg()

`xbbg/core/pipeline.py:350-358`:

```python
def _fetch_from_bloomberg(self, request, session_window) -> pa.Table | None:
    """Fetch data from Bloomberg, return as Arrow Table."""
    # ... existing request building ...

    # Collect events into lists (columnar)
    events = list(process.rec_events(
        func=self.config.process_func,
        event_queue=handle['event_queue'],
        timeout=timeout,
        max_timeouts=max_timeouts,
        **ctx_kwargs,
    ))

    if not events:
        return None

    # Build Arrow Table directly from dicts
    return pa.Table.from_pylist(events)
```

#### Step 3: Refactor Transformers to use narwhals

`xbbg/core/pipeline.py` - ResponseTransformerStrategy:

```python
class ResponseTransformerStrategy(Protocol):
    """Strategy for transforming Bloomberg responses."""

    def transform(
        self,
        raw_data: pa.Table,              # Changed from pd.DataFrame
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> nw.DataFrame:                    # Returns narwhals
        ...
```

Example transformer (HistoricalTransformer):

```python
class HistoricalTransformer:
    def transform(self, raw_data, request, exchange_info, session_window):
        import narwhals as nw

        df = nw.from_native(raw_data)

        # Sort by date
        df = df.sort('date')

        # Return in semi-long format (ticker, date, field1, field2, ...)
        return df
```

#### Step 4: Convert to output in BloombergPipeline.run()

`xbbg/core/pipeline.py:139-229`:

```python
def run(self, request: DataRequest) -> Any:
    # ... existing steps 1-7 ...

    # Step 8: Transform response (now returns narwhals DataFrame)
    transformed = self.config.transformer.transform(
        raw_data, request, resolver_result.exchange_info, session_window
    )

    # Step 9: Convert to requested backend/format
    from xbbg.io.convert import to_output
    from xbbg.options import get_backend, get_format
    from xbbg.deprecation import warn_defaults_changing

    backend = request.backend or get_backend()
    format = request.format or get_format()

    # Warn if using implicit defaults
    if request.backend is None or request.format is None:
        warn_defaults_changing()

    result = to_output(
        nw.to_native(transformed),  # Get Arrow table
        backend=backend,
        format=format,
        ticker_col='ticker',
        date_col='date',
        field_cols=self._get_field_cols(request),
    )

    # Step 10: Persist cache (cache in Arrow format)
    if request.cache_policy.enabled:
        self._persist_cache(transformed, request, session_window)

    return result
```

#### Step 5: Update API functions to pass backend/format

Each API function just needs to add `backend` and `format` parameters and pass them through:

```python
def bdh(tickers, flds, ..., backend=None, format=None):
    # ... existing logic to build DataRequest ...
    request = RequestBuilder(...).with_output(backend, format).build()
    return pipeline.run(request)
```

### 1.6 Files to Modify

| File | Changes |
|------|---------|
| `xbbg/core/domain/contracts.py` | Add `backend`, `format` to DataRequest |
| `xbbg/core/pipeline.py:350` | Build Arrow instead of pandas |
| `xbbg/core/pipeline.py:218` | Add to_output() conversion |
| `xbbg/core/pipeline.py:458+` | Refactor transformers to use narwhals |
| `xbbg/api/*` | Add `backend`, `format` params (pass-through only) |

### 1.7 Benefits of Lower-Level Approach

| Benefit | Description |
|---------|-------------|
| Single change point | Modify pipeline once, all APIs inherit |
| Arrow-native | No pandas→Arrow conversion overhead |
| Consistent | Same transformation logic for all endpoints |
| Testable | Test pipeline once, not each API function |
| Cache compatible | Cache stores Arrow (parquet), no conversion needed |

### 1.8 Testing

- [ ] Unit tests for `to_output()` with all backend/format combinations
- [ ] Regression tests: verify current output matches new output with `backend='pandas', format='wide'`
- [ ] Test each API function with new parameters
- [ ] Test global options

---

## Phase 2: v0.12 — Warnings

### 2.1 Enable Warnings

Modify API functions to warn when backend/format not explicitly set:

```python
def bdh(..., backend=None, format=None):
    from xbbg.deprecation import warn_defaults_changing

    # Warn if using implicit defaults
    if backend is None or format is None:
        warn_defaults_changing()

    backend = backend or options.backend
    format = format or options.format
    # ...
```

### 2.2 Documentation

- [ ] Update README with migration guide
- [ ] Update docstrings with deprecation notices
- [ ] Add examples showing explicit backend/format usage
- [ ] Document how to silence warnings

---

## Phase 3: v1.0 — New Defaults

### 3.1 Flip Defaults

In `xbbg/options.py`:

```python
def __init__(self):
    self._backend = 'narwhals'    # NEW default
    self._format = 'semi-long'    # NEW default
```

### 3.2 Remove Warnings

- Remove deprecation warnings (no longer needed)
- Keep `XbbgFutureWarning` class for future use

### 3.3 Update Documentation

- Update all examples to show new default output
- Remove migration notices

---

## Output Format Reference

### Semi-long (default in 1.0)
```
│ ticker         │ date       │ PX_LAST │ VOLUME    │
│ AAPL US Equity │ 2024-01-02 │ 185.5   │ 3825044   │
│ MSFT US Equity │ 2024-01-02 │ 372.2   │ 2194832   │
```

### Long
```
│ ticker         │ date       │ field   │ value     │
│ AAPL US Equity │ 2024-01-02 │ PX_LAST │ 185.5     │
│ AAPL US Equity │ 2024-01-02 │ VOLUME  │ 3825044   │
```

### Wide (pandas only)
```
                 │ AAPL US Equity      │ MSFT US Equity      │
                 │ PX_LAST │ VOLUME    │ PX_LAST │ VOLUME    │
date             │         │           │         │           │
2024-01-02       │ 185.5   │ 3825044   │ 372.2   │ 2194832   │
```

---

## Backend Compatibility Matrix

| Backend | semi-long | long | wide |
|---------|-----------|------|------|
| pandas | ✅ | ✅ | ✅ (MultiIndex) |
| polars | ✅ | ✅ | ❌ |
| arrow | ✅ | ✅ | ❌ |
| narwhals | ✅ | ✅ | ❌ |

---

## Migration Checklist

### v0.11
- [ ] Remove unused deps (pytest, python-stdnum, pytz)
- [ ] Add narwhals dependency
- [ ] Create `xbbg/options.py`
- [ ] Create `xbbg/deprecation.py`
- [ ] Create `xbbg/io/convert.py`
- [ ] Refactor `bdh()` to use Arrow internally
- [ ] Refactor `bdib()` to use Arrow internally
- [ ] Refactor `bdp()` to use Arrow internally
- [ ] Refactor `bds()` to use Arrow internally
- [ ] Add backend/format parameters to all API functions
- [ ] Write conversion tests
- [ ] Write regression tests
- [ ] Update type hints

### v0.12
- [ ] Enable deprecation warnings
- [ ] Write migration guide
- [ ] Update documentation

### v1.0
- [ ] Flip defaults
- [ ] Remove warnings
- [ ] Final documentation update
- [ ] Release notes
