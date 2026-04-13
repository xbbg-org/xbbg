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
import atexit
from collections.abc import Awaitable, Callable, Sequence
import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import functools
import inspect
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, TypeAlias, cast
import warnings

import narwhals.stable.v1 as nw
from narwhals.typing import IntoFrame
import pyarrow as pa

from xbbg.services import (
    ExtractorHint,
    Format,
    Operation,
    OutputMode,
    RequestParams,
    Service,
)

from ._exports import BLP_MODULE_EXPORTS
from .backend import Backend

# Type alias for backend conversion return types
# Covers: nw.DataFrame, nw.LazyFrame (narwhals wrappers) + IntoFrame (all native types)
DataFrameResult: TypeAlias = nw.DataFrame | nw.LazyFrame | IntoFrame

logger = logging.getLogger(__name__)


__all__ = list(BLP_MODULE_EXPORTS)


_REMOVED_LEGACY_ATTRS: dict[str, str] = {
    "connect": (
        "blp.connect() was removed in xbbg 1.0. The engine now starts automatically "
        "on the first request. If you need a non-default host, port, or auth (e.g. "
        "for B-PIPE), call xbbg.configure() once before your first request:\n\n"
        "    import xbbg\n"
        "    xbbg.configure(\n"
        "        host='bpipe-host',\n"
        "        port=8194,\n"
        "        auth_method='app',\n"
        "        app_name='my-app',\n"
        "    )\n\n"
        "See https://alpha-xone.github.io/xbbg/guides/migration/#connection-setup"
    ),
    "disconnect": (
        "blp.disconnect() was removed in xbbg 1.0. The engine lifecycle is managed "
        "automatically and you no longer need to disconnect. If you really need to "
        "tear down the engine (e.g. in tests), call xbbg.shutdown() or xbbg.reset()."
    ),
    "getBlpapiVersion": (
        "blp.getBlpapiVersion() was removed in xbbg 1.0. Use xbbg.get_sdk_info() "
        "instead, which returns a dict including 'runtime_version' (the linked C "
        "SDK version) and the active SDK source."
    ),
}


def __getattr__(name: str):
    msg = _REMOVED_LEGACY_ATTRS.get(name)
    if msg is not None:
        raise AttributeError(msg)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Generated sync wrappers are installed dynamically by _install_generated_endpoints().
# Define placeholders so static analysis recognizes these exported names.
if TYPE_CHECKING:
    bdp: Callable[..., Any]
    bdh: Callable[..., Any]
    bds: Callable[..., Any]
    bdib: Callable[..., Any]
    bdtick: Callable[..., Any]
    bql: Callable[..., Any]
    bsrch: Callable[..., Any]
    bqr: Callable[..., Any]
    bflds: Callable[..., Any]
    beqs: Callable[..., Any]
    blkp: Callable[..., Any]
    bport: Callable[..., Any]
    bcurves: Callable[..., Any]
    bgovts: Callable[..., Any]
else:
    (bdp, bdh, bds, bdib, bdtick, bql, bsrch, bqr, bflds, beqs, blkp, bport, bcurves, bgovts) = (None,) * 14


# Backend configuration
_default_backend: Backend | None = None

# Engine configuration (set before first use)
_config = None  # PyEngineConfig instance or None

# Lazy-load the engine to avoid import errors when the Rust module isn't built
_engine = None
_engine_lock = threading.Lock()

# Scoped engine for multi-engine routing (async-safe via contextvars)
_active_engine: contextvars.ContextVar[Engine | None] = contextvars.ContextVar("_active_engine", default=None)


class Engine:
    """Non-global Bloomberg engine for multi-source routing.

    Use as a context manager to scope all ``blp.*`` calls to this engine:

        engine = blp.Engine(host="bpipe.firm.com", auth_method="app", app_name="myapp")
        with engine:
            df = blp.bdp(...)  # uses this engine, not the global

    Or pass directly to individual calls:

        df = blp.bdp(..., engine=engine)

    The global ``configure()`` + ``blp.bdp()`` API is unaffected.
    """

    def __init__(self, **kwargs: Any) -> None:
        from . import _core

        normalized = _normalize_config_kwargs(kwargs)
        config = _core.PyEngineConfig(**normalized)
        self._config_snapshot = config
        self._py_engine = _core.PyEngine.with_config(config)
        self._token: contextvars.Token | None = None

    def __enter__(self) -> Engine:
        self._token = _active_engine.set(self)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._token is not None:
            _active_engine.reset(self._token)
            self._token = None

    async def __aenter__(self) -> Engine:
        self._token = _active_engine.set(self)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._token is not None:
            _active_engine.reset(self._token)
            self._token = None

    def shutdown(self) -> None:
        self._py_engine.signal_shutdown()


RequestHandler: TypeAlias = Callable[["RequestContext"], Awaitable[DataFrameResult]]
RequestMiddleware: TypeAlias = Callable[
    ["RequestContext", RequestHandler],
    DataFrameResult | Awaitable[DataFrameResult],
]


@dataclass(frozen=True, slots=True)
class RequestEnvironment:
    """Read-only engine and auth snapshot available to request middleware."""

    source: str
    host: str | None = None
    port: int | None = None
    servers: tuple[tuple[str, int], ...] = ()
    zfp_remote: str | None = None
    auth_method: str | None = None
    app_name: str | None = None
    user_id: str | None = None
    validation_mode: str | None = None


@dataclass(slots=True)
class RequestContext:
    """Mutable context object passed through the request middleware chain."""

    request_id: str
    params: RequestParams
    params_dict: dict[str, Any]
    backend: Backend | str | None
    securities: list[str]
    fields: list[str]
    environment: RequestEnvironment
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)
    elapsed_ms: float | None = None
    batch: pa.RecordBatch | None = None
    table: pa.Table | None = None
    frame: DataFrameResult | None = None
    error: Exception | None = None


_request_middleware: list[RequestMiddleware] = []


async def _await_request_value(value: DataFrameResult | Awaitable[DataFrameResult]) -> DataFrameResult:
    if inspect.isawaitable(value):
        return cast("DataFrameResult", await value)
    return value


def add_middleware(middleware: RequestMiddleware) -> RequestMiddleware:
    """Register a request middleware callable.

    Middleware is called as ``middleware(context, call_next)`` and may be sync or async.
    Returning the middleware makes this usable as a decorator.
    """
    _request_middleware.append(middleware)
    return middleware


def remove_middleware(middleware: RequestMiddleware) -> None:
    """Remove a previously registered middleware callable."""
    _request_middleware.remove(middleware)


def clear_middleware() -> None:
    """Remove all registered middleware."""
    _request_middleware.clear()


def get_middleware() -> tuple[RequestMiddleware, ...]:
    """Return the currently registered middleware chain."""
    return tuple(_request_middleware)


def set_middleware(middleware: Sequence[RequestMiddleware]) -> None:
    """Replace the current middleware chain."""
    _request_middleware[:] = list(middleware)


async def _run_request_middleware(
    context: RequestContext,
    terminal: RequestHandler,
) -> DataFrameResult:
    async def invoke(index: int, current_context: RequestContext) -> DataFrameResult:
        if index >= len(_request_middleware):
            return await terminal(current_context)

        middleware = _request_middleware[index]

        async def call_next(next_context: RequestContext) -> DataFrameResult:
            return await invoke(index + 1, next_context)

        try:
            return await _await_request_value(middleware(current_context, call_next))
        except Exception as exc:
            current_context.error = exc
            raise

    return await invoke(0, context)


# =============================================================================
# Engine Lifecycle Management
# =============================================================================


def _atexit_cleanup() -> None:
    """Release engine reference during interpreter shutdown.

    This is called automatically by atexit. The Rust Drop chain handles
    actual cleanup (signaling worker threads to stop).

    Non-blocking: just releases the reference, doesn't wait for threads.
    """
    global _engine
    if _engine is not None:
        try:
            _engine.signal_shutdown()
        except Exception:
            logger.debug("Exception during atexit cleanup (ignored)", exc_info=True)
        _engine = None


# Register cleanup handler
atexit.register(_atexit_cleanup)


def shutdown() -> None:
    """Signal the Bloomberg engine to shutdown.

    Signals all worker threads to stop. They will terminate when they
    finish their current work or see the shutdown signal.

    This is called automatically during Python interpreter shutdown.
    You usually don't need to call this directly.

    Example::

        import xbbg

        df = xbbg.bdp("AAPL US Equity", "PX_LAST")

        # Explicit shutdown (optional - happens automatically on exit)
        xbbg.shutdown()
    """
    global _engine
    if _engine is not None:
        _engine.signal_shutdown()
        _engine = None


def reset() -> None:
    """Reset the engine to allow reconfiguration.

    Shuts down the current engine (if any) and clears configuration.
    The next Bloomberg request will create a fresh engine.

    Example::

        import xbbg

        # Initial usage
        df = xbbg.bdp("AAPL US Equity", "PX_LAST")

        # Need different config? Reset first
        xbbg.reset()
        xbbg.configure(port=9999)
        df = xbbg.bdp("AAPL US Equity", "PX_LAST")  # Uses new config
    """
    global _engine, _config
    shutdown()
    _config = None


def is_connected() -> bool:
    """Check if Bloomberg is connected and healthy.

    Returns True if the engine exists and at least one worker has
    a live Bloomberg session. Returns False if the engine hasn't
    been created yet or all workers have lost their connection.

    Example::

        import xbbg

        print(xbbg.is_connected())  # False - not initialized yet

        df = xbbg.bdp("AAPL US Equity", "PX_LAST")

        print(xbbg.is_connected())  # True - connected
    """
    if _engine is None:
        return False
    return _engine.is_connected()


_VALID_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "host",
        "port",
        "servers",
        "zfp_remote",
        "request_pool_size",
        "subscription_pool_size",
        "validation_mode",
        "subscription_flush_threshold",
        "max_event_queue_size",
        "command_queue_size",
        "subscription_stream_capacity",
        "overflow_policy",
        "warmup_services",
        "field_cache_path",
        "auth_method",
        "app_name",
        "dir_property",
        "user_id",
        "ip_address",
        "token",
        "tls_client_credentials",
        "tls_client_credentials_password",
        "tls_trust_material",
        "tls_handshake_timeout_ms",
        "tls_crl_fetch_timeout_ms",
        "num_start_attempts",
        "auto_restart_on_disconnection",
        "max_recovery_attempts",
        "recovery_timeout_ms",
        "retry_max_retries",
        "retry_initial_delay_ms",
        "retry_backoff_factor",
        "retry_max_delay_ms",
        "health_check_interval_ms",
        "sdk_log_level",
        "socks5_host",
        "socks5_port",
    }
)


def _normalize_config_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(kwargs) - _VALID_CONFIG_KEYS)
    if unknown:
        raise TypeError(
            f"xbbg.configure() got unexpected keyword argument(s): {', '.join(unknown)}. "
            f"See EngineConfig() for available fields."
        )
    return dict(kwargs)


def configure(
    config=None,
    **kwargs,
) -> None:
    """Configure the xbbg engine before first use.

    This function must be called before any Bloomberg request is made.
    If called after the engine has started, the existing engine is shut
    down and will restart with the new config on next use.

    Can be called with an EngineConfig object, keyword arguments, or both
    (kwargs override config fields). All defaults come from Rust.

    See ``EngineConfig()`` for available fields and their defaults::

        >>> from xbbg import EngineConfig
        >>> EngineConfig()
        EngineConfig(host='localhost', port=8194, request_pool_size=2,
                     subscription_pool_size=1, ...)

    Args:
        config: An EngineConfig object with all settings.
        **kwargs: Override individual fields (host, port, request_pool_size,
            subscription_pool_size, field_cache_path, auth_method, app_name,
            user_id, ip_address, token, etc.).

    Raises:
        TypeError: If an unknown keyword argument is passed.
        ValueError: If `num_start_attempts` is less than 1.
        RuntimeWarning: If called after the engine has already started
            (the existing engine is shut down and will restart with the new config).

    Example::

        import xbbg

        # Option 1: Using keyword arguments (most common)
        xbbg.configure(request_pool_size=4, subscription_pool_size=2)

        # Option 2: Using EngineConfig object
        from xbbg import EngineConfig

        xbbg.configure(EngineConfig(request_pool_size=4))

        # Option 3: EngineConfig + overrides
        cfg = EngineConfig(request_pool_size=4)
        xbbg.configure(cfg, subscription_pool_size=2)

        # Option 4: B-PIPE / SAPI authentication
        xbbg.configure(
            host="bpipe-host",
            port=8195,
            auth_method="manual",
            app_name="my-app",
            user_id="123456",
            ip_address="10.0.0.1",
            num_start_attempts=5,
            auto_restart_on_disconnection=False,
        )

        # Option 5: Custom field cache location
        xbbg.configure(field_cache_path="/data/bloomberg/field_cache.json")
    """
    global _config, _engine

    normalized = _normalize_config_kwargs(kwargs)

    if (num_start_attempts := normalized.get("num_start_attempts")) is not None and num_start_attempts < 1:
        raise ValueError("num_start_attempts must be at least 1")

    with _engine_lock:
        if _engine is not None:
            warnings.warn(
                "xbbg.configure() called after engine was already started. "
                "The existing engine has been shut down and will restart with new config on next use. "
                "To avoid this, call configure() before any Bloomberg request, "
                "or use xbbg.Engine(...) for scoped configuration.",
                RuntimeWarning,
                stacklevel=2,
            )
            _engine.signal_shutdown()
            _engine = None

    from . import _core

    if config is not None:
        # Start from the provided config, apply kwargs on top
        _config = config
        for key, value in normalized.items():
            setattr(_config, key, value)
    else:
        # Build from kwargs; PyEngineConfig fills Rust defaults for anything unset
        _config = _core.PyEngineConfig(**normalized)

    logger.info("Engine configured: %s", _config)


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


def _resolve_backend(backend: Backend | str | None) -> Backend | None:
    """Resolve per-request backend with global fallback."""
    if backend is None:
        return _default_backend
    return Backend(backend) if isinstance(backend, str) else backend


def _get_engine(*, engine: Engine | None = None):
    """Get the active engine: explicit arg > contextvar scope > global singleton.

    Thread-safe: uses double-checked locking for the global singleton.
    """
    if engine is not None:
        return engine._py_engine

    scoped = _active_engine.get()
    if scoped is not None:
        return scoped._py_engine

    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from . import _core

                if _config is not None:
                    logger.debug("Creating PyEngine with config: %s", _config)
                    _engine = _core.PyEngine.with_config(_config)
                else:
                    logger.debug("Creating PyEngine with default config")
                    _engine = _core.PyEngine()
                logger.info("PyEngine connected to Bloomberg")
    return _engine


def _coerce_server_snapshot(value: Any) -> tuple[tuple[str, int], ...]:
    if not value:
        return ()

    servers: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        host, port = item
        try:
            servers.append((str(host), int(port)))
        except (TypeError, ValueError):
            continue
    return tuple(servers)


def _snapshot_request_environment() -> RequestEnvironment:
    scoped = _active_engine.get()
    if scoped is not None:
        config = getattr(scoped, "_config_snapshot", None)
        source = "scoped_engine"
    elif _config is not None:
        config = _config
        source = "global_config"
    else:
        config = None
        source = "default_engine"

    if config is None:
        return RequestEnvironment(source=source, host="localhost", port=8194)

    host = getattr(config, "host", None)
    port = getattr(config, "port", None)
    servers = _coerce_server_snapshot(getattr(config, "servers", None))
    if not servers and host is not None and port is not None:
        try:
            servers = ((str(host), int(port)),)
        except (TypeError, ValueError):
            servers = ()

    return RequestEnvironment(
        source=source,
        host=str(host) if host is not None else None,
        port=int(port) if port is not None else None,
        servers=servers,
        zfp_remote=getattr(config, "zfp_remote", None),
        auth_method=getattr(config, "auth_method", None),
        app_name=getattr(config, "app_name", None),
        user_id=getattr(config, "user_id", None),
        validation_mode=getattr(config, "validation_mode", None),
    )


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
        logger.debug("Schema lookup failed for %s/%s, using empty set", service, operation, exc_info=True)
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


def _convert_backend(
    nw_df: Any,
    backend: Backend | str | None,
) -> DataFrameResult:
    """Convert narwhals DataFrame to the requested backend.

    Uses Any for input because the narwhals generic type system makes
    precise typing of the wrapper impractical.
    """
    effective = _resolve_backend(backend)

    import pandas as pd

    if isinstance(nw_df, pd.DataFrame):
        if effective == Backend.PANDAS:
            return nw_df
        nw_df = nw.from_native(nw_df)

    if effective == Backend.PANDAS:
        return nw_df.to_pandas()
    if effective == Backend.POLARS:
        import polars as pl

        native = nw_df.to_native()
        if isinstance(native, pl.DataFrame):
            return native
        if isinstance(native, pa.Table):
            return pl.from_arrow(native)
        return pl.from_pandas(nw_df.to_pandas())
    if effective == Backend.POLARS_LAZY:
        import polars as pl

        native = nw_df.to_native()
        if isinstance(native, pl.DataFrame):
            return native.lazy()
        if isinstance(native, pa.Table):
            return pl.from_arrow(native).lazy()
        return pl.from_pandas(nw_df.to_pandas()).lazy()
    if effective == Backend.PYARROW:
        native = nw_df.to_native()
        if isinstance(native, pa.Table):
            return native
        if isinstance(native, pd.DataFrame):
            return pa.Table.from_pandas(native)
        if hasattr(native, "to_arrow"):
            return native.to_arrow()  # polars — capability check avoids importing an optional dep
        return pa.Table.from_pandas(nw_df.to_pandas())
    if effective == Backend.NARWHALS_LAZY:
        # Return narwhals LazyFrame (backed by polars)
        return nw_df.lazy()
    if effective == Backend.DUCKDB:
        # Convert to DuckDB relation via narwhals lazy with duckdb backend
        return nw_df.lazy(backend="duckdb")
    # Default: return narwhals DataFrame
    return nw_df


async def _execute_request_terminal(context: RequestContext) -> DataFrameResult:
    engine = _get_engine()
    started = time.perf_counter()

    try:
        batch = await engine.request(context.params_dict)
    except Exception as exc:
        context.elapsed_ms = (time.perf_counter() - started) * 1000
        context.error = exc
        raise

    context.batch = batch
    context.elapsed_ms = (time.perf_counter() - started) * 1000

    logger.info(
        "bloomberg %s.%s [request_id=%s]: %d rows in %.1fms | securities=%s fields=%s",
        context.params.service,
        context.params.operation,
        context.request_id,
        batch.num_rows,
        context.elapsed_ms,
        context.securities or None,
        context.fields or None,
    )

    context.table = pa.Table.from_batches([batch])
    nw_df = nw.from_native(context.table)
    context.frame = _convert_backend(nw_df, context.backend)
    return context.frame


# =============================================================================
# Generic API - Power Users
# =============================================================================


async def arequest(
    service: str | Service,
    operation: str | Operation,
    *,
    request_operation: str | Operation | None = None,
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
    event_types: Sequence[str] | None = None,
    interval: int | None = None,
    options: dict[str, Any] | Sequence[tuple[str, str]] | None = None,
    field_types: dict[str, str] | None = None,
    output: OutputMode | str = OutputMode.ARROW,
    extractor: ExtractorHint | str | None = None,
    format: Format | str | None = None,
    include_security_errors: bool = False,
    validate_fields: bool | None = None,
    backend: Backend | str | None = None,
    request_tz: str | None = None,
    output_tz: str | None = None,
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
        request_operation: Actual Bloomberg operation name when using
            ``Operation.RAW_REQUEST`` as the low-level escape hatch.
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
        request_tz: For intraday requests, how naive datetimes are interpreted before
            sending to Bloomberg (``UTC``, ``local``, ``exchange``, aliases, or IANA).
            Resolved and converted to UTC in the Rust engine.
        output_tz: For intraday responses, relabel the ``time`` column to this zone
            (same instants; handled in the Rust engine).
        event_type: Event type for intraday bars (TRADE, BID, ASK, etc.).
        interval: Bar interval in minutes for intraday bars.
        options: Additional Bloomberg options as dict or list of (key, value) tuples.
        field_types: Manual type overrides for fields (for future type resolution).
        output: Output format: OutputMode.ARROW (default) or OutputMode.JSON.
        extractor: Override the auto-detected extractor. Use ExtractorHint.BULK for
            bulk data fields. If None, auto-detected from operation.
        format: Output format hint for result structure.
        include_security_errors: Include ``__SECURITY_ERROR__`` rows for
            failed securities on ReferenceData requests.
        validate_fields: Optional per-request override for field validation.
            ``True`` forces strict validation, ``False`` disables it, and
            ``None`` follows engine-level validation mode.
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

        # Raw request marker with explicit Bloomberg operation
        df = await arequest(
            Service.REFDATA,
            Operation.RAW_REQUEST,
            request_operation=Operation.REFERENCE_DATA,
            extractor=ExtractorHint.REFDATA,
            securities=["AAPL US Equity"],
            fields=["PX_LAST"],
        )
    """
    # Normalize inputs
    securities_list = _normalize_tickers(securities) if securities is not None else None
    fields_list = _normalize_fields(fields) if fields is not None else None

    overrides_list: list[tuple[str, str]] | None = None
    elements_list: list[tuple[str, Any]] | None = None

    # Handle explicit elements parameter
    # Convert all element values to strings because the PyO3 boundary expects Vec<(String, String)>.
    # Booleans are lowercased ("true"/"false") to match Bloomberg schema expectations.
    if elements is not None:
        elements_list = [(str(k), str(v).lower() if isinstance(v, bool) else str(v)) for k, v in elements]

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
        request_operation=request_operation,
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
        event_types=list(event_types) if event_types else None,
        interval=interval,
        options=options_list,
        field_types=field_types,
        output=OutputMode(output) if isinstance(output, str) else output,
        extractor=extractor_hint,
        format=format_hint,
        include_security_errors=include_security_errors,
        validate_fields=validate_fields,
        request_tz=request_tz,
        output_tz=output_tz,
    )
    params.validate()

    params_dict = params.to_dict()
    request_id = f"req-{time.time_ns()}"
    params_dict["request_id"] = request_id
    context = RequestContext(
        request_id=request_id,
        params=params,
        params_dict=params_dict,
        backend=backend,
        securities=list(securities_list or []),
        fields=list(fields_list or []),
        environment=_snapshot_request_environment(),
    )

    try:
        return await _run_request_middleware(context, _execute_request_terminal)
    except Exception as exc:
        context.error = exc
        raise


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
    include_security_errors: bool = False,
    validate_fields: bool | None = None,
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
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
            If None, types are auto-resolved from Bloomberg field metadata.
        include_security_errors: Include ``__SECURITY_ERROR__`` rows for
            securities that Bloomberg rejected.
        validate_fields: Optional per-request override for field validation.
            ``True`` forces strict validation, ``False`` disables it, and
            ``None`` follows engine-level validation mode.
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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abdp"], locals())


async def abdh(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str = "today",
    *,
    backend: Backend | str | None = None,
    format: Format | str | None = None,
    field_types: dict[str, str] | None = None,
    validate_fields: bool | None = None,
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
        field_types: Manual type overrides for fields (e.g., {'VOLUME': 'int64'}).
            If None, types are auto-resolved from Bloomberg field metadata.
        validate_fields: Optional per-request override for field validation.
            ``True`` forces strict validation, ``False`` disables it, and
            ``None`` follows engine-level validation mode.
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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abdh"], locals())


async def abds(
    tickers: str | Sequence[str],
    flds: str,
    *,
    backend: Backend | str | None = None,
    validate_fields: bool | None = None,
    **kwargs,
):
    """Async Bloomberg bulk data (BDS).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field name (bulk fields return multiple rows).
        backend: DataFrame backend to return. If None, uses global default.
        validate_fields: Optional per-request override for field validation.
            ``True`` forces strict validation, ``False`` disables it, and
            ``None`` follows engine-level validation mode.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        DataFrame with bulk data, multiple rows per ticker.

    Example::

        df = await abds("AAPL US Equity", "DVD_Hist_All")
        df = await abds("SPX Index", "INDX_MEMBERS", backend="polars")
    """
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abds"], locals())


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
    request_tz: str | None = None,
    output_tz: str | None = None,
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
        request_tz: How naive ``start_datetime`` / ``end_datetime`` (and full-day ``dt`` window)
            are interpreted before Bloomberg: ``UTC`` (default when omitted), ``local``,
            ``exchange`` (uses this ticker), ``NY``/``LN``/``TK``/``HK``, another ticker string,
            or an IANA zone. Conversion to UTC is done in the Rust engine.
        output_tz: Relabel the ``time`` column to this zone (same instants; Rust engine).
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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abdib"], locals())


async def abdtick(
    ticker: str,
    start_datetime: str,
    end_datetime: str,
    *,
    event_types: Sequence[str] | None = None,
    backend: Backend | str | None = None,
    request_tz: str | None = None,
    output_tz: str | None = None,
    **kwargs,
):
    """Async Bloomberg tick data (BDTICK).

    Args:
        ticker: Ticker name.
        start_datetime: Start datetime.
        end_datetime: End datetime.
        event_types: Event types to retrieve. Defaults to ["TRADE"].
            Options: TRADE, BID, ASK, BID_BEST, ASK_BEST, MID_PRICE, AT_TRADE, BEST_BID, BEST_ASK.
        backend: DataFrame backend to return. If None, uses global default.
        request_tz: How naive datetimes are interpreted before Bloomberg (see ``abdib``).
        output_tz: Relabel ``time`` column (same instants; Rust engine).
        **kwargs: Additional options.

    Returns:
        DataFrame with tick data.

    Example::

        df = await abdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00")
        df = await abdtick(
            "AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00", event_types=["TRADE", "BID", "ASK"]
        )
        df = await abdtick("AAPL US Equity", "2024-12-01 09:30", "2024-12-01 10:00", backend="polars")
    """
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abdtick"], locals())


# =============================================================================
# Sync API - Convenience Wrappers
# =============================================================================


@dataclass(frozen=True)
class _EndpointPlan:
    request_kwargs: dict[str, Any]
    backend: Backend | str | None
    postprocess: Callable[[Any], DataFrameResult] | None = None
    service: Service | None = None
    operation: Operation | None = None
    extractor: ExtractorHint | None = None


@dataclass(frozen=True)
class _GeneratedEndpointSpec:
    async_name: str
    sync_name: str
    service: Service
    operation: Operation
    builder: Callable[[dict[str, Any]], Awaitable[_EndpointPlan] | _EndpointPlan]
    extractor: ExtractorHint | None = None


_GENERATED_ENDPOINT_SPECS: dict[str, _GeneratedEndpointSpec] = {}


def _strip_signature_annotations(func: Callable[..., Any]) -> str:
    signature = inspect.signature(func)
    stripped_params = [param.replace(annotation=inspect._empty) for param in signature.parameters.values()]
    stripped = signature.replace(parameters=stripped_params, return_annotation=inspect._empty)
    return str(stripped)


def _build_sync_wrapper(
    sync_name: str,
    async_func: Callable[..., Any],
    *,
    template: Callable[..., Any] | None = None,
) -> Callable[..., Any]:
    template_func = template if template is not None else async_func

    @functools.wraps(template_func)
    def wrapped(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass  # No running loop — asyncio.run() is safe
        else:
            raise RuntimeError(
                f"{sync_name}() cannot be used inside an async context "
                f"(FastAPI, Jupyter, etc.). "
                f"Use 'await a{sync_name}()' instead, "
                f"or use xbbg.Engine(...) for scoped async engines."
            )
        return asyncio.run(async_func(*args, **kwargs))

    wrapped.__name__ = sync_name
    wrapped.__qualname__ = sync_name
    wrapped.__module__ = __name__
    wrapped.__signature__ = inspect.signature(template_func)  # type: ignore[unresolved-attribute]
    return wrapped


async def _execute_generated_endpoint(spec: _GeneratedEndpointSpec, call_args: dict[str, Any]) -> DataFrameResult:
    plan_or_awaitable = spec.builder(call_args)
    if inspect.isawaitable(plan_or_awaitable):
        plan: _EndpointPlan = cast("_EndpointPlan", await plan_or_awaitable)
    else:
        plan = plan_or_awaitable

    request_kwargs = dict(plan.request_kwargs)
    if plan.extractor is not None:
        request_kwargs["extractor"] = plan.extractor
    elif spec.extractor is not None and "extractor" not in request_kwargs:
        request_kwargs["extractor"] = spec.extractor

    service = plan.service if plan.service is not None else spec.service
    operation = plan.operation if plan.operation is not None else spec.operation

    nw_df = await arequest(
        service=service,
        operation=operation,
        backend=None,
        **request_kwargs,
    )

    if plan.postprocess is not None:
        return plan.postprocess(nw_df)

    return _convert_backend(nw_df, plan.backend)


def _build_generated_async(spec: _GeneratedEndpointSpec, async_template: Callable[..., Any]) -> Callable[..., Any]:
    signature_text = _strip_signature_annotations(async_template)
    source = (
        f"async def {spec.async_name}{signature_text}:\n"
        f"    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS[{spec.async_name!r}], locals())"
    )
    namespace: dict[str, Any] = {}
    exec(source, globals(), namespace)
    generated = namespace[spec.async_name]
    generated.__doc__ = async_template.__doc__
    generated.__annotations__ = dict(getattr(async_template, "__annotations__", {}))
    generated.__module__ = __name__
    generated.__qualname__ = spec.async_name
    return generated


def _install_generated_endpoint(spec: _GeneratedEndpointSpec) -> None:
    async_template = globals()[spec.async_name]
    generated_async = _build_generated_async(spec, async_template)
    globals()[spec.async_name] = generated_async

    globals()[spec.sync_name] = _build_sync_wrapper(spec.sync_name, generated_async, template=async_template)


def _install_generated_endpoints() -> None:
    for spec in _GENERATED_ENDPOINT_SPECS.values():
        _install_generated_endpoint(spec)


# Generated endpoint sync wrappers are installed via _install_generated_endpoints().


# =============================================================================
# Streaming API - Real-time Market Data
# =============================================================================


# Bloomberg field values can be various primitive types
TickValue: TypeAlias = float | int | str | bool | datetime | None


@dataclass
class Tick:
    """Single tick data point from a subscription.

    Attributes:
        ticker: Security identifier
        field: Bloomberg field name
        value: Field value (float, int, str, bool, datetime, or None)
        timestamp: Time the tick was received
    """

    ticker: str
    field: str
    value: TickValue
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

    def __init__(self, py_sub, raw: bool, backend: Backend | None, tick_mode: bool = False):
        """Initialize subscription wrapper.

        Args:
            py_sub: The underlying PySubscription from Rust
            raw: If True, yield raw Arrow batches
            backend: DataFrame backend for conversion (if not raw)
            tick_mode: If True, convert batches to dicts (implies raw=True)
        """
        self._sub = py_sub
        self._raw = raw
        self._backend = backend
        self._tick_mode = tick_mode

    def __aiter__(self):
        return self

    async def __anext__(self) -> pa.RecordBatch | nw.DataFrame | dict[str, Any]:
        """Get next batch of data."""
        batch = await self._sub.__anext__()

        # Tick mode: convert RecordBatch to dict
        if self._tick_mode:
            return {field.name: batch.column(i)[0].as_py() for i, field in enumerate(batch.schema)}

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
        ticker_list = _normalize_tickers(tickers)
        logger.debug("subscription add: %s", ticker_list)
        await self._sub.add(ticker_list)

    async def remove(self, tickers: str | list[str]) -> None:
        """Remove tickers from subscription dynamically.

        Args:
            tickers: Single ticker or list of tickers to remove
        """
        ticker_list = _normalize_tickers(tickers)
        logger.debug("subscription remove: %s", ticker_list)
        await self._sub.remove(ticker_list)

    @property
    def tickers(self) -> list[str]:
        """Currently active tickers."""
        return self._sub.tickers

    @property
    def failed_tickers(self) -> list[str]:
        """Tickers Bloomberg rejected or terminated."""
        return self._sub.failed_tickers

    @property
    def failures(self) -> list[dict[str, str]]:
        """Non-fatal per-ticker subscription failures.

        Each entry contains:
            - ticker: Bloomberg topic string
            - reason: Bloomberg failure detail
            - kind: "failure" or "terminated"
        """
        return [{"ticker": ticker, "reason": reason, "kind": kind} for ticker, reason, kind in self._sub.failures]

    @property
    def topic_states(self) -> dict[str, dict[str, int | str]]:
        """Topic lifecycle state keyed by ticker/topic."""
        return {
            ticker: {"state": state, "last_change_us": last_change_us}
            for ticker, state, last_change_us in self._sub.topic_states
        }

    @property
    def session_status(self) -> dict[str, int | str]:
        """Session-level connection status for this subscription."""
        return dict(self._sub.session_status)

    @property
    def admin_status(self) -> dict[str, int | bool | None]:
        """Bloomberg admin/slow-consumer status for this subscription."""
        return dict(self._sub.admin_status)

    @property
    def service_status(self) -> dict[str, dict[str, int | bool]]:
        """Service availability status keyed by Bloomberg service name."""
        return {
            service: {"up": up, "last_change_us": last_change_us}
            for service, up, last_change_us in self._sub.service_status
        }

    @property
    def events(self) -> list[dict[str, str | int | None]]:
        """Bounded lifecycle/event history for the subscription."""
        return [
            {
                "at_us": at_us,
                "category": category,
                "level": level,
                "message_type": message_type,
                "topic": topic,
                "detail": detail,
            }
            for at_us, category, level, message_type, topic, detail in self._sub.events
        ]

    @property
    def status(self) -> dict[str, Any]:
        """Combined operational status snapshot."""
        return {
            "active": self.is_active,
            "all_failed": self.all_failed,
            "tickers": self.tickers,
            "failed_tickers": self.failed_tickers,
            "topic_states": self.topic_states,
            "session": self.session_status,
            "admin": self.admin_status,
            "services": self.service_status,
        }

    @property
    def fields(self) -> list[str]:
        """Subscribed fields."""
        return self._sub.fields

    @property
    def is_active(self) -> bool:
        """Whether the subscription is still active."""
        return self._sub.is_active

    @property
    def all_failed(self) -> bool:
        """Whether every requested ticker has ended in failure/termination."""
        return self._sub.all_failed

    @property
    def stats(self) -> dict:
        """Subscription metrics.

        Returns:
            dict with keys:
                - messages_received: int - total messages received from Bloomberg
                - dropped_batches: int - batches dropped due to overflow
                - batches_sent: int - batches successfully sent to Python
                - slow_consumer: bool - True if DATALOSS was received
                - data_loss_events: int - total Bloomberg data-loss signals observed
                - last_message_us: int - latest receive timestamp seen from Bloomberg
                - last_data_loss_us: int - latest data-loss timestamp seen from Bloomberg
                - effective_overflow_policy: str - actual runtime policy used by the Rust stream
        """
        return self._sub.stats

    async def unsubscribe(self, drain: bool = False) -> list[pa.RecordBatch] | None:
        """Close subscription and optionally drain remaining data.

        Args:
            drain: If True, return any remaining buffered batches

        Returns:
            List of remaining batches if drain=True, else None
        """
        logger.debug("unsubscribe: drain=%s", drain)
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
    all_fields: bool = False,
    backend: Backend | str | None = None,
    service: str | None = None,
    options: list[str] | None = None,
    tick_mode: bool = False,
    flush_threshold: int | None = None,
    stream_capacity: int | None = None,
    overflow_policy: str | None = None,
    recovery_policy: str | None = None,
) -> Subscription:
    """Create an async subscription to real-time market data.

    This is the low-level subscription API with full control over
    the subscription lifecycle, including dynamic add/remove.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to (e.g., 'LAST_PRICE', 'BID', 'ASK')
        raw: If True, yield raw Arrow RecordBatches for max performance
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
        backend: DataFrame backend for batch conversion (ignored if raw=True)
        service: Bloomberg service (e.g., '//blp/mktdata'). If provided, uses subscribe_with_options
        options: List of subscription options. If provided, uses subscribe_with_options
        tick_mode: If True, convert batches to dicts (implies raw=True)
        flush_threshold: Batch flush threshold (validation only in Wave 1)
        stream_capacity: Stream channel capacity (validation only in Wave 1)
        overflow_policy: Overflow policy for stream (validation only in Wave 1)
        recovery_policy: Optional reconnect policy: None/"none" or "resubscribe"

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

        # Tick mode (dict conversion)
        sub = await xbbg.asubscribe(["AAPL US Equity"], ["LAST_PRICE"], tick_mode=True)
        async for tick_dict in sub:
            print(tick_dict)  # {'ticker': 'AAPL US Equity', 'LAST_PRICE': 150.25, ...}
    """
    # Validate config parameters
    if flush_threshold is not None and flush_threshold < 1:
        raise ValueError("flush_threshold must be >= 1")
    if stream_capacity is not None and stream_capacity < 1:
        raise ValueError("stream_capacity must be >= 1")
    if overflow_policy is not None and overflow_policy not in ("drop_newest", "block"):
        raise ValueError(f"overflow_policy must be one of 'drop_newest', 'block', got {overflow_policy!r}")
    if recovery_policy is not None and recovery_policy not in ("none", "resubscribe"):
        raise ValueError(f"recovery_policy must be one of 'none', 'resubscribe', got {recovery_policy!r}")

    # tick_mode=True forces flush_threshold=1
    if tick_mode and flush_threshold is not None and flush_threshold > 1:
        warnings.warn(
            f"tick_mode=True forces flush_threshold=1, ignoring flush_threshold={flush_threshold}", stacklevel=2
        )
        flush_threshold = 1

    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(fields)

    effective_backend = _resolve_backend(backend)

    engine = _get_engine()
    logger.debug("subscribe: tickers=%s fields=%s", ticker_list, field_list)

    # Use subscribe_with_options if service, options, or config params provided
    if (
        service is not None
        or options is not None
        or flush_threshold is not None
        or stream_capacity is not None
        or overflow_policy is not None
        or recovery_policy is not None
    ):
        opt_kwargs = {
            k: v
            for k, v in {
                "flush_threshold": flush_threshold,
                "stream_capacity": stream_capacity,
                "overflow_policy": overflow_policy,
                "recovery_policy": recovery_policy,
                "all_fields": all_fields,
            }.items()
            if v is not None
        }
        py_sub = await engine.subscribe_with_options(
            service or "//blp/mktdata",
            ticker_list,
            field_list,
            options or [],
            **opt_kwargs,
        )
    else:
        py_sub = await engine.subscribe(ticker_list, field_list, all_fields=all_fields)

    return Subscription(py_sub, raw=raw or tick_mode, backend=effective_backend, tick_mode=tick_mode)


async def astream(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    all_fields: bool = False,
    backend: Backend | str | None = None,
    callback: Callable[[pa.RecordBatch | nw.DataFrame | dict[str, Any]], None] | None = None,
    tick_mode: bool = False,
    flush_threshold: int | None = None,
    stream_capacity: int | None = None,
    overflow_policy: str | None = None,
    recovery_policy: str | None = None,
):
    """High-level async streaming - simple iteration.

    This is the simple API for streaming data. For dynamic add/remove,
    use asubscribe() instead.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to
        raw: If True, yield raw Arrow RecordBatches
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
        backend: DataFrame backend for batch conversion
        callback: Optional callback function to invoke on each batch
        tick_mode: If True, convert batches to dicts

    Yields:
        Batches of market data (RecordBatch, DataFrame, or dict)

    Example::

        async for batch in xbbg.astream(["AAPL US Equity"], ["LAST_PRICE"]):
            print(batch)
            if done:
                break


        # With callback
        def on_batch(batch):
            print(f"Got batch: {batch}")


        async for _ in xbbg.astream(["AAPL US Equity"], ["LAST_PRICE"], callback=on_batch):
            pass
    """
    async with await asubscribe(
        tickers,
        fields,
        raw=raw,
        all_fields=all_fields,
        backend=backend,
        tick_mode=tick_mode,
        flush_threshold=flush_threshold,
        stream_capacity=stream_capacity,
        overflow_policy=overflow_policy,
        recovery_policy=recovery_policy,
    ) as sub:
        async for batch in sub:
            if callback is not None:
                try:
                    callback(batch)
                except Exception as e:
                    logger.warning("callback raised exception: %s", e, exc_info=True)
            yield batch


def stream(
    tickers: str | list[str],
    fields: str | list[str],
    *,
    raw: bool = False,
    all_fields: bool = False,
    backend: Backend | str | None = None,
    callback: Callable[[pa.RecordBatch | nw.DataFrame | dict[str, Any]], None] | None = None,
    tick_mode: bool = False,
    flush_threshold: int | None = None,
    stream_capacity: int | None = None,
    overflow_policy: str | None = None,
):
    """High-level sync streaming using a background thread.

    Note: This is a generator that runs the async stream in a background
    thread. Use astream() for async contexts.

    Args:
        tickers: Securities to subscribe to
        fields: Fields to subscribe to
        raw: If True, yield raw Arrow RecordBatches
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
        backend: DataFrame backend for batch conversion
        callback: Optional callback function to invoke on each batch
        tick_mode: If True, convert batches to dicts

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
            async for batch in astream(
                tickers,
                fields,
                raw=raw,
                all_fields=all_fields,
                backend=backend,
                callback=callback,
                tick_mode=tick_mode,
                flush_threshold=flush_threshold,
                stream_capacity=stream_capacity,
                overflow_policy=overflow_policy,
            ):
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
    all_fields: bool = False,
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
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
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
    ticker_list = _normalize_tickers(tickers)

    # Default fields if not provided
    if fields is None:
        field_list = ["RT_PX_VWAP", "RT_VWAP_VOLUME"]
    else:
        field_list = _normalize_fields(fields)

    # Build subscription options
    options: list[str] = []
    if start_time:
        options.append(f"VWAP_START_TIME={start_time}")
    if end_time:
        options.append(f"VWAP_END_TIME={end_time}")

    effective_backend = _resolve_backend(backend)

    engine = _get_engine()
    py_sub = await engine.subscribe_with_options(
        Service.MKTVWAP.value,
        ticker_list,
        field_list,
        options if options else None,
        all_fields=all_fields,
    )

    return Subscription(py_sub, raw=raw, backend=effective_backend)


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
    all_fields: bool = False,
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
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
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
    ticker_list = _normalize_tickers(tickers)
    effective_backend = _resolve_backend(backend)

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
        all_fields=all_fields,
    )

    return Subscription(py_sub, raw=raw, backend=effective_backend)


# =============================================================================
# MKTDEPTH API - Level 2 Market Depth (B-PIPE Only)
# =============================================================================


async def adepth(
    tickers: str | list[str],
    *,
    raw: bool = False,
    all_fields: bool = False,
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
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
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
    ticker_list = _normalize_tickers(tickers)
    effective_backend = _resolve_backend(backend)

    # Get engine and subscribe
    engine = _get_engine()
    try:
        py_sub = await engine.subscribe_with_options(
            Service.MKTDEPTH.value,
            ticker_list,
            [],  # Fields are implicit for market depth
            None,
            all_fields=all_fields,
        )
    except Exception as e:
        # Check for B-PIPE related errors
        if "MKTDEPTHDATA" in str(e).upper() or "SERVICE" in str(e).upper():
            raise BlpBPipeError("Level 2 market depth requires Bloomberg B-PIPE license.") from e
        raise

    return Subscription(py_sub, raw=raw, backend=effective_backend)


# =============================================================================
# MKTLIST API - Option/Futures Chains (B-PIPE Only)
# =============================================================================


async def achains(
    underlying: str,
    *,
    chain_type: str = "OPTIONS",
    raw: bool = False,
    all_fields: bool = False,
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
        all_fields: If True, expose all top-level scalar Bloomberg subscription fields
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

    effective_backend = _resolve_backend(backend)

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
            all_fields=all_fields,
        )
    except Exception as e:
        # Check for B-PIPE related errors
        if "MKTLIST" in str(e).upper() or "SERVICE" in str(e).upper():
            raise BlpBPipeError("Option/futures chains require Bloomberg B-PIPE license.") from e
        raise

    return Subscription(py_sub, raw=raw, backend=effective_backend)


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
) -> list[tuple[str, str]]:
    """Build dotted-path elements for a //blp/tasvc studyRequest.

    Returns a list of (dotted_path, value_str) tuples that the Rust worker
    applies via ``set_nested_str`` / ``set_nested_int`` on the request.

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

    elements: list[tuple[str, str]] = []

    # Normalize dates to YYYYMMDD (Bloomberg tasvc expects this format)
    def _norm_date(d: str | None) -> str | None:
        return d.replace("-", "").replace("/", "") if d else None

    sd = _norm_date(start_date)
    ed = _norm_date(end_date)

    # Price source
    elements.append(("priceSource.securityName", ticker))

    # Data range
    if periodicity.upper() in ("DAILY", "WEEKLY", "MONTHLY"):
        prefix = "priceSource.dataRange.historical"
        if sd:
            elements.append((f"{prefix}.startDate", sd))
        if ed:
            elements.append((f"{prefix}.endDate", ed))
        elements.append((f"{prefix}.periodicitySelection", periodicity.upper()))
    else:
        # Intraday
        prefix = "priceSource.dataRange.intraday"
        if sd:
            elements.append((f"{prefix}.startDate", sd))
        if ed:
            elements.append((f"{prefix}.endDate", ed))
        elements.append((f"{prefix}.eventType", "TRADE"))
        elements.append((f"{prefix}.interval", str(interval or 60)))

    # Study attributes
    sa_prefix = f"studyAttributes.{attr_name}"
    for key, value in params.items():
        elements.append((f"{sa_prefix}.{key}", str(value)))

    return elements


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

    ticker_list = _normalize_tickers(tickers)
    engine = _get_engine()

    async def fetch_single(ticker: str) -> pa.RecordBatch | Exception:
        """Fetch TA data for a single ticker."""
        study_elements = _build_study_request(
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
            elements=study_elements,
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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abql"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["absrch"], locals())


# =============================================================================
# BQR API - Bloomberg Quote Request
# =============================================================================


def _parse_date_offset(offset: str, reference: datetime) -> datetime:
    """Parse date offset string like '-2d', '-1w', '-1m', '-3h'."""
    import re

    offset = offset.strip().lower()
    match = re.match(r"^(-?\d+)([dwmh])$", offset)
    if not match:
        raise ValueError(f"Invalid date offset format: {offset}. Use format like '-2d', '-1w', '-1m', '-3h'")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return reference + timedelta(days=value)
    if unit == "w":
        return reference + timedelta(weeks=value)
    if unit == "m":
        return reference + timedelta(days=value * 30)
    if unit == "h":
        return reference + timedelta(hours=value)
    raise ValueError(f"Unknown time unit: {unit}")


def _reshape_bqr_generic(table: pa.Table, ticker: str) -> nw.DataFrame:
    """Reshape generic extractor output into structured BQR rows.

    When includeBrokerCodes (or similar) is set, the Rust tick extractor
    falls back to the generic flattener. This function groups the flat
    path/value rows back into one row per tick with proper columns.
    """
    import re

    if "path" not in table.column_names:
        return nw.from_native(pa.table({"ticker": [], "time": [], "type": [], "value": [], "size": []}))

    paths = table["path"].to_pylist()
    value_strs = table["value_str"].to_pylist() if "value_str" in table.column_names else [None] * len(paths)
    value_nums = table["value_num"].to_pylist() if "value_num" in table.column_names else [None] * len(paths)

    pattern = re.compile(r"tickData\[(\d+)\]\.(\w+)")

    tick_values: list[tuple[str, str, Any]] = []
    all_fields: set[str] = set()

    for row_idx, path in enumerate(paths):
        if not isinstance(path, str):
            continue
        match = pattern.search(path)
        if not match:
            continue

        idx, field = match.group(1), match.group(2)
        all_fields.add(field)

        value_str = value_strs[row_idx]
        value_num = value_nums[row_idx]
        value = value_str if value_str not in (None, "") else value_num
        tick_values.append((idx, field, value))

    if not tick_values:
        return nw.from_native(pa.table({"ticker": [], "time": [], "type": [], "value": [], "size": []}))

    records_by_idx: dict[str, dict[str, Any]] = {}
    for idx, field, value in tick_values:
        if idx not in records_by_idx:
            record: dict[str, Any] = {"ticker": ticker}
            for name in all_fields:
                record[name] = None
            records_by_idx[idx] = record
        records_by_idx[idx][field] = value

    records = list(records_by_idx.values())

    result = pa.Table.from_pylist(records)

    # Reorder: ticker first, then standard tick fields, then extras
    cols = result.column_names
    priority = ["ticker", "time", "type", "value", "size"]
    ordered = [c for c in priority if c in cols]
    ordered += [c for c in cols if c not in priority]
    result = result.select(ordered)

    return nw.from_native(result)


async def abqr(
    ticker: str,
    date_offset: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    event_types: Sequence[str] | None = None,
    include_broker_codes: bool = False,
    include_spread_price: bool = False,
    include_yield: bool = False,
    include_condition_codes: bool = False,
    include_exchange_codes: bool = False,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg Quote Request (BQR).

    Retrieves dealer quote data using IntradayTickRequest with BID/ASK events.
    Emulates the Excel =BQR() function.

    Args:
        ticker: Security identifier. Supports Bloomberg tickers with pricing
            source qualifiers (e.g., 'IBM US Equity@MSG1', '/isin/US037833FB15@MSG1').
        date_offset: Date offset from now (e.g., '-2d', '-1w', '-3h').
            Mutually exclusive with start_date/end_date.
        start_date: Start date (e.g., '2024-01-15'). Defaults to 2 days ago.
        end_date: End date (e.g., '2024-01-17'). Defaults to today.
        event_types: Event types to retrieve. Defaults to ['BID', 'ASK'].
        include_broker_codes: Include broker/dealer codes (default False).
        include_spread_price: Include spread price for bonds (default False).
        include_yield: Include yield data for bonds (default False).
        include_condition_codes: Include trade condition codes (default False).
        include_exchange_codes: Include exchange codes (default False).
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Additional options.

    Returns:
        DataFrame with columns: ticker, time, type, value, size,
        plus optional brokerBuyCode, brokerSellCode, spreadPrice, etc.

    Example::

        # With date offset (like Excel BQR)
        df = await abqr("IBM US Equity@MSG1", date_offset="-2d")

        # Bond with broker codes and spread
        df = await abqr(
            "US037833FB15@MSG1 Corp",
            date_offset="-2d",
            include_broker_codes=True,
            include_spread_price=True,
        )

        # With explicit date range
        df = await abqr(
            "XYZ 4.5 01/15/30@MSG1 Corp",
            start_date="2024-01-15",
            end_date="2024-01-17",
        )

        # Trade events only
        df = await abqr(
            "XYZ 4.5 01/15/30@MSG1 Corp",
            date_offset="-1d",
            event_types=["TRADE"],
        )
    """
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abqr"], locals())


async def abflds(
    fields: str | list[str] | None = None,
    *,
    search_spec: str | None = None,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Async Bloomberg field metadata lookup (BFLDS).

    Unified field function: get metadata for specific fields, or search by keyword.

    Args:
        fields: Single field or list of fields to get metadata for.
            Mutually exclusive with search_spec.
        search_spec: Search term to find fields by name/description.
            Mutually exclusive with fields.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame with field information or search results.

    Raises:
        ValueError: If neither fields nor search_spec is provided, or both are provided.

    Example::

        # Get info for specific fields
        df = await abflds(fields=["PX_LAST", "VOLUME"])

        # Search for fields by keyword
        df = await abflds(search_spec="vwap")
    """
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abflds"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abeqs"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["ablkp"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abport"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abcurves"], locals())


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
    return await _execute_generated_endpoint(_GENERATED_ENDPOINT_SPECS["abgovts"], locals())


async def _build_abdp_plan(args: dict[str, Any]) -> _EndpointPlan:
    ticker_list = _normalize_tickers(args["tickers"])
    field_list = _normalize_fields(args.get("flds"))
    kwargs = dict(args.get("kwargs", {}))

    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.REFERENCE_DATA, kwargs)
    fmt = Format(args["format"]) if isinstance(args.get("format"), str) else args.get("format")

    resolved_types = await _get_engine().resolve_field_types(
        field_list,
        args.get("field_types"),
        "string",
    )

    return _EndpointPlan(
        request_kwargs={
            "securities": ticker_list,
            "fields": field_list,
            "overrides": overrides if overrides else None,
            "elements": elements if elements else None,
            "field_types": resolved_types,
            "format": fmt,
            "include_security_errors": args.get("include_security_errors", False),
            "validate_fields": args.get("validate_fields"),
        },
        backend=args.get("backend"),
        postprocess=None,
    )


async def _build_abdh_plan(args: dict[str, Any]) -> _EndpointPlan:
    ticker_list = _normalize_tickers(args["tickers"])
    field_list = _normalize_fields(args.get("flds"))
    kwargs = dict(args.get("kwargs", {}))

    fmt = Format(args["format"]) if isinstance(args.get("format"), str) else args.get("format")

    end_value = args.get("end_date", "today")
    start_value = args.get("start_date")

    e_dt = _fmt_date(end_value, "%Y%m%d")
    if start_value is None:
        end_dt_parsed = datetime.strptime(e_dt, "%Y%m%d")
        s_dt = (end_dt_parsed - timedelta(weeks=8)).strftime("%Y%m%d")
    else:
        s_dt = _fmt_date(start_value, "%Y%m%d")

    options: list[tuple[str, str]] = []
    adjust = kwargs.pop("adjust", None)
    if adjust == "all":
        options.extend(
            [
                ("adjustmentSplit", "true"),
                ("adjustmentNormal", "true"),
                ("adjustmentAbnormal", "true"),
            ]
        )
    elif adjust == "dvd":
        options.extend(
            [
                ("adjustmentNormal", "true"),
                ("adjustmentAbnormal", "true"),
            ]
        )
    elif adjust == "split":
        options.append(("adjustmentSplit", "true"))

    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.HISTORICAL_DATA, kwargs)

    resolved_types = await _get_engine().resolve_field_types(
        field_list,
        args.get("field_types"),
        "float64",
    )

    return _EndpointPlan(
        request_kwargs={
            "securities": ticker_list,
            "fields": field_list,
            "start_date": s_dt,
            "end_date": e_dt,
            "overrides": overrides if overrides else None,
            "elements": elements if elements else None,
            "options": options if options else None,
            "field_types": resolved_types,
            "format": fmt,
            "validate_fields": args.get("validate_fields"),
        },
        backend=args.get("backend"),
        postprocess=None,
    )


async def _build_abds_plan(args: dict[str, Any]) -> _EndpointPlan:
    ticker_list = _normalize_tickers(args["tickers"])
    kwargs = dict(args.get("kwargs", {}))
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.REFERENCE_DATA, kwargs)

    return _EndpointPlan(
        request_kwargs={
            "securities": ticker_list,
            "fields": [args["flds"]],
            "overrides": overrides if overrides else None,
            "elements": elements if elements else None,
            "validate_fields": args.get("validate_fields"),
        },
        backend=args.get("backend"),
    )


async def _build_abdib_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))

    start_dt = args.get("start_datetime")
    end_dt = args.get("end_datetime")
    dt_value = args.get("dt")

    if start_dt is not None and end_dt is not None:
        s_dt = datetime.fromisoformat(start_dt.replace(" ", "T")).isoformat()
        e_dt = datetime.fromisoformat(end_dt.replace(" ", "T")).isoformat()
    elif dt_value is not None:
        cur_dt = datetime.fromisoformat(dt_value.replace(" ", "T")).strftime("%Y-%m-%d")
        s_dt = f"{cur_dt}T00:00:00"
        e_dt = f"{cur_dt}T23:59:59"
    else:
        raise ValueError("Either dt or both start_datetime and end_datetime must be provided")

    elements, _ = await _aroute_kwargs(Service.REFDATA, Operation.INTRADAY_BAR, kwargs)

    req: dict[str, Any] = {
        "security": args["ticker"],
        "event_type": args["typ"],
        "interval": args["interval"],
        "start_datetime": s_dt,
        "end_datetime": e_dt,
        "elements": elements if elements else None,
    }
    if args.get("request_tz") is not None:
        req["request_tz"] = args["request_tz"]
    if args.get("output_tz") is not None:
        req["output_tz"] = args["output_tz"]

    return _EndpointPlan(
        request_kwargs=req,
        backend=args.get("backend"),
    )


async def _build_abdtick_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))

    s_dt = datetime.fromisoformat(args["start_datetime"].replace(" ", "T")).isoformat()
    e_dt = datetime.fromisoformat(args["end_datetime"].replace(" ", "T")).isoformat()

    event_types = args.get("event_types")
    if event_types is None:
        event_types = ["TRADE"]

    elements, _ = await _aroute_kwargs(Service.REFDATA, Operation.INTRADAY_TICK, kwargs)

    req: dict[str, Any] = {
        "security": args["ticker"],
        "start_datetime": s_dt,
        "end_datetime": e_dt,
        "event_types": list(event_types),
        "elements": elements if elements else None,
    }
    if args.get("request_tz") is not None:
        req["request_tz"] = args["request_tz"]
    if args.get("output_tz") is not None:
        req["output_tz"] = args["output_tz"]

    return _EndpointPlan(
        request_kwargs=req,
        backend=args.get("backend"),
    )


def _build_abql_plan(args: dict[str, Any]) -> _EndpointPlan:
    return _EndpointPlan(
        request_kwargs={"overrides": {"expression": args["expression"]}},
        backend=args.get("backend"),
    )


def _build_abqr_plan(args: dict[str, Any]) -> _EndpointPlan:
    event_types = args.get("event_types")
    if event_types is None:
        event_types = ["BID", "ASK"]

    now = datetime.now()
    time_fmt = "%Y-%m-%dT%H:%M:%S"

    date_offset = args.get("date_offset")
    start_date = args.get("start_date")
    end_date = args.get("end_date")

    if date_offset:
        end_dt = now
        start_dt = _parse_date_offset(date_offset, now)
        s_dt = start_dt.strftime(time_fmt)
        e_dt = end_dt.strftime(time_fmt)
    elif start_date is not None:
        s_dt = _fmt_date(start_date, "%Y-%m-%d") + "T00:00:00"
        if end_date is not None:
            e_dt = _fmt_date(end_date, "%Y-%m-%d") + "T23:59:59"
        else:
            e_dt = now.strftime(time_fmt)
    else:
        start_dt = now - timedelta(days=2)
        s_dt = start_dt.strftime(time_fmt)
        e_dt = now.strftime(time_fmt)

    elements: list[tuple[str, Any]] = []
    if args.get("include_broker_codes"):
        elements.append(("includeBrokerCodes", "true"))
    if args.get("include_spread_price"):
        elements.append(("includeSpreadPrice", "true"))
    if args.get("include_yield"):
        elements.append(("includeYield", "true"))
    if args.get("include_condition_codes"):
        elements.append(("includeConditionCodes", "true"))
    if args.get("include_exchange_codes"):
        elements.append(("includeExchangeCodes", "true"))

    has_extras = bool(elements)
    ticker = args["ticker"]
    backend = args.get("backend")

    logger.debug(
        "abqr: ticker=%s start=%s end=%s events=%s",
        ticker,
        s_dt,
        e_dt,
        event_types,
    )

    def postprocess(nw_df: Any) -> DataFrameResult:
        logger.debug("abqr: received %d rows", len(nw_df))
        result = nw_df
        if has_extras:
            table = result.to_arrow()
            if "path" in table.column_names:
                result = _reshape_bqr_generic(table, ticker)
        return _convert_backend(result, backend)

    return _EndpointPlan(
        request_kwargs={
            "security": ticker,
            "start_datetime": s_dt,
            "end_datetime": e_dt,
            "event_types": list(event_types),
            "elements": elements if elements else None,
        },
        backend=backend,
        postprocess=postprocess,
    )


def _build_absrch_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    overrides: dict[str, str] = {"Domain": args["domain"]}
    for key, value in kwargs.items():
        overrides[key] = str(value)

    return _EndpointPlan(
        request_kwargs={"overrides": overrides},
        backend=args.get("backend"),
    )


async def _build_abeqs_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    routed_elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.BEQS, kwargs)

    elements: list[tuple[str, Any]] = [
        ("screenName", args["screen"]),
        ("screenType", args["screen_type"]),
        ("Group", args["group"]),
    ]
    if args.get("asof"):
        elements.append(("asOfDate", _fmt_date(args["asof"])))
    elements.extend(routed_elements)

    return _EndpointPlan(
        request_kwargs={
            "elements": elements,
            "overrides": overrides if overrides else None,
        },
        backend=args.get("backend"),
    )


async def _build_ablkp_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.INSTRUMENT_LIST, kwargs)

    elements: list[tuple[str, Any]] = [
        ("query", args["query"]),
        ("yellowKeyFilter", args["yellowkey"]),
        ("languageOverride", args["language"]),
        ("maxResults", args["max_results"]),
    ]
    elements.extend(routed_elements)

    return _EndpointPlan(
        request_kwargs={"elements": elements},
        backend=args.get("backend"),
    )


async def _build_abport_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    field_list = _normalize_fields(args["fields"])
    elements, overrides = await _aroute_kwargs(Service.REFDATA, Operation.PORTFOLIO_DATA, kwargs)

    return _EndpointPlan(
        request_kwargs={
            "securities": [args["portfolio"]],
            "fields": field_list,
            "elements": elements if elements else None,
            "overrides": overrides if overrides else None,
        },
        backend=args.get("backend"),
    )


async def _build_abcurves_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.CURVE_LIST, kwargs)

    elements: list[tuple[str, Any]] = []
    if args.get("country") is not None:
        elements.append(("countryCode", args["country"]))
    if args.get("currency") is not None:
        elements.append(("currencyCode", args["currency"]))
    if args.get("curve_type") is not None:
        elements.append(("type", args["curve_type"]))
    if args.get("subtype") is not None:
        elements.append(("subtype", args["subtype"]))
    if args.get("curveid") is not None:
        elements.append(("curveid", args["curveid"]))
    if args.get("bbgid") is not None:
        elements.append(("bbgid", args["bbgid"]))
    elements.extend(routed_elements)

    return _EndpointPlan(
        request_kwargs={"elements": elements if elements else None},
        backend=args.get("backend"),
    )


async def _build_abgovts_plan(args: dict[str, Any]) -> _EndpointPlan:
    kwargs = dict(args.get("kwargs", {}))
    routed_elements, _ = await _aroute_kwargs(Service.INSTRUMENTS, Operation.GOVT_LIST, kwargs)

    elements: list[tuple[str, Any]] = []
    if args.get("query") is not None:
        elements.append(("ticker", args["query"]))
    elements.append(("partialMatch", args["partial_match"]))
    elements.extend(routed_elements)

    return _EndpointPlan(
        request_kwargs={"elements": elements if elements else None},
        backend=args.get("backend"),
    )


def _build_abflds_plan(args: dict[str, Any]) -> _EndpointPlan:
    fields = args.get("fields")
    search_spec = args.get("search_spec")

    if fields is not None and search_spec is not None:
        raise ValueError("Cannot specify both 'fields' and 'search_spec'")
    if fields is None and search_spec is None:
        raise ValueError("Must specify either 'fields' or 'search_spec'")

    if fields is not None:
        field_list = _normalize_fields(fields)
        return _EndpointPlan(
            request_kwargs={"fields": field_list},
            backend=args.get("backend"),
            service=Service.APIFLDS,
            operation=Operation.FIELD_INFO,
        )

    return _EndpointPlan(
        request_kwargs={"fields": [search_spec]},
        backend=args.get("backend"),
        service=Service.APIFLDS,
        operation=Operation.FIELD_SEARCH,
        extractor=ExtractorHint.FIELD_INFO,
    )


_GENERATED_ENDPOINT_SPECS.update(
    {
        "abdp": _GeneratedEndpointSpec(
            async_name="abdp",
            sync_name="bdp",
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            builder=_build_abdp_plan,
        ),
        "abdh": _GeneratedEndpointSpec(
            async_name="abdh",
            sync_name="bdh",
            service=Service.REFDATA,
            operation=Operation.HISTORICAL_DATA,
            builder=_build_abdh_plan,
        ),
        "abds": _GeneratedEndpointSpec(
            async_name="abds",
            sync_name="bds",
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            builder=_build_abds_plan,
            extractor=ExtractorHint.BULK,
        ),
        "abdib": _GeneratedEndpointSpec(
            async_name="abdib",
            sync_name="bdib",
            service=Service.REFDATA,
            operation=Operation.INTRADAY_BAR,
            builder=_build_abdib_plan,
        ),
        "abdtick": _GeneratedEndpointSpec(
            async_name="abdtick",
            sync_name="bdtick",
            service=Service.REFDATA,
            operation=Operation.INTRADAY_TICK,
            builder=_build_abdtick_plan,
        ),
        "abql": _GeneratedEndpointSpec(
            async_name="abql",
            sync_name="bql",
            service=Service.BQLSVC,
            operation=Operation.BQL_SEND_QUERY,
            builder=_build_abql_plan,
            extractor=ExtractorHint.BQL,
        ),
        "abqr": _GeneratedEndpointSpec(
            async_name="abqr",
            sync_name="bqr",
            service=Service.REFDATA,
            operation=Operation.INTRADAY_TICK,
            builder=_build_abqr_plan,
        ),
        "absrch": _GeneratedEndpointSpec(
            async_name="absrch",
            sync_name="bsrch",
            service=Service.EXRSVC,
            operation=Operation.EXCEL_GET_GRID,
            builder=_build_absrch_plan,
            extractor=ExtractorHint.BSRCH,
        ),
        "abeqs": _GeneratedEndpointSpec(
            async_name="abeqs",
            sync_name="beqs",
            service=Service.REFDATA,
            operation=Operation.BEQS,
            builder=_build_abeqs_plan,
            extractor=ExtractorHint.GENERIC,
        ),
        "ablkp": _GeneratedEndpointSpec(
            async_name="ablkp",
            sync_name="blkp",
            service=Service.INSTRUMENTS,
            operation=Operation.INSTRUMENT_LIST,
            builder=_build_ablkp_plan,
            extractor=ExtractorHint.GENERIC,
        ),
        "abport": _GeneratedEndpointSpec(
            async_name="abport",
            sync_name="bport",
            service=Service.REFDATA,
            operation=Operation.PORTFOLIO_DATA,
            builder=_build_abport_plan,
        ),
        "abcurves": _GeneratedEndpointSpec(
            async_name="abcurves",
            sync_name="bcurves",
            service=Service.INSTRUMENTS,
            operation=Operation.CURVE_LIST,
            builder=_build_abcurves_plan,
            extractor=ExtractorHint.GENERIC,
        ),
        "abgovts": _GeneratedEndpointSpec(
            async_name="abgovts",
            sync_name="bgovts",
            service=Service.INSTRUMENTS,
            operation=Operation.GOVT_LIST,
            builder=_build_abgovts_plan,
            extractor=ExtractorHint.GENERIC,
        ),
        "abflds": _GeneratedEndpointSpec(
            async_name="abflds",
            sync_name="bflds",
            service=Service.APIFLDS,
            operation=Operation.FIELD_INFO,
            builder=_build_abflds_plan,
        ),
    }
)

_install_generated_endpoints()

# Backward-compatible aliases
abfld = abflds
bfld = globals()["bflds"]


async def afieldInfo(
    fields: str | list[str],
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Get metadata about Bloomberg fields (async).

    Convenience wrapper around abflds(fields=...).

    Args:
        fields: Single field or list of fields to get metadata for.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Infrastructure options.

    Returns:
        DataFrame with field information.

    Example::

        df = await afieldInfo(["PX_LAST", "VOLUME"])
    """
    return await abflds(fields=fields, backend=backend, **kwargs)


async def afieldSearch(
    searchterm: str,
    *,
    backend: Backend | str | None = None,
    **kwargs,
) -> DataFrameResult:
    """Search for Bloomberg fields by keyword (async).

    Convenience wrapper around abflds(search_spec=...).

    Args:
        searchterm: Search term to find fields by name/description.
        backend: DataFrame backend to return. If None, uses global default.
        **kwargs: Infrastructure options.

    Returns:
        DataFrame with search results.

    Example::

        df = await afieldSearch("vwap")
    """
    return await abflds(search_spec=searchterm, backend=backend, **kwargs)


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


def _install_manual_sync_wrappers() -> None:
    for sync_name, async_func in (
        ("request", arequest),
        ("subscribe", asubscribe),
        ("vwap", avwap),
        ("mktbar", amktbar),
        ("depth", adepth),
        ("chains", achains),
        ("bta", abta),
        ("fieldInfo", afieldInfo),
        ("fieldSearch", afieldSearch),
        ("bops", abops),
        ("bschema", abschema),
    ):
        globals()[sync_name] = _build_sync_wrapper(sync_name, async_func)


_install_manual_sync_wrappers()


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
