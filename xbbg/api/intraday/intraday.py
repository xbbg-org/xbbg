"""Bloomberg intraday data API (BDIB/BDTICK).

Provides functions for intraday bar data and tick-by-tick data.
"""

# pyright: reportImportCycles=false

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from xbbg import const
from xbbg.backend import Backend, Format
from xbbg.core import process
from xbbg.core.infra import conn
from xbbg.core.process import DEFAULT_TZ
from xbbg.core.utils import utils
from xbbg.io.convert import is_empty

logger = logging.getLogger(__name__)

__all__ = ["bdib", "abdib", "bdtick", "abdtick", "exchange_tz"]


def exchange_tz(ticker: str, **kwargs) -> str:
    """Return the exchange timezone for a Bloomberg ticker.

    Looks up exchange metadata via the same resolution path used by
    ``bdib`` / ``bdtick`` so the result matches the timezone of the
    data those functions return.

    Args:
        ticker: Bloomberg ticker (e.g., ``'AAPL US Equity'``).
        **kwargs: Forwarded to the exchange-info resolver (e.g., ``ref``).

    Returns:
        IANA timezone string (e.g., ``'America/New_York'``).

    Raises:
        LookupError: If exchange metadata cannot be resolved for *ticker*.

    Examples:
        >>> exchange_tz("AAPL US Equity")  # doctest: +SKIP
        'America/New_York'
        >>> exchange_tz("7974 JT Equity")  # doctest: +SKIP
        'Asia/Tokyo'
    """
    exch = const.exch_info(ticker=ticker, **kwargs)
    if exch.empty or "tz" not in exch.index:
        raise LookupError(f"Cannot resolve exchange timezone for {ticker}")
    return exch.tz


def _get_default_exchange_info(ticker: str, dt=None, session="allday", **kwargs) -> pd.Series:
    """Get default exchange info for fixed income securities.

    Uses timezone-based defaults inferred from country code.

    Returns:
        pd.Series with default timezone and session info.
    """
    # Try to infer country code from ticker
    country_code = None

    # Handle identifier-based tickers (/isin/, /cusip/, /sedol/)
    if ticker.startswith("/isin/"):
        # ISIN format: /isin/US912810FE39 -> extract US (first 2 chars after /isin/)
        identifier = ticker.replace("/isin/", "")
        if len(identifier) >= 2:
            country_code = identifier[:2].upper()
    elif ticker.startswith("/cusip/") or ticker.startswith("/sedol/"):
        # CUSIP/SEDOL: Cannot reliably determine country code from identifier alone
        country_code = None
    else:
        # Regular ticker format: US912810FE39 Govt -> extract US
        t_info = ticker.split()
        if t_info and len(t_info[0]) == 2:
            country_code = t_info[0].upper()

    # Timezone-based defaults
    default_tz = kwargs.get("tz", "America/New_York")
    if country_code:
        tz_map = {
            "US": "America/New_York",
            "GB": "Europe/London",
            "UK": "Europe/London",
            "JP": "Asia/Tokyo",
            "DE": "Europe/Berlin",
            "FR": "Europe/Paris",
            "IT": "Europe/Rome",
            "ES": "Europe/Madrid",
            "NL": "Europe/Amsterdam",
            "CH": "Europe/Zurich",
            "AU": "Australia/Sydney",
            "CA": "America/Toronto",
        }
        default_tz = tz_map.get(country_code, default_tz)

    # Create default exchange info with allday session
    return pd.Series(
        {
            "tz": default_tz,
            "allday": ["00:00", "23:59"],
            "day": ["00:00", "23:59"],
        }
    )


async def abdib(
    ticker: str,
    dt=None,
    session="allday",
    typ="TRADE",
    start_datetime=None,
    end_datetime=None,
    tz: str | None = None,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg intraday bar data (source of truth).

    Truly non-blocking -- uses async event polling via arequest().
    Use ``bdib()`` for synchronous usage.

    Args:
        ticker: ticker name
        dt: date to download (for single-day requests). Can be omitted if
            start_datetime and end_datetime are provided.
        session: Trading session name. Sessions are dynamically resolved from Bloomberg.
            Common sessions: ``allday``, ``day``, ``am``, ``pm``, ``pre``, ``post``, ``night``.
            Availability depends on exchange.
            Raises ``ValueError`` if session is not defined for the ticker's exchange.
            Ignored when start_datetime and end_datetime are provided.
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        start_datetime: explicit start datetime for multi-day requests (e.g., '2025-01-01 09:30:00').
            When provided with end_datetime, bypasses session-based time resolution.
            Can be timezone-aware (will be converted to UTC) or timezone-naive (assumed UTC).
        end_datetime: explicit end datetime for multi-day requests (e.g., '2025-01-05 16:00:00').
            When provided with start_datetime, bypasses session-based time resolution.
            Can be timezone-aware (will be converted to UTC) or timezone-naive (assumed UTC).
        tz: Output timezone for timestamps. Controls which timezone the returned
            DataFrame's time index is expressed in.

            - ``None`` (default): exchange local timezone (e.g. ``'America/New_York'``
              for US equities, ``'Asia/Tokyo'`` for Japanese equities).  This matches
              the behaviour of ``bdtick()`` and xbbg v0.7.x ``bdib()``.
            - ``'UTC'``: keep timestamps in UTC (skip conversion).
            - Any IANA timezone string: convert to that timezone.
        backend: Backend for data processing (e.g., Backend.PANDAS, Backend.POLARS).
            If None, uses the default backend.
        format: Output format for the data (e.g., Format.LONG, Format.WIDE).
            If None, uses the default format.
        **kwargs:
            interval: bar interval in minutes (default: 1). For sub-minute intervals,
                set ``intervalHasSeconds=True`` and specify seconds (e.g., interval=10
                with intervalHasSeconds=True for 10-second bars).
            intervalHasSeconds: if True, interpret ``interval`` as seconds instead of
                minutes. Default is False (interval always in minutes).
            ref: reference ticker or exchange
                 used as supplement if exchange info is not defined for `ticker`
            batch: whether is batch process to download data
            log: level of logs

    Returns:
        pd.DataFrame

    Examples:
        >>> import asyncio
        >>> # Single request -- timestamps in exchange local timezone (default)
        >>> # df = await blp.abdib('AAPL US Equity', dt='2025-11-12', interval=10)
        >>>
        >>> # Timestamps in UTC
        >>> # df = await blp.abdib('AAPL US Equity', dt='2025-11-12', tz='UTC')
        >>>
        >>> # Concurrent requests (true async)
        >>> # results = await asyncio.gather(
        >>> #     blp.abdib('AAPL US Equity', dt='2025-11-12'),
        >>> #     blp.abdib('MSFT US Equity', dt='2025-11-12'),
        >>> # )
    """
    # Validate parameters
    is_multi_day = start_datetime is not None and end_datetime is not None
    if not is_multi_day and dt is None:
        raise ValueError("Either dt or both start_datetime and end_datetime must be provided")

    # For multi-day requests without dt, use start_datetime's date as fallback
    if dt is None and is_multi_day:
        assert start_datetime is not None  # guaranteed by is_multi_day check above
        dt = utils.fmt_dt(start_datetime, fmt="%Y-%m-%d")
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import intraday_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

    # Build request using RequestBuilder
    request = RequestBuilder.from_legacy_kwargs(
        ticker=ticker,
        dt=dt,
        session=session,
        typ=typ,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        tz=tz,
        backend=backend,
        output_format=format,
        **kwargs,
    )

    # Preserve legacy KeyError behavior: check if exchange info exists
    # (pipeline will handle resolution, but we want to raise KeyError early for non-fixed-income)
    from xbbg.core.domain.context import split_kwargs

    split = split_kwargs(**kwargs)
    ctx_kwargs = split.infra.to_kwargs()
    ex_info = const.exch_info(ticker=ticker, **ctx_kwargs)
    if ex_info.empty:
        # Check if this is a fixed income security
        t_info = ticker.split()
        is_fixed_income = (
            ticker.startswith("/isin/")
            or ticker.startswith("/cusip/")
            or ticker.startswith("/sedol/")
            or (
                len(t_info) > 0
                and t_info[-1] in ["Govt", "Corp", "Mtge", "Muni"]
                and t_info[0]
                and len(t_info[0]) >= 2
                and t_info[0][:2].isalpha()
            )
        )
        if not is_fixed_income:
            raise KeyError(f"Cannot find exchange info for {ticker}")

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=intraday_pipeline_config())
    return await pipeline.arun(request)


bdib = conn.sync_api(abdib)


async def abdtick(
    ticker: str,
    dt: str | pd.Timestamp,
    session: str = "allday",
    time_range: tuple[str, str] | list[str] | None = None,
    types: str | list[str] | None = None,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> Any:
    """Async Bloomberg tick data (source of truth).

    Truly non-blocking -- uses async event polling via arequest().
    Use ``bdtick()`` for synchronous usage.

    Args:
        ticker: Ticker name.
        dt: Date to download.
        session: Trading session name. Defaults to 'allday'.
        time_range: Tuple of (start_time, end_time) in HH:MM format.
        types: Event types. Defaults to ['TRADE'].
        backend: Backend for data processing.
        format: Output format.
        **kwargs: Additional options.

    Returns:
        pd.DataFrame: Tick data with time as index and ticker as column level.
    """
    if types is None:
        types = ["TRADE"]
    exch = const.exch_info(ticker=ticker, **kwargs)
    if exch.empty:
        raise LookupError(f"Cannot find exchange info for {ticker}")

    if isinstance(time_range, (tuple, list)) and (len(time_range) == 2):
        cur_dt = utils.fmt_dt(dt, fmt="%Y-%m-%d")
        time_rng = (
            pd.DatetimeIndex(
                [
                    f"{cur_dt} {time_range[0]}",
                    f"{cur_dt} {time_range[1]}",
                ]
            )
            .tz_localize(exch.tz)
            .tz_convert(DEFAULT_TZ)
            .tz_convert("UTC")
        )
        time_fmt = "%Y-%m-%dT%H:%M:%S"
        start_dt = time_rng[0].strftime(time_fmt)
        end_dt = time_rng[1].strftime(time_fmt)
    else:
        from xbbg.core.domain.context import split_kwargs

        split = split_kwargs(**kwargs)
        ctx = split.infra
        tz = exch.tz
        time_rng = process.time_range(dt=dt, ticker=ticker, session=session, tz=tz, ctx=ctx, **kwargs)
        if time_rng.start_time is None or time_rng.end_time is None:
            raise ValueError(f"Unable to resolve trading session for ticker {ticker} on date {dt}")
        from xbbg.markets import convert_session_times_to_utc

        time_fmt = "%Y-%m-%dT%H:%M:%S"
        start_dt, end_dt = convert_session_times_to_utc(
            start_time=time_rng.start_time,
            end_time=time_rng.end_time,
            exchange_tz=exch.tz,
            time_fmt=time_fmt,
        )

    blp_request = process.create_request(
        service="//blp/refdata",
        request="IntradayTickRequest",
        settings=[
            ("security", ticker),
            ("startDateTime", start_dt),
            ("endDateTime", end_dt),
            ("includeConditionCodes", True),
            ("includeExchangeCodes", True),
            ("includeNonPlottableEvents", True),
            ("includeBrokerCodes", True),
            ("includeRpsCodes", True),
            ("includeTradeTime", True),
            ("includeActionCodes", True),
            ("includeIndicatorCodes", True),
        ],
        append={"eventTypes": types},
        **kwargs,
    )

    logger.debug("Sending Bloomberg tick data request for ticker: %s, event types: %s", ticker, types)

    # Use arequest() -- the async foundation
    events = await conn.arequest(
        request=blp_request,
        process_func=process.process_bar,
        service="//blp/refdata",
        typ="t",
        **kwargs,
    )

    res = pd.DataFrame(events)
    if kwargs.get("raw", False):
        return res
    if is_empty(res) or ("time" not in res):
        from xbbg.backend import Backend as BackendEnum
        from xbbg.options import get_backend

        actual_backend = backend if backend is not None else get_backend()
        if isinstance(actual_backend, str):
            actual_backend = BackendEnum(actual_backend)

        if actual_backend == BackendEnum.POLARS:
            import polars as pl

            return pl.DataFrame()
        if actual_backend == BackendEnum.PYARROW:
            import pyarrow as pa

            return pa.table({})
        return pd.DataFrame()

    result = (
        res.set_index("time")
        .tz_localize("UTC")
        .tz_convert(exch.tz)
        .rename(
            columns={
                "size": "volume",
                "type": "typ",
                "conditionCodes": "cond",
                "exchangeCode": "exch",
                "tradeTime": "trd_time",
            }
        )
    )
    # Add ticker as a flat column (NOT MultiIndex) so to_output can find
    # the "ticker" and "time" columns and apply format transformations.
    result["ticker"] = ticker

    import pyarrow as pa

    from xbbg.backend import Backend as BackendEnum
    from xbbg.deprecation import warn_defaults_changing
    from xbbg.io.convert import to_output
    from xbbg.options import get_backend, get_format

    actual_backend = backend if backend is not None else get_backend()
    actual_format = format if format is not None else get_format()

    if isinstance(actual_backend, str):
        actual_backend = BackendEnum(actual_backend)
    if isinstance(actual_format, str):
        actual_format = Format(actual_format)

    if backend is None or format is None:
        warn_defaults_changing()

    result_reset = result.reset_index()
    for col in result_reset.columns:
        if result_reset[col].dtype == object:
            result_reset[col] = result_reset[col].astype(str)
    arrow_table = pa.Table.from_pandas(result_reset)

    return to_output(
        arrow_table,
        backend=actual_backend,
        format=actual_format,
        ticker_col="ticker",
        date_col="time",
        field_cols=None,
    )


bdtick = conn.sync_api(abdtick)
