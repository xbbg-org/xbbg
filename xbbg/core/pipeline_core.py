"""Core pipeline infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import logging
from typing import Any, Protocol

import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.contracts import (
    BaseContextAware,
    CacheAdapter,
    DataRequest,
    MarketResolver,
    ResolverResult,
    SessionWindow,
)
from xbbg.core.infra import conn

logger = logging.getLogger(__name__)


def _events_to_table(events: list[dict[str, Any]]) -> pa.Table | None:
    """Convert Bloomberg event dicts directly to a PyArrow Table (no pandas).

    Bloomberg's ``process_*`` functions yield ``dict[str, Any]`` where values
    come from ``blpapi.Element.getValue()`` -- native Python types that vary
    by field (``float`` for Double fields, ``str`` for String fields,
    ``datetime`` for Date fields, etc.).  When multiple fields are requested,
    the ``value`` column becomes a true **variant column** with mixed Python
    types in the same list.

    ``pa.Table.from_pylist()`` and ``pa.Table.from_pandas()`` both choke on
    this because Arrow columns are strongly typed.  Instead, we build the
    table directly: collect all column names from the events, then for each
    column attempt ``pa.array()`` with type inference.  If inference fails
    (mixed types), stringify all values in that column to ``pa.string()``,
    preserving ``None`` as Arrow null.

    Args:
        events: List of dicts from Bloomberg process functions.

    Returns:
        PyArrow Table, or None if events is empty.
    """
    if not events:
        return None

    # Collect column names in insertion order (first event defines order,
    # later events may add columns -- e.g. BDS array fields)
    col_names: list[str] = []
    seen: set[str] = set()
    for evt in events:
        for key in evt:
            if key not in seen:
                col_names.append(key)
                seen.add(key)

    # Build one Arrow array per column
    arrays: list[pa.Array] = []
    for col in col_names:
        values = [evt.get(col) for evt in events]

        # Fast path: let Arrow infer the type
        try:
            arrays.append(pa.array(values, from_pandas=True))
            continue
        except (pa.ArrowInvalid, pa.ArrowTypeError, pa.ArrowNotImplementedError):
            pass

        # Slow path: stringify non-None values -> pa.string()
        arrays.append(
            pa.array(
                [None if v is None else str(v) for v in values],
                type=pa.string(),
            )
        )

    return pa.table(dict(zip(col_names, arrays, strict=True)))


class RequestBuilderStrategy(Protocol):
    """Strategy for building Bloomberg requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:  # Returns (blpapi.Request, ctx_kwargs)
        """Build Bloomberg API request.

        Args:
            request: Data request.
            session_window: Session window (may be unused).

        Returns:
            Tuple of (Bloomberg request, context kwargs for sending).
        """
        ...


class ResponseTransformerStrategy(Protocol):
    """Strategy for transforming Bloomberg responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform raw Bloomberg response.

        Args:
            raw_data: Arrow table from Bloomberg.
            request: Original data request.
            exchange_info: Exchange information.
            session_window: Session window.

        Returns:
            Transformed Arrow table.
        """
        ...


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for pipeline behavior.

    Attributes:
        service: Bloomberg service name (e.g., '//blp/refdata').
        request_type: Bloomberg request type (e.g., 'ReferenceDataRequest').
        process_func: Function to process events (e.g., process.process_ref).
        request_builder: Strategy for building requests.
        transformer: Strategy for transforming responses.
        needs_session: Whether this API needs session resolution.
        default_resolvers: Default resolver chain factory.
        default_cache_adapter: Default cache adapter factory.
    """

    service: str
    request_type: str
    process_func: Callable
    request_builder: RequestBuilderStrategy
    transformer: ResponseTransformerStrategy
    needs_session: bool = False
    default_resolvers: Callable[[], list[MarketResolver]] | None = None
    default_cache_adapter: Callable[[], CacheAdapter | None] = lambda: None


class BloombergPipeline(BaseContextAware):
    """Unified pipeline for all Bloomberg API requests.

    Uses Strategy pattern for request building and response transformation,
    eliminating the need for separate pipeline classes.
    """

    def __init__(
        self,
        config: PipelineConfig,
        market_resolvers: list[MarketResolver] | None = None,
        cache_adapter: CacheAdapter | None = None,
    ):
        """Initialize pipeline.

        Args:
            config: Pipeline configuration.
            market_resolvers: List of resolvers (defaults from config).
            cache_adapter: Cache adapter (defaults from config).
        """
        self.config = config
        self.market_resolvers = (
            market_resolvers
            if market_resolvers is not None
            else (config.default_resolvers() if config.default_resolvers else [])
        )
        self.cache_adapter = (
            cache_adapter
            if cache_adapter is not None
            else (config.default_cache_adapter() if config.default_cache_adapter else None)
        )

    def run(self, request: DataRequest) -> Any:
        """Execute the pipeline synchronously. Wraps arun().

        Args:
            request: Data request to process.

        Returns:
            Data in requested backend/format.
        """
        return conn._run_sync(self.arun(request))

    async def arun(self, request: DataRequest) -> Any:
        """Execute the pipeline asynchronously (source of truth).

        All Bloomberg I/O flows through arequest(). CPU-bound steps
        (context prep, market resolution, caching, transformation)
        run synchronously since they are fast.

        Args:
            request: Data request to process.

        Returns:
            Data in requested backend/format.
        """
        # Step 1: Prepare context
        ctx = self._prepare_context(request)
        request = self._with_context(request, ctx)

        # Step 2: Resolve market (ticker + exchange info)
        # Skip market resolution if not needed (no session required and no resolvers configured)
        if self.config.needs_session or self.market_resolvers:
            resolver_result = self._resolve_market(request)
            if not resolver_result.success:
                if self.config.needs_session:
                    # Intraday endpoints need market resolution for session windows
                    logger.warning("Market resolution failed for %s", request.ticker)
                    return pd.DataFrame()
                # Endpoints with resolvers but no session requirement can proceed without exchange info
                logger.debug("Market resolution failed for %s, proceeding without exchange info", request.ticker)
                resolver_result = ResolverResult(
                    resolved_ticker=request.ticker,
                    exchange_info=pd.Series(dtype=object),
                    success=True,  # Allow pipeline to continue
                    resolver_name=resolver_result.resolver_name,
                )
            # Update request with resolved ticker
            request = self._with_resolved_ticker(request, resolver_result.resolved_ticker)
        else:
            # No market resolution needed - use original ticker and empty exchange info
            resolver_result = ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=pd.Series(dtype=object),
                success=True,
                resolver_name="None",
            )

        # Step 3: Resolve session window (if needed)
        session_window = self._resolve_session(request, resolver_result.exchange_info)
        # Skip session validation for multi-day requests (they use explicit datetime range)
        if (
            self.config.needs_session
            and not request.is_multi_day()
            and session_window.session_name
            and not session_window.is_valid()
        ):
            logger.warning(
                "Session resolution failed for %s / %s / %s",
                request.ticker,
                request.dt,
                request.session,
            )
            return pd.DataFrame()

        # Step 4: Try cache
        if request.cache_policy.enabled and not request.cache_policy.reload:
            cached_data = self._read_cache(request, session_window)
            from xbbg.io.convert import is_empty as check_empty

            if cached_data is not None and not check_empty(cached_data):
                logger.debug("Cache hit for %s / %s", request.ticker, request.to_date_string())
                return cached_data

        # Step 5: Validate before fetch
        if not self._validate_request(request):
            return pd.DataFrame()

        # Step 6: Fetch from Bloomberg (async -- the only I/O step)
        raw_data = await self._afetch_from_bloomberg(request, session_window)
        # Check for empty data (handle both Arrow and pandas)
        raw_is_empty = (
            raw_data is None
            or (isinstance(raw_data, pa.Table) and raw_data.num_rows == 0)
            or (isinstance(raw_data, pd.DataFrame) and raw_data.empty)
        )
        if raw_is_empty:
            logger.debug("No data returned from Bloomberg for %s", request.ticker)
            raw_data = pa.table({})  # Empty Arrow table for transformer

        # Step 7: Transform response
        # Transformer should handle empty data and return appropriate structure
        # (e.g., MultiIndex for historical data to support operations like .xs())
        transformed = self.config.transformer.transform(
            raw_data, request, resolver_result.exchange_info, session_window
        )
        # Don't return early if empty - let the transformer decide the structure
        # Some transformers (like HistoricalTransformer) return empty DataFrames with
        # proper MultiIndex structure that downstream code expects

        # Step 8: Handle raw flag - return before format conversion
        if request.context and request.context.raw:
            # For raw data, convert Arrow to pandas for backward compatibility
            if isinstance(transformed, pa.Table):
                return transformed.to_pandas()
            return transformed

        # Step 9: Convert to requested backend/format
        from xbbg.backend import Backend, Format
        from xbbg.deprecation import warn_defaults_changing
        from xbbg.io.convert import to_output
        from xbbg.options import get_backend, get_format

        backend = request.backend if request.backend is not None else get_backend()
        format_ = request.format if request.format is not None else get_format()

        # Ensure backend and format are enum values (not strings)
        if isinstance(backend, str):
            backend = Backend(backend)
        if isinstance(format_, str):
            format_ = Format(format_)

        # WIDE format requires pandas MultiIndex — non-pandas backends have
        # no equivalent, so when the user hasn't explicitly requested WIDE we
        # fall back to SEMI_LONG which preserves ticker as a column.  Users
        # who explicitly pass format=Format.WIDE get the flattened-column
        # approximation from _pivot_wide_non_pandas().  (#225)
        if request.format is None and format_ == Format.WIDE and backend != Backend.PANDAS:
            from xbbg.deprecation import warn_once

            warn_once(
                "wide_to_semi_long",
                f"WIDE format requires pandas MultiIndex which {backend.value} does not support. "
                "Automatically using SEMI_LONG format instead (ticker preserved as column). "
                "Pass format=Format.WIDE explicitly to force flattened column names, "
                "or format=Format.SEMI_LONG to silence this warning.",
                stacklevel=4,
            )
            format_ = Format.SEMI_LONG

        # Warn if using implicit defaults
        if request.backend is None or request.format is None:
            warn_defaults_changing()

        # Get Arrow table from transformed data (fallback for pandas during transition)
        if isinstance(transformed, pa.Table):
            arrow_table = transformed
        else:
            try:
                arrow_table = pa.Table.from_pandas(transformed)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                # Mixed-type columns -- coerce object columns to string
                transformed = transformed.copy()
                for col in transformed.columns:
                    if transformed[col].dtype == object:
                        transformed[col] = transformed[col].astype("string")
                arrow_table = pa.Table.from_pandas(transformed)

        result = to_output(
            arrow_table,
            backend=backend,
            format=format_,
            ticker_col="ticker",
            date_col="date",
            field_cols=None,  # Will be inferred from columns
        )

        # Step 10: Persist cache
        if request.cache_policy.enabled:
            self._persist_cache(result, request, session_window)

        return result

    def _resolve_market(self, request: DataRequest) -> ResolverResult:
        """Resolve market using resolver chain."""
        for resolver in self.market_resolvers:
            if resolver.can_resolve(request):
                result = resolver.resolve(request)
                if result.success:
                    return result
        # No resolver succeeded - return failure result
        # The main pipeline will decide whether to proceed based on needs_session
        return ResolverResult(
            resolved_ticker=request.ticker,
            exchange_info=pd.Series(dtype=object),
            success=False,
            resolver_name="None",
        )

    def _resolve_session(
        self,
        request: DataRequest,
        exchange_info: pd.Series,
    ) -> SessionWindow:
        """Resolve session window (delegates to config if needed)."""
        if not self.config.needs_session:
            return SessionWindow(
                start_time=None,
                end_time=None,
                session_name="",
                timezone="UTC",
            )

        # For multi-day requests with explicit datetime range, skip session resolution
        # The IntradayRequestBuilder will use the explicit datetime range directly
        if request.is_multi_day():
            # Determine timezone from exchange_info or default to UTC
            tz = exchange_info.get("tz", "UTC") if not exchange_info.empty else "UTC"
            return SessionWindow(
                start_time=None,  # Not used for multi-day
                end_time=None,  # Not used for multi-day
                session_name="",  # No session filtering for multi-day
                timezone=tz,
            )

        # For intraday: use process.time_range
        from xbbg.core.process import time_range
        from xbbg.core.utils.timezone import get_tz

        if exchange_info.empty:
            cur_dt = pd.Timestamp(request.dt).strftime("%Y-%m-%d")
            tz = "UTC"
            return SessionWindow(
                start_time=f"{cur_dt}T00:00:00",
                end_time=f"{cur_dt}T23:59:59",
                session_name=request.session,
                timezone=tz,
            )

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        tz = exchange_info.get("tz", "UTC")
        try:
            dest_tz = get_tz(tz)
        except Exception:
            dest_tz = tz

        try:
            ss = time_range(
                dt=request.dt,
                ticker=request.ticker,
                session=request.session,
                tz=dest_tz,
                ctx=request.context,
                **ctx_kwargs,
            )

            if ss.start_time is not None and ss.end_time is not None:
                return SessionWindow(
                    start_time=ss.start_time,
                    end_time=ss.end_time,
                    session_name=request.session,
                    timezone=dest_tz,
                )
        except Exception as e:
            logger.debug("Session resolution failed: %s", e)

        # Fallback: invalid session
        return SessionWindow(
            start_time=None,
            end_time=None,
            session_name=request.session,
            timezone=tz,
        )

    def _read_cache(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> pd.DataFrame | None:
        """Read from cache."""
        if self.cache_adapter is None:
            return None
        return self.cache_adapter.load(request, session_window)

    def _validate_request(self, request: DataRequest) -> bool:
        """Validate request before fetching."""
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        return process.check_current(dt=request.dt, logger=logger, **ctx_kwargs)

    async def _afetch_from_bloomberg(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> pa.Table | None:
        """Fetch data from Bloomberg using arequest() (async)."""
        blp_request, ctx_kwargs = self.config.request_builder.build_request(request, session_window)

        events = await conn.arequest(
            request=blp_request,
            process_func=self.config.process_func,
            service=self.config.service,
            **ctx_kwargs,
        )

        return self._events_to_arrow(events)

    @staticmethod
    def _events_to_arrow(events: list[dict]) -> pa.Table | None:
        """Convert event dicts to Arrow table (no pandas intermediary)."""
        return _events_to_table(events)

    def _persist_cache(
        self,
        data: pd.DataFrame,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> None:
        """Persist to cache."""
        if self.cache_adapter is None:
            return
        self.cache_adapter.save(data, request, session_window)

    # BaseContextAware methods
    def _prepare_context(self, request: DataRequest):
        """Prepare Bloomberg context."""
        if request.context is not None:
            return request.context
        return self._get_context(**request.request_opts)

    def _with_context(self, request: DataRequest, ctx) -> DataRequest:
        """Update request with context."""
        return replace(request, context=ctx)

    def _with_resolved_ticker(self, request: DataRequest, resolved_ticker: str) -> DataRequest:
        """Update request with resolved ticker."""
        return replace(request, ticker=resolved_ticker)
