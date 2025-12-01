"""Bloomberg intraday data API (BDIB/BDTICK).

Provides functions for intraday bar data and tick-by-tick data.
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg import const
from xbbg.core import process
from xbbg.core.infra import conn
from xbbg.core.process import DEFAULT_TZ
from xbbg.io import cache, files
from xbbg.markets import resolvers
from xbbg.utils import pipeline

logger = logging.getLogger(__name__)

__all__ = ['bdib', 'bdtick']


def _load_cached_bdib(
    ticker: str,
    dt,
    session: str,
    typ: str,
    ex_info,
    ctx=None,
    **kwargs,
) -> pd.DataFrame | None:
    """Load cached intraday bar data if available.

    Args:
        ticker: Ticker symbol.
        dt: Date.
        session: Session name.
        typ: Event type.
        ex_info: Exchange info.
        ctx: Bloomberg context (infrastructure kwargs only).
        **kwargs: Legacy kwargs support.

    Returns:
        Cached DataFrame if available, None otherwise.
    """
    ss_rng = process.time_range(dt=dt, ticker=ticker, session=session, tz=ex_info.tz, ctx=ctx, **kwargs)
    if ss_rng.start_time is None or ss_rng.end_time is None:
        raise ValueError(
            f'Unable to resolve trading session "{session}" for ticker {ticker} on date {dt}. '
            f'This should not happen - session validation should have caught this earlier.'
        )
    data_file = cache.bar_file(ticker=ticker, dt=dt, typ=typ)
    if ctx is None:
        cache_enabled = kwargs.get('cache', True)
        reload_flag = kwargs.get('reload', False)
    else:
        cache_enabled = ctx.cache
        reload_flag = ctx.reload
    if files.exists(data_file) and cache_enabled and (not reload_flag):
        res = (
            pd.read_parquet(data_file)
            .pipe(pipeline.add_ticker, ticker=ticker)
            .loc[ss_rng.start_time:ss_rng.end_time]
        )
        if not res.empty:
            logger.debug('Loading cached Bloomberg intraday data from: %s', data_file)
            return res
    return None


def _resolve_bdib_ticker(ticker: str, dt, ex_info) -> tuple[str, bool]:
    """Resolve futures ticker if needed.

    Returns:
        Tuple of (resolved_ticker, success_flag).
    """
    q_tckr = ticker
    if ex_info.get('is_fut', False):
        is_sprd = ex_info.get('has_sprd', False) and (len(ticker[:-1]) != ex_info['tickers'][0])
        if not is_sprd:
            q_tckr = resolvers.fut_ticker(gen_ticker=ticker, dt=dt, freq=ex_info['freq'])
            if q_tckr == '':
                logger.error('Unable to resolve futures ticker for generic ticker: %s', ticker)
                return '', False
    return q_tckr, True


def _get_default_exchange_info(ticker: str, dt=None, session='allday', **kwargs) -> pd.Series:
    """Get default exchange info for fixed income securities.

    Tries to use pandas-market-calendars (PMC) with appropriate bond market calendars
    (SIFMA_US, SIFMA_UK, SIFMA_JP, etc.) based on country code.
    Falls back to timezone-based defaults if PMC is not available.

    Returns:
        pd.Series with default timezone and session info.
    """
    # Map country codes to PMC bond market calendars
    country_to_pmc_calendar = {
        'US': 'SIFMA_US',
        'GB': 'SIFMA_UK',
        'UK': 'SIFMA_UK',
        'JP': 'SIFMA_JP',
    }

    # Try to infer country code from ticker
    country_code = None

    # Handle identifier-based tickers (/isin/, /cusip/, /sedol/)
    if ticker.startswith('/isin/'):
        # ISIN format: /isin/US912810FE39 -> extract US (first 2 chars after /isin/)
        identifier = ticker.replace('/isin/', '')
        if len(identifier) >= 2:
            country_code = identifier[:2].upper()
    elif ticker.startswith('/cusip/') or ticker.startswith('/sedol/'):
        # CUSIP/SEDOL: Cannot reliably determine country code from identifier alone
        # User needs to provide calendar mapping or use ISIN format instead
        country_code = None
    else:
        # Regular ticker format: US912810FE39 Govt -> extract US
        # Note: CUSIP/SEDOL followed by asset type (e.g., "12345678 Govt") won't match here
        # as they don't start with country code
        t_info = ticker.split()
        if t_info and len(t_info[0]) == 2:
            country_code = t_info[0].upper()

    # Try to use PMC calendar if available and date is provided
    if dt and country_code and country_code in country_to_pmc_calendar:
        try:
            import pandas_market_calendars as mcal  # type: ignore
            cal_name = country_to_pmc_calendar[country_code]
            cal = mcal.get_calendar(cal_name)
            s_date = pd.Timestamp(dt).date()

            # Get schedule for the date
            # Note: SIFMA calendars may not support 'pre'/'post', so use regular schedule
            sched = cal.schedule(start_date=s_date, end_date=s_date)
            if sched.empty:
                # Date might be a holiday/weekend, fall through to defaults
                raise ValueError(f'No schedule available for {s_date} (likely holiday/weekend)')

            # Check for extended hours columns, fallback to regular market hours
            if 'pre' in sched.columns and 'post' in sched.columns and session == 'allday':
                pre_col = 'pre'
                post_col = 'post'
            else:
                pre_col = 'market_open'
                post_col = 'market_close'

            if not sched.empty:
                tz_name = cal.tz.zone if hasattr(cal.tz, 'zone') else str(cal.tz)
                start_ts = sched.iloc[0][pre_col]
                end_ts = sched.iloc[0][post_col]

                # Convert to timezone-aware timestamps and extract HH:MM
                start_time = start_ts.tz_convert(tz_name).strftime('%H:%M')
                end_time = end_ts.tz_convert(tz_name).strftime('%H:%M')

                logger.debug('Using PMC calendar %s for fixed income security %s', cal_name, ticker)
                return pd.Series({
                    'tz': tz_name,
                    'allday': [start_time, end_time],
                    'day': [start_time, end_time],
                })
        except Exception as e:
            # PMC not available or calendar lookup failed, fall through to defaults
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('PMC calendar lookup failed for %s: %s, using timezone defaults', ticker, e)

    # Fallback: timezone-based defaults
    # If country_code is None (e.g., CUSIP/SEDOL), we can't determine calendar
    if country_code is None:
        # Check if this is a CUSIP/SEDOL identifier format
        if ticker.startswith('/cusip/') or ticker.startswith('/sedol/'):
            raise ValueError(
                f'Cannot determine country code from {ticker}. '
                'CUSIP/SEDOL identifiers do not contain country information. '
                'Please use ISIN format (/isin/...) which includes country code, '
                'or provide a calendar mapping via pandas-market-calendars.'
            )
        # For other cases where country_code is None, use default
        default_tz = kwargs.get('tz', 'America/New_York')
    else:
        default_tz = kwargs.get('tz', 'America/New_York')  # Default to US Eastern
        tz_map = {
            'US': 'America/New_York',
            'GB': 'Europe/London',
            'UK': 'Europe/London',
            'JP': 'Asia/Tokyo',
            'DE': 'Europe/Berlin',
            'FR': 'Europe/Paris',
            'IT': 'Europe/Rome',
            'ES': 'Europe/Madrid',
            'NL': 'Europe/Amsterdam',
            'CH': 'Europe/Zurich',
            'AU': 'Australia/Sydney',
            'CA': 'America/Toronto',
        }
        default_tz = tz_map.get(country_code, default_tz)

    # Create default exchange info with allday session
    return pd.Series({
        'tz': default_tz,
        'allday': ['00:00', '23:59'],
        'day': ['00:00', '23:59'],
    })


def _build_bdib_request(ticker: str, dt, typ: str, ex_info, ctx=None, **kwargs):
    """Build Bloomberg intraday bar request.

    Args:
        ticker: Ticker symbol.
        dt: Date.
        typ: Event type.
        ex_info: Exchange info.
        ctx: Bloomberg context (infrastructure kwargs only).
        **kwargs: Legacy kwargs support.

    Returns:
        Tuple of (request, date_string).
    """
    time_rng = process.time_range(dt=dt, ticker=ticker, session='allday', tz=ex_info.tz, ctx=ctx, **kwargs)

    time_fmt = '%Y-%m-%dT%H:%M:%S'

    # If time_range returns None (no session found), create default time range
    if time_rng.start_time is None or time_rng.end_time is None:
        cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
        # Use allday session from ex_info or default to full day
        if 'allday' in ex_info.index:
            start_time = ex_info['allday'][0]
            end_time = ex_info['allday'][1]
        else:
            start_time = '00:00'
            end_time = '23:59'

        time_idx = (
            pd.DatetimeIndex([
                f'{cur_dt} {start_time}',
                f'{cur_dt} {end_time}'],
            )
            .tz_localize(ex_info.tz)
            .tz_convert('UTC')
        )
        start_dt = time_idx[0].strftime(time_fmt)
        end_dt = time_idx[1].strftime(time_fmt)
    else:
        # Convert timezone-naive times from exchange timezone to UTC
        # time_rng.start_time/end_time are in ex_info.tz but timezone-naive
        from xbbg.markets import convert_session_times_to_utc
        start_dt, end_dt = convert_session_times_to_utc(
            start_time=time_rng.start_time,
            end_time=time_rng.end_time,
            exchange_tz=ex_info.tz,
            time_fmt=time_fmt,
        )

    interval = kwargs.get('interval', 1)
    use_seconds = kwargs.get('intervalHasSeconds', False)

    settings = [
        ('security', ticker),
        ('eventType', typ),
        ('interval', interval),
        ('startDateTime', start_dt),
        ('endDateTime', end_dt),
    ]
    if use_seconds:
        settings.append(('intervalHasSeconds', True))

    request = process.create_request(
        service='//blp/refdata',
        request='IntradayBarRequest',
        settings=settings,
        **kwargs,
    )
    cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
    return request, cur_dt


def _process_bdib_response(
    res: pd.DataFrame,
    ticker: str,
    dt,
    session: str,
    typ: str,
    ex_info,
    ctx=None,
    **kwargs,
) -> pd.DataFrame:
    """Process and transform Bloomberg intraday bar response.

    Args:
        res: Raw response DataFrame.
        ticker: Ticker symbol.
        dt: Date.
        session: Session name.
        typ: Event type.
        ex_info: Exchange info.
        ctx: Bloomberg context (infrastructure kwargs only).
        **kwargs: Legacy kwargs support.

    Returns:
        Processed DataFrame filtered by session range.
    """
    if res.empty or ('time' not in res):
        return pd.DataFrame()

    ss_rng = process.time_range(dt=dt, ticker=ticker, session=session, tz=ex_info.tz, ctx=ctx, **kwargs)
    data = (
        res
        .set_index('time')
        .rename_axis(index=None)
        .rename(columns={'numEvents': 'num_trds'})
        .tz_localize('UTC')
        .tz_convert(ex_info.tz)
        .pipe(pipeline.add_ticker, ticker=ticker)
    )
    if ctx is None:
        cache_enabled = kwargs.get('cache', True)
        cache_kwargs = kwargs
    else:
        cache_enabled = ctx.cache
        cache_kwargs = ctx.to_kwargs()
    if cache_enabled:
        cache.save_intraday(data=data[ticker], ticker=ticker, dt=dt, typ=typ, **cache_kwargs)

    if ss_rng.start_time is None or ss_rng.end_time is None:
        raise ValueError(
            f'Unable to resolve trading session "{session}" for ticker {ticker} on date {dt}. '
            f'This should not happen - session validation should have caught this earlier.'
        )
    return data.loc[ss_rng.start_time:ss_rng.end_time]


def bdib(
    ticker: str,
    dt=None,
    session='allday',
    typ='TRADE',
    start_datetime=None,
    end_datetime=None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg intraday bar data.

    Args:
        ticker: ticker name
        dt: date to download (for single-day requests). Can be omitted if
            start_datetime and end_datetime are provided.
        session: Trading session name. Sessions are dynamically extracted from ``exch.yml``.
            Common sessions: ``allday``, ``day``, ``am``, ``pm``, ``pre``, ``post``, ``night``.
            Availability depends on exchange - check ``xbbg/markets/exch.yml`` for definitions.
            Raises ``ValueError`` if session is not defined for the ticker's exchange.
            Ignored when start_datetime and end_datetime are provided.
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        start_datetime: explicit start datetime for multi-day requests (e.g., '2025-01-01 09:30:00').
            When provided with end_datetime, bypasses session-based time resolution.
            Can be timezone-aware (will be converted to UTC) or timezone-naive (assumed UTC).
        end_datetime: explicit end datetime for multi-day requests (e.g., '2025-01-05 16:00:00').
            When provided with start_datetime, bypasses session-based time resolution.
            Can be timezone-aware (will be converted to UTC) or timezone-naive (assumed UTC).
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
        Get 10-second bars (requires Bloomberg):

        >>> # from xbbg import blp
        >>> # blp.bdib('AAPL US Equity', dt='2025-11-12', interval=10, intervalHasSeconds=True)

        Get 10-minute bars (default behavior):

        >>> # blp.bdib('AAPL US Equity', dt='2025-11-12', interval=10)

        Get multi-day intraday data:

        >>> # blp.bdib('AAPL US Equity', start_datetime='2025-01-01 09:30:00',
        >>> #         end_datetime='2025-01-05 16:00:00', interval=5)
    """
    # Validate parameters
    is_multi_day = start_datetime is not None and end_datetime is not None
    if not is_multi_day and dt is None:
        raise ValueError('Either dt or both start_datetime and end_datetime must be provided')

    # For multi-day requests without dt, use start_datetime's date as fallback
    if dt is None and is_multi_day:
        dt = pd.Timestamp(start_datetime).strftime('%Y-%m-%d')
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, intraday_pipeline_config
    from xbbg.core.utils import trials

    # Build request using RequestBuilder
    request = RequestBuilder.from_legacy_kwargs(
        ticker=ticker,
        dt=dt,
        session=session,
        typ=typ,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
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
            ticker.startswith('/isin/') or ticker.startswith('/cusip/') or ticker.startswith('/sedol/') or
            (len(t_info) > 0 and t_info[-1] in ['Govt', 'Corp', 'Mtge', 'Muni'] and
             t_info[0] and len(t_info[0]) >= 2 and t_info[0][:2].isalpha())
        )
        if not is_fixed_income:
            raise KeyError(f'Cannot find exchange info for {ticker}')

    # Check trial count (preserve legacy behavior) - skip for multi-day requests
    if not is_multi_day:
        trial_kw = {'ticker': ticker, 'dt': dt, 'typ': typ, 'func': 'bdib'}
        num_trials = trials.num_trials(**trial_kw)
        if num_trials >= 2:
            if request.context and request.context.batch:
                return pd.DataFrame()
            if logger.isEnabledFor(logging.INFO):
                cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
                logger.info(
                    'No data available after %d attempt(s) for %s / %s / %s',
                    num_trials,
                    ticker,
                    cur_dt,
                    typ,
                )
            return pd.DataFrame()
    else:
        num_trials = 0

    # Run pipeline
    pipeline = BloombergPipeline(config=intraday_pipeline_config())
    result = pipeline.run(request)

    # Update trial count if no data returned (only for single-day requests)
    if result.empty and not is_multi_day:
        trials.update_trials(cnt=num_trials + 1, **trial_kw)

    return result


def bdtick(
    ticker: str,
    dt: str | pd.Timestamp,
    session: str = 'allday',
    time_range: tuple[str, str] | list[str] | None = None,
    types: str | list[str] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg tick data.

    Args:
        ticker: Ticker name.
        dt: Date to download.
        session: Trading session name. Sessions are dynamically extracted from ``exch.yml``.
            Common sessions: ``allday``, ``day``, ``am``, ``pm``, ``pre``, ``post``, ``night``.
            Availability depends on exchange. Defaults to 'allday'.
            Raises ``ValueError`` if session is not defined for the ticker's exchange.
        time_range: Tuple of (start_time, end_time) in HH:MM format.
            If provided, `dt` and `session` are ignored. Times are converted to UTC.
        types: Single event type or list of event types. One or more of:
            TRADE, AT_TRADE, BID, ASK, MID_PRICE, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK.
            Defaults to ['TRADE'].
        **kwargs: Additional options forwarded to helpers (e.g., logging).

    Returns:
        pd.DataFrame: Tick data with time as index and ticker as column level.
    """
    if types is None: types = ['TRADE']
    exch = const.exch_info(ticker=ticker, **kwargs)
    if exch.empty: raise LookupError(f'Cannot find exchange info for {ticker}')

    if isinstance(time_range, (tuple, list)) and (len(time_range) == 2):
        cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
        time_rng = (
            pd.DatetimeIndex([
                f'{cur_dt} {time_range[0]}',
                f'{cur_dt} {time_range[1]}',
            ])
            .tz_localize(exch.tz)
            .tz_convert(DEFAULT_TZ)
            .tz_convert('UTC')
        )
        # Extract start_dt and end_dt from time_rng DatetimeIndex
        time_fmt = '%Y-%m-%dT%H:%M:%S'
        start_dt = time_rng[0].strftime(time_fmt)
        end_dt = time_rng[1].strftime(time_fmt)
    else:
        from xbbg.core.domain.context import split_kwargs
        split = split_kwargs(**kwargs)
        ctx = split.infra
        time_rng = process.time_range(dt=dt, ticker=ticker, session=session, ctx=ctx, **kwargs)
        if time_rng.start_time is None or time_rng.end_time is None:
            raise ValueError(f'Unable to resolve trading session for ticker {ticker} on date {dt}')
        # Convert timezone-naive times from exchange timezone to UTC
        # time_rng.start_time/end_time are in exch.tz but timezone-naive
        from xbbg.markets import convert_session_times_to_utc
        time_fmt = '%Y-%m-%dT%H:%M:%S'
        start_dt, end_dt = convert_session_times_to_utc(
            start_time=time_rng.start_time,
            end_time=time_rng.end_time,
            exchange_tz=exch.tz,
            time_fmt=time_fmt,
        )

    request = process.create_request(
        service='//blp/refdata',
        request='IntradayTickRequest',
        settings=[
            ('security', ticker),
            ('startDateTime', start_dt),
            ('endDateTime', end_dt),
            ('includeConditionCodes', True),
            ('includeExchangeCodes', True),
            ('includeNonPlottableEvents', True),
            ('includeBrokerCodes', True),
            ('includeRpsCodes', True),
            ('includeTradeTime', True),
            ('includeActionCodes', True),
            ('includeIndicatorCodes', True),
        ],
        append={'eventTypes': types},
        **kwargs,
    )

    logger.debug('Sending Bloomberg tick data request for ticker: %s, event types: %s', ticker, types)
    handle = conn.send_request(request=request, service='//blp/refdata', **kwargs)

    res = pd.DataFrame(process.rec_events(func=process.process_bar, typ='t', event_queue=handle["event_queue"], **kwargs))
    if kwargs.get('raw', False): return res
    if res.empty or ('time' not in res): return pd.DataFrame()

    return (
        res
        .set_index('time')
        .rename_axis(index=None)
        .tz_localize('UTC')
        .tz_convert(exch.tz)
        .pipe(pipeline.add_ticker, ticker=ticker)
        .rename(columns={
            'size': 'volume',
            'type': 'typ',
            'conditionCodes': 'cond',
            'exchangeCode': 'exch',
            'tradeTime': 'trd_time',
        })
    )

