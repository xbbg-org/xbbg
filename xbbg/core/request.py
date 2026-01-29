# pyright: ignore
# basedpyright: ignore
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
import logging
from typing import Any, cast

import pandas as pd  # type: ignore

from xbbg.backend import Backend, Format
from xbbg.core.domain.context import BloombergContext, KwargsSplit, split_kwargs
from xbbg.core.domain.contracts import DataRequest
from xbbg.core.pipeline import BloombergPipeline, PipelineConfig, RequestBuilder
from xbbg.core.utils import utils
from xbbg.io.convert import concat_frames, is_empty

logger = logging.getLogger(__name__)

__all__ = ["request", "arequest"]


def _normalize_tickers(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return utils.normalize_tickers(value)
    return utils.normalize_tickers(list(value))  # type: ignore[arg-type]


def _normalize_fields(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return utils.normalize_flds(value)
    return utils.normalize_flds(list(value))  # type: ignore[arg-type]


def request(
    config: PipelineConfig | Callable[[], PipelineConfig],
    tickers: str | list[str] | None = None,
    fields: str | list[str] | None = None,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    dt: str | pd.Timestamp | None = None,
    asof: str | pd.Timestamp | None = None,
    start_datetime: str | pd.Timestamp | None = None,
    end_datetime: str | pd.Timestamp | None = None,
    session: str | None = None,
    typ: str | None = None,
    tickers_key: str | None = "tickers",
    fields_key: str | None = "flds",
    primary_ticker: str | None = None,
    request_opts: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
    infra: Mapping[str, Any] | None = None,
    backend: Backend | None = None,
    format: Format | None = None,
    cache_enabled: bool | None = None,
    reload: bool | None = None,
    per_ticker: bool = False,
    concat: bool = True,
    max_retries: int | None = None,
    raise_on_error: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Unified Bloomberg request handler.

    Args:
        config: Pipeline configuration or factory.
        tickers: Bloomberg security identifiers.
        fields: Bloomberg fields.
        start_date: Start date for date-range endpoints.
        end_date: End date for date-range endpoints.
        dt: Single-day date for intraday endpoints.
        asof: As-of date for screening endpoints.
        start_datetime: Explicit start datetime for multi-day intraday requests.
        end_datetime: Explicit end datetime for multi-day intraday requests.
        session: Trading session name for intraday endpoints.
        typ: Intraday event type (e.g., TRADE, BID, ASK).
        tickers_key: Key used to inject tickers into request options.
        fields_key: Key used to inject fields into request options.
        primary_ticker: Ticker used for resolver/session context.
        request_opts: Explicit request options merged into RequestBuilder.request_opts().
        overrides: Explicit override-like arguments merged into RequestBuilder.override_kwargs().
        infra: Infrastructure options (server, port, cache, reload).
        backend: Output backend for returned data.
        format: Output format selection.
        cache_enabled: Override for cache policy.
        reload: Override for cache reload.
        per_ticker: Run a separate pipeline per ticker and combine results.
        concat: When per_ticker=True, concatenate results with backend-aware concat.
        max_retries: Optional retry count for empty/timeout responses.
        raise_on_error: Re-raise pipeline exceptions if True.
        **kwargs: Legacy keyword arguments for split_kwargs.

    Returns:
        Data in requested backend/format.

    Examples:
        >>> from xbbg.core.pipeline import reference_pipeline_config
        >>> request(
        ...     config=reference_pipeline_config,
        ...     tickers="AAPL US Equity",
        ...     fields=["PX_LAST", "VOLUME"],
        ... )

        >>> from xbbg.core.pipeline import historical_pipeline_config
        >>> request(
        ...     config=historical_pipeline_config,
        ...     tickers="SPX Index",
        ...     fields="PX_LAST",
        ...     start_date="2024-01-01",
        ...     end_date="2024-12-31",
        ... )

        >>> from xbbg.core.pipeline import bql_pipeline_config
        >>> request(
        ...     config=bql_pipeline_config,
        ...     tickers=None,
        ...     fields=None,
        ...     primary_ticker="DUMMY",
        ...     tickers_key=None,
        ...     fields_key=None,
        ...     cache_enabled=False,
        ...     request_opts={"query": "get(px_last) for('AAPL US Equity')"},
        ... )

        >>> from xbbg.core.pipeline import block_data_pipeline_config
        >>> request(
        ...     config=block_data_pipeline_config,
        ...     tickers=["AAPL US Equity", "MSFT US Equity"],
        ...     fields="DVD_Hist_All",
        ...     fields_key="fld",
        ...     per_ticker=True,
        ... )
    """
    pipeline_config = config() if callable(config) else config

    split: KwargsSplit = cast(KwargsSplit, split_kwargs(**kwargs))  # type: ignore[reportAny]

    infra_kwargs = split.infra.to_kwargs()
    if infra:
        infra_kwargs.update(infra)
    if cache_enabled is not None:
        infra_kwargs["cache"] = cache_enabled
    if reload is not None:
        infra_kwargs["reload"] = reload
    context = BloombergContext.from_kwargs(infra_kwargs)

    ticker_list = _normalize_tickers(tickers)  # type: ignore[arg-type]
    field_list = _normalize_fields(fields)  # type: ignore[arg-type]

    if primary_ticker is None:
        primary_ticker = ticker_list[0] if ticker_list else "DUMMY"

    merged_request_opts: dict[str, Any] = dict(split.request_opts)
    if request_opts:
        merged_request_opts.update(request_opts)

    if start_date is not None:
        merged_request_opts["start_date"] = start_date
    if end_date is not None:
        merged_request_opts["end_date"] = end_date
    if asof is not None:
        merged_request_opts["asof"] = asof

    if tickers_key is not None:
        merged_request_opts[tickers_key] = ticker_list
    if fields_key is not None:
        merged_request_opts[fields_key] = field_list

    override_kwargs: dict[str, Any] = dict(split.override_like)
    if overrides:
        override_kwargs.update(overrides)

    dt_value: str | pd.Timestamp = "today"
    if start_datetime is not None and end_datetime is not None:
        assert start_datetime is not None
        dt_value = cast(str | pd.Timestamp, start_datetime)
    elif dt is not None:
        dt_value = dt
    elif start_date is not None or end_date is not None:
        if end_date is not None:
            dt_value = end_date
        else:
            assert start_date is not None
            dt_value = start_date
    elif asof is not None:
        dt_value = asof
    else:
        dt_value = "today"

    session_value = session if session is not None else "allday"
    typ_value = typ if typ is not None else "TRADE"

    interval_value = merged_request_opts.get("interval", 1)
    if isinstance(interval_value, (int, float, str, bool)):
        interval = int(interval_value)
    else:
        interval = 1
    interval_has_seconds: bool = bool(merged_request_opts.get("intervalHasSeconds", False))

    cache_policy_enabled = cache_enabled if cache_enabled is not None else context.cache
    cache_policy_reload = reload if reload is not None else context.reload

    pipeline = BloombergPipeline(config=pipeline_config)

    def _build_request(ticker: str, opts: dict[str, Any]) -> DataRequest:
        builder: RequestBuilder = RequestBuilder()
        builder = builder.ticker(ticker)
        builder = builder.date(dt_value)
        builder = builder.session(session_value)
        builder = builder.event_type(typ_value)
        builder = builder.interval(interval, interval_has_seconds)
        builder = builder.context(context)
        builder = builder.cache_policy(enabled=cache_policy_enabled, reload=cache_policy_reload)
        builder = builder.request_opts(**opts)
        builder = builder.override_kwargs(**override_kwargs)

        if backend is not None or format is not None:
            from xbbg.options import get_backend, get_format

            backend_value = backend if backend is not None else get_backend()
            format_value = format if format is not None else get_format()

            backend_str: str = backend_value.value if isinstance(backend_value, Backend) else str(backend_value)
            format_str: str = format_value.value if isinstance(format_value, Format) else str(format_value)

            builder = builder.with_output(cast(str, backend_str), cast(str, format_str))

        if start_datetime is not None and end_datetime is not None:
            builder = builder.datetime_range(start_datetime, end_datetime)

        return builder.build()

    def _run_request(req: DataRequest) -> Any:
        attempts = (max_retries or 0) + 1
        for attempt in range(attempts):
            try:
                result = pipeline.run(req)
            except Exception as exc:  # noqa: BLE001
                if raise_on_error:
                    raise
                logger.warning(
                    "Pipeline request failed for %s (attempt %d/%d): %s",
                    req.ticker,
                    attempt + 1,
                    attempts,
                    exc,
                )
                if attempt < attempts - 1:
                    continue
                return pd.DataFrame()

            if max_retries is not None and max_retries > 0 and is_empty(result):
                if attempt < attempts - 1:
                    logger.debug(
                        "Empty result for %s (attempt %d/%d), retrying",
                        req.ticker,
                        attempt + 1,
                        attempts,
                    )
                    continue

            return result

        return pd.DataFrame()

    if per_ticker and ticker_list:
        results = []
        for ticker in ticker_list:
            per_ticker_opts = dict(merged_request_opts)
            if tickers_key is not None:
                per_ticker_opts[tickers_key] = [ticker]
            request_obj = _build_request(ticker, per_ticker_opts)
            results.append(_run_request(request_obj))

        return concat_frames(results, backend) if concat else results

    request_obj = _build_request(primary_ticker, merged_request_opts)
    return _run_request(request_obj)


async def arequest(
    config: PipelineConfig | Callable[[], PipelineConfig],
    tickers: str | list[str] | None = None,
    fields: str | list[str] | None = None,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    dt: str | pd.Timestamp | None = None,
    asof: str | pd.Timestamp | None = None,
    start_datetime: str | pd.Timestamp | None = None,
    end_datetime: str | pd.Timestamp | None = None,
    session: str | None = None,
    typ: str | None = None,
    tickers_key: str | None = "tickers",
    fields_key: str | None = "flds",
    primary_ticker: str | None = None,
    request_opts: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
    infra: Mapping[str, Any] | None = None,
    backend: Backend | None = None,
    format: Format | None = None,
    cache_enabled: bool | None = None,
    reload: bool | None = None,
    per_ticker: bool = False,
    concat: bool = True,
    max_retries: int | None = None,
    raise_on_error: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Async unified Bloomberg request handler."""
    return await asyncio.to_thread(
        request,
        config,
        tickers,
        fields,
        start_date=start_date,
        end_date=end_date,
        dt=dt,
        asof=asof,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        session=session,
        typ=typ,
        tickers_key=tickers_key,
        fields_key=fields_key,
        primary_ticker=primary_ticker,
        request_opts=request_opts,
        overrides=overrides,
        infra=infra,
        backend=backend,
        format=format,
        cache_enabled=cache_enabled,
        reload=reload,
        per_ticker=per_ticker,
        concat=concat,
        max_retries=max_retries,
        raise_on_error=raise_on_error,
        **kwargs,
    )
