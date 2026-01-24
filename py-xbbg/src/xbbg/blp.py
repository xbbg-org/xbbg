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
from typing import TYPE_CHECKING, Any, TypeAlias
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

from narwhals.typing import IntoFrame

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd

# Type alias for backend conversion return types
# Covers: nw.DataFrame, nw.LazyFrame (narwhals wrappers) + IntoFrame (all native types)
DataFrameResult: TypeAlias = nw.DataFrame | nw.LazyFrame | IntoFrame

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
    "abeqs",
    "ablkp",
    "abport",
    "abcurves",
    "abgovts",
    # Sync API (wrappers)
    "bdp",
    "bdh",
    "bds",
    "bdib",
    "bdtick",
    "bql",
    "bsrch",
    "bfld",
    "beqs",
    "blkp",
    "bport",
    "bcurves",
    "bgovts",
    # Streaming API
    "Tick",
    "Subscription",
    "asubscribe",
    "subscribe",
    "astream",
    "stream",
    # VWAP Streaming
    "avwap",
    "vwap",
    # Technical Analysis
    "abta",
    "bta",
    "ta_studies",
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
        configure(
            EngineConfig(
                request_pool_size=4,
                subscription_pool_size=8,
            )
        )

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
            "Cannot configure after engine has started. Call xbbg.configure() before any Bloomberg request."
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


# Cache for valid request elements per (service, operation)
_VALID_ELEMENTS_CACHE: dict[tuple[str, str], set[str]] = {}


async def _aget_valid_elements(service: str, operation: str) -> set[str]:
    """Get valid request element names from schema cache (async).

    Returns cached set of valid element names for the operation.
    Falls back to empty set if schema not available.
    """
    cache_key = (service, operation)
    if cache_key in _VALID_ELEMENTS_CACHE:
        return _VALID_ELEMENTS_CACHE[cache_key]

    try:
        engine = _get_engine()
        elements = await engine.list_valid_elements(service, operation)
        valid = set(elements) if elements else set()
        _VALID_ELEMENTS_CACHE[cache_key] = valid
        return valid
    except Exception:
        # Schema not available, return empty set
        return set()


async def _aroute_kwargs(
    service: str | Service,
    operation: str | Operation,
    kwargs: dict,
) -> tuple[list[tuple[str, Any]], list[tuple[str, str]]]:
    """Route kwargs to elements or overrides using schema introspection (async).

    Uses the Bloomberg schema to determine if a kwarg is:
    1. A valid request element (e.g., intervalHasSeconds, periodicitySelection)
    2. A Bloomberg field override (UPPERCASE names like GICS_SECTOR_NAME)

    Args:
        service: Bloomberg service URI
        operation: Request operation name
        kwargs: User-provided kwargs (will be modified in place)

    Returns:
        Tuple of (elements, overrides) where:
        - elements: List of (name, value) for valid request elements
        - overrides: List of (name, value) for Bloomberg field overrides
    """
    # Normalize service/operation to strings
    svc = service.value if isinstance(service, Service) else service
    op = operation.value if isinstance(operation, Operation) else operation

    # Get valid elements from schema
    valid_elements = await _aget_valid_elements(svc, op)

    elements: list[tuple[str, Any]] = []
    overrides: list[tuple[str, str]] = []

    # Handle explicit overrides dict first
    if "overrides" in kwargs:
        ovrd = kwargs.pop("overrides")
        if isinstance(ovrd, dict):
            overrides.extend((k, str(v)) for k, v in ovrd.items())
        elif isinstance(ovrd, list):
            overrides.extend((str(k), str(v)) for k, v in ovrd)

    # Route remaining kwargs
    for key in list(kwargs.keys()):
        value = kwargs.pop(key)

        if key in valid_elements:
            # Schema-recognized request element
            elements.append((key, value))
        elif key.isupper() or (len(key) > 2 and key[0].isupper() and "_" in key):
            # Looks like a Bloomberg field override (UPPERCASE or Mixed_Case_Field)
            overrides.append((key, str(value)))
        elif valid_elements:
            # Schema available but key not recognized - warn and pass as element
            warnings.warn(
                f"Unknown parameter '{key}' for {op} - passing to Bloomberg. "
                f"Valid elements: {sorted(valid_elements)[:10]}{'...' if len(valid_elements) > 10 else ''}",
                stacklevel=4,
            )
            elements.append((key, value))
        else:
            # No schema available - pass as element (Bloomberg will validate)
            elements.append((key, value))

    return elements, overrides


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


def _handle_deprecated_wide_format(
    format: Format | str | None,
    pivot_index: str | list[str],
    stacklevel: int = 3,
) -> tuple[Format | None, bool]:
    """Handle deprecated WIDE format with warning.

    Args:
        format: User-provided format (may be Format.WIDE)
        pivot_index: Column(s) to use as index when pivoting
            - For bdp: "ticker"
            - For bdh: ["ticker", "date"]
        stacklevel: Stack level for the deprecation warning

    Returns:
        Tuple of (adjusted_format, want_wide) where:
        - adjusted_format: Format to use (None if WIDE was requested)
        - want_wide: True if WIDE was requested and post-pivot is needed
    """
    fmt = Format(format) if isinstance(format, str) else format
    want_wide = fmt == Format.WIDE if fmt else False

    if want_wide:
        # Build the pivot example string
        if isinstance(pivot_index, list):
            index_str = str(pivot_index)
        else:
            index_str = f"'{pivot_index}'"

        warnings.warn(
            f"Format.WIDE is deprecated and will be removed in v2.0. "
            f"Use format=Format.LONG (default) and then call "
            f"df.pivot(on='field', index={index_str}, values='value') "
            f"to convert to wide format.",
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        fmt = None  # Use default long format, then pivot

    return fmt, want_wide


def _apply_wide_pivot_bdp(df) -> "pd.DataFrame":
    """Apply wide format pivot to BDP DataFrame for 0.7.7 compatibility.

    Converts from long format to wide format with ticker as index.

    Args:
        df: DataFrame with columns [ticker, field, value]

    Returns:
        pandas DataFrame with ticker as index and fields as columns
    """
    import pandas as pd

    # Convert to pandas if needed
    if hasattr(df, "to_pandas"):
        pdf = df.to_pandas()
    else:
        pdf = df

    # Pivot: ticker as index, field as columns, value as values
    result = pdf.pivot(index="ticker", columns="field", values="value")
    result.columns.name = None  # Remove column name
    return result


def _apply_wide_pivot_bdh(df) -> "pd.DataFrame":
    """Apply wide format pivot to BDH DataFrame for 0.7.7 compatibility.

    Converts from Long format [ticker, date, field, value] to
    0.7.7 wide format with DatetimeIndex and MultiIndex columns (ticker, field).

    Args:
        df: DataFrame with columns [ticker, date, field, value]

    Returns:
        pandas DataFrame with DatetimeIndex and MultiIndex columns
    """
    import pandas as pd

    # Convert to pandas if needed
    if hasattr(df, "to_pandas"):
        pdf = df.to_pandas()
    else:
        pdf = df

    # Data is already in Long format: [ticker, date, field, value]
    # Just need to pivot to 0.7.7 Wide format
    pivoted = pdf.pivot_table(
        index="date",
        columns=["ticker", "field"],
        values="value",
        aggfunc="first",  # In case of duplicates
    )

    # Convert index to DatetimeIndex
    pivoted.index = pd.to_datetime(pivoted.index)
    pivoted.index.name = None  # 0.7.7 style has no index name

    return pivoted


def _convert_backend(
    nw_df: Any,
    backend: Backend | str | None,
) -> DataFrameResult:
    """Convert narwhals DataFrame to the requested backend.

    Args:
        nw_df: A narwhals DataFrame (or already-converted DataFrame)
        backend: Target backend (Backend enum, string, or None)

    Returns:
        DataFrame/LazyFrame in the requested backend format
    """
    # Resolve effective backend
    effective = (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend

    # Handle already-converted DataFrames (avoid double-conversion)
    # Check for pandas DataFrame
    if hasattr(nw_df, "_mgr"):  # pandas DataFrame has _mgr attribute
        if effective == Backend.PANDAS:
            return nw_df  # Already pandas
        # Convert pandas to narwhals first for other conversions
        nw_df = nw.from_native(nw_df)

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
    elements: Sequence[tuple[str, Any]] | None = None,
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
        elements: Additional request elements as list of (name, value) tuples.
            Used for schema-driven parameters like intervalHasSeconds, periodicitySelection.
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
        format: Output format hint for result structure.
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        DataFrame/Table in the requested format.

    Example::

        # Query field metadata (//blp/apiflds service)
        df = await arequest(
            Service.APIFLDS,
            Operation.FIELD_INFO,
            fields=["PX_LAST", "VOLUME"],
        )

        # Get raw JSON for debugging
        json_table = await arequest(
            Service.REFDATA,
            Operation.REFERENCE_DATA,
            securities=["AAPL US Equity"],
            fields=["PX_LAST"],
            output=OutputMode.JSON,
        )

        # Custom Bloomberg request (power user)
        df = await arequest(
            "//blp/refdata",
            "ReferenceDataRequest",
            securities=["AAPL US Equity"],
            fields=["PX_LAST"],
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
    elements_list: list[tuple[str, Any]] | None = None

    # Handle explicit elements parameter
    if elements is not None:
        elements_list = list(elements)

    if overrides is not None:
        override_tuples: list[tuple[str, str]] = (
            [(str(k), str(v)) for k, v in overrides.items()] if isinstance(overrides, dict) else list(overrides)
        )
        # For BQL and bsrch services, pass overrides as generic elements (not Bloomberg field overrides)
        service_str = service.value if isinstance(service, Service) else service
        if service_str in (Service.BQLSVC.value, Service.EXRSVC.value):
            if elements_list:
                elements_list.extend(override_tuples)
            else:
                elements_list = override_tuples
        else:
            overrides_list = override_tuples

    options_list: list[tuple[str, str]] | None = None
    if options is not None:
        options_list = [(str(k), str(v)) for k, v in options.items()] if isinstance(options, dict) else list(options)

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
            fields=["PX_LAST", "VOLUME"],
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
        df = await abdp("AAPL US Equity", ["PX_LAST", "VOLUME"])

        # Concurrent requests
        dfs = await asyncio.gather(
            abdp("AAPL US Equity", "PX_LAST"),
            abdp("MSFT US Equity", "PX_LAST"),
        )
    """
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)

    # Route kwargs to elements/overrides using schema introspection
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.REFERENCE_DATA, kwargs)

    # Handle deprecated WIDE format
    fmt, want_wide = _handle_deprecated_wide_format(format, pivot_index="ticker")

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
        elements=elements if elements else None,
        field_types=resolved_types,
        format=fmt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdp: received %d rows", len(nw_df))

    # Handle deprecated wide format
    if want_wide:
        return _apply_wide_pivot_bdp(nw_df)

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
        df = await abdh("AAPL US Equity", "PX_LAST", start_date="2024-01-01")

        # Concurrent requests
        dfs = await asyncio.gather(
            abdh("AAPL US Equity", "PX_LAST"),
            abdh("MSFT US Equity", "PX_LAST"),
        )
    """
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)

    # Handle deprecated WIDE format
    fmt, want_wide = _handle_deprecated_wide_format(format, pivot_index=["ticker", "date"])

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

    # Route remaining kwargs to elements/overrides using schema introspection
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.HISTORICAL_DATA, kwargs)

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
        elements=elements if elements else None,
        options=options if options else None,
        field_types=resolved_types,
        format=fmt,
        backend=None,  # Get narwhals DataFrame, we'll convert below
    )

    logger.debug("abdh: received %d rows", len(nw_df))

    # Handle deprecated wide format
    if want_wide:
        return _apply_wide_pivot_bdh(nw_df)

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

        df = await abds("AAPL US Equity", "DVD_Hist_All")
        df = await abds("SPX Index", "INDX_MEMBERS", backend="polars")
    """
    ticker_list = _normalize_tickers(tickers)

    # Route kwargs to elements/overrides using schema introspection
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.REFERENCE_DATA, kwargs)

    logger.debug("abds: tickers=%s field=%s", ticker_list, flds)

    # Use generic arequest with ReferenceDataRequest but BULK extractor
    # BDS uses the same Bloomberg operation as BDP, but returns multi-row results
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=ticker_list,
        fields=[flds],  # BDS takes a single field
        overrides=overrides if overrides else None,
        elements=elements if elements else None,
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
        interval: Bar interval in minutes (default: 1), or seconds if intervalHasSeconds=True.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional Bloomberg options (e.g., intervalHasSeconds, gapFillInitialBar).

    Returns:
        DataFrame with intraday bar data.

    Example::

        # 1-minute bars (default)
        df = await abdib("AAPL US Equity", dt="2024-12-01")

        # 5-minute bars with explicit datetime range
        df = await abdib(
            "AAPL US Equity",
            start_datetime="2024-12-01 09:30",
            end_datetime="2024-12-01 16:00",
            interval=5,
        )

        # 10-second bars
        df = await abdib("AAPL US Equity", dt="2024-12-01", interval=10, intervalHasSeconds=True)
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

    # Route kwargs to elements using schema introspection
    elements, _overrides = await _aroute_kwargs(Service.REFDATA, Operation.INTRADAY_BAR, kwargs)

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
        elements=elements if elements else None,
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

        df = await abdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00")
        df = await abdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00", backend="polars")
    """
    s_dt = datetime.fromisoformat(start_datetime.replace(" ", "T")).isoformat()
    e_dt = datetime.fromisoformat(end_datetime.replace(" ", "T")).isoformat()

    # Route kwargs to elements using schema introspection
    elements, _overrides = await _aroute_kwargs(Service.REFDATA, Operation.INTRADAY_TICK, kwargs)

    logger.debug("abdtick: ticker=%s start=%s end=%s", ticker, s_dt, e_dt)

    # Use generic arequest with IntradayTickRequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.INTRADAY_TICK,
        security=ticker,
        start_datetime=s_dt,
        end_datetime=e_dt,
        elements=elements if elements else None,
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

        df = bdp("AAPL US Equity", ["PX_LAST", "VOLUME"])
        df = bdp(["AAPL US Equity", "MSFT US Equity"], "PX_LAST", backend="polars")
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

        df = bdh("AAPL US Equity", "PX_LAST", start_date="2024-01-01")
        df = bdh(["AAPL", "MSFT"], ["PX_LAST", "VOLUME"], backend="polars")
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

        df = bds("AAPL US Equity", "DVD_Hist_All")
        df = bds("SPX Index", "INDX_MEMBERS", backend="polars")
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

        df = bdib("AAPL US Equity", dt="2024-12-01")
        df = bdib(
            "AAPL US Equity",
            start_datetime="2024-12-01 09:30",
            end_datetime="2024-12-01 16:00",
            interval=5,
            backend="polars",
        )
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

        df = bdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00")
        df = bdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00", backend="polars")
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

        sub = await xbbg.asubscribe(["AAPL US Equity"], ["LAST_PRICE", "BID"])

        async for batch in sub:
            # batch is pyarrow.RecordBatch
            print(batch.to_pandas())

            if should_add_msft:
                await sub.add(["MSFT US Equity"])

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
        sub = await xbbg.asubscribe(["AAPL US Equity"], ["LAST_PRICE", "BID"])
        async for batch in sub:
            print(batch)
        await sub.unsubscribe()

        # With context manager
        async with xbbg.asubscribe(["AAPL US Equity"], ["LAST_PRICE"]) as sub:
            count = 0
            async for batch in sub:
                print(batch)
                count += 1
                if count >= 10:
                    break

        # Dynamic add/remove
        sub = await xbbg.asubscribe(["AAPL US Equity"], ["LAST_PRICE"])
        async for batch in sub:
            if should_add_msft:
                await sub.add(["MSFT US Equity"])
            if should_remove_aapl:
                await sub.remove(["AAPL US Equity"])
    """
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    field_list = [fields] if isinstance(fields, str) else list(fields)

    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend
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

        async for batch in xbbg.astream(["AAPL US Equity"], ["LAST_PRICE"]):
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

        for batch in xbbg.stream(["AAPL US Equity"], ["LAST_PRICE"]):
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
# VWAP Streaming API - Real-time Volume Weighted Average Price
# =============================================================================


async def avwap(
    tickers: str | list[str],
    fields: str | list[str] | None = None,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to real-time VWAP data (//blp/mktvwap).

    Provides streaming Volume Weighted Average Price calculations.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to (default: RT_PX_VWAP, RT_VWAP_VOLUME)
        start_time: VWAP calculation start time (e.g., "09:30")
        end_time: VWAP calculation end time (e.g., "16:00")
        raw: If True, yield raw Arrow RecordBatches for max performance
        backend: DataFrame backend for batch conversion (ignored if raw=True)

    Returns:
        Subscription handle for iteration and control

    Example::

        # Basic usage - subscribe to VWAP
        sub = await xbbg.avwap(["AAPL US Equity"])
        async for batch in sub:
            print(batch)
        await sub.unsubscribe()

        # With custom time window
        sub = await xbbg.avwap(["AAPL US Equity", "MSFT US Equity"], start_time="09:30", end_time="16:00")

        # With specific fields
        sub = await xbbg.avwap("AAPL US Equity", ["RT_PX_VWAP", "RT_VWAP_VOLUME", "RT_VWAP_TURNOVER"])
    """
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)

    # Default fields if not provided
    if fields is None:
        field_list = ["RT_PX_VWAP", "RT_VWAP_VOLUME"]
    else:
        field_list = [fields] if isinstance(fields, str) else list(fields)

    # Build subscription options
    options: list[str] = []
    if start_time:
        options.append(f"VWAP_START_TIME={start_time}")
    if end_time:
        options.append(f"VWAP_END_TIME={end_time}")

    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend
    )

    engine = _get_engine()
    py_sub = await engine.subscribe_with_options(
        Service.MKTVWAP.value,
        ticker_list,
        field_list,
        options if options else None,
    )

    return Subscription(py_sub, raw=raw, backend=effective_backend)


def vwap(
    tickers: str | list[str],
    fields: str | list[str] | None = None,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to real-time VWAP data (sync version).

    Note: This returns an async Subscription. Use in an async context
    or call methods with asyncio.run().

    See avwap() for full documentation.
    """
    return asyncio.run(
        avwap(
            tickers,
            fields,
            start_time=start_time,
            end_time=end_time,
            raw=raw,
            backend=backend,
        )
    )


# =============================================================================
# MKTBAR API - Real-time Streaming OHLC Bars
# =============================================================================


async def amktbar(
    tickers: str | list[str],
    *,
    interval: int = 1,
    start_time: str | None = None,
    end_time: str | None = None,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to real-time streaming OHLC bars.

    Like bdib but streaming instead of historical. Provides real-time
    bar updates as they form during the trading day.

    Args:
        tickers: Security identifier(s).
        interval: Bar interval in minutes (default: 1).
        start_time: Optional start time in HH:MM format.
        end_time: Optional end time in HH:MM format.
        raw: If True, return raw pyarrow RecordBatch (default: False).
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        Subscription object for async iteration.

    Example::

        # Subscribe to 5-minute bars
        async with await amktbar("AAPL US Equity", interval=5) as sub:
            async for batch in sub:
                print(batch)

        # Multiple securities
        sub = await amktbar(["AAPL US Equity", "MSFT US Equity"], interval=1)
        async for batch in sub:
            print(batch)
    """
    logger.debug("amktbar: tickers=%s interval=%d", tickers, interval)

    # Normalize inputs
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend
    )

    # Build subscription options
    options: list[str] = [f"interval={interval}"]
    if start_time:
        options.append(f"START_TIME={start_time}")
    if end_time:
        options.append(f"END_TIME={end_time}")

    # Get engine and subscribe
    engine = _get_engine()
    py_sub = await engine.subscribe_with_options(
        Service.MKTBAR.value,
        ticker_list,
        ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "NUM_TRADES"],
        options if options else None,
    )

    return Subscription(py_sub, raw=raw, backend=effective_backend)


def mktbar(
    tickers: str | list[str],
    *,
    interval: int = 1,
    start_time: str | None = None,
    end_time: str | None = None,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to real-time streaming OHLC bars (sync version).

    Note: This returns an async Subscription. Use in an async context
    or call methods with asyncio.run().

    See amktbar() for full documentation.
    """
    return asyncio.run(
        amktbar(
            tickers,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            raw=raw,
            backend=backend,
        )
    )


# =============================================================================
# MKTDEPTH API - Level 2 Market Depth (B-PIPE Only)
# =============================================================================


async def adepth(
    tickers: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to Level 2 market depth / order book data.

    .. warning::
        **Requires Bloomberg B-PIPE license.** This feature is not available
        with standard Terminal connections.

    Provides real-time order book updates with bid/ask prices and sizes
    at multiple levels.

    Args:
        tickers: Security identifier(s).
        raw: If True, return raw pyarrow RecordBatch (default: False).
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        Subscription object for async iteration.

    Raises:
        BlpBPipeError: If B-PIPE license is not available.

    Example::

        # Subscribe to market depth
        async with await adepth("AAPL US Equity") as sub:
            async for batch in sub:
                print(batch)  # Order book updates
    """
    from xbbg.exceptions import BlpBPipeError

    logger.debug("adepth: tickers=%s", tickers)

    # Normalize inputs
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend
    )

    # Get engine and subscribe
    engine = _get_engine()
    try:
        py_sub = await engine.subscribe_with_options(
            Service.MKTDEPTH.value,
            ticker_list,
            [],  # Fields are implicit for market depth
            None,
        )
    except Exception as e:
        # Check for B-PIPE related errors
        if "MKTDEPTHDATA" in str(e).upper() or "SERVICE" in str(e).upper():
            raise BlpBPipeError("Level 2 market depth requires Bloomberg B-PIPE license.") from e
        raise

    return Subscription(py_sub, raw=raw, backend=effective_backend)


def depth(
    tickers: str | list[str],
    *,
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to Level 2 market depth / order book data (sync version).

    .. warning::
        **Requires Bloomberg B-PIPE license.** This feature is not available
        with standard Terminal connections.

    Note: This returns an async Subscription. Use in an async context
    or call methods with asyncio.run().

    See adepth() for full documentation.
    """
    return asyncio.run(
        adepth(
            tickers,
            raw=raw,
            backend=backend,
        )
    )


# =============================================================================
# MKTLIST API - Option/Futures Chains (B-PIPE Only)
# =============================================================================


async def achains(
    underlying: str,
    *,
    chain_type: str = "OPTIONS",
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to option or futures chain updates.

    .. warning::
        **Requires Bloomberg B-PIPE license.** This feature is not available
        with standard Terminal connections.

    Provides real-time updates for option chains or futures chains
    on a given underlying security.

    Args:
        underlying: Underlying security identifier.
        chain_type: Type of chain - "OPTIONS" or "FUTURES" (default: "OPTIONS").
        raw: If True, return raw pyarrow RecordBatch (default: False).
        backend: DataFrame backend to return. If None, uses global default.

    Returns:
        Subscription object for async iteration.

    Raises:
        BlpBPipeError: If B-PIPE license is not available.

    Example::

        # Subscribe to option chain
        async with await achains("AAPL US Equity") as sub:
            async for batch in sub:
                print(batch)  # Option chain updates

        # Subscribe to futures chain
        sub = await achains("ES1 Index", chain_type="FUTURES")
    """
    from xbbg.exceptions import BlpBPipeError

    logger.debug("achains: underlying=%s chain_type=%s", underlying, chain_type)

    effective_backend = (
        (Backend(backend) if isinstance(backend, str) else backend) if backend is not None else _default_backend
    )

    # Build subscription options
    options: list[str] = [f"chainType={chain_type}"]

    # Get engine and subscribe
    engine = _get_engine()
    try:
        py_sub = await engine.subscribe_with_options(
            Service.MKTLIST.value,
            [underlying],
            [],  # Fields depend on chain type
            options,
        )
    except Exception as e:
        # Check for B-PIPE related errors
        if "MKTLIST" in str(e).upper() or "SERVICE" in str(e).upper():
            raise BlpBPipeError("Option/futures chains require Bloomberg B-PIPE license.") from e
        raise

    return Subscription(py_sub, raw=raw, backend=effective_backend)


def chains(
    underlying: str,
    *,
    chain_type: str = "OPTIONS",
    raw: bool = False,
    backend: Backend | str | None = None,
) -> Subscription:
    """Subscribe to option or futures chain updates (sync version).

    .. warning::
        **Requires Bloomberg B-PIPE license.** This feature is not available
        with standard Terminal connections.

    Note: This returns an async Subscription. Use in an async context
    or call methods with asyncio.run().

    See achains() for full documentation.
    """
    return asyncio.run(
        achains(
            underlying,
            chain_type=chain_type,
            raw=raw,
            backend=backend,
        )
    )


# =============================================================================
# Technical Analysis API - Bloomberg Technical Analysis Service
# =============================================================================

# Study type to attribute name mapping
_TA_STUDIES: dict[str, str] = {
    # Moving Averages
    "smavg": "smavgStudyAttributes",
    "sma": "smavgStudyAttributes",
    "emavg": "emavgStudyAttributes",
    "ema": "emavgStudyAttributes",
    "wmavg": "wmavgStudyAttributes",
    "wma": "wmavgStudyAttributes",
    "vmavg": "vmavgStudyAttributes",
    "vma": "vmavgStudyAttributes",
    "tmavg": "tmavgStudyAttributes",
    "tma": "tmavgStudyAttributes",
    "ipmavg": "ipmavgStudyAttributes",
    # Oscillators
    "rsi": "rsiStudyAttributes",
    "macd": "macdStudyAttributes",
    "mao": "maoStudyAttributes",
    "momentum": "momentumStudyAttributes",
    "mom": "momentumStudyAttributes",
    "roc": "rocStudyAttributes",
    # Bands & Channels
    "boll": "bollStudyAttributes",
    "bb": "bollStudyAttributes",
    "kltn": "kltnStudyAttributes",
    "keltner": "kltnStudyAttributes",
    "mae": "maeStudyAttributes",
    "te": "teStudyAttributes",
    "al": "alStudyAttributes",
    # Trend
    "dmi": "dmiStudyAttributes",
    "adx": "dmiStudyAttributes",
    "tas": "tasStudyAttributes",
    "stoch": "tasStudyAttributes",
    "trender": "trenderStudyAttributes",
    "ptps": "ptpsStudyAttributes",
    "parabolic": "ptpsStudyAttributes",
    "sar": "ptpsStudyAttributes",
    # Volume
    "chko": "chkoStudyAttributes",
    "ado": "adoStudyAttributes",
    "vat": "vatStudyAttributes",
    "tvat": "tvatStudyAttributes",
    # Volatility
    "atr": "atrStudyAttributes",
    "hurst": "hurstStudyAttributes",
    # Other
    "fg": "fgStudyAttributes",
    "fear_greed": "fgStudyAttributes",
    "goc": "gocStudyAttributes",
    "ichimoku": "gocStudyAttributes",
    "cmci": "cmciStudyAttributes",
    "wlpr": "wlprStudyAttributes",
    "williams": "wlprStudyAttributes",
    "maxmin": "maxminStudyAttributes",
    "rex": "rexStudyAttributes",
    "etd": "etdStudyAttributes",
    "pd": "pdStudyAttributes",
    "rv": "rvStudyAttributes",
    "pivot": "pivotStudyAttributes",
    "or": "orStudyAttributes",
    "pcr": "pcrStudyAttributes",
    "bs": "bsStudyAttributes",
}

# Default study parameters
_TA_DEFAULTS: dict[str, dict[str, Any]] = {
    "smavgStudyAttributes": {"period": 20, "priceSourceClose": "PX_LAST"},
    "emavgStudyAttributes": {"period": 20, "priceSourceClose": "PX_LAST"},
    "wmavgStudyAttributes": {"period": 20, "priceSourceClose": "PX_LAST"},
    "vmavgStudyAttributes": {"period": 20, "priceSourceClose": "PX_LAST"},
    "tmavgStudyAttributes": {"period": 20, "priceSourceClose": "PX_LAST"},
    "rsiStudyAttributes": {"period": 14, "priceSourceClose": "PX_LAST"},
    "macdStudyAttributes": {
        "maPeriod1": 12,
        "maPeriod2": 26,
        "sigPeriod": 9,
        "priceSourceClose": "PX_LAST",
    },
    "bollStudyAttributes": {
        "period": 20,
        "upperBand": 2.0,
        "lowerBand": 2.0,
        "priceSourceClose": "PX_LAST",
    },
    "dmiStudyAttributes": {
        "period": 14,
        "priceSourceHigh": "PX_HIGH",
        "priceSourceLow": "PX_LOW",
        "priceSourceClose": "PX_LAST",
    },
    "atrStudyAttributes": {
        "maType": "Simple",
        "period": 14,
        "priceSourceHigh": "PX_HIGH",
        "priceSourceLow": "PX_LOW",
        "priceSourceClose": "PX_LAST",
    },
    "tasStudyAttributes": {
        "periodK": 14,
        "periodD": 3,
        "periodDS": 3,
        "periodDSS": 3,
        "priceSourceHigh": "PX_HIGH",
        "priceSourceLow": "PX_LOW",
        "priceSourceClose": "PX_LAST",
    },
}


def _get_study_attr_name(study: str) -> str:
    """Get the Bloomberg attribute name for a study."""
    study_lower = study.lower().replace("-", "_").replace(" ", "_")
    if study_lower in _TA_STUDIES:
        return _TA_STUDIES[study_lower]
    # Try direct match with StudyAttributes suffix
    if study_lower.endswith("studyattributes"):
        return study_lower
    return f"{study_lower}StudyAttributes"


def _build_study_request(
    ticker: str,
    study: str,
    start_date: str | None = None,
    end_date: str | None = None,
    periodicity: str = "DAILY",
    interval: int | None = None,
    **study_params,
) -> dict[str, Any]:
    """Build a studyRequest element for //blp/tasvc.

    Args:
        ticker: Security name
        study: Study type
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)
        periodicity: Data periodicity ('DAILY', 'WEEKLY', 'MONTHLY', or 'INTRADAY')
        interval: Intraday interval in minutes (only used if periodicity is INTRADAY)
        **study_params: Study-specific parameters (e.g., period=20 for SMA period)
    """
    attr_name = _get_study_attr_name(study)

    # Get defaults and merge with user params
    defaults = _TA_DEFAULTS.get(attr_name, {})
    params = {**defaults, **study_params}

    # Build data range
    if periodicity.upper() in ("DAILY", "WEEKLY", "MONTHLY"):
        data_range = {
            "historical": {
                "startDate": start_date or "",
                "endDate": end_date or "",
                "periodicitySelection": periodicity.upper(),
            }
        }
    else:
        # Intraday
        data_range = {
            "intraday": {
                "startDate": start_date or "",
                "endDate": end_date or "",
                "eventType": "TRADE",
                "interval": interval or 60,
            }
        }

    return {
        "priceSource": {"securityName": ticker, "dataRange": data_range},
        "studyAttributes": {attr_name: params},
    }


async def abta(
    tickers: str | list[str],
    study: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    periodicity: str = "DAILY",
    interval: int | None = None,
    **study_params,
) -> DataFrameResult:
    """Get technical analysis study data (async).

    Uses Bloomberg //blp/tasvc service to calculate technical indicators.

    Args:
        tickers: Security or list of securities
        study: Study type (e.g., 'sma', 'rsi', 'macd', 'boll', 'atr')
        start_date: Start date (YYYYMMDD format)
        end_date: End date (YYYYMMDD format)
        periodicity: Data periodicity ('DAILY', 'WEEKLY', 'MONTHLY', 'INTRADAY')
        interval: Intraday interval in minutes (only for periodicity='INTRADAY')
        **study_params: Study-specific parameters (e.g., period=20 for SMA period)

    Returns:
        DataFrame with study results

    Available Studies:
        Moving Averages: sma, ema, wma, vma, tma
        Oscillators: rsi, macd, mao, momentum, roc
        Bands: boll (Bollinger), keltner, mae
        Trend: dmi/adx, stoch, trender, parabolic/sar
        Volume: chko, ado, vat
        Volatility: atr, hurst
        Other: ichimoku, pivot, williams

    Example::

        # Simple Moving Average with 20-day period
        df = await xbbg.abta("AAPL US Equity", "sma", period=20)

        # RSI with 14-day period
        df = await xbbg.abta("AAPL US Equity", "rsi", period=14)

        # MACD with custom parameters
        df = await xbbg.abta("AAPL US Equity", "macd", maPeriod1=12, maPeriod2=26, sigPeriod=9)

        # Bollinger Bands with 20-day period and 2 std devs
        df = await xbbg.abta("AAPL US Equity", "boll", period=20, upperBand=2.0, lowerBand=2.0)

        # Intraday RSI with 60-minute bars
        df = await xbbg.abta("AAPL US Equity", "rsi", periodicity="INTRADAY", interval=60)

        # Multiple securities (sends concurrent requests)
        df = await xbbg.abta(["AAPL US Equity", "MSFT US Equity"], "rsi")
    """
    import warnings

    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    engine = _get_engine()

    async def fetch_single(ticker: str) -> pa.RecordBatch | Exception:
        """Fetch TA data for a single ticker."""
        request_elements = _build_study_request(
            ticker,
            study,
            start_date=start_date,
            end_date=end_date,
            periodicity=periodicity,
            interval=interval,
            **study_params,
        )
        params = RequestParams(
            service=Service.TASVC,
            operation=Operation.STUDY_REQUEST,
            extractor=ExtractorHint.GENERIC,
            json_elements=json.dumps(request_elements),
        )
        return await engine.request(params.to_dict())

    # tasvc only supports 1 security per request, so send concurrent requests
    results = await asyncio.gather(
        *[fetch_single(t) for t in ticker_list],
        return_exceptions=True,
    )

    # Filter successful results and warn about failures
    batches: list[pa.RecordBatch] = []
    for ticker, result in zip(ticker_list, results, strict=True):
        if isinstance(result, Exception):
            warnings.warn(f"Failed to fetch TA data for {ticker}: {result}", stacklevel=2)
        else:
            batches.append(result)

    if not batches:
        raise RuntimeError("All TA requests failed")

    # Combine all batches into a single table
    table = pa.concat_tables([pa.Table.from_batches([b]) for b in batches])
    return _convert_backend(nw.from_native(table), _default_backend)


def bta(
    tickers: str | list[str],
    study: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    periodicity: str = "DAILY",
    interval: int | None = None,
    **study_params,
) -> DataFrameResult:
    """Get technical analysis study data (sync).

    See abta() for full documentation.
    """
    return asyncio.run(
        abta(
            tickers,
            study,
            start_date=start_date,
            end_date=end_date,
            periodicity=periodicity,
            interval=interval,
            **study_params,
        )
    )


def ta_studies() -> list[str]:
    """List available technical analysis study names.

    Returns:
        List of study short names that can be used with bta()/abta()

    Example::

        >>> xbbg.ta_studies()
        ['sma', 'ema', 'rsi', 'macd', 'boll', 'atr', ...]
    """
    # Return unique study short names
    seen = set()
    result = []
    for name in _TA_STUDIES:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return sorted(result)


def ta_study_params(study: str) -> dict[str, Any]:
    """Get default parameters for a technical analysis study.

    Args:
        study: Study name (e.g., 'rsi', 'macd', 'boll')

    Returns:
        Dictionary of parameter names and their default values

    Example::

        >>> xbbg.ta_study_params('rsi')
        {'period': 14, 'priceSourceClose': 'PX_LAST'}

        >>> xbbg.ta_study_params('macd')
        {'maPeriod1': 12, 'maPeriod2': 26, 'sigPeriod': 9, 'priceSourceClose': 'PX_LAST'}

        >>> xbbg.ta_study_params('boll')
        {'period': 20, 'upperBand': 2.0, 'lowerBand': 2.0, 'priceSourceClose': 'PX_LAST'}
    """
    attr_name = _get_study_attr_name(study)
    return _TA_DEFAULTS.get(attr_name, {})


def generate_ta_stubs(output_dir: str | None = None) -> str:
    """Generate Python type stubs for technical analysis studies.

    Creates a .pyi file with TypedDict definitions for all TA study parameters.
    Stubs are generated from the //blp/tasvc schema for IDE autocomplete support.

    Args:
        output_dir: Output directory (default: ~/.xbbg/stubs/)

    Returns:
        Path to the generated stub file.

    Example::

        >>> xbbg.generate_ta_stubs()
        '~/.xbbg/stubs/ta_studies.pyi'

        # Then in your code, IDE will autocomplete:
        >>> from xbbg.stubs.ta_studies import RSIParams
        >>> params: RSIParams = {'period': 14}
    """
    from pathlib import Path

    from .schema import aget_schema

    # Get tasvc schema
    schema = asyncio.run(aget_schema("//blp/tasvc"))

    # Find studyRequest operation
    op = schema.get_operation("studyRequest")
    if not op:
        raise RuntimeError("Could not find studyRequest operation in tasvc schema")

    # Find studyAttributes element
    study_attrs = None
    for child in op.request.children:
        if child.name == "studyAttributes":
            study_attrs = child
            break

    if not study_attrs:
        raise RuntimeError("Could not find studyAttributes in schema")

    # Generate stub content
    lines = [
        '"""',
        "Bloomberg Technical Analysis Study Type Stubs",
        "",
        "Auto-generated from //blp/tasvc schema.",
        "DO NOT EDIT - regenerate using xbbg.generate_ta_stubs()",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import sys",
        "if sys.version_info >= (3, 11):",
        "    from typing import Literal, NotRequired, TypedDict",
        "else:",
        "    from typing import Literal",
        "    from typing_extensions import NotRequired, TypedDict",
        "",
    ]

    # Map of Bloomberg attribute names to friendly names
    attr_to_friendly = {v: k for k, v in _TA_STUDIES.items()}

    # Type mapping
    type_map = {
        "Bool": "bool",
        "Int32": "int",
        "Int64": "int",
        "Float32": "float",
        "Float64": "float",
        "String": "str",
        "Enumeration": "str",
    }

    # Generate TypedDict for each study
    for study_child in study_attrs.children:
        attr_name = study_child.name
        friendly = attr_to_friendly.get(attr_name, attr_name.replace("StudyAttributes", ""))

        # Create class name (e.g., rsiStudyAttributes -> RSIParams)
        class_name = friendly.upper() + "Params"
        if class_name.startswith("_"):
            class_name = class_name[1:]

        lines.append(f"class {class_name}(TypedDict, total=False):")
        lines.append(f'    """Parameters for {friendly} study."""')

        if not study_child.children:
            lines.append("    pass")
        else:
            for param in study_child.children:
                param_name = param.name
                if param.enum_values:
                    values_str = ", ".join(f'"{v}"' for v in param.enum_values)
                    param_type = f"Literal[{values_str}]"
                else:
                    param_type = type_map.get(param.data_type, "str")

                # Add default value comment if we have one
                defaults = _TA_DEFAULTS.get(attr_name, {})
                default_val = defaults.get(param_name)
                if default_val is not None:
                    lines.append(f"    {param_name}: NotRequired[{param_type}]  # default: {default_val}")
                else:
                    lines.append(f"    {param_name}: NotRequired[{param_type}]")

        lines.append("")

    # Add StudyName literal type
    study_names = sorted(set(_TA_STUDIES.keys()))
    lines.append("# All available study names")
    lines.append(f"StudyName = Literal[{', '.join(repr(s) for s in study_names)}]")
    lines.append("")

    # Write files
    output_path = Path.home() / ".xbbg" / "stubs" if output_dir is None else Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stub_path = output_path / "ta_studies.pyi"
    stub_path.write_text("\n".join(lines))

    # Also write .py for runtime imports
    py_path = output_path / "ta_studies.py"
    py_path.write_text("\n".join(lines))

    # Configure IDE
    from .schema import configure_ide_stubs

    ide_msg = configure_ide_stubs(output_path)
    print(ide_msg)

    return str(stub_path)


# =============================================================================
# BQL API - Bloomberg Query Language
# =============================================================================


async def abql(
    expression: str,
    *,
    backend: Backend | str | None = None,
) -> DataFrameResult:
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

    # Send BQL request via arequest with BQL extractor (parsed in Rust)
    nw_df = await arequest(
        service=Service.BQLSVC,
        operation=Operation.BQL_SEND_QUERY,
        overrides={"expression": expression},
        extractor=ExtractorHint.BQL,
        backend=None,
    )

    logger.debug("abql: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def bql(
    expression: str,
    *,
    backend: Backend | str | None = None,
) -> DataFrameResult:
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


async def absrch(
    domain: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
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

    # Send bsrch request via arequest with BSRCH extractor (parsed in Rust)
    nw_df = await arequest(
        service=Service.EXRSVC,
        operation=Operation.EXCEL_GET_GRID,
        overrides=overrides,
        extractor=ExtractorHint.BSRCH,
        backend=None,
    )

    logger.debug("absrch: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def bsrch(
    domain: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
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
) -> DataFrameResult:
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
) -> DataFrameResult:
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


# =============================================================================
# BEQS API - Bloomberg Equity Screening
# =============================================================================


async def abeqs(
    screen: str,
    *,
    asof: str | None = None,
    screen_type: str = "PRIVATE",
    group: str = "General",
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg Equity Screening (BEQS) request.

    Execute a saved Bloomberg equity screen and return matching securities.

    Args:
        screen: Screen name as saved in Bloomberg.
        asof: As-of date for the screen (YYYYMMDD format).
        screen_type: Screen type - "PRIVATE" (custom) or "GLOBAL" (Bloomberg).
        group: Group name if screen is organized into groups.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with columns from the screen results (security, fieldData, etc.).

    Example::

        # Run a private screen
        df = await abeqs("MyScreen")

        # Run with as-of date
        df = await abeqs("MyScreen", asof="20240101")

        # Run a Bloomberg global screen
        df = await abeqs("TOP_DECL_DVD", screen_type="GLOBAL")
    """
    logger.debug("abeqs: screen=%s asof=%s type=%s group=%s", screen, asof, screen_type, group)

    # Route kwargs to elements and overrides using schema introspection
    routed_elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.BEQS, dict(kwargs))

    # Build elements for BEQS request (core elements first)
    elements: list[tuple[str, Any]] = [
        ("screenName", screen),
        ("screenType", screen_type),
        ("Group", group),
    ]

    if asof:
        elements.append(("asOfDate", _fmt_date(asof)))

    # Add routed elements
    elements.extend(routed_elements)

    # Send BEQS request via arequest with JSON_ARROW extractor (parsed in Rust)
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.BEQS,
        elements=elements,
        overrides=overrides if overrides else None,
        extractor=ExtractorHint.JSON_ARROW,
        backend=None,
    )

    logger.debug("abeqs: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def beqs(
    screen: str,
    *,
    asof: str | None = None,
    screen_type: str = "PRIVATE",
    group: str = "General",
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Bloomberg Equity Screening (BEQS) request.

    Sync wrapper around abeqs(). For async usage, use abeqs() directly.

    Execute a saved Bloomberg equity screen and return matching securities.

    Args:
        screen: Screen name as saved in Bloomberg.
        asof: As-of date for the screen (YYYYMMDD format).
        screen_type: Screen type - "PRIVATE" (custom) or "GLOBAL" (Bloomberg).
        group: Group name if screen is organized into groups.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with columns: ticker, and any fields from the screen.

    Example::

        # Run a private screen
        df = beqs("MyScreen")

        # Run with as-of date
        df = beqs("MyScreen", asof="20240101")

        # Run a Bloomberg global screen
        df = beqs("TOP_DECL_DVD", screen_type="GLOBAL")
    """
    return asyncio.run(abeqs(screen, asof=asof, screen_type=screen_type, group=group, backend=backend, **kwargs))


# =============================================================================
# BLKP API - Bloomberg Security Lookup
# =============================================================================


async def ablkp(
    query: str,
    *,
    yellowkey: str = "YK_FILTER_NONE",
    language: str = "LANG_OVERRIDE_NONE",
    max_results: int = 20,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg security lookup (BLKP) request.

    Search for securities by company name or partial ticker.

    Args:
        query: Search query (company name or partial ticker).
        yellowkey: Asset class filter. Common values:
            - "YK_FILTER_NONE" (default, all asset classes)
            - "YK_FILTER_EQTY" (equities only)
            - "YK_FILTER_CORP" (corporate bonds)
            - "YK_FILTER_GOVT" (government bonds)
            - "YK_FILTER_INDX" (indices)
            - "YK_FILTER_CURR" (currencies)
            - "YK_FILTER_CMDT" (commodities)
        language: Language override for results.
        max_results: Maximum number of results (default: 20, max: 1000).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with columns: security, description, and other result fields.

    Example::

        # Search for Apple
        df = await ablkp("Apple")

        # Search for equities only
        df = await ablkp("NVDA", yellowkey="YK_FILTER_EQTY")

        # Get more results
        df = await ablkp("Microsoft", max_results=50)
    """
    logger.debug("ablkp: query=%s yellowkey=%s max_results=%d", query, yellowkey, max_results)

    # Route kwargs to elements using schema introspection
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.INSTRUMENT_LIST, dict(kwargs))

    # Build elements for instrumentListRequest (core elements first)
    elements: list[tuple[str, Any]] = [
        ("query", query),
        ("yellowKeyFilter", yellowkey),
        ("languageOverride", language),
        ("maxResults", max_results),
    ]

    # Add routed elements
    elements.extend(routed_elements)

    # Send request via arequest with JSON_ARROW extractor (parsed in Rust)
    nw_df = await arequest(
        service=Service.INSTRUMENTS,
        operation=Operation.INSTRUMENT_LIST,
        elements=elements,
        extractor=ExtractorHint.JSON_ARROW,
        backend=None,
    )

    logger.debug("ablkp: received %d rows", len(nw_df))

    return _convert_backend(nw_df, backend)


def blkp(
    query: str,
    *,
    yellowkey: str = "YK_FILTER_NONE",
    language: str = "LANG_OVERRIDE_NONE",
    max_results: int = 20,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Bloomberg security lookup (BLKP) request.

    Sync wrapper around ablkp(). For async usage, use ablkp() directly.

    Search for securities by company name or partial ticker.

    Args:
        query: Search query (company name or partial ticker).
        yellowkey: Asset class filter. Common values:
            - "YK_FILTER_NONE" (default, all asset classes)
            - "YK_FILTER_EQTY" (equities only)
            - "YK_FILTER_CORP" (corporate bonds)
            - "YK_FILTER_GOVT" (government bonds)
            - "YK_FILTER_INDX" (indices)
            - "YK_FILTER_CURR" (currencies)
            - "YK_FILTER_CMDT" (commodities)
        language: Language override for results.
        max_results: Maximum number of results (default: 20, max: 1000).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with columns: security, description.

    Example::

        # Search for Apple
        df = blkp("Apple")

        # Search for equities only
        df = blkp("NVDA", yellowkey="YK_FILTER_EQTY")

        # Get more results
        df = blkp("Microsoft", max_results=50)
    """
    return asyncio.run(
        ablkp(
            query,
            yellowkey=yellowkey,
            language=language,
            max_results=max_results,
            backend=backend,
            **kwargs,
        )
    )


# =============================================================================
# BPORT API - Bloomberg Portfolio Data
# =============================================================================


async def abport(
    portfolio: str,
    fields: str | Sequence[str],
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg portfolio data (BPORT) request.

    Get portfolio holdings and related data using PortfolioDataRequest.

    Args:
        portfolio: Portfolio identifier/name.
        fields: Field name or list of fields (e.g., "PORTFOLIO_MWEIGHT").
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters/overrides.

    Returns:
        DataFrame with portfolio data.

    Example::

        # Get portfolio weights
        df = await abport("MY_PORTFOLIO", "PORTFOLIO_MWEIGHT")

        # Get multiple fields
        df = await abport("MY_PORTFOLIO", ["PORTFOLIO_MWEIGHT", "PORTFOLIO_POSITION"])
    """
    field_list = _normalize_fields(fields)
    logger.debug("abport: portfolio=%s fields=%s", portfolio, field_list)

    # Route kwargs to elements and overrides
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.PORTFOLIO_DATA, dict(kwargs))

    # Send PortfolioDataRequest via arequest
    nw_df = await arequest(
        service=Service.REFDATA,
        operation=Operation.PORTFOLIO_DATA,
        securities=[portfolio],
        fields=field_list,
        elements=elements if elements else None,
        overrides=overrides if overrides else None,
        backend=None,
    )

    logger.debug("abport: received %d rows, %d columns", len(nw_df), len(nw_df.columns))

    return _convert_backend(nw_df, backend)


def bport(
    portfolio: str,
    fields: str | Sequence[str],
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Bloomberg portfolio data (BPORT) request.

    Sync wrapper around abport(). For async usage, use abport() directly.

    Get portfolio holdings and related data using PortfolioDataRequest.

    Args:
        portfolio: Portfolio identifier/name.
        fields: Field name or list of fields (e.g., "PORTFOLIO_MWEIGHT").
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters/overrides.

    Returns:
        DataFrame with portfolio data.

    Example::

        # Get portfolio weights
        df = bport("MY_PORTFOLIO", "PORTFOLIO_MWEIGHT")

        # Get multiple fields
        df = bport("MY_PORTFOLIO", ["PORTFOLIO_MWEIGHT", "PORTFOLIO_POSITION"])
    """
    return asyncio.run(abport(portfolio, fields, backend=backend, **kwargs))


# =============================================================================
# BCURVES API - Bloomberg Yield Curve List
# =============================================================================


async def abcurves(
    *,
    country: str | None = None,
    currency: str | None = None,
    curve_type: str | None = None,
    subtype: str | None = None,
    curveid: str | None = None,
    bbgid: str | None = None,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg yield curve list (BCURVES) request.

    Search for yield curves by country, currency, type, or other filters.

    Args:
        country: Country code filter (e.g., "US", "GB", "DE").
        currency: Currency code filter (e.g., "USD", "EUR", "GBP").
        curve_type: Curve type filter (e.g., "GOVERNMENT", "CORPORATE").
        subtype: Curve subtype filter.
        curveid: Specific curve ID to look up.
        bbgid: Bloomberg Global ID filter.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with yield curve information.

    Example::

        # List US yield curves
        df = await abcurves(country="US")

        # List USD government curves
        df = await abcurves(currency="USD", curve_type="GOVERNMENT")

        # Look up specific curve
        df = await abcurves(curveid="YCSW0023 Index")
    """
    logger.debug(
        "abcurves: country=%s currency=%s type=%s",
        country,
        currency,
        curve_type,
    )

    # Route kwargs to elements using schema introspection
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.CURVE_LIST, dict(kwargs))

    # Build elements for curveListRequest
    elements: list[tuple[str, Any]] = []

    if country is not None:
        elements.append(("countryCode", country))
    if currency is not None:
        elements.append(("currencyCode", currency))
    if curve_type is not None:
        elements.append(("type", curve_type))
    if subtype is not None:
        elements.append(("subtype", subtype))
    if curveid is not None:
        elements.append(("curveid", curveid))
    if bbgid is not None:
        elements.append(("bbgid", bbgid))

    # Add routed elements
    elements.extend(routed_elements)

    # Send request via arequest with JSON_ARROW extractor
    nw_df = await arequest(
        service=Service.INSTRUMENTS,
        operation=Operation.CURVE_LIST,
        elements=elements if elements else None,
        extractor=ExtractorHint.JSON_ARROW,
        backend=None,
    )

    logger.debug("abcurves: received %d rows", len(nw_df))

    return _convert_backend(nw_df, backend)


def bcurves(
    *,
    country: str | None = None,
    currency: str | None = None,
    curve_type: str | None = None,
    subtype: str | None = None,
    curveid: str | None = None,
    bbgid: str | None = None,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Bloomberg yield curve list (BCURVES) request.

    Sync wrapper around abcurves(). For async usage, use abcurves() directly.

    Search for yield curves by country, currency, type, or other filters.

    Args:
        country: Country code filter (e.g., "US", "GB", "DE").
        currency: Currency code filter (e.g., "USD", "EUR", "GBP").
        curve_type: Curve type filter (e.g., "GOVERNMENT", "CORPORATE").
        subtype: Curve subtype filter.
        curveid: Specific curve ID to look up.
        bbgid: Bloomberg Global ID filter.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with yield curve information.

    Example::

        # List US yield curves
        df = bcurves(country="US")

        # List USD government curves
        df = bcurves(currency="USD", curve_type="GOVERNMENT")

        # Look up specific curve
        df = bcurves(curveid="YCSW0023 Index")
    """
    return asyncio.run(
        abcurves(
            country=country,
            currency=currency,
            curve_type=curve_type,
            subtype=subtype,
            curveid=curveid,
            bbgid=bbgid,
            backend=backend,
            **kwargs,
        )
    )


# =============================================================================
# BGOVTS API - Bloomberg Government Securities List
# =============================================================================


async def abgovts(
    query: str | None = None,
    *,
    partial_match: bool = True,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg government securities list (BGOVTS) request.

    Search for government securities by ticker or name.

    Args:
        query: Search query (ticker or partial name).
        partial_match: If True, match partial ticker names (default: True).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with government securities information.

    Example::

        # Search for US Treasury securities
        df = await abgovts("T")

        # Search for German government bonds
        df = await abgovts("DBR")

        # Exact match only
        df = await abgovts("T 2.5 05/15/24", partial_match=False)
    """
    logger.debug("abgovts: query=%s partial_match=%s", query, partial_match)

    # Route kwargs to elements using schema introspection
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.GOVT_LIST, dict(kwargs))

    # Build elements for govtListRequest
    elements: list[tuple[str, Any]] = []

    if query is not None:
        elements.append(("ticker", query))
    elements.append(("partialMatch", partial_match))

    # Add routed elements
    elements.extend(routed_elements)

    # Send request via arequest with JSON_ARROW extractor
    nw_df = await arequest(
        service=Service.INSTRUMENTS,
        operation=Operation.GOVT_LIST,
        elements=elements if elements else None,
        extractor=ExtractorHint.JSON_ARROW,
        backend=None,
    )

    logger.debug("abgovts: received %d rows", len(nw_df))

    return _convert_backend(nw_df, backend)


def bgovts(
    query: str | None = None,
    *,
    partial_match: bool = True,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Bloomberg government securities list (BGOVTS) request.

    Sync wrapper around abgovts(). For async usage, use abgovts() directly.

    Search for government securities by ticker or name.

    Args:
        query: Search query (ticker or partial name).
        partial_match: If True, match partial ticker names (default: True).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional request parameters.

    Returns:
        DataFrame with government securities information.

    Example::

        # Search for US Treasury securities
        df = bgovts("T")

        # Search for German government bonds
        df = bgovts("DBR")

        # Exact match only
        df = bgovts("T 2.5 05/15/24", partial_match=False)
    """
    return asyncio.run(
        abgovts(
            query,
            partial_match=partial_match,
            backend=backend,
            **kwargs,
        )
    )


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
