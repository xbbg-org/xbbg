"""High-level Bloomberg data API: reference, historical, intraday.

This module provides the xbbg-compatible API using the Rust backend,
with support for multiple DataFrame backends via narwhals.

API Design:
- Async-first: Core implementation uses async/await (abdp, abdh, etc.)
- Sync wrappers: Convenience functions (bdp, bdh, etc.) wrap async with asyncio.run()
- Users can use either style based on their needs
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import TYPE_CHECKING
import warnings

import narwhals as nw
import pyarrow as pa

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class Backend(str, Enum):
    """DataFrame backend options for xbbg functions.

    Attributes:
        NARWHALS: Return narwhals DataFrame (default). Convert with .to_pandas(), .to_polars(), etc.
        NARWHALS_LAZY: Return narwhals LazyFrame. Call .collect() to materialize.
        PANDAS: Return pandas DataFrame directly.
        POLARS: Return polars DataFrame directly.
        POLARS_LAZY: Return polars LazyFrame directly. Call .collect() to materialize.
        PYARROW: Return pyarrow Table directly.
        DUCKDB: Return DuckDB relation (lazy). Call .df() or .arrow() to materialize.
    """

    NARWHALS = "narwhals"
    NARWHALS_LAZY = "narwhals_lazy"
    PANDAS = "pandas"
    POLARS = "polars"
    POLARS_LAZY = "polars_lazy"
    PYARROW = "pyarrow"
    DUCKDB = "duckdb"


__all__ = [
    "Backend",
    # Async API (primary)
    "abdp",
    "abdh",
    "abds",
    "abdib",
    "abdtick",
    # Sync API (wrappers)
    "bdp",
    "bdh",
    "bds",
    "bdib",
    "bdtick",
    # Config
    "set_backend",
    "get_backend",
]

# Backend configuration
_default_backend: Backend | None = None

# Lazy-load the engine to avoid import errors when the Rust module isn't built
_engine = None


def set_backend(backend: Backend | str | None) -> None:
    """Set the default DataFrame backend for all xbbg functions.

    Args:
        backend: The backend to use. Can be a Backend enum or string:
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
    """
    global _default_backend
    if backend is None:
        _default_backend = None
    elif isinstance(backend, Backend):
        _default_backend = backend
    elif isinstance(backend, str):
        try:
            _default_backend = Backend(backend)
        except ValueError:
            valid = [b.value for b in Backend]
            raise ValueError(f"Invalid backend: {backend}. Must be one of {valid}") from None
    else:
        raise TypeError(f"backend must be Backend, str, or None, not {type(backend).__name__}")


def get_backend() -> Backend | None:
    """Get the current default DataFrame backend."""
    return _default_backend


def _get_engine():
    """Get or create the shared engine instance."""
    global _engine
    if _engine is None:
        from . import _core

        _engine = _core.PyEngine()
    return _engine


def _normalize_tickers(tickers: str | Sequence[str]) -> list[str]:
    """Normalize ticker input to a list of strings."""
    if isinstance(tickers, str):
        return [tickers]
    return list(tickers)


def _normalize_fields(fields: str | Sequence[str] | None) -> list[str]:
    """Normalize field input to a list of strings."""
    if fields is None:
        return ["PX_LAST"]
    if isinstance(fields, str):
        return [fields]
    return list(fields)


def _extract_overrides(kwargs: dict) -> list[tuple[str, str]]:
    """Extract Bloomberg overrides from kwargs.

    Overrides can be passed as:
    - Individual kwargs (e.g., GICS_SECTOR_NAME='Energy')
    - An 'overrides' dict

    Returns list of (name, value) tuples.
    """
    overrides = []

    # Check for explicit overrides dict
    if "overrides" in kwargs:
        ovrd = kwargs.pop("overrides")
        if isinstance(ovrd, dict):
            overrides.extend((k, str(v)) for k, v in ovrd.items())
        elif isinstance(ovrd, list):
            overrides.extend((str(k), str(v)) for k, v in ovrd)

    # Known infrastructure keys to skip
    infra_keys = {
        "cache",
        "reload",
        "raw",
        "timeout",
        "host",
        "port",
        "log",
        "batch",
        "session",
        "interval",
        "typ",
        "adjust",
        "wide",
        "backend",
    }

    # Treat remaining kwargs as potential overrides
    for key in list(kwargs.keys()):
        if key not in infra_keys:
            val = kwargs.pop(key)
            overrides.append((key, str(val)))

    return overrides


def _fmt_date(dt: str | None, fmt: str = "%Y%m%d") -> str:
    """Format date to string."""
    if dt is None:
        return datetime.now().strftime(fmt)
    if isinstance(dt, str):
        if dt.lower() == "today":
            return datetime.now().strftime(fmt)
        # Try to parse and reformat
        try:
            return datetime.fromisoformat(dt).strftime(fmt)
        except (ValueError, TypeError):
            # Try common formats
            for parse_fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(dt, parse_fmt).strftime(fmt)
                except ValueError:
                    continue
            return dt
    return dt.strftime(fmt)


def _convert_backend(
    nw_df: nw.DataFrame,
    backend: Backend | str | None,
) -> nw.DataFrame | nw.LazyFrame | pa.Table:
    """Convert narwhals DataFrame to the requested backend.

    Args:
        nw_df: A narwhals DataFrame
        backend: Target backend (Backend enum, string, or None)

    Returns:
        DataFrame/LazyFrame in the requested backend format
    """
    # Resolve effective backend
    effective = (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend

    if effective == Backend.PANDAS:
        return nw_df.to_pandas()
    if effective == Backend.POLARS:
        return nw_df.to_native()
    if effective == Backend.POLARS_LAZY:
        # Convert to polars LazyFrame
        return nw_df.to_native().lazy()
    if effective == Backend.PYARROW:
        # narwhals doesn't have direct to_arrow, go through polars or pandas
        try:
            # polars import needed to check if available for to_arrow()
            import polars as _  # noqa: F401

            return nw_df.to_native().to_arrow()
        except ImportError:
            return pa.Table.from_pandas(nw_df.to_pandas())
    if effective == Backend.NARWHALS_LAZY:
        # Return narwhals LazyFrame (backed by polars)
        return nw_df.lazy()
    if effective == Backend.DUCKDB:
        # Convert to DuckDB relation via narwhals lazy with duckdb backend
        return nw_df.lazy(backend="duckdb")
    # Default: return narwhals DataFrame
    return nw_df


def _handle_wide_deprecation(wide: bool | None, kwargs: dict) -> bool:
    """Handle the deprecated wide parameter.

    Returns True if wide format was requested (with warning).
    """
    if wide is True:
        warnings.warn(
            "wide=True is deprecated and will be removed in v2.0. "
            "Data is now returned in long format by default. "
            "Use df.pivot(on='field', index=['ticker', 'date'], values='value') "
            "to convert to wide format.",
            DeprecationWarning,
            stacklevel=4,
        )
        return True
    return False


# =============================================================================
# Async API - Primary Implementation
# =============================================================================


async def abdp(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    *,
    backend: Backend | str | None = None,
    wide: bool | None = None,
    **kwargs,
):
    """Async Bloomberg reference data (BDP).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: DataFrame backend to return. If None, uses global default.
            Supports lazy backends: 'polars_lazy', 'narwhals_lazy', 'duckdb'.
        wide: DEPRECATED. Use df.pivot() for wide format.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
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
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)
    overrides = _extract_overrides(kwargs)
    want_wide = _handle_wide_deprecation(wide, kwargs)

    # Await the async Rust call
    table = await engine.abdp(ticker_list, field_list, overrides, False)

    # Wrap in narwhals
    nw_df = nw.from_native(table)

    # Handle deprecated wide format
    if want_wide:
        nw_df = nw_df.pivot(on="field", index="ticker", values="value")

    return _convert_backend(nw_df, backend)


async def abdh(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str = "today",
    *,
    backend: Backend | str | None = None,
    wide: bool | None = None,
    **kwargs,
):
    """Async Bloomberg historical data (BDH).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields. Defaults to ['PX_LAST'].
        start_date: Start date. Defaults to 8 weeks before end_date.
        end_date: End date. Defaults to 'today'.
        backend: DataFrame backend to return. If None, uses global default.
            Supports lazy backends: 'polars_lazy', 'narwhals_lazy', 'duckdb'.
        wide: DEPRECATED. Use df.pivot() for wide format.
        **kwargs: Additional overrides and infrastructure options.
            adjust: Adjustment type ('all', 'dvd', 'split', '-', None).

    Returns:
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
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)
    want_wide = _handle_wide_deprecation(wide, kwargs)

    # Handle dates
    e_dt = _fmt_date(end_date, "%Y%m%d")
    if start_date is None:
        end_dt_parsed = datetime.strptime(e_dt, "%Y%m%d")
        s_dt = (end_dt_parsed - timedelta(weeks=8)).strftime("%Y%m%d")
    else:
        s_dt = _fmt_date(start_date, "%Y%m%d")

    # Extract options
    options = []
    adjust = kwargs.pop("adjust", None)
    if adjust:
        if adjust == "all":
            options.append(("adjustmentSplit", "true"))
            options.append(("adjustmentNormal", "true"))
            options.append(("adjustmentAbnormal", "true"))
        elif adjust == "dvd":
            options.append(("adjustmentNormal", "true"))
            options.append(("adjustmentAbnormal", "true"))
        elif adjust == "split":
            options.append(("adjustmentSplit", "true"))
        elif adjust == "-":
            pass  # No adjustments

    # Add any remaining overrides as options
    overrides = _extract_overrides(kwargs)
    options.extend(overrides)

    # Await the async Rust call
    table = await engine.abdh(ticker_list, field_list, s_dt, e_dt, options)
    nw_df = nw.from_native(table)

    # Handle deprecated wide format
    if want_wide:
        nw_df = nw_df.pivot(on="field", index=["ticker", "date"], values="value")

    return _convert_backend(nw_df, backend)


async def abds(
    tickers: str | Sequence[str],
    flds: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Async Bloomberg bulk data (BDS).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field name (bulk fields return multiple rows).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        DataFrame with bulk data, multiple rows per ticker.

    Example::

        df = await abds('AAPL US Equity', 'DVD_Hist_All')
        df = await abds('SPX Index', 'INDX_MEMBERS', backend='polars')
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    overrides = _extract_overrides(kwargs)

    # Process each ticker
    tables = []
    for ticker in ticker_list:
        table = await engine.abds(ticker, flds, overrides)
        tables.append(table)

    if not tables:
        # Return empty narwhals DataFrame
        empty = pa.table({"ticker": [], "field": [], "value": []})
        return _convert_backend(nw.from_native(empty), backend)

    # Concatenate tables
    combined = pa.concat_tables(tables)
    nw_df = nw.from_native(combined)

    return _convert_backend(nw_df, backend)


async def abdib(
    ticker: str,
    dt: str | None = None,
    session: str = "allday",
    typ: str = "TRADE",
    *,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    interval: int = 1,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Async Bloomberg intraday bar data (BDIB).

    Args:
        ticker: Ticker name.
        dt: Date to download (for single-day requests).
        session: Trading session name. Ignored when start_datetime/end_datetime provided.
        typ: Event type (TRADE, BID, ASK, etc.).
        start_datetime: Explicit start datetime for multi-day requests.
        end_datetime: Explicit end datetime for multi-day requests.
        interval: Bar interval in minutes (default: 1).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional options.

    Returns:
        DataFrame with intraday bar data.

    Example::

        df = await abdib('AAPL US Equity', dt='2024-12-01')
        df = await abdib('AAPL US Equity', start_datetime='2024-12-01 09:30',
                  end_datetime='2024-12-01 16:00', interval=5, backend='polars')
    """
    engine = _get_engine()

    # Determine datetime range
    if start_datetime is not None and end_datetime is not None:
        s_dt = datetime.fromisoformat(start_datetime.replace(" ", "T")).isoformat()
        e_dt = datetime.fromisoformat(end_datetime.replace(" ", "T")).isoformat()
    elif dt is not None:
        # Single day request - use full day
        cur_dt = datetime.fromisoformat(dt.replace(" ", "T")).strftime("%Y-%m-%d")
        s_dt = f"{cur_dt}T00:00:00"
        e_dt = f"{cur_dt}T23:59:59"
    else:
        raise ValueError("Either dt or both start_datetime and end_datetime must be provided")

    table = await engine.abdib(ticker, typ, interval, s_dt, e_dt)
    nw_df = nw.from_native(table)

    return _convert_backend(nw_df, backend)


async def abdtick(
    ticker: str,
    start_datetime: str,
    end_datetime: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Async Bloomberg tick data (BDTICK).

    Args:
        ticker: Ticker name.
        start_datetime: Start datetime.
        end_datetime: End datetime.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional options.

    Returns:
        DataFrame with tick data.

    Example::

        df = await abdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00')
        df = await abdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00', backend='polars')
    """
    engine = _get_engine()

    s_dt = datetime.fromisoformat(start_datetime.replace(" ", "T")).isoformat()
    e_dt = datetime.fromisoformat(end_datetime.replace(" ", "T")).isoformat()

    table = await engine.abdtick(ticker, s_dt, e_dt)
    nw_df = nw.from_native(table)

    return _convert_backend(nw_df, backend)


# =============================================================================
# Sync API - Convenience Wrappers
# =============================================================================


def bdp(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    *,
    backend: Backend | str | None = None,
    wide: bool | None = None,
    **kwargs,
):
    """Bloomberg reference data (BDP).

    Sync wrapper around abdp(). For async usage, use abdp() directly.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: DataFrame backend to return. If None, uses global default.
        wide: DEPRECATED. Use df.pivot() for wide format.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        DataFrame in long format with columns: ticker, field, value

    Example::

        df = bdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
        df = bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST', backend='polars')
    """
    return asyncio.run(abdp(tickers, flds, backend=backend, wide=wide, **kwargs))


def bdh(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str = "today",
    *,
    backend: Backend | str | None = None,
    wide: bool | None = None,
    **kwargs,
):
    """Bloomberg historical data (BDH).

    Sync wrapper around abdh(). For async usage, use abdh() directly.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields. Defaults to ['PX_LAST'].
        start_date: Start date. Defaults to 8 weeks before end_date.
        end_date: End date. Defaults to 'today'.
        backend: DataFrame backend to return. If None, uses global default.
        wide: DEPRECATED. Use df.pivot() for wide format.
        **kwargs: Additional overrides and infrastructure options.

    Returns:
        DataFrame in long format with columns: ticker, date, field, value

    Example::

        df = bdh('AAPL US Equity', 'PX_LAST', start_date='2024-01-01')
        df = bdh(['AAPL', 'MSFT'], ['PX_LAST', 'VOLUME'], backend='polars')
    """
    return asyncio.run(abdh(tickers, flds, start_date, end_date, backend=backend, wide=wide, **kwargs))


def bds(
    tickers: str | Sequence[str],
    flds: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Bloomberg bulk data (BDS).

    Sync wrapper around abds(). For async usage, use abds() directly.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field name (bulk fields return multiple rows).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        DataFrame with bulk data, multiple rows per ticker.

    Example::

        df = bds('AAPL US Equity', 'DVD_Hist_All')
        df = bds('SPX Index', 'INDX_MEMBERS', backend='polars')
    """
    return asyncio.run(abds(tickers, flds, backend=backend, **kwargs))


def bdib(
    ticker: str,
    dt: str | None = None,
    session: str = "allday",
    typ: str = "TRADE",
    *,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    interval: int = 1,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Bloomberg intraday bar data (BDIB).

    Sync wrapper around abdib(). For async usage, use abdib() directly.

    Args:
        ticker: Ticker name.
        dt: Date to download (for single-day requests).
        session: Trading session name.
        typ: Event type (TRADE, BID, ASK, etc.).
        start_datetime: Explicit start datetime for multi-day requests.
        end_datetime: Explicit end datetime for multi-day requests.
        interval: Bar interval in minutes (default: 1).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional options.

    Returns:
        DataFrame with intraday bar data.

    Example::

        df = bdib('AAPL US Equity', dt='2024-12-01')
        df = bdib('AAPL US Equity', start_datetime='2024-12-01 09:30',
                  end_datetime='2024-12-01 16:00', interval=5, backend='polars')
    """
    return asyncio.run(
        abdib(
            ticker,
            dt,
            session,
            typ,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval=interval,
            backend=backend,
            **kwargs,
        )
    )


def bdtick(
    ticker: str,
    start_datetime: str,
    end_datetime: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
):
    """Bloomberg tick data (BDTICK).

    Sync wrapper around abdtick(). For async usage, use abdtick() directly.

    Args:
        ticker: Ticker name.
        start_datetime: Start datetime.
        end_datetime: End datetime.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional options.

    Returns:
        DataFrame with tick data.

    Example::

        df = bdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00')
        df = bdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00', backend='polars')
    """
    return asyncio.run(abdtick(ticker, start_datetime, end_datetime, backend=backend, **kwargs))
