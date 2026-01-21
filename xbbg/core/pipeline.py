"""Unified Bloomberg data pipeline with Strategy pattern.

This module provides a single, configurable pipeline that handles all Bloomberg
API requests through Strategy-based handlers for request building and response transformation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Protocol

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.context import split_kwargs
from xbbg.core.domain.contracts import (
    BaseContextAware,
    CacheAdapter,
    CachePolicy,
    DataRequest,
    MarketResolver,
    ResolverResult,
    SessionWindow,
)
from xbbg.core.infra import conn
from xbbg.core.utils import utils as utils_module

logger = logging.getLogger(__name__)


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
        """Execute the pipeline (Template Method).

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

        # Step 6: Fetch from Bloomberg
        raw_data = self._fetch_from_bloomberg(request, session_window)
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

        # Warn if using implicit defaults
        if request.backend is None or request.format is None:
            warn_defaults_changing()

        # Get Arrow table from transformed data (fallback for pandas during transition)
        arrow_table = transformed if isinstance(transformed, pa.Table) else pa.Table.from_pandas(transformed)

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

    def _fetch_from_bloomberg(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> pa.Table | None:
        """Fetch data from Bloomberg using configured strategy."""
        blp_request, ctx_kwargs = self.config.request_builder.build_request(request, session_window)

        handle = conn.send_request(request=blp_request, service=self.config.service, **ctx_kwargs)

        events = list(
            process.rec_events(
                func=self.config.process_func,
                event_queue=handle["event_queue"],
                **ctx_kwargs,
            )
        )

        if not events:
            return None

        # Build DataFrame from events - let pandas infer types naturally
        df = pd.DataFrame(events)

        # Handle mixed-type 'value' column (can contain strings, floats, dates)
        # Convert to string only if it has mixed types that PyArrow can't handle
        if "value" in df.columns and df["value"].dtype == object:
            # Check if all non-null values are numeric
            try:
                pd.to_numeric(df["value"], errors="raise")
            except (ValueError, TypeError):
                # Mixed types - convert to string for Arrow compatibility
                df["value"] = df["value"].astype(str)

        # Convert to Arrow table, letting PyArrow infer types from pandas
        # This preserves numeric types (float64, int64) and handles dates properly
        return pa.Table.from_pandas(df, preserve_index=False)

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
        return DataRequest(
            ticker=request.ticker,
            dt=request.dt,
            session=request.session,
            event_type=request.event_type,
            interval=request.interval,
            interval_has_seconds=request.interval_has_seconds,
            start_datetime=request.start_datetime,
            end_datetime=request.end_datetime,
            context=ctx,
            cache_policy=request.cache_policy,
            override_kwargs=request.override_kwargs,
            request_opts=request.request_opts,
            backend=request.backend,
            format=request.format,
        )

    def _with_resolved_ticker(self, request: DataRequest, resolved_ticker: str) -> DataRequest:
        """Update request with resolved ticker."""
        return DataRequest(
            ticker=resolved_ticker,
            dt=request.dt,
            session=request.session,
            event_type=request.event_type,
            interval=request.interval,
            interval_has_seconds=request.interval_has_seconds,
            start_datetime=request.start_datetime,
            end_datetime=request.end_datetime,
            context=request.context,
            cache_policy=request.cache_policy,
            override_kwargs=request.override_kwargs,
            request_opts=request.request_opts,
            backend=request.backend,
            format=request.format,
        )


# ============================================================================
# Strategy Implementations
# ============================================================================


class ReferenceRequestBuilder:
    """Strategy for building Bloomberg reference data (BDP) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build reference data request."""
        tickers = request.request_opts.get("tickers", [request.ticker])
        flds = request.request_opts.get("flds", [])

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        tickers = utils_module.normalize_tickers(tickers)
        flds = utils_module.normalize_flds(flds)

        blp_request = process.create_request(
            service="//blp/refdata",
            request="ReferenceDataRequest",
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=tickers, flds=flds, **all_kwargs)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Sending Bloomberg reference data request for %d ticker(s), %d field(s)",
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class ReferenceTransformer:
    """Strategy for transforming Bloomberg reference data responses to Arrow format."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform reference data response.

        Args:
            raw_data: Arrow table with columns: ticker, field, value
            request: Data request containing context and options
            exchange_info: Exchange information (unused in Arrow path)
            session_window: Session window (unused in Arrow path)

        Returns:
            Arrow table sorted by ticker with standardized column names
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Check for empty result (all values null in required columns)
        required_cols = ["ticker", "field"]
        for col in required_cols:
            if col not in df.columns:
                return pa.table({})

        # Get column name mappings from context
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        col_maps = ctx_kwargs.get("col_maps", {}) or {}

        # Get original ticker order from request for sorting
        original_tickers = request.request_opts.get("tickers", [request.ticker])
        original_tickers = utils_module.normalize_tickers(original_tickers)
        if original_tickers is None:
            original_tickers = []
        elif not isinstance(original_tickers, list):
            original_tickers = list(original_tickers)

        # Create ticker order mapping for sorting
        ticker_order = {t: i for i, t in enumerate(original_tickers)}

        # Add sort order column based on original ticker order
        # Tickers not in original list get a high order value
        max_order = len(original_tickers)
        df = df.with_columns(
            nw.col("ticker")
            .replace_strict(
                ticker_order,
                default=max_order,
            )
            .alias("_ticker_order")
        )

        # Sort by ticker order to preserve original request order
        df = df.sort("_ticker_order", "_ticker_order")

        # Drop the temporary sort column
        df = df.drop("_ticker_order")

        # Standardize column names to snake_case
        def standardize_col_name(name: str) -> str:
            if name in col_maps:
                return col_maps[name]
            return name.lower().replace(" ", "_").replace("-", "_")

        # Rename columns
        rename_map = {col: standardize_col_name(col) for col in df.columns}
        df = df.rename(rename_map)

        # Convert back to Arrow table
        return nw.to_native(df)


# Historical Data Strategies
# ----------------------------------------------------------------------------


class HistoricalRequestBuilder:
    """Strategy for building Bloomberg historical data (BDH) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build historical data request."""
        tickers = request.request_opts.get("tickers", [request.ticker])
        flds = request.request_opts.get("flds", ["Last_Price"])
        start_date = request.request_opts.get("start_date")
        end_date = request.request_opts.get("end_date", "today")
        adjust = request.request_opts.get("adjust")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        e_dt = utils_module.fmt_dt(end_date, fmt="%Y%m%d")
        if start_date is None:
            start_date = pd.Timestamp(e_dt) - pd.Timedelta(weeks=8)
        s_dt = utils_module.fmt_dt(start_date, fmt="%Y%m%d")

        blp_request = process.create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            **all_kwargs,
        )
        process.init_request(
            request=blp_request,
            tickers=tickers,
            flds=flds,
            start_date=s_dt,
            end_date=e_dt,
            adjust=adjust,
            **all_kwargs,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Sending Bloomberg historical data request for %d ticker(s), %d field(s)",
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class HistoricalTransformer:
    """Strategy for transforming Bloomberg historical data responses.

    Returns data in semi-long format (ticker, date, field1, field2, ...).
    MultiIndex creation is handled by to_output() if format='wide' and backend='pandas'.
    """

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform historical data response.

        Args:
            raw_data: Arrow table with columns: ticker, date, field1, field2, ...
            request: Data request containing tickers and fields.
            exchange_info: Exchange information (unused in Arrow path).
            session_window: Session window (unused in Arrow path).

        Returns:
            Arrow table in semi-long format, sorted by ticker and date.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return raw_data

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Sort by ticker and date for consistent output
        df = df.sort("ticker", "date")

        # Return as Arrow table
        return nw.to_native(df)


# Intraday Data Strategies
# ----------------------------------------------------------------------------


class IntradayRequestBuilder:
    """Strategy for building Bloomberg intraday bar data requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build intraday bar data request."""
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **request.request_opts}

        # Check if this is a multi-day request with explicit datetime range
        if request.is_multi_day():
            # Use explicit datetime range - convert to UTC ISO format
            time_fmt = "%Y-%m-%dT%H:%M:%S"
            start_ts = pd.Timestamp(request.start_datetime)
            end_ts = pd.Timestamp(request.end_datetime)

            # If timestamps are timezone-aware, convert to UTC
            # If timezone-naive, assume they are already in UTC
            if start_ts.tzinfo is not None:
                start_dt = start_ts.tz_convert("UTC").strftime(time_fmt)
            else:
                start_dt = start_ts.strftime(time_fmt)

            if end_ts.tzinfo is not None:
                end_dt = end_ts.tz_convert("UTC").strftime(time_fmt)
            else:
                end_dt = end_ts.strftime(time_fmt)
        else:
            # Use session window for single-day requests
            start_dt = session_window.start_time
            end_dt = session_window.end_time

            if not start_dt or not end_dt:
                raise ValueError("Invalid session window for Bloomberg request")

            # Convert session window times from exchange timezone to UTC
            # Session window times are timezone-naive strings in the exchange timezone,
            # but Bloomberg expects UTC times
            if session_window.timezone:
                from xbbg.markets import convert_session_times_to_utc

                start_dt, end_dt = convert_session_times_to_utc(
                    start_time=start_dt,
                    end_time=end_dt,
                    exchange_tz=session_window.timezone,
                )
            else:
                # No timezone info - assume UTC (fallback)
                logger.warning("Session window has no timezone info, assuming UTC for Bloomberg request")

        settings = [
            ("security", request.ticker),
            ("eventType", request.event_type),
            ("interval", request.interval),
            ("startDateTime", start_dt),
            ("endDateTime", end_dt),
        ]
        if request.interval_has_seconds:
            settings.append(("intervalHasSeconds", True))

        blp_request = process.create_request(
            service="//blp/refdata",
            request="IntradayBarRequest",
            settings=settings,
            **all_kwargs,
        )

        if request.is_multi_day():
            logger.debug(
                "Sending Bloomberg intraday bar data request for %s / %s to %s / %s",
                request.ticker,
                start_dt,
                end_dt,
                request.event_type,
            )
        else:
            logger.debug(
                "Sending Bloomberg intraday bar data request for %s / %s / %s",
                request.ticker,
                request.to_date_string(),
                request.event_type,
            )

        return blp_request, ctx_kwargs


class IntradayTransformer:
    """Strategy for transforming Bloomberg intraday bar data responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform intraday bar data response.

        Args:
            raw_data: Arrow table with intraday bar data.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information including timezone.
            session_window: Session window for filtering (single-day requests).

        Returns:
            Arrow table in semi-long format (ticker, time, field1, field2, ...).
        """
        # Wrap Arrow table with narwhals
        df = nw.from_native(raw_data, eager_only=True)

        # Check for empty data or missing time column
        if df.shape[0] == 0 or "time" not in df.columns:
            # Return empty Arrow table with expected schema
            return pa.table({"ticker": [], "time": []})

        # Rename numEvents to num_trds for consistency
        if "numEvents" in df.columns:
            df = df.rename({"numEvents": "num_trds"})

        # Add ticker column for semi-long format
        df = df.with_columns(nw.lit(request.ticker).alias("ticker"))

        # Sort by time column
        df = df.sort("time")

        # Reorder columns to have ticker first, then time, then other fields
        cols = df.columns
        other_cols = [c for c in cols if c not in ("ticker", "time")]
        df = df.select(["ticker", "time"] + other_cols)

        # Return as Arrow table
        return nw.to_native(df)


# Block Data Strategies
# ----------------------------------------------------------------------------


class BlockDataRequestBuilder:
    """Strategy for building Bloomberg block data (BDS) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build block data request."""
        ticker = request.ticker
        fld = request.request_opts.get("fld", "")
        use_port = request.request_opts.get("use_port", False)

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        # Exclude request-specific options (fld, use_port) from kwargs passed to create_request
        # These are not Bloomberg overrides and should not be added to the request
        request_specific_opts = {"fld", "use_port"}
        filtered_request_opts = {k: v for k, v in request.request_opts.items() if k not in request_specific_opts}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **filtered_request_opts}

        # Set has_date if not already set
        if "has_date" not in all_kwargs:
            all_kwargs["has_date"] = True

        blp_request = process.create_request(
            service="//blp/refdata",
            request="PortfolioDataRequest" if use_port else "ReferenceDataRequest",
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=ticker, flds=fld, **all_kwargs)

        logger.debug("Sending Bloomberg block data request for ticker: %s, field: %s", ticker, fld)

        return blp_request, ctx_kwargs


class BlockDataTransformer:
    """Strategy for transforming Bloomberg block data (BDS) responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform block data response."""
        if raw_data.num_rows == 0:
            return pa.table({})

        df = nw.from_native(raw_data, eager_only=True)

        # Block data is already in a good format, just wrap and return
        return nw.to_native(df)


# Screening & Query Strategies
# ============================================================================


class BeqsRequestBuilder:
    """Strategy for building Bloomberg BEQS requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BEQS request."""
        screen = request.request_opts.get("screen", "")
        asof = request.request_opts.get("asof")
        typ = request.request_opts.get("typ", "PRIVATE")
        group = request.request_opts.get("group", "General")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **request.request_opts}

        blp_request = process.create_request(
            service="//blp/refdata",
            request="BeqsRequest",
            settings=[
                ("screenName", screen),
                ("screenType", "GLOBAL" if typ[0].upper() in ["G", "B"] else "PRIVATE"),
                ("Group", group),
            ],
            ovrds=[("PiTDate", utils_module.fmt_dt(asof, "%Y%m%d"))] if asof else [],
            **all_kwargs,
        )

        logger.debug(
            "Sending Bloomberg Equity Screening (BEQS) request for screen: %s, type: %s, group: %s",
            screen,
            typ,
            group,
        )

        return blp_request, ctx_kwargs


class BeqsTransformer:
    """Strategy for transforming Bloomberg BEQS responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BEQS response.

        Args:
            raw_data: Arrow table with columns: ticker, field, value
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with tickers as rows and fields as columns.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Check for required columns
        if "ticker" not in df.columns or "field" not in df.columns:
            return pa.table({})

        # Pivot using narwhals: ticker as index, field as columns, value as values
        pivoted = df.pivot(on="field", index="ticker", values="value")

        # Standardize column names to snake_case
        rename_map = {col: str(col).lower().replace(" ", "_").replace("-", "_") for col in pivoted.columns}
        pivoted = pivoted.rename(rename_map)

        # Return as Arrow table
        return nw.to_native(pivoted)


class BsrchRequestBuilder:
    """Strategy for building Bloomberg BSRCH requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BSRCH request."""
        from xbbg.core.infra.blpapi_wrapper import blpapi

        domain = request.request_opts.get("domain", "")
        overrides = request.request_opts.get("overrides")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Create request using exrsvc service
        exr_service = conn.bbg_service(service="//blp/exrsvc", **ctx_kwargs)
        blp_request = exr_service.createRequest("ExcelGetGridRequest")

        # Set Domain element
        blp_request.getElement(blpapi.Name("Domain")).setValue(domain)

        # Add overrides if provided
        if overrides:
            overrides_elem = blp_request.getElement(blpapi.Name("Overrides"))
            for name, value in overrides.items():
                override_item = overrides_elem.appendElement()
                override_item.setElement(blpapi.Name("name"), name)
                override_item.setElement(blpapi.Name("value"), str(value))

        if logger.isEnabledFor(logging.DEBUG):
            override_info = f" with {len(overrides)} override(s)" if overrides else ""
            logger.debug("Sending Bloomberg SRCH request for domain: %s%s", domain, override_info)

        return blp_request, ctx_kwargs


class BsrchTransformer:
    """Strategy for transforming Bloomberg BSRCH responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BSRCH response.

        Args:
            raw_data: Arrow table with search results.
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table (pass-through, no transformation needed).
        """
        # BSRCH returns data in a good format already, just pass through
        return raw_data


class BqlRequestBuilder:
    """Strategy for building Bloomberg BQL requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BQL request."""
        query = request.request_opts.get("query", "")
        params = request.request_opts.get("params")
        overrides = request.request_opts.get("overrides")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        settings = [("expression", query)]
        if params:
            settings.extend([(str(k), v) for k, v in params.items()])

        blp_request = process.create_request(
            service="//blp/bqlsvc",
            request="sendQuery",
            settings=settings,
            ovrds=overrides or [],
            **ctx_kwargs,
        )

        logger.debug("Sending Bloomberg Query Language (BQL) request")

        return blp_request, ctx_kwargs


class BqlTransformer:
    """Strategy for transforming Bloomberg BQL responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BQL response.

        Args:
            raw_data: Arrow table with BQL query results.
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with date columns auto-converted.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return raw_data

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Auto-convert date columns by name pattern
        # Identify potential date columns by name
        date_cols = [
            col for col in df.columns if any(keyword in str(col).lower() for keyword in ["date", "dt", "time"])
        ]

        if not date_cols:
            return nw.to_native(df)

        # Process each potential date column using narwhals
        for col in date_cols:
            # Get the column dtype - only convert string columns
            col_dtype = df.select(col).schema[col]

            # Check if it's a string type (narwhals String dtype)
            if col_dtype == nw.String:
                from contextlib import suppress

                # Attempt datetime conversion using narwhals
                with suppress(Exception):
                    df = df.with_columns(nw.col(col).str.to_datetime(format=None).alias(col))

        return nw.to_native(df)


# ============================================================================
# Request Builder (Builder Pattern)
# ============================================================================


class RequestBuilder:
    """Builder for DataRequest objects (Builder pattern).

    Provides fluent API to construct DataRequest from legacy kwargs.
    """

    def __init__(self):
        """Initialize builder."""
        self._ticker: str | None = None
        self._dt = None
        self._session: str = "allday"
        self._event_type: str = "TRADE"
        self._interval: int = 1
        self._interval_has_seconds: bool = False
        self._start_datetime = None
        self._end_datetime = None
        self._context = None
        self._cache_policy = CachePolicy()
        self._request_opts: dict = {}
        self._override_kwargs: dict = {}
        self._backend: str | None = None
        self._format: str | None = None

    def ticker(self, ticker: str) -> RequestBuilder:
        """Set ticker."""
        self._ticker = ticker
        return self

    def date(self, dt) -> RequestBuilder:
        """Set date."""
        self._dt = dt
        return self

    def session(self, session: str) -> RequestBuilder:
        """Set session."""
        self._session = session
        return self

    def event_type(self, typ: str) -> RequestBuilder:
        """Set event type."""
        self._event_type = typ
        return self

    def interval(self, interval: int, has_seconds: bool = False) -> RequestBuilder:
        """Set interval."""
        self._interval = interval
        self._interval_has_seconds = has_seconds
        return self

    def datetime_range(self, start_datetime, end_datetime) -> RequestBuilder:
        """Set explicit datetime range for multi-day requests."""
        self._start_datetime = start_datetime
        self._end_datetime = end_datetime
        return self

    def context(self, ctx) -> RequestBuilder:
        """Set Bloomberg context."""
        self._context = ctx
        return self

    def cache_policy(self, enabled: bool = True, reload: bool = False) -> RequestBuilder:
        """Set cache policy."""
        self._cache_policy = CachePolicy(enabled=enabled, reload=reload)
        return self

    def request_opts(self, **opts) -> RequestBuilder:
        """Add request-specific options."""
        self._request_opts.update(opts)
        return self

    def override_kwargs(self, **kwargs) -> RequestBuilder:
        """Add Bloomberg override kwargs."""
        self._override_kwargs.update(kwargs)
        return self

    def with_output(self, backend: str, format: str) -> RequestBuilder:
        """Set output backend and format.

        Args:
            backend: Output backend (e.g., 'pandas', 'polars').
            format: Output format (e.g., 'dataframe', 'series').

        Returns:
            Self for method chaining.
        """
        self._backend = backend
        self._format = format
        return self

    def build(self) -> DataRequest:
        """Build DataRequest from builder state.

        Returns:
            DataRequest instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if self._ticker is None:
            raise ValueError("ticker is required")
        if self._dt is None:
            raise ValueError("dt is required")

        return DataRequest(
            ticker=self._ticker,
            dt=self._dt,
            session=self._session,
            event_type=self._event_type,
            interval=self._interval,
            interval_has_seconds=self._interval_has_seconds,
            start_datetime=self._start_datetime,
            end_datetime=self._end_datetime,
            context=self._context,
            cache_policy=self._cache_policy,
            request_opts=self._request_opts,
            override_kwargs=self._override_kwargs,
            backend=self._backend,
            format=self._format,
        )

    @classmethod
    def from_legacy_kwargs(
        cls,
        ticker: str,
        dt,
        session: str = "allday",
        typ: str = "TRADE",
        start_datetime=None,
        end_datetime=None,
        backend: str | None = None,
        format: str | None = None,
        **kwargs,
    ) -> DataRequest:
        """Build from legacy function signature.

        Args:
            ticker: Ticker symbol.
            dt: Date.
            session: Session name.
            typ: Event type.
            start_datetime: Optional explicit start datetime for multi-day requests.
            end_datetime: Optional explicit end datetime for multi-day requests.
            backend: Backend for data processing (e.g., 'pandas', 'polars').
            format: Output format for the data (e.g., 'long', 'wide').
            **kwargs: Legacy kwargs (will be split).

        Returns:
            DataRequest instance.
        """
        split = split_kwargs(**kwargs)
        builder = cls()
        builder.ticker(ticker).date(dt).session(session).event_type(typ)
        builder.context(split.infra)
        builder.cache_policy(
            enabled=split.infra.cache,
            reload=split.infra.reload,
        )

        # Extract interval and intervalHasSeconds from request_opts
        interval = split.request_opts.get("interval", 1)
        interval_has_seconds = split.request_opts.get("intervalHasSeconds", False)
        builder.interval(interval, interval_has_seconds)

        # Set datetime range if provided
        if start_datetime is not None and end_datetime is not None:
            builder.datetime_range(start_datetime, end_datetime)

        # Merge remaining request_opts and override_kwargs
        builder.request_opts(**split.request_opts)
        builder.override_kwargs(**split.override_like)

        # Set output backend and format if provided
        if backend is not None or format is not None:
            builder.with_output(backend, format)

        return builder.build()


# ============================================================================
# Factory Functions for PipelineConfig
# ============================================================================


def reference_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg reference data (BDP)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="ReferenceDataRequest",
        process_func=process.process_ref,
        request_builder=ReferenceRequestBuilder(),
        transformer=ReferenceTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def historical_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg historical data (BDH)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="HistoricalDataRequest",
        process_func=process.process_hist,
        request_builder=HistoricalRequestBuilder(),
        transformer=HistoricalTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def intraday_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg intraday bar data (BDIB)."""
    from xbbg.io.cache import BarCacheAdapter
    from xbbg.markets.resolver_chain import create_default_resolver_chain

    return PipelineConfig(
        service="//blp/refdata",
        request_type="IntradayBarRequest",
        process_func=process.process_bar,
        request_builder=IntradayRequestBuilder(),
        transformer=IntradayTransformer(),
        needs_session=True,
        default_resolvers=create_default_resolver_chain,
        default_cache_adapter=BarCacheAdapter,
    )


def block_data_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg block data (BDS)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="ReferenceDataRequest",
        process_func=process.process_ref,
        request_builder=BlockDataRequestBuilder(),
        transformer=BlockDataTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def beqs_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Equity Screening (BEQS)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="BeqsRequest",
        process_func=process.process_ref,
        request_builder=BeqsRequestBuilder(),
        transformer=BeqsTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bsrch_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg SRCH (Search) queries."""
    return PipelineConfig(
        service="//blp/exrsvc",
        request_type="ExcelGetGridRequest",
        process_func=process.process_bsrch,
        request_builder=BsrchRequestBuilder(),
        transformer=BsrchTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bql_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Query Language (BQL)."""
    return PipelineConfig(
        service="//blp/bqlsvc",
        request_type="sendQuery",
        process_func=process.process_bql,
        request_builder=BqlRequestBuilder(),
        transformer=BqlTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


class BtaRequestBuilder:
    """Strategy for building Bloomberg Technical Analysis (TASVC) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build TASVC studyRequest.

        The TASVC request has a nested structure:
        studyRequest = {
            priceSource = {
                securityName = "IBM US Equity"
                dataRange = {
                    historical = {
                        startDate, endDate, periodicitySelection, ...
                    }
                }
            }
            studyAttributes = {
                <studyType>StudyAttributes = {
                    period, priceSourceClose, ...
                }
            }
        }
        """
        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Get request options
        opts = request.request_opts
        study = opts.get("study", "SMA")
        study_attribute = opts.get("study_attribute", "smavgStudyAttributes")
        study_params = opts.get("study_params", {})
        start_date = opts.get("start_date")
        end_date = opts.get("end_date")
        periodicity = opts.get("periodicity", "DAILY")

        # Format dates
        if start_date:
            start_date = pd.Timestamp(start_date).strftime("%Y%m%d")
        else:
            # Default to 1 year ago
            start_date = (pd.Timestamp("today") - pd.Timedelta(days=365)).strftime("%Y%m%d")

        end_date = pd.Timestamp(end_date).strftime("%Y%m%d") if end_date else pd.Timestamp("today").strftime("%Y%m%d")

        # Get service and create request
        service = conn.bbg_service(service="//blp/tasvc", **ctx_kwargs)
        blp_request = service.createRequest("studyRequest")

        # Set up priceSource
        price_source = blp_request.getElement("priceSource")
        price_source.setElement("securityName", request.ticker)

        # Set up dataRange.historical
        data_range = price_source.getElement("dataRange")
        historical = data_range.getElement("historical")
        historical.setElement("startDate", start_date)
        historical.setElement("endDate", end_date)
        historical.setElement("periodicitySelection", periodicity)

        # Set up studyAttributes
        study_attrs = blp_request.getElement("studyAttributes")
        study_elem = study_attrs.getElement(study_attribute)

        for param_name, param_value in study_params.items():
            study_elem.setElement(param_name, param_value)

        logger.debug(f"Sending TASVC studyRequest for {request.ticker} with {study} study")

        return blp_request, ctx_kwargs


class BtaTransformer:
    """Strategy for transforming Bloomberg TASVC responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform TASVC response to Arrow table.

        Args:
            raw_data: Arrow table with date and study value columns.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with date column converted to datetime.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Convert to pandas for date parsing (handles timezone-aware strings)
        df_pd = raw_data.to_pandas()

        # Convert date column to datetime if present
        if "date" in df_pd.columns and df_pd["date"].dtype == object:
            df_pd["date"] = pd.to_datetime(df_pd["date"], utc=True)

        # Sort by date for consistent output
        if "date" in df_pd.columns:
            df_pd = df_pd.sort_values("date").reset_index(drop=True)

        # Return as Arrow table
        return pa.Table.from_pandas(df_pd, preserve_index=False)


def bta_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Technical Analysis (TASVC)."""
    return PipelineConfig(
        service="//blp/tasvc",
        request_type="studyRequest",
        process_func=process.process_tasvc,
        request_builder=BtaRequestBuilder(),
        transformer=BtaTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


# ============================================================================
# BQR (Bloomberg Quote Request) Strategies
# ============================================================================


class BqrRequestBuilder:
    """Strategy for building Bloomberg Quote Request (BQR) using IntradayTickRequest.

    BQR emulates the Excel =BQR() function by using IntradayTickRequest with
    BID/ASK event types and broker codes enabled. This provides dealer quote
    data similar to what the Excel formula returns.
    """

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BQR request using IntradayTickRequest.

        Args:
            request: Data request containing ticker, date range, and options.
            session_window: Session window (unused for BQR).

        Returns:
            Tuple of (Bloomberg request, context kwargs).
        """
        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Get request options
        opts = request.request_opts
        ticker = opts.get("ticker", request.ticker)
        event_types = opts.get("event_types", ["BID", "ASK"])
        include_broker_codes = opts.get("include_broker_codes", True)
        include_condition_codes = opts.get("include_condition_codes", False)
        include_exchange_codes = opts.get("include_exchange_codes", False)

        # Parse date offset or explicit dates
        date_offset = opts.get("date_offset")
        start_date = opts.get("start_date")
        end_date = opts.get("end_date")

        # Calculate time range
        now = pd.Timestamp.now(tz="UTC")
        time_fmt = "%Y-%m-%dT%H:%M:%S"

        if date_offset:
            # Parse offset like "-2d", "-1w", etc.
            end_dt = now
            start_dt = self._parse_date_offset(date_offset, now)
        elif start_date:
            start_dt = pd.Timestamp(start_date, tz="UTC")
            end_dt = pd.Timestamp(end_date, tz="UTC") if end_date else now
        else:
            # Default: last 2 days
            end_dt = now
            start_dt = now - pd.Timedelta(days=2)

        # Create IntradayTickRequest
        service = conn.bbg_service(service="//blp/refdata", **ctx_kwargs)
        blp_request = service.createRequest("IntradayTickRequest")

        # Set security
        blp_request.set("security", ticker)

        # Set time range
        blp_request.set("startDateTime", start_dt.strftime(time_fmt))
        blp_request.set("endDateTime", end_dt.strftime(time_fmt))

        # Add event types
        event_types_elem = blp_request.getElement("eventTypes")
        for event_type in event_types:
            event_types_elem.appendValue(event_type)

        # Enable broker codes (key for BQR/AllQuotes functionality)
        blp_request.set("includeBrokerCodes", include_broker_codes)

        # Optional: condition and exchange codes
        if include_condition_codes:
            blp_request.set("includeConditionCodes", True)
        if include_exchange_codes:
            blp_request.set("includeExchangeCodes", True)

        logger.debug(
            "Sending BQR request for %s from %s to %s with event types %s",
            ticker,
            start_dt.strftime(time_fmt),
            end_dt.strftime(time_fmt),
            event_types,
        )

        return blp_request, ctx_kwargs

    def _parse_date_offset(self, offset: str, reference: pd.Timestamp) -> pd.Timestamp:
        """Parse date offset string like '-2d', '-1w', '-1m'.

        Args:
            offset: Offset string (e.g., '-2d', '-1w', '-1m', '-3h').
            reference: Reference timestamp.

        Returns:
            Calculated timestamp.
        """
        import re

        offset = offset.strip().lower()

        # Match pattern like -2d, -1w, -1m, -3h
        match = re.match(r"^(-?\d+)([dwmh])$", offset)
        if not match:
            raise ValueError(f"Invalid date offset format: {offset}. Use format like '-2d', '-1w', '-1m', '-3h'")

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "d":
            return reference + pd.Timedelta(days=value)
        if unit == "w":
            return reference + pd.Timedelta(weeks=value)
        if unit == "m":
            # Approximate month as 30 days
            return reference + pd.Timedelta(days=value * 30)
        if unit == "h":
            return reference + pd.Timedelta(hours=value)
        raise ValueError(f"Unknown time unit: {unit}")


class BqrTransformer:
    """Strategy for transforming Bloomberg BQR (Quote Request) responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BQR tick response to Arrow table.

        Args:
            raw_data: Arrow table with tick data including broker codes.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with standardized column names and sorted by time.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Standardize column names
        rename_map = {
            "time": "time",
            "type": "event_type",
            "value": "price",
            "size": "size",
            "brokerBuyCode": "broker_buy",
            "brokerSellCode": "broker_sell",
            "conditionCodes": "condition_codes",
            "exchangeCode": "exchange",
        }

        # Only rename columns that exist
        actual_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        if actual_renames:
            df = df.rename(actual_renames)

        # Add ticker column
        ticker = request.request_opts.get("ticker", request.ticker)
        df = df.with_columns(nw.lit(ticker).alias("ticker"))

        # Sort by time
        if "time" in df.columns:
            df = df.sort("time")

        # Reorder columns: ticker first, then time, then others
        cols = df.columns
        priority_cols = ["ticker", "time", "event_type", "price", "size", "broker_buy", "broker_sell"]
        ordered_cols = [c for c in priority_cols if c in cols]
        other_cols = [c for c in cols if c not in priority_cols]
        df = df.select(ordered_cols + other_cols)

        return nw.to_native(df)


def bqr_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Quote Request (BQR).

    BQR emulates the Excel =BQR() function for retrieving dealer quote data
    using IntradayTickRequest with BID/ASK events and broker codes.
    """
    return PipelineConfig(
        service="//blp/refdata",
        request_type="IntradayTickRequest",
        process_func=process.process_bqr,
        request_builder=BqrRequestBuilder(),
        transformer=BqrTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )
