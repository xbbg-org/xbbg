"""Unified Bloomberg data pipeline with Strategy pattern.

This module provides a single, configurable pipeline that handles all Bloomberg
API requests through Strategy-based handlers for request building and response transformation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Protocol

import pandas as pd

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
from xbbg.utils import pipeline as pipeline_utils

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
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform raw Bloomberg response.

        Args:
            raw_data: Raw DataFrame from Bloomberg.
            request: Original data request.
            exchange_info: Exchange information.
            session_window: Session window.

        Returns:
            Transformed DataFrame.
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
        timeout: Request timeout in milliseconds.
        max_timeouts: Maximum allowed timeouts.
    """

    service: str
    request_type: str
    process_func: Callable
    request_builder: RequestBuilderStrategy
    transformer: ResponseTransformerStrategy
    needs_session: bool = False
    default_resolvers: Callable[[], list[MarketResolver]] | None = None
    default_cache_adapter: Callable[[], CacheAdapter | None] = lambda: None
    timeout: int | None = None
    max_timeouts: int | None = None


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

    def run(self, request: DataRequest) -> pd.DataFrame:
        """Execute the pipeline (Template Method).

        Args:
            request: Data request to process.

        Returns:
            DataFrame with requested data.
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
                    logger.warning('Market resolution failed for %s', request.ticker)
                    return pd.DataFrame()
                # Endpoints with resolvers but no session requirement can proceed without exchange info
                logger.debug('Market resolution failed for %s, proceeding without exchange info', request.ticker)
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
                resolver_name='None',
            )

        # Step 3: Resolve session window (if needed)
        session_window = self._resolve_session(request, resolver_result.exchange_info)
        # Skip session validation for multi-day requests (they use explicit datetime range)
        if self.config.needs_session and not request.is_multi_day() and session_window.session_name and not session_window.is_valid():
            logger.warning(
                'Session resolution failed for %s / %s / %s',
                request.ticker,
                request.dt,
                request.session,
            )
            return pd.DataFrame()

        # Step 4: Try cache
        if request.cache_policy.enabled and not request.cache_policy.reload:
            cached_data = self._read_cache(request, session_window)
            if cached_data is not None and not cached_data.empty:
                logger.debug('Cache hit for %s / %s', request.ticker, request.to_date_string())
                return cached_data

        # Step 5: Validate before fetch
        if not self._validate_request(request):
            return pd.DataFrame()

        # Step 6: Fetch from Bloomberg
        raw_data = self._fetch_from_bloomberg(request, session_window)
        # Ensure raw_data is always a DataFrame (not None) for transformer
        if raw_data is None:
            raw_data = pd.DataFrame()
        if raw_data.empty:
            logger.debug('No data returned from Bloomberg for %s', request.ticker)

        # Step 7: Handle raw flag
        if request.context and request.context.raw:
            return raw_data

        # Step 8: Transform response
        # Transformer should handle empty data and return appropriate structure
        # (e.g., MultiIndex for historical data to support operations like .xs())
        transformed = self.config.transformer.transform(
            raw_data, request, resolver_result.exchange_info, session_window
        )
        # Don't return early if empty - let the transformer decide the structure
        # Some transformers (like HistoricalTransformer) return empty DataFrames with
        # proper MultiIndex structure that downstream code expects

        # Step 9: Persist cache
        if request.cache_policy.enabled:
            self._persist_cache(transformed, request, session_window)

        return transformed

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
            resolver_name='None',
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
                session_name='',
                timezone='UTC',
            )

        # For multi-day requests with explicit datetime range, skip session resolution
        # The IntradayRequestBuilder will use the explicit datetime range directly
        if request.is_multi_day():
            # Determine timezone from exchange_info or default to UTC
            tz = exchange_info.get('tz', 'UTC') if not exchange_info.empty else 'UTC'
            return SessionWindow(
                start_time=None,  # Not used for multi-day
                end_time=None,    # Not used for multi-day
                session_name='',  # No session filtering for multi-day
                timezone=tz,
            )

        # For intraday: use process.time_range
        from xbbg.core.process import time_range
        from xbbg.core.utils.timezone import get_tz

        if exchange_info.empty:
            cur_dt = pd.Timestamp(request.dt).strftime('%Y-%m-%d')
            tz = 'UTC'
            return SessionWindow(
                start_time=f'{cur_dt}T00:00:00',
                end_time=f'{cur_dt}T23:59:59',
                session_name=request.session,
                timezone=tz,
            )

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        tz = exchange_info.get('tz', 'UTC')
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
            logger.debug('Session resolution failed: %s', e)

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
    ) -> pd.DataFrame | None:
        """Fetch data from Bloomberg using configured strategy."""
        blp_request, ctx_kwargs = self.config.request_builder.build_request(request, session_window)

        timeout = self.config.timeout or ctx_kwargs.get('timeout', 500)
        max_timeouts = self.config.max_timeouts or ctx_kwargs.get('max_timeouts', 20)

        handle = conn.send_request(request=blp_request, service=self.config.service, **ctx_kwargs)

        res = pd.DataFrame(
            process.rec_events(
                func=self.config.process_func,
                event_queue=handle['event_queue'],
                timeout=timeout,
                max_timeouts=max_timeouts,
                **ctx_kwargs,
            )
        )

        if res.empty:
            return None

        return res

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
        tickers = request.request_opts.get('tickers', [request.ticker])
        flds = request.request_opts.get('flds', [])

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        tickers = utils_module.normalize_tickers(tickers)
        flds = utils_module.normalize_flds(flds)

        blp_request = process.create_request(
            service='//blp/refdata',
            request='ReferenceDataRequest',
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=tickers, flds=flds, **all_kwargs)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                'Sending Bloomberg reference data request for %d ticker(s), %d field(s)',
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class ReferenceTransformer:
    """Strategy for transforming Bloomberg reference data responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform reference data response."""
        if raw_data.empty:
            return pd.DataFrame()

        if utils_module.check_empty_result(raw_data, ['ticker', 'field']):
            return pd.DataFrame()

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        col_maps = ctx_kwargs.get('col_maps')

        # Get original ticker order from request
        original_tickers = request.request_opts.get('tickers', [request.ticker])
        # Normalize to iterable of tickers while preserving duplicates and order
        original_tickers = utils_module.normalize_tickers(original_tickers)
        # Convert to list explicitly in case normalize_tickers returned a tuple or other iterable
        if original_tickers is None:
            original_tickers = []
        elif not isinstance(original_tickers, list):
            original_tickers = list(original_tickers)

        # Transform the data
        result = (
            raw_data
            .set_index(['ticker', 'field'])
            .unstack(level=1)
            .rename_axis(index=None, columns=[None, None])
            .droplevel(axis=1, level=0)
            .loc[:, raw_data.field.unique()]
            .pipe(pipeline_utils.standard_cols, col_maps=col_maps)
        )

        # Preserve original ticker order by reindexing
        # Only include tickers that exist in the result
        available_tickers = [t for t in original_tickers if t in result.index]
        if available_tickers:
            result = result.reindex(available_tickers)

        return result


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
        tickers = request.request_opts.get('tickers', [request.ticker])
        flds = request.request_opts.get('flds', ['Last_Price'])
        start_date = request.request_opts.get('start_date')
        end_date = request.request_opts.get('end_date', 'today')
        adjust = request.request_opts.get('adjust')

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        e_dt = utils_module.fmt_dt(end_date, fmt='%Y%m%d')
        if start_date is None:
            start_date = pd.Timestamp(e_dt) - pd.Timedelta(weeks=8)
        s_dt = utils_module.fmt_dt(start_date, fmt='%Y%m%d')

        blp_request = process.create_request(
            service='//blp/refdata',
            request='HistoricalDataRequest',
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
                'Sending Bloomberg historical data request for %d ticker(s), %d field(s)',
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class HistoricalTransformer:
    """Strategy for transforming Bloomberg historical data responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform historical data response."""
        tickers = request.request_opts.get('tickers', [request.ticker])
        flds = request.request_opts.get('flds', ['Last_Price'])

        # Normalize to lists
        ticker_list = utils_module.flatten(tickers)
        fld_list = utils_module.flatten(flds)

        # If empty or missing required columns, return empty DataFrame with proper MultiIndex structure
        if raw_data.empty or utils_module.check_empty_result(raw_data, ['ticker', 'date']):
            # Create empty DataFrame with proper MultiIndex columns (ticker, field)
            # This ensures operations like .xs('Last_Price', axis=1, level=1) work correctly
            multi_index = pd.MultiIndex.from_product([ticker_list, fld_list], names=[None, None])
            return pd.DataFrame(index=pd.DatetimeIndex([]), columns=multi_index)

        return (
            raw_data
            .set_index(['ticker', 'date'])
            .unstack(level=0)
            .rename_axis(index=None, columns=[None, None])
            .swaplevel(0, 1, axis=1)
            .reindex(columns=ticker_list, level=0)
            .reindex(columns=fld_list, level=1)
        )


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
            time_fmt = '%Y-%m-%dT%H:%M:%S'
            start_ts = pd.Timestamp(request.start_datetime)
            end_ts = pd.Timestamp(request.end_datetime)

            # If timestamps are timezone-aware, convert to UTC
            # If timezone-naive, assume they are already in UTC
            if start_ts.tzinfo is not None:
                start_dt = start_ts.tz_convert('UTC').strftime(time_fmt)
            else:
                start_dt = start_ts.strftime(time_fmt)

            if end_ts.tzinfo is not None:
                end_dt = end_ts.tz_convert('UTC').strftime(time_fmt)
            else:
                end_dt = end_ts.strftime(time_fmt)
        else:
            # Use session window for single-day requests
            start_dt = session_window.start_time
            end_dt = session_window.end_time

            if not start_dt or not end_dt:
                raise ValueError('Invalid session window for Bloomberg request')

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
                logger.warning(
                    'Session window has no timezone info, assuming UTC for Bloomberg request'
                )

        settings = [
            ('security', request.ticker),
            ('eventType', request.event_type),
            ('interval', request.interval),
            ('startDateTime', start_dt),
            ('endDateTime', end_dt),
        ]
        if request.interval_has_seconds:
            settings.append(('intervalHasSeconds', True))

        blp_request = process.create_request(
            service='//blp/refdata',
            request='IntradayBarRequest',
            settings=settings,
            **all_kwargs,
        )

        if request.is_multi_day():
            logger.debug(
                'Sending Bloomberg intraday bar data request for %s / %s to %s / %s',
                request.ticker,
                start_dt,
                end_dt,
                request.event_type,
            )
        else:
            logger.debug(
                'Sending Bloomberg intraday bar data request for %s / %s / %s',
                request.ticker,
                request.to_date_string(),
                request.event_type,
            )

        return blp_request, ctx_kwargs


class IntradayTransformer:
    """Strategy for transforming Bloomberg intraday bar data responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform intraday bar data response."""
        if raw_data.empty or 'time' not in raw_data:
            return pd.DataFrame()

        tz = exchange_info.get('tz', 'UTC') if not exchange_info.empty else 'UTC'

        data = (
            raw_data
            .set_index('time')
            .rename_axis(index=None)
            .rename(columns={'numEvents': 'num_trds'})
            .tz_localize('UTC')
            .tz_convert(tz)
            .pipe(pipeline_utils.add_ticker, ticker=request.ticker)
        )

        # For multi-day requests, return all data without session filtering
        if request.is_multi_day():
            return data

        # Filter by session window for single-day requests
        if session_window.is_valid():
            return data.loc[session_window.start_time:session_window.end_time]

        return data


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
        fld = request.request_opts.get('fld', '')
        use_port = request.request_opts.get('use_port', False)

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        # Exclude request-specific options (fld, use_port) from kwargs passed to create_request
        # These are not Bloomberg overrides and should not be added to the request
        request_specific_opts = {'fld', 'use_port'}
        filtered_request_opts = {
            k: v for k, v in request.request_opts.items()
            if k not in request_specific_opts
        }
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **filtered_request_opts}

        # Set has_date if not already set
        if 'has_date' not in all_kwargs:
            all_kwargs['has_date'] = True

        blp_request = process.create_request(
            service='//blp/refdata',
            request='PortfolioDataRequest' if use_port else 'ReferenceDataRequest',
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=ticker, flds=fld, **all_kwargs)

        logger.debug('Sending Bloomberg block data request for ticker: %s, field: %s', ticker, fld)

        return blp_request, ctx_kwargs


class BlockDataTransformer:
    """Strategy for transforming Bloomberg block data (BDS) responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform block data response."""
        if raw_data.empty:
            return pd.DataFrame()

        if utils_module.check_empty_result(raw_data, ['ticker', 'field']):
            return pd.DataFrame()

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        col_maps = ctx_kwargs.get('col_maps')

        return (
            raw_data
            .set_index(['ticker', 'field'])
            .droplevel(axis=0, level=1)
            .rename_axis(index=None)
            .pipe(pipeline_utils.standard_cols, col_maps=col_maps)
        )


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
        screen = request.request_opts.get('screen', '')
        asof = request.request_opts.get('asof')
        typ = request.request_opts.get('typ', 'PRIVATE')
        group = request.request_opts.get('group', 'General')

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **request.request_opts}

        blp_request = process.create_request(
            service='//blp/refdata',
            request='BeqsRequest',
            settings=[
                ('screenName', screen),
                ('screenType', 'GLOBAL' if typ[0].upper() in ['G', 'B'] else 'PRIVATE'),
                ('Group', group),
            ],
            ovrds=[('PiTDate', utils_module.fmt_dt(asof, '%Y%m%d'))] if asof else [],
            **all_kwargs,
        )

        logger.debug(
            'Sending Bloomberg Equity Screening (BEQS) request for screen: %s, type: %s, group: %s',
            screen,
            typ,
            group,
        )

        return blp_request, ctx_kwargs


class BeqsTransformer:
    """Strategy for transforming Bloomberg BEQS responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform BEQS response."""
        if raw_data.empty:
            return pd.DataFrame()

        cols = raw_data.field.unique()
        return (
            raw_data
            .set_index(['ticker', 'field'])
            .unstack(level=1)
            .rename_axis(index=None, columns=[None, None])
            .droplevel(axis=1, level=0)
            .loc[:, cols]
            .pipe(pipeline_utils.standard_cols)
        )


class BsrchRequestBuilder:
    """Strategy for building Bloomberg BSRCH requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BSRCH request."""
        from xbbg.core.infra.blpapi_wrapper import blpapi

        domain = request.request_opts.get('domain', '')
        overrides = request.request_opts.get('overrides')

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Create request using exrsvc service
        exr_service = conn.bbg_service(service='//blp/exrsvc', **ctx_kwargs)
        blp_request = exr_service.createRequest('ExcelGetGridRequest')

        # Set Domain element
        blp_request.getElement(blpapi.Name('Domain')).setValue(domain)

        # Add overrides if provided
        if overrides:
            overrides_elem = blp_request.getElement(blpapi.Name('Overrides'))
            for name, value in overrides.items():
                override_item = overrides_elem.appendElement()
                override_item.setElement(blpapi.Name('name'), name)
                override_item.setElement(blpapi.Name('value'), str(value))

        if logger.isEnabledFor(logging.DEBUG):
            override_info = f' with {len(overrides)} override(s)' if overrides else ''
            logger.debug('Sending Bloomberg SRCH request for domain: %s%s', domain, override_info)

        return blp_request, ctx_kwargs


class BsrchTransformer:
    """Strategy for transforming Bloomberg BSRCH responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform BSRCH response."""
        return raw_data


class BqlRequestBuilder:
    """Strategy for building Bloomberg BQL requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BQL request."""
        query = request.request_opts.get('query', '')
        params = request.request_opts.get('params')
        overrides = request.request_opts.get('overrides')

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        settings = [('expression', query)]
        if params:
            settings.extend([(str(k), v) for k, v in params.items()])

        blp_request = process.create_request(
            service='//blp/bqlsvc',
            request='sendQuery',
            settings=settings,
            ovrds=overrides or [],
            **ctx_kwargs,
        )

        logger.debug('Sending Bloomberg Query Language (BQL) request')

        return blp_request, ctx_kwargs


class BqlTransformer:
    """Strategy for transforming Bloomberg BQL responses."""

    def transform(
        self,
        raw_data: pd.DataFrame,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pd.DataFrame:
        """Transform BQL response."""
        if raw_data.empty:
            return raw_data

        # Auto-convert date columns (vectorized approach)
        # Identify potential date columns by name
        date_cols = [
            col for col in raw_data.columns
            if any(keyword in str(col).lower() for keyword in ['date', 'dt', 'time'])
        ]

        if not date_cols:
            return raw_data

        # Process each potential date column
        for col in date_cols:
            # Only attempt conversion for object/string columns
            if raw_data[col].dtype != 'object':
                continue

            # Check if column contains date-like strings
            # Sample a few non-null values to determine if conversion is needed
            non_null_values = raw_data[col].dropna()
            if non_null_values.empty:
                continue

            # Check if values look like dates (sample-based check for efficiency)
            sample_size = min(10, len(non_null_values))
            sample = non_null_values.head(sample_size)

            # Check if sample contains date-like strings
            date_like_patterns = ['-', '/', 'T', ':']
            has_date_patterns = any(
                isinstance(val, str) and any(pattern in val for pattern in date_like_patterns)
                for val in sample
            )

            if has_date_patterns:
                from contextlib import suppress
                # Attempt vectorized conversion
                with suppress(ValueError, TypeError):
                    raw_data[col] = pd.to_datetime(raw_data[col], errors='coerce', infer_datetime_format=True)

        return raw_data


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
        self._session: str = 'allday'
        self._event_type: str = 'TRADE'
        self._interval: int = 1
        self._interval_has_seconds: bool = False
        self._start_datetime = None
        self._end_datetime = None
        self._context = None
        self._cache_policy = CachePolicy()
        self._request_opts: dict = {}
        self._override_kwargs: dict = {}

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

    def build(self) -> DataRequest:
        """Build DataRequest from builder state.

        Returns:
            DataRequest instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if self._ticker is None:
            raise ValueError('ticker is required')
        if self._dt is None:
            raise ValueError('dt is required')

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
        )

    @classmethod
    def from_legacy_kwargs(
        cls,
        ticker: str,
        dt,
        session: str = 'allday',
        typ: str = 'TRADE',
        start_datetime=None,
        end_datetime=None,
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
        interval = split.request_opts.get('interval', 1)
        interval_has_seconds = split.request_opts.get('intervalHasSeconds', False)
        builder.interval(interval, interval_has_seconds)

        # Set datetime range if provided
        if start_datetime is not None and end_datetime is not None:
            builder.datetime_range(start_datetime, end_datetime)

        # Merge remaining request_opts and override_kwargs
        builder.request_opts(**split.request_opts)
        builder.override_kwargs(**split.override_like)

        return builder.build()


# ============================================================================
# Factory Functions for PipelineConfig
# ============================================================================


def reference_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg reference data (BDP)."""
    return PipelineConfig(
        service='//blp/refdata',
        request_type='ReferenceDataRequest',
        process_func=process.process_ref,
        request_builder=ReferenceRequestBuilder(),
        transformer=ReferenceTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def historical_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg historical data (BDH)."""
    return PipelineConfig(
        service='//blp/refdata',
        request_type='HistoricalDataRequest',
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
        service='//blp/refdata',
        request_type='IntradayBarRequest',
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
        service='//blp/refdata',
        request_type='ReferenceDataRequest',
        process_func=process.process_ref,
        request_builder=BlockDataRequestBuilder(),
        transformer=BlockDataTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def beqs_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Equity Screening (BEQS)."""
    return PipelineConfig(
        service='//blp/refdata',
        request_type='BeqsRequest',
        process_func=process.process_ref,
        request_builder=BeqsRequestBuilder(),
        transformer=BeqsTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
        timeout=2000,
        max_timeouts=50,
    )


def bsrch_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg SRCH (Search) queries."""
    return PipelineConfig(
        service='//blp/exrsvc',
        request_type='ExcelGetGridRequest',
        process_func=process.process_bsrch,
        request_builder=BsrchRequestBuilder(),
        transformer=BsrchTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
        timeout=2000,
        max_timeouts=50,
    )


def bql_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Query Language (BQL)."""
    return PipelineConfig(
        service='//blp/bqlsvc',
        request_type='sendQuery',
        process_func=process.process_bql,
        request_builder=BqlRequestBuilder(),
        transformer=BqlTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )
