"""High-level Bloomberg data API: reference, historical, intraday.

This module provides the xbbg-compatible API using the Rust backend,
with support for multiple DataFrame backends via narwhals.

API Design:
- Async-first: Core implementation uses async/await (abdp, abdh, etc.)
- Sync wrappers: Convenience functions (bdp, bdh, etc.) wrap async with asyncio.run()
- Generic API: arequest() and request() for power users and arbitrary Bloomberg requests
- Users can use either style based on their needs
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from typing import TYPE_CHECKING, Any
import warnings

import narwhals.stable.v1 as nw
import pyarrow as pa

from xbbg.services import (
    ExtractorHint,
    Format,
    Operation,
    OutputMode,
    RequestParams,
    Service,
)

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
    "EngineConfig",
    # Generic API (power users)
    "arequest",
    "request",
    # Async API (typed convenience)
    "abdp",
    "abdh",
    "abds",
    "abdib",
    "abdtick",
    "abql",
    "absrch",
    "abfld",
    # Sync API (wrappers)
    "bdp",
    "bdh",
    "bds",
    "bdib",
    "bdtick",
    "bql",
    "bsrch",
    "bfld",
    # Streaming API
    "Tick",
    "Subscription",
    "asubscribe",
    "subscribe",
    "astream",
    "stream",
    # Config
    "configure",
    "set_backend",
    "get_backend",
    # Re-exports from services
    "Service",
    "Operation",
    "OutputMode",
    "RequestParams",
    "ExtractorHint",
    # Schema introspection
    "abops",
    "bops",
    "abschema",
    "bschema",
]


@dataclass
class EngineConfig:
    """Configuration for the xbbg Engine.

    All settings have sensible defaults - you only need to specify what you want to change.

    Attributes:
        host: Bloomberg server host (default: "localhost")
        port: Bloomberg server port (default: 8194)
        request_pool_size: Number of pre-warmed request workers (default: 2)
        subscription_pool_size: Number of pre-warmed subscription sessions (default: 4)

    Example::

        from xbbg import configure, EngineConfig

        # Configure before first request
        configure(EngineConfig(
            request_pool_size=4,
            subscription_pool_size=8,
        ))

        # Or use configure() with keyword arguments
        configure(request_pool_size=4, subscription_pool_size=8)
    """

    host: str = "localhost"
    port: int = 8194
    request_pool_size: int = 2
    subscription_pool_size: int = 4


# Backend configuration
_default_backend: Backend | None = None

# Engine configuration (set before first use)
_config: EngineConfig | None = None

# Lazy-load the engine to avoid import errors when the Rust module isn't built
_engine = None


def configure(
    config: EngineConfig | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    request_pool_size: int | None = None,
    subscription_pool_size: int | None = None,
) -> None:
    """Configure the xbbg engine before first use.

    This function must be called before any Bloomberg request is made.
    If called after the engine has started, a RuntimeError is raised.

    Can be called with either an EngineConfig object or keyword arguments.

    Args:
        config: An EngineConfig object with all settings.
        host: Bloomberg server host (default: "localhost")
        port: Bloomberg server port (default: 8194)
        request_pool_size: Number of pre-warmed request workers (default: 2)
        subscription_pool_size: Number of pre-warmed subscription sessions (default: 4)

    Raises:
        RuntimeError: If called after the engine has already started.

    Example::

        import xbbg

        # Option 1: Using keyword arguments
        xbbg.configure(request_pool_size=4, subscription_pool_size=8)

        # Option 2: Using EngineConfig object
        from xbbg import EngineConfig
        xbbg.configure(EngineConfig(request_pool_size=4))

        # Now make requests - configuration takes effect
        df = xbbg.bdp("AAPL US Equity", "PX_LAST")
    """
    global _config, _engine

    if _engine is not None:
        raise RuntimeError(
            "Cannot configure after engine has started. "
            "Call xbbg.configure() before any Bloomberg request."
        )

    if config is not None:
        # Use the provided config, optionally overriding with kwargs
        _config = EngineConfig(
            host=host if host is not None else config.host,
            port=port if port is not None else config.port,
            request_pool_size=request_pool_size if request_pool_size is not None else config.request_pool_size,
            subscription_pool_size=subscription_pool_size
            if subscription_pool_size is not None
            else config.subscription_pool_size,
        )
    else:
        # Build config from kwargs, using defaults for unspecified values
        _config = EngineConfig(
            host=host if host is not None else "localhost",
            port=port if port is not None else 8194,
            request_pool_size=request_pool_size if request_pool_size is not None else 2,
            subscription_pool_size=subscription_pool_size if subscription_pool_size is not None else 4,
        )

    logger.info(
        "Engine configured: host=%s port=%d request_pool=%d subscription_pool=%d",
        _config.host,
        _config.port,
        _config.request_pool_size,
        _config.subscription_pool_size,
    )


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

        if _config is not None:
            # Use user-provided configuration
            logger.debug(
                "Creating PyEngine with config: host=%s port=%d request_pool=%d subscription_pool=%d",
                _config.host,
                _config.port,
                _config.request_pool_size,
                _config.subscription_pool_size,
            )
            py_config = _core.PyEngineConfig(
                host=_config.host,
                port=_config.port,
                request_pool_size=_config.request_pool_size,
                subscription_pool_size=_config.subscription_pool_size,
            )
            _engine = _core.PyEngine.with_config(py_config)
        else:
            # Use defaults
            logger.debug("Creating new PyEngine instance with default config")
            _engine = _core.PyEngine()
        logger.info("PyEngine connected to Bloomberg")
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




# =============================================================================
# Generic API - Power Users
# =============================================================================


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
):
    """Async generic Bloomberg request.

    This is the low-level API for power users who need to:
    - Send requests to arbitrary Bloomberg services
    - Use operations not covered by the typed convenience functions
    - Get raw JSON responses for debugging

    For common use cases, prefer the typed functions: abdp, abdh, abds, abdib, abdtick.

    Args:
        service: Bloomberg service URI (e.g., Service.REFDATA or "//blp/refdata").
        operation: Request operation name (e.g., Operation.REFERENCE_DATA).
        securities: List of security identifiers (for multi-security requests).
        security: Single security identifier (for intraday requests).
        fields: List of field names to retrieve.
        overrides: Field overrides as dict or list of (name, value) tuples.
        start_date: Start date for historical requests (YYYYMMDD format).
        end_date: End date for historical requests (YYYYMMDD format).
        start_datetime: Start datetime for intraday requests (ISO format).
        end_datetime: End datetime for intraday requests (ISO format).
        event_type: Event type for intraday bars (TRADE, BID, ASK, etc.).
        interval: Bar interval in minutes for intraday bars.
        options: Additional Bloomberg options as dict or list of (key, value) tuples.
        field_types: Manual type overrides for fields (for future type resolution).
        output: Output format: OutputMode.ARROW (default) or OutputMode.JSON.
        extractor: Override the auto-detected extractor. Use ExtractorHint.BULK for
            bulk data fields. If None, auto-detected from operation.
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
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
    """
    # Normalize inputs
    securities_list: list[str] | None = None
    if securities is not None:
        securities_list = [securities] if isinstance(securities, str) else list(securities)

    fields_list: list[str] | None = None
    if fields is not None:
        fields_list = [fields] if isinstance(fields, str) else list(fields)

    overrides_list: list[tuple[str, str]] | None = None
    elements_list: list[tuple[str, str]] | None = None
    if overrides is not None:
        override_tuples = [(k, str(v)) for k, v in overrides.items()] if isinstance(overrides, dict) else list(overrides)
        # For BQL and bsrch services, pass overrides as generic elements (not Bloomberg field overrides)
        service_str = service.value if isinstance(service, Service) else service
        if service_str in ("//blp/bqlsvc", "//blp/exrsvc"):
            elements_list = override_tuples
        else:
            overrides_list = override_tuples

    options_list: list[tuple[str, str]] | None = None
    if options is not None:
        options_list = [(k, str(v)) for k, v in options.items()] if isinstance(options, dict) else list(options)

    # Normalize extractor hint
    extractor_hint: ExtractorHint | None = None
    if extractor is not None:
        extractor_hint = ExtractorHint(extractor) if isinstance(extractor, str) else extractor

    # Normalize format
    format_hint: Format | None = None
    if format is not None:
        format_hint = Format(format) if isinstance(format, str) else format

    # Build and validate params
    params = RequestParams(
        service=service,
        operation=operation,
        securities=securities_list,
        security=security,
        fields=fields_list,
        overrides=overrides_list,
        elements=elements_list,
        start_date=start_date,
        end_date=end_date,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        event_type=event_type,
        interval=interval,
        options=options_list,
        field_types=field_types,
        output=OutputMode(output) if isinstance(output, str) else output,
        extractor=extractor_hint,
        format=format_hint,
    )
    params.validate()
    logger.debug(
        "Request validated: service=%s operation=%s securities=%s fields=%s",
        params.service,
        params.operation,
        securities_list,
        fields_list,
    )

    # Get engine and send request
    engine = _get_engine()
    params_dict = params.to_dict()

    # Call the generic request method on the engine
    logger.debug("Sending request to Rust engine")
    batch = await engine.request(params_dict)
    logger.debug("Received response: %d rows", batch.num_rows)

    # Convert RecordBatch to Table for narwhals native support (zero-copy)
    table = pa.Table.from_batches([batch])
    nw_df = nw.from_native(table)
    return _convert_backend(nw_df, backend)


def request(
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
    backend: Backend | str | None = None,
):
    """Generic Bloomberg request (sync wrapper).

    Sync wrapper around arequest(). For async usage, use arequest() directly.

    See arequest() for full documentation.

    Example::

        # Query field metadata
        df = request(
            Service.APIFLDS,
            Operation.FIELD_INFO,
            fields=['PX_LAST', 'VOLUME'],
        )
    """
    return asyncio.run(
        arequest(
            service,
            operation,
            securities=securities,
            security=security,
            fields=fields,
            overrides=overrides,
            start_date=start_date,
            end_date=end_date,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            event_type=event_type,
            interval=interval,
            options=options,
            field_types=field_types,
            output=output,
            extractor=extractor,
            backend=backend,
        )
    )


# =============================================================================
# Async API - Typed Convenience Functions
# =============================================================================


async def abdp(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    *,
    backend: Backend | str | None = None,
    format: Format | str | None = None,
    field_types: dict[str, str] | None = None,
    **kwargs,
):
    """Async Bloomberg reference data (BDP).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: DataFrame backend to return. If None, uses global default.
            Supports lazy backends: 'polars_lazy', 'narwhals_lazy', 'duckdb'.
        format: Output format. Options:
            - Format.LONG (default): ticker, field, value (strings)
            - Format.LONG_TYPED: ticker, field, value_f64, value_i64, etc.
            - Format.LONG_WITH_METADATA: ticker, field, value, dtype
            - Format.WIDE: Pivoted format (DEPRECATED, use df.pivot() instead)
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
            If None, types are auto-resolved from Bloomberg field metadata.
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
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)
    overrides = _extract_overrides(kwargs)

    # Normalize format
    fmt = Format(format) if isinstance(format, str) else format

    # Handle deprecated WIDE format
    want_wide = fmt == Format.WIDE if fmt else False
    if want_wide:
        warnings.warn(
            "Format.WIDE is deprecated and will be removed in v2.0. "
            "Use format=Format.LONG (default) and then call "
            "df.pivot(on='field', index='ticker', values='value') "
            "to convert to wide format.",
            DeprecationWarning,
            stacklevel=2,
        )
        fmt = None  # Use default long format, then pivot

    logger.debug("abdp: tickers=%s fields=%s", ticker_list, field_list)

    # Resolve field types if not manually provided
    engine = _get_engine()
    resolved_types = await engine.resolve_field_types(
        field_list,
        field_types,  # Manual overrides take precedence
        "string",  # Default type for BDP
    )

    # Use generic arequest with ReferenceDataRequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=ticker_list,
        fields=field_list,
        overrides=overrides if overrides else None,
        field_types=resolved_types,
        format=fmt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdp: received %d rows", len(nw_df))

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
    format: Format | str | None = None,
    field_types: dict[str, str] | None = None,
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
        format: Output format. Options:
            - Format.LONG (default): ticker, date, field, value (strings)
            - Format.LONG_TYPED: ticker, date, field, value_f64, value_i64, etc.
            - Format.LONG_WITH_METADATA: ticker, date, field, value, dtype
            - Format.WIDE: Pivoted format (DEPRECATED, use df.pivot() instead)
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
            If None, types are auto-resolved from Bloomberg field metadata.
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
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)

    # Normalize format
    fmt = Format(format) if isinstance(format, str) else format

    # Handle deprecated WIDE format
    want_wide = fmt == Format.WIDE if fmt else False
    if want_wide:
        warnings.warn(
            "Format.WIDE is deprecated and will be removed in v2.0. "
            "Use format=Format.LONG (default) and then call "
            "df.pivot(on='field', index=['ticker', 'date'], values='value') "
            "to convert to wide format.",
            DeprecationWarning,
            stacklevel=2,
        )
        fmt = None  # Use default long format, then pivot

    # Handle dates
    e_dt = _fmt_date(end_date, "%Y%m%d")
    if start_date is None:
        end_dt_parsed = datetime.strptime(e_dt, "%Y%m%d")
        s_dt = (end_dt_parsed - timedelta(weeks=8)).strftime("%Y%m%d")
    else:
        s_dt = _fmt_date(start_date, "%Y%m%d")

    # Build options list
    options: list[tuple[str, str]] = []
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

    # Add any remaining kwargs as overrides
    overrides = _extract_overrides(kwargs)

    logger.debug("abdh: tickers=%s fields=%s start=%s end=%s", ticker_list, field_list, s_dt, e_dt)

    # Resolve field types if not manually provided
    engine = _get_engine()
    resolved_types = await engine.resolve_field_types(
        field_list,
        field_types,  # Manual overrides take precedence
        "float64",  # Default type for BDH
    )

    # Use generic arequest with HistoricalDataRequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.HISTORICAL_DATA,
        securities=ticker_list,
        fields=field_list,
        start_date=s_dt,
        end_date=e_dt,
        overrides=overrides if overrides else None,
        options=options if options else None,
        field_types=resolved_types,
        format=fmt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdh: received %d rows", len(nw_df))

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
    ticker_list = _normalize_tickers(tickers)
    overrides = _extract_overrides(kwargs)

    logger.debug("abds: tickers=%s field=%s", ticker_list, flds)

    # Use generic arequest with ReferenceDataRequest but BULK extractor
    # BDS uses the same Bloomberg operation as BDP, but returns multi-row results
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=ticker_list,
        fields=[flds],  # BDS takes a single field
        overrides=overrides if overrides else None,
        extractor=ExtractorHint.BULK,  # Use bulk extractor for multi-row results
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abds: received %d rows", len(nw_df))

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

    logger.debug("abdib: ticker=%s interval=%d start=%s end=%s", ticker, interval, s_dt, e_dt)

    # Use generic arequest with IntradayBarRequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.INTRADAY_BAR,
        security=ticker,
        event_type=typ,
        interval=interval,
        start_datetime=s_dt,
        end_datetime=e_dt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdib: received %d bars", len(nw_df))

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
    s_dt = datetime.fromisoformat(start_datetime.replace(" ", "T")).isoformat()
    e_dt = datetime.fromisoformat(end_datetime.replace(" ", "T")).isoformat()

    logger.debug("abdtick: ticker=%s start=%s end=%s", ticker, s_dt, e_dt)

    # Use generic arequest with IntradayTickRequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.INTRADAY_TICK,
        security=ticker,
        start_datetime=s_dt,
        end_datetime=e_dt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdtick: received %d ticks", len(nw_df))

    return _convert_backend(nw_df, backend)


# =============================================================================
# Sync API - Convenience Wrappers
# =============================================================================


def bdp(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    *,
    backend: Backend | str | None = None,
    format: Format | str | None = None,
    field_types: dict[str, str] | None = None,
    **kwargs,
):
    """Bloomberg reference data (BDP).

    Sync wrapper around abdp(). For async usage, use abdp() directly.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: DataFrame backend to return. If None, uses global default.
        format: Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, WIDE).
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        DataFrame in long format with columns: ticker, field, value

    Example::

        df = bdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
        df = bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST', backend='polars')
    """
    return asyncio.run(abdp(tickers, flds, backend=backend, format=format, field_types=field_types, **kwargs))


def bdh(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str = "today",
    *,
    backend: Backend | str | None = None,
    format: Format | str | None = None,
    field_types: dict[str, str] | None = None,
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
        format: Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, WIDE).
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
        **kwargs: Additional overrides and infrastructure options.

    Returns:
        DataFrame in long format with columns: ticker, date, field, value

    Example::

        df = bdh('AAPL US Equity', 'PX_LAST', start_date='2024-01-01')
        df = bdh(['AAPL', 'MSFT'], ['PX_LAST', 'VOLUME'], backend='polars')
    """
    return asyncio.run(
        abdh(tickers, flds, start_date, end_date, backend=backend, format=format, field_types=field_types, **kwargs)
    )


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


# =============================================================================
# Streaming API - Real-time Market Data
# =============================================================================


@dataclass
class Tick:
    """Single tick data point from a subscription.

    Attributes:
        ticker: Security identifier
        field: Bloomberg field name
        value: Field value (type depends on field)
        timestamp: Time the tick was received
    """

    ticker: str
    field: str
    value: Any
    timestamp: datetime


class Subscription:
    """Subscription handle with async iteration and dynamic control.

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
    """

    def __init__(self, py_sub, raw: bool, backend: Backend | None):
        """Initialize subscription wrapper.

        Args:
            py_sub: The underlying PySubscription from Rust
            raw: If True, yield raw Arrow batches
            backend: DataFrame backend for conversion (if not raw)
        """
        self._sub = py_sub
        self._raw = raw
        self._backend = backend

    def __aiter__(self):
        return self

    async def __anext__(self) -> pa.RecordBatch | nw.DataFrame:
        """Get next batch of data."""
        batch = await self._sub.__anext__()

        if self._raw:
            return batch

        # Convert to narwhals DataFrame, then to requested backend
        table = pa.Table.from_batches([batch])
        nw_df = nw.from_native(table)
        return _convert_backend(nw_df, self._backend)

    async def add(self, tickers: str | list[str]) -> None:
        """Add tickers to subscription dynamically.

        Args:
            tickers: Single ticker or list of tickers to add
        """
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        await self._sub.add(ticker_list)

    async def remove(self, tickers: str | list[str]) -> None:
        """Remove tickers from subscription dynamically.

        Args:
            tickers: Single ticker or list of tickers to remove
        """
        ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
        await self._sub.remove(ticker_list)

    @property
    def tickers(self) -> list[str]:
        """Currently subscribed tickers."""
        return self._sub.tickers

    @property
    def fields(self) -> list[str]:
        """Subscribed fields."""
        return self._sub.fields

    @property
    def is_active(self) -> bool:
        """Whether the subscription is still active."""
        return self._sub.is_active

    async def unsubscribe(self, drain: bool = False) -> list[pa.RecordBatch] | None:
        """Close subscription and optionally drain remaining data.

        Args:
            drain: If True, return any remaining buffered batches

        Returns:
            List of remaining batches if drain=True, else None
        """
        return await self._sub.unsubscribe(drain)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.unsubscribe()

    def __repr__(self) -> str:
        return repr(self._sub)


async def asubscribe(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Create an async subscription to real-time market data.

    This is the low-level subscription API with full control over
    the subscription lifecycle, including dynamic add/remove.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to (e.g., 'LAST_PRICE', 'BID', 'ASK')
        raw: If True, yield raw Arrow RecordBatches for max performance
        backend: DataFrame backend for batch conversion (ignored if raw=True)

    Returns:
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
    """
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    field_list = [fields] if isinstance(fields, str) else list(fields)

    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend)
        if backend is not None
        else _default_backend
    )

    engine = _get_engine()
    py_sub = await engine.subscribe(ticker_list, field_list)

    return Subscription(py_sub, raw=raw, backend=effective_backend)


def subscribe(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Create a subscription to real-time market data (sync version).

    Note: This returns an async Subscription. Use in an async context
    or call methods with asyncio.run().

    For simple sync iteration, use stream() instead.

    See asubscribe() for full documentation.
    """
    return asyncio.run(asubscribe(tickers, fields, raw=raw, backend=backend))


async def astream(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
):
    """High-level async streaming - simple iteration.

    This is the simple API for streaming data. For dynamic add/remove,
    use asubscribe() instead.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to
        raw: If True, yield raw Arrow RecordBatches
        backend: DataFrame backend for batch conversion

    Yields:
        Batches of market data (RecordBatch or DataFrame)

    Example::

        async for batch in xbbg.astream(['AAPL US Equity'], ['LAST_PRICE']):
            print(batch)
            if done:
                break
    """
    async with await asubscribe(tickers, fields, raw=raw, backend=backend) as sub:
        async for batch in sub:
            yield batch


def stream(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
):
    """High-level sync streaming using a background thread.

    Note: This is a generator that runs the async stream in a background
    thread. Use astream() for async contexts.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to
        raw: If True, yield raw Arrow RecordBatches
        backend: DataFrame backend for batch conversion

    Yields:
        Batches of market data

    Example::

        for batch in xbbg.stream(['AAPL US Equity'], ['LAST_PRICE']):
            print(batch)
            if done:
                break
    """
    import queue
    import threading

    q: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    async def run_stream():
        try:
            async for batch in astream(tickers, fields, raw=raw, backend=backend):
                if stop_event.is_set():
                    break
                q.put(batch)
        except Exception as e:
            q.put(e)
        finally:
            q.put(None)  # Sentinel

    def thread_target():
        asyncio.run(run_stream())

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()

    try:
        while True:
            item = q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        stop_event.set()
        thread.join(timeout=1.0)


# =============================================================================
# BQL API - Bloomberg Query Language
# =============================================================================


def _parse_bql_response(raw_json: str) -> nw.DataFrame:
    """Parse BQL JSON response into a DataFrame.

    BQL responses have this structure:
    {
        "results": {
            "field1": {
                "idColumn": {"name": "ID", "type": "STRING", "values": [...]},
                "valuesColumn": {"type": "DOUBLE", "values": [...]},
                "secondaryColumns": [{"name": "...", "type": "...", "values": [...]}]
            },
            "field2": {...}
        }
    }

    All arrays are index-aligned, so we zip them together.
    All fields share the same idColumn (the universe/ticker list).
    """
    # BQL returns double-encoded JSON
    data = json.loads(json.loads(raw_json))

    results = data.get("results", {})
    if not results:
        # Return empty DataFrame
        return nw.from_native(pa.table({"id": pa.array([], type=pa.string())}))

    # Get field names and data
    field_names = list(results.keys())
    if not field_names:
        return nw.from_native(pa.table({"id": pa.array([], type=pa.string())}))

    # All fields share the same idColumn, use first field to get it
    first_field = results[field_names[0]]
    id_col = first_field["idColumn"]
    ids = id_col["values"]

    # Build columns dict starting with id
    columns: dict[str, list] = {"id": ids}

    # Add each field's values
    for field_name in field_names:
        field_data = results[field_name]
        values = field_data["valuesColumn"]["values"]
        columns[field_name] = values

        # Add secondary columns if present (prefixed with field name)
        sec_cols = field_data.get("secondaryColumns", [])
        for sec_col in sec_cols:
            col_name = f"{field_name}_{sec_col['name']}"
            columns[col_name] = sec_col["values"]

    # Convert to Arrow table (narwhals-compatible)
    # Let pyarrow infer types from the Python values
    arrow_arrays = {}
    for col_name, values in columns.items():
        arrow_arrays[col_name] = pa.array(values)

    table = pa.table(arrow_arrays)
    return nw.from_native(table)


async def abql(
    expression: str,
    *,
    backend: Backend | str | None = None,
) -> nw.DataFrame:
    """Async Bloomberg Query Language (BQL) request.

    BQL is Bloomberg's powerful query language for financial analytics.
    It allows you to query data across universes of securities with
    complex filters, calculations, and time series operations.

    Args:
        expression: BQL expression string.
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
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
    """
    logger.debug("abql: expression=%s", expression)

    # Send BQL request via arequest
    raw_df = await arequest(
        service="//blp/bqlsvc",
        operation="sendQuery",
        overrides={"expression": expression},
        extractor=ExtractorHint.RAW_JSON,
        backend=None,  # Get narwhals to extract raw JSON
    )

    # Extract raw JSON from the response
    raw_json = raw_df.to_native().to_pylist()[0]["json"]

    # Parse and convert to DataFrame
    nw_df = _parse_bql_response(raw_json)

    logger.debug("abql: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def bql(
    expression: str,
    *,
    backend: Backend | str | None = None,
) -> nw.DataFrame:
    """Bloomberg Query Language (BQL) request.

    Sync wrapper around abql(). For async usage, use abql() directly.

    BQL is Bloomberg's powerful query language for financial analytics.
    It allows you to query data across universes of securities with
    complex filters, calculations, and time series operations.

    Args:
        expression: BQL expression string.
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        DataFrame with columns: id, <field1>, <field2>, ...
        Where 'id' is the security identifier from the BQL universe.

    Example::

        # Get price for a single security
        df = bql("get(px_last) for('AAPL US Equity')")

        # Holdings of an ETF
        df = bql("get(id_isin, weights) for(holdings('SPY US Equity'))")

        # Index members with filter
        df = bql("get(px_last, pe_ratio) for(members('SPX Index')) with(pe_ratio > 20)")
    """
    return asyncio.run(abql(expression, backend=backend))


# =============================================================================
# BSRCH API - Bloomberg Search
# =============================================================================


def _parse_bsrch_response(raw_json: str) -> nw.DataFrame:
    """Parse bsrch JSON response into a DataFrame.

    Bsrch responses have this structure:
    {
        "NumOfFields": 3,
        "NumOfRecords": 10,
        "ColumnTitles": ["Ticker", "Name", "Price"],
        "DataRecords": [
            {"DataFields": ["AAPL US Equity", "Apple Inc", "150.00"]},
            ...
        ],
        "ReachMax": false,
        "Error": "",
        "SequenceNumber": 0
    }
    """
    data = json.loads(raw_json)
    if isinstance(data, str):
        data = json.loads(data)

    # Check for errors
    error = data.get("Error", "")
    if error:
        logger.warning("bsrch returned error: %s", error)

    column_titles = data.get("ColumnTitles", [])
    data_records = data.get("DataRecords", [])

    if not column_titles or not data_records:
        # Return empty DataFrame with no columns
        return nw.from_native(pa.table({}))

    # Build columns dict
    columns: dict[str, list] = {col: [] for col in column_titles}

    for record in data_records:
        fields = record.get("DataFields", [])
        for i, col in enumerate(column_titles):
            if i < len(fields):
                columns[col].append(fields[i])
            else:
                columns[col].append(None)

    # Convert to Arrow table
    arrow_arrays = {col: pa.array(values) for col, values in columns.items()}
    table = pa.table(arrow_arrays)
    return nw.from_native(table)


async def absrch(
    domain: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> nw.DataFrame:
    """Async Bloomberg Search (BSRCH) request.

    BSRCH executes saved Bloomberg searches and returns matching securities.

    Args:
        domain: The saved search domain/name (e.g., "FI:SOVR", "COMDTY:PRECIOUS").
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional search parameters passed as request elements.

    Returns:
        DataFrame with columns from the saved search results.

    Example::

        # Sovereign bonds
        df = await absrch("FI:SOVR")

        # With additional parameters
        df = await absrch("COMDTY:WEATHER", LOCATION="NYC", MODEL="GFS")
    """
    logger.debug("absrch: domain=%s kwargs=%s", domain, kwargs)

    # Build overrides dict with Domain and any extra parameters
    overrides: dict[str, str] = {"Domain": domain}
    for key, value in kwargs.items():
        overrides[key] = str(value)

    # Send bsrch request via arequest
    raw_df = await arequest(
        service="//blp/exrsvc",
        operation="ExcelGetGridRequest",
        overrides=overrides,
        extractor=ExtractorHint.RAW_JSON,
        backend=None,
    )

    # Extract raw JSON from the response
    raw_json = raw_df.to_native().to_pylist()[0]["json"]

    # Parse and convert to DataFrame
    nw_df = _parse_bsrch_response(raw_json)

    logger.debug("absrch: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def bsrch(
    domain: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> nw.DataFrame:
    """Bloomberg Search (BSRCH) request.

    Sync wrapper around absrch(). For async usage, use absrch() directly.

    BSRCH executes saved Bloomberg searches and returns matching securities.

    Args:
        domain: The saved search domain/name (e.g., "FI:SOVR", "COMDTY:PRECIOUS").
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional search parameters passed as request elements.

    Returns:
        DataFrame with columns from the saved search results.

    Example::

        # Sovereign bonds
        df = bsrch("FI:SOVR")

        # With additional parameters
        df = bsrch("COMDTY:WEATHER", LOCATION="NYC", MODEL="GFS")
    """
    return asyncio.run(absrch(domain, backend=backend, **kwargs))


# =============================================================================
# BFLD API - Bloomberg Field Search
# =============================================================================


async def abfld(
    fields: str | Sequence[str],
    *,
    backend: Backend | str | None = None,
) -> nw.DataFrame:
    """Async Bloomberg Field Info (BFLD) request.

    Get metadata about specific Bloomberg fields including description,
    data type, and category.

    Args:
        fields: Field name or list of field names (e.g., "PX_LAST", ["PX_LAST", "VOLUME"]).
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        DataFrame with columns: field, datatype, description, category, etc.

    Example::

        # Get info for a single field
        df = await abfld("PX_LAST")

        # Get info for multiple fields
        df = await abfld(["PX_LAST", "VOLUME", "NAME"])
    """
    field_list = [fields] if isinstance(fields, str) else list(fields)
    logger.debug("abfld: fields=%s", field_list)

    # Send field info request via arequest
    # The //blp/apiflds service uses FieldInfoRequest with field_ids
    nw_df = await arequest(
        service=Service.APIFLDS,
        operation=Operation.FIELD_INFO,
        fields=field_list,
        backend=None,
    )

    logger.debug("abfld: received %d rows", len(nw_df))

    return _convert_backend(nw_df, backend)


def bfld(
    fields: str | Sequence[str],
    *,
    backend: Backend | str | None = None,
) -> nw.DataFrame:
    """Bloomberg Field Info (BFLD) request.

    Sync wrapper around abfld(). For async usage, use abfld() directly.

    Get metadata about specific Bloomberg fields including description,
    data type, and category.

    Args:
        fields: Field name or list of field names (e.g., "PX_LAST", ["PX_LAST", "VOLUME"]).
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        DataFrame with columns: field, datatype, description, category, etc.

    Example::

        # Get info for a single field
        df = bfld("PX_LAST")

        # Get info for multiple fields
        df = bfld(["PX_LAST", "VOLUME", "NAME"])
    """
    return asyncio.run(abfld(fields, backend=backend))


# ─── Schema Introspection API ────────────────────────────────────────────────


async def abops(service: str | Service = Service.REFDATA) -> list[str]:
    """List available operations for a Bloomberg service (async).

    Args:
        service: Service URI or Service enum (default: //blp/refdata)

    Returns:
        List of operation names.

    Example::

        >>> ops = await abops()
        >>> print(ops)
        ['ReferenceDataRequest', 'HistoricalDataRequest', ...]

        >>> ops = await abops("//blp/instruments")
        >>> print(ops)
        ['InstrumentListRequest', ...]
    """
    from . import schema

    service_uri = service.value if isinstance(service, Service) else service
    return await schema.alist_operations(service_uri)


def bops(service: str | Service = Service.REFDATA) -> list[str]:
    """List available operations for a Bloomberg service.

    Sync wrapper around abops(). For async usage, use abops() directly.

    Args:
        service: Service URI or Service enum (default: //blp/refdata)

    Returns:
        List of operation names.

    Example::

        >>> bops()
        ['ReferenceDataRequest', 'HistoricalDataRequest', ...]

        >>> bops("//blp/instruments")
        ['InstrumentListRequest', ...]
    """
    return asyncio.run(abops(service))


async def abschema(
    service: str | Service = Service.REFDATA,
    operation: str | Operation | None = None,
) -> dict:
    """Get Bloomberg service or operation schema (async).

    Returns introspected schema with element definitions, types, and enum values.
    Schemas are cached locally (~/.xbbg/schemas/) for fast subsequent access.

    Args:
        service: Service URI or Service enum (default: //blp/refdata)
        operation: Optional operation name. If None, returns full service schema.

    Returns:
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
    """
    from . import schema

    service_uri = service.value if isinstance(service, Service) else service

    if operation is not None:
        op_name = operation.value if isinstance(operation, Operation) else operation
        op_schema = await schema.aget_operation(service_uri, op_name)
        return {
            "name": op_schema.name,
            "description": op_schema.description,
            "request": _element_to_dict(op_schema.request),
            "responses": [_element_to_dict(r) for r in op_schema.responses],
        }
    svc_schema = await schema.aget_schema(service_uri)
    return {
        "service": svc_schema.service,
        "description": svc_schema.description,
        "operations": [
            {
                "name": op.name,
                "description": op.description,
                "request": _element_to_dict(op.request),
                "responses": [_element_to_dict(r) for r in op.responses],
            }
            for op in svc_schema.operations
        ],
        "cached_at": svc_schema.cached_at,
    }


def bschema(
    service: str | Service = Service.REFDATA,
    operation: str | Operation | None = None,
) -> dict:
    """Get Bloomberg service or operation schema.

    Sync wrapper around abschema(). For async usage, use abschema() directly.

    Returns introspected schema with element definitions, types, and enum values.
    Schemas are cached locally (~/.xbbg/schemas/) for fast subsequent access.

    Args:
        service: Service URI or Service enum (default: //blp/refdata)
        operation: Optional operation name. If None, returns full service schema.

    Returns:
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
    """
    return asyncio.run(abschema(service, operation))


def _element_to_dict(elem) -> dict:
    """Convert ElementInfo to dictionary."""
    return {
        "name": elem.name,
        "description": elem.description,
        "data_type": elem.data_type,
        "type_name": elem.type_name,
        "is_array": elem.is_array,
        "is_optional": elem.is_optional,
        "enum_values": elem.enum_values,
        "children": [_element_to_dict(c) for c in elem.children],
    }
