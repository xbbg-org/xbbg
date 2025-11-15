"""Bloomberg screening and query API (BEQS/BSRCH/BQL).

Provides functions for equity screening, search queries, and Bloomberg Query Language.
"""

from __future__ import annotations

import logging

import pandas as pd

try:
    import blpapi  # type: ignore[reportMissingImports]
except (ImportError, AttributeError):
    import pytest  # type: ignore[reportMissingImports]
    blpapi = pytest.importorskip('blpapi')

from xbbg.utils import pipeline
from xbbg.core import conn, process, utils

logger = logging.getLogger(__name__)

__all__ = ['beqs', 'bsrch', 'bql']


def beqs(
    screen: str,
    asof: str | pd.Timestamp | None = None,
    typ: str = 'PRIVATE',
    group: str = 'General',
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg equity screening.

    Args:
        screen: screen name
        asof: as of date
        typ: GLOBAL/B (Bloomberg) or PRIVATE/C (Custom, default)
        group: group name if screen is organized into groups
        timeout: Timeout in milliseconds for waiting between events (default: 2000ms).
            Increase for complex screens that may have longer gaps between events.
        max_timeouts: Maximum number of timeout events allowed before giving up
            (default: 50). Increase for screens that take longer to complete.
        **kwargs: Additional request overrides for BeqsRequest.

    Returns:
        pd.DataFrame.
    """
    request = process.create_request(
        service='//blp/refdata',
        request='BeqsRequest',
        settings=[
            ('screenName', screen),
            ('screenType', 'GLOBAL' if typ[0].upper() in ['G', 'B'] else 'PRIVATE'),
            ('Group', group),
        ],
        ovrds=[('PiTDate', utils.fmt_dt(asof, '%Y%m%d'))] if asof else [],
        **kwargs,
    )

    logger.debug('Sending Bloomberg Equity Screening (BEQS) request for screen: %s, type: %s, group: %s', screen, typ, group)
    handle = conn.send_request(request=request, service='//blp/refdata', **kwargs)
    # Use longer timeout and more allowed timeouts for BEQS requests to ensure complete response
    # BEQS requests can take longer, especially for complex screens, and may have longer gaps between events
    beqs_timeout = kwargs.pop('timeout', 2000)  # 2 seconds default for BEQS (vs 500ms default)
    beqs_max_timeouts = kwargs.pop('max_timeouts', 50)  # Allow more timeouts for BEQS (vs 20 default)
    res = pd.DataFrame(process.rec_events(
        func=process.process_ref,
        event_queue=handle["event_queue"],
        timeout=beqs_timeout,
        max_timeouts=beqs_max_timeouts,
        **kwargs
    ))
    if res.empty:
        if kwargs.get('trial', 0): return pd.DataFrame()
        return beqs(screen=screen, asof=asof, typ=typ, group=group, trial=1, **kwargs)

    if kwargs.get('raw', False): return res
    cols = res.field.unique()
    return (
        res
        .set_index(['ticker', 'field'])
        .unstack(level=1)
        .rename_axis(index=None, columns=[None, None])
        .droplevel(axis=1, level=0)
        .loc[:, cols]
        .pipe(pipeline.standard_cols)
    )


def bsrch(domain: str, overrides: dict | None = None, **kwargs) -> pd.DataFrame:
    """Bloomberg SRCH (Search) queries - equivalent to Excel =@BSRCH function.

    Executes Bloomberg search queries using the Excel service (exrsvc).
    Supports user-defined SRCH screens, commodity screens, and Bloomberg example screens.

    Args:
        domain: Domain string in format <domain>:<search_name>.
            Examples: "FI:YOURSRCH", "comdty:weather", "FI:SRCHEX.@CLOSUB"
        overrides: Optional dict of override name-value pairs for search parameters.
            For weather data: {"provider": "wsi", "location": "US_IL", "model": "ACTUALS",
            "frequency": "DAILY", "target_start_date": "2021-01-01",
            "target_end_date": "2024-12-31", "location_time": "false",
            "fields": "WIND_SPEED|TEMPERATURE|..."}
        timeout: Timeout in milliseconds for waiting between events (default: 2000ms).
        max_timeouts: Maximum number of timeout events allowed (default: 50).
        **kwargs: Additional options forwarded to session and logging.

    Returns:
        pd.DataFrame: Search results with columns as returned by the search.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Fixed income search
        >>> df = blp.bsrch("FI:SRCHEX.@CLOSUB")  # doctest: +SKIP
        >>> # Weather data with parameters
        >>> weather_df = blp.bsrch(  # doctest: +SKIP
        ...     "comdty:weather",
        ...     overrides={
        ...         "provider": "wsi",
        ...         "location": "US_IL",
        ...         "model": "ACTUALS",
        ...         "frequency": "DAILY",
        ...         "target_start_date": "2021-01-01",
        ...         "target_end_date": "2024-12-31",
        ...         "fields": "WIND_SPEED|TEMPERATURE"
        ...     }
        ... )  # doctest: +SKIP
    """
    # Create request using exrsvc service
    exr_service = conn.bbg_service(service='//blp/exrsvc', **kwargs)
    request = exr_service.createRequest('ExcelGetGridRequest')

    # Set Domain element
    request.getElement(blpapi.Name('Domain')).setValue(domain)

    # Add overrides if provided
    if overrides:
        overrides_elem = request.getElement(blpapi.Name('Overrides'))
        for name, value in overrides.items():
            override_item = overrides_elem.appendElement()
            override_item.setElement(blpapi.Name('name'), name)
            override_item.setElement(blpapi.Name('value'), str(value))

    if logger.isEnabledFor(logging.DEBUG):
        override_info = f' with {len(overrides)} override(s)' if overrides else ''
        logger.debug('Sending Bloomberg SRCH request for domain: %s%s', domain, override_info)

    handle = conn.send_request(request=request, service='//blp/exrsvc', **kwargs)

    # Use longer timeout for BSRCH requests (similar to BEQS)
    bsrch_timeout = kwargs.pop('timeout', 2000)
    bsrch_max_timeouts = kwargs.pop('max_timeouts', 50)

    rows = list(process.rec_events(
        func=process.process_bsrch,
        event_queue=handle["event_queue"],
        timeout=bsrch_timeout,
        max_timeouts=bsrch_max_timeouts,
        **kwargs
    ))

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def bql(query: str, params: dict | None = None, overrides: list[tuple[str, object]] | None = None, **kwargs) -> pd.DataFrame:
    r"""Execute a BQL (Bloomberg Query Language) request.

    Args:
        query: BQL query string. Must be a complete BQL expression.
            **IMPORTANT:** The ``for`` clause must be OUTSIDE the ``get()`` function,
            not inside. Correct: ``get(px_last) for('AAPL US Equity')``.
            Incorrect: ``get(px_last for('AAPL US Equity'))``.
        params: Optional request options for BQL (mapped directly to elements).
            Note: The ``mode`` parameter is not currently supported by the Bloomberg
            BQL API. If you need cached/live mode, check Bloomberg documentation
            for the correct syntax or use query-level options.
        overrides: Optional list of (field, value) overrides for the BQL request.
        **kwargs: Session and logging options.

    Returns:
        pd.DataFrame: Parsed tabular results when available; otherwise a flattened view.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Simple price query - NOTE: 'for' is OUTSIDE get()
        >>> df = blp.bql("get(px_last) for('AAPL US Equity')")  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Multiple fields for multiple securities
        >>> df = blp.bql("get(px_last, volume) for(['AAPL US Equity', 'MSFT US Equity'])")  # doctest: +SKIP

        Options queries with filters and aggregations:

        >>> # Options query: Get open interest for filtered options
        >>> # IMPORTANT: 'for' clause is OUTSIDE get(), filter() is inside for()
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(open_int) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )

        >>> # Options query: Sum of open interest for filtered options
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(sum(group(open_int))) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )

        >>> # Get individual option contracts with multiple fields
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(id, open_int, strike_px) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )

        >>> # Options query: Group by strike price and sum open interest
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(sum(group(open_int, by=strike_px))) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )

        >>> # Options query: Filter by multiple criteria
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(open_int, strike_px) for(filter(options('SPX Index'), expire_dt=='2025-11-21', call_put=='C'))"
        ... )

        >>> # Alternative date format (integer YYYYMMDD)
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(open_int) for(filter(options('SPX Index'), expire_dt==20251121))"
        ... )

        Option chain metadata queries:

        >>> # Get available option expiries for an underlying
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(expire_dt) for(options('SPX Index'))"
        ... )

        >>> # Get option tickers/IDs for an underlying
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(id) for(options('SPX Index'))"
        ... )

        >>> # Get option chain metadata (expiry, strike, put/call) for specific expiry
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(id, expire_dt, strike_px, PUT_CALL) for(filter(options('SPX Index'), expire_dt=='2025-12-19'))"
        ... )

        >>> # Get all options for a specific expiry date
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(id, expire_dt, strike_px) for(filter(options('SPX Index'), expire_dt=='2025-12-19'))"
        ... )

        Historical data queries:

        >>> # Historical data query with period
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(px_last) for('AAPL US Equity') with(Period('1M', '2024-01-01', '2024-01-31'))"
        ... )

        >>> # Daily historical data query
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(px_last) for('AAPL US Equity') with(Period('1D', '2024-01-01', '2024-01-31'))"
        ... )

        Common mistakes to avoid:

        >>> # INCORRECT: 'for' inside get() - will cause parse error
        >>> # df = blp.bql("get(px_last for('AAPL US Equity'))")  # doctest: +SKIP

        >>> # INCORRECT: Missing get() wrapper
        >>> # This will return empty results without error
        >>> # df = blp.bql("filter(options('SPX Index'), expire_dt=='2025-11-21'), sum(group(open_int))")  # doctest: +SKIP

        >>> # INCORRECT: Using mode parameter (not supported)
        >>> # This will raise NotFoundException
        >>> # df = blp.bql("get(...)", params={"mode": "cached"})  # doctest: +SKIP

        >>> # CORRECT: 'for' is OUTSIDE get(), filter() is inside for()
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(sum(group(open_int))) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )
    """
    # Use BQL sendQuery with 'expression', mirroring common BQL request shape.
    settings = [('expression', query)]
    if params:
        settings.extend([(str(k), v) for k, v in params.items()])

    request = process.create_request(
        service='//blp/bqlsvc',
        request='sendQuery',
        settings=settings,
        ovrds=overrides or [],
        **kwargs,
    )

    logger.debug('Sending Bloomberg Query Language (BQL) request')
    handle = conn.send_request(request=request, service='//blp/bqlsvc', **kwargs)

    rows = list(process.rec_events(func=process.process_bql, event_queue=handle["event_queue"], **kwargs))
    return pd.DataFrame(rows) if rows else pd.DataFrame()

