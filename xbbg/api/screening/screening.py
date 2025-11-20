"""Bloomberg screening and query API (BEQS/BSRCH/BQL).

Provides functions for equity screening, search queries, and Bloomberg Query Language.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

__all__ = ['beqs', 'bsrch', 'bql', 'etf_holdings']


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
        **kwargs: Additional request overrides for BeqsRequest and infrastructure options.

    Returns:
        pd.DataFrame.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, beqs_pipeline_config

    # Preserve retry mechanism
    trial = kwargs.get('trial', 0)

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request - use a dummy ticker since BEQS doesn't use tickers
    request = (
        RequestBuilder()
        .ticker('DUMMY')  # BEQS doesn't use ticker, but DataRequest requires one
        .date(asof if asof else 'today')
        .context(split.infra)
        .cache_policy(enabled=False)  # BEQS typically not cached
        .request_opts(screen=screen, asof=asof, typ=typ, group=group)
        .override_kwargs(**split.override_like)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=beqs_pipeline_config())
    result = pipeline.run(request)

    # Handle retry logic
    if result.empty and trial == 0:
        return beqs(screen=screen, asof=asof, typ=typ, group=group, trial=1, **kwargs)

    return result


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
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, bsrch_pipeline_config

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request
    request = (
        RequestBuilder()
        .ticker('DUMMY')  # BSRCH doesn't use ticker
        .date('today')
        .context(split.infra)
        .cache_policy(enabled=False)  # BSRCH typically not cached
        .request_opts(domain=domain, overrides=overrides)
        .override_kwargs(**split.override_like)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bsrch_pipeline_config())
    return pipeline.run(request)


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
        >>> # df = blp.bql("get(px_last for('AAPL US Equity'))")

        >>> # INCORRECT: Missing get() wrapper
        >>> # This will return empty results without error
        >>> # df = blp.bql("filter(options('SPX Index'), expire_dt=='2025-11-21'), sum(group(open_int))")

        >>> # INCORRECT: Using mode parameter (not supported)
        >>> # This will raise NotFoundException
        >>> # df = blp.bql("get(...)", params={"mode": "cached"})

        >>> # CORRECT: 'for' is OUTSIDE get(), filter() is inside for()
        >>> df = blp.bql(  # doctest: +SKIP
        ...     "get(sum(group(open_int))) for(filter(options('SPX Index'), expire_dt=='2025-11-21'))"
        ... )
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, bql_pipeline_config

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request
    request = (
        RequestBuilder()
        .ticker('DUMMY')  # BQL doesn't use ticker
        .date('today')
        .context(split.infra)
        .cache_policy(enabled=False)  # BQL typically not cached
        .request_opts(query=query, params=params, overrides=overrides)
        .override_kwargs(**split.override_like)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bql_pipeline_config())
    return pipeline.run(request)


def etf_holdings(
    etf_ticker: str,
    fields: list[str] | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Get ETF holdings using Bloomberg Query Language (BQL).

    Retrieves holdings information for an ETF including ISIN, weights, and position IDs.

    Args:
        etf_ticker: ETF ticker (e.g., 'SPY US Equity' or 'SPY'). If no suffix is provided,
            ' US Equity' will be appended automatically.
        fields: Optional list of additional fields to retrieve. Default fields are
            id_isin, weights, and id().position. If provided, these will be added to
            the default fields.
        **kwargs: Additional options passed to the underlying BQL query (e.g., params, overrides).

    Returns:
        pd.DataFrame: ETF holdings data with columns for ISIN, weights, position IDs,
            and any additional requested fields.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Get holdings for an ETF
        >>> df = blp.etf_holdings('SPY US Equity')  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Get holdings with additional fields
        >>> df = blp.etf_holdings(  # doctest: +SKIP
        ...     'SPY US Equity',
        ...     fields=['name', 'px_last']
        ... )

        >>> # Ticker without suffix (will append ' US Equity')
        >>> df = blp.etf_holdings('SPY')  # doctest: +SKIP
    """
    # Normalize ticker format - ensure it has proper suffix
    if ' ' not in etf_ticker:
        etf_ticker = f"{etf_ticker} US Equity"

    # Default fields
    default_fields = ['id_isin', 'weights', 'id().position']

    # Combine default fields with any additional fields
    all_fields = default_fields + [f for f in fields if f not in default_fields] if fields else default_fields

    # Build BQL query - format: holdings('FULL_TICKER')
    fields_str = ', '.join(all_fields)
    bql_query = f"get({fields_str}) for(holdings('{etf_ticker}'))"

    logger.debug(f"ETF holdings BQL query: {bql_query}")

    # Execute BQL query
    res = bql(query=bql_query, **kwargs)

    if res.empty:
        return res

    # Clean up column names
    # BQL returns 'id().position' which is awkward to access
    rename_map = {
        'id().position': 'position',
        'ID': 'holding'
    }
    return res.rename(columns=rename_map)


