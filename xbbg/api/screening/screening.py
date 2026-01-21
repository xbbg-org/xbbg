"""Bloomberg screening and query API (BEQS/BSRCH/BQL).

Provides functions for equity screening, search queries, and Bloomberg Query Language.
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg.backend import Backend, Format
from xbbg.io.convert import is_empty, rename_columns

logger = logging.getLogger(__name__)

__all__ = ["beqs", "bsrch", "bql", "bqr", "etf_holdings", "preferreds", "corporate_bonds"]


def beqs(
    screen: str,
    asof: str | pd.Timestamp | None = None,
    typ: str = "PRIVATE",
    group: str = "General",
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg equity screening.

    Args:
        screen: screen name
        asof: as of date
        typ: GLOBAL/B (Bloomberg) or PRIVATE/C (Custom, default)
        group: group name if screen is organized into groups
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
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
    trial = kwargs.get("trial", 0)

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request - use a dummy ticker since BEQS doesn't use tickers
    request = (
        RequestBuilder()
        .ticker("DUMMY")  # BEQS doesn't use ticker, but DataRequest requires one
        .date(asof if asof else "today")
        .context(split.infra)
        .cache_policy(enabled=False)  # BEQS typically not cached
        .request_opts(screen=screen, asof=asof, typ=typ, group=group)
        .override_kwargs(**split.override_like)
        .with_output(backend, format)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=beqs_pipeline_config())
    result = pipeline.run(request)

    # Handle retry logic
    if is_empty(result) and trial == 0:
        return beqs(screen=screen, asof=asof, typ=typ, group=group, backend=backend, format=format, trial=1, **kwargs)

    return result


def bsrch(
    domain: str,
    overrides: dict | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
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
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
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
        .ticker("DUMMY")  # BSRCH doesn't use ticker
        .date("today")
        .context(split.infra)
        .cache_policy(enabled=False)  # BSRCH typically not cached
        .request_opts(domain=domain, overrides=overrides)
        .override_kwargs(**split.override_like)
        .with_output(backend, format)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bsrch_pipeline_config())
    return pipeline.run(request)


def bql(
    query: str,
    params: dict | None = None,
    overrides: list[tuple[str, object]] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
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
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
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
        .ticker("DUMMY")  # BQL doesn't use ticker
        .date("today")
        .context(split.infra)
        .cache_policy(enabled=False)  # BQL typically not cached
        .request_opts(query=query, params=params, overrides=overrides)
        .override_kwargs(**split.override_like)
        .with_output(backend, format)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bql_pipeline_config())
    return pipeline.run(request)


def etf_holdings(
    etf_ticker: str,
    fields: list[str] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
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
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
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
    if " " not in etf_ticker:
        etf_ticker = f"{etf_ticker} US Equity"

    # Default fields
    default_fields = ["id_isin", "weights", "id().position"]

    # Combine default fields with any additional fields
    all_fields = default_fields + [f for f in fields if f not in default_fields] if fields else default_fields

    # Build BQL query - format: holdings('FULL_TICKER')
    fields_str = ", ".join(all_fields)
    bql_query = f"get({fields_str}) for(holdings('{etf_ticker}'))"

    logger.debug(f"ETF holdings BQL query: {bql_query}")

    # Execute BQL query
    res = bql(query=bql_query, backend=backend, format=format, **kwargs)

    if is_empty(res):
        return res

    # Clean up column names
    # BQL returns 'id().position' which is awkward to access
    col_map = {"id().position": "position", "ID": "holding"}
    return rename_columns(res, col_map)


def preferreds(
    equity_ticker: str,
    fields: list[str] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Find preferred stocks associated with an equity ticker using BQL.

    Searches Bloomberg's debt universe to find preferred stock securities tied
    to the specified equity ticker. Useful for discovering preferreds issued
    by a company when you only know the common stock ticker.

    Args:
        equity_ticker: Equity ticker (e.g., 'BAC US Equity' or 'BAC'). If no suffix
            is provided, ' US Equity' will be appended automatically.
        fields: Optional list of additional fields to retrieve. Default fields are
            id (ticker) and name. If provided, these will be added to the defaults.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Additional options passed to the underlying BQL query.

    Returns:
        pd.DataFrame: Preferred stock data with columns for ticker, name, and any
            additional requested fields. Returns empty DataFrame if no preferreds found.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Find preferred stocks for Bank of America
        >>> df = blp.preferreds('BAC US Equity')  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Find preferreds with additional fields
        >>> df = blp.preferreds(  # doctest: +SKIP
        ...     'BAC',
        ...     fields=['cpn', 'maturity']
        ... )

        >>> # Works with just the ticker symbol
        >>> df = blp.preferreds('WFC')  # doctest: +SKIP

    Notes:
        The underlying BQL query uses the debt() function with a filter for
        SRCH_ASSET_CLASS=='Preferreds' to find associated preferred securities.
    """
    # Normalize ticker format - ensure it has proper suffix
    if " " not in equity_ticker:
        equity_ticker = f"{equity_ticker} US Equity"

    # Default fields
    default_fields = ["id", "name"]

    # Combine default fields with any additional fields
    all_fields = default_fields + [f for f in fields if f not in default_fields] if fields else default_fields

    # Build BQL query
    # Pattern: get(id, name) for(filter(debt(['{ticker}']), SRCH_ASSET_CLASS=='Preferreds'))
    fields_str = ", ".join(all_fields)
    bql_query = (
        f"get({fields_str}) "
        f"for(filter(debt(['{equity_ticker}'], CONSOLIDATEDUPLICATES='N'), "
        f"SRCH_ASSET_CLASS=='Preferreds'))"
    )

    logger.debug(f"Preferreds BQL query: {bql_query}")

    # Execute BQL query
    res = bql(query=bql_query, backend=backend, format=format, **kwargs)

    if is_empty(res):
        return res

    # Clean up column names
    col_map = {"ID": "ticker"}
    return rename_columns(res, col_map)


def corporate_bonds(
    ticker: str,
    ccy: str = "USD",
    fields: list[str] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Find active corporate bonds for a ticker using BQL.

    Searches Bloomberg's bond universe to find active corporate bonds matching
    the specified company ticker and currency. Useful for discovering outstanding
    debt securities for a company.

    Args:
        ticker: Company ticker symbol (e.g., 'AAPL', 'T', 'BAC'). This matches
            against the TICKER field in Bloomberg's bond universe.
        ccy: Currency filter (default: 'USD'). Filters bonds by their currency.
        fields: Optional list of additional fields to retrieve. Default field is id
            (the bond ticker). If provided, these will be added to the defaults.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Additional options passed to the underlying BQL query.

    Returns:
        pd.DataFrame: Corporate bond data with columns for ticker and any
            additional requested fields. Returns empty DataFrame if no bonds found.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Find USD corporate bonds for Apple
        >>> df = blp.corporate_bonds('AAPL')  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Find EUR bonds for AT&T with additional fields
        >>> df = blp.corporate_bonds(  # doctest: +SKIP
        ...     'T',
        ...     ccy='EUR',
        ...     fields=['name', 'cpn', 'maturity', 'amt_outstanding']
        ... )

        >>> # Find all USD bonds for Bank of America
        >>> df = blp.corporate_bonds('BAC', ccy='USD')  # doctest: +SKIP

    Notes:
        The underlying BQL query uses bondsuniv('active') with filters for
        SRCH_ASSET_CLASS=='Corporates', TICKER, and CRNCY to find matching bonds.
        Only active (non-matured) bonds are returned.
    """
    # Default fields
    default_fields = ["id"]

    # Combine default fields with any additional fields
    all_fields = default_fields + [f for f in fields if f not in default_fields] if fields else default_fields

    # Build BQL query
    # Pattern: get(id) for(filter(bondsuniv('active'), SRCH_ASSET_CLASS=='Corporates' AND TICKER=='{ticker}' AND CRNCY=='{ccy}'))
    fields_str = ", ".join(all_fields)
    bql_query = (
        f"get({fields_str}) "
        f"for(filter(bondsuniv('active', CONSOLIDATEDUPLICATES='N'), "
        f"SRCH_ASSET_CLASS=='Corporates' AND TICKER=='{ticker}' AND CRNCY=='{ccy}'))"
    )

    logger.debug(f"Corporate bonds BQL query: {bql_query}")

    # Execute BQL query
    res = bql(query=bql_query, backend=backend, format=format, **kwargs)

    if is_empty(res):
        return res

    # Clean up column names
    col_map = {"ID": "ticker"}
    return rename_columns(res, col_map)


def bqr(
    ticker: str,
    date_offset: str | None = None,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    event_types: list[str] | None = None,
    include_broker_codes: bool = True,
    include_condition_codes: bool = False,
    include_exchange_codes: bool = False,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg Quote Request - get dealer quotes with broker information.

    Emulates the Excel =BQR() function for retrieving quote data from Bloomberg.
    BQR returns a grid of quotes from different dealers/contributors with
    timestamps, prices, sizes, and broker codes.

    This function uses IntradayTickRequest internally with BID/ASK event types
    and broker codes enabled to replicate Excel BQR functionality.

    Args:
        ticker: Security identifier. Supports various formats:
            - Bloomberg ticker with pricing source: "AAPL 3.45 02/09/45@MSG1 Corp"
            - ISIN with pricing source: "/isin/US037833BA77@MSG1"
            - ISIN with Corp suffix: "US037833BA77@MSG1 Corp"
            - Plain ISIN: "/isin/US037833BA77" (returns all quotes, no broker codes)
        date_offset: Date offset from now (e.g., "-2d", "-1w", "-3h").
            Takes precedence over start_date/end_date if provided.
        start_date: Start date for quote range (if date_offset not provided).
        end_date: End date for quote range (defaults to now if not provided).
        event_types: List of event types to retrieve. Defaults to ["BID", "ASK"].
            Other options: ["TRADE"], ["BID"], ["ASK"].
        include_broker_codes: Include broker/dealer codes (default True for AllQuotes).
            Set to True to get dealer-level quote attribution (MSG1 sources).
        include_condition_codes: Include trade condition codes (default False).
        include_exchange_codes: Include exchange codes (default False).
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS).
            Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG).
            Defaults to global setting.
        **kwargs: Additional options passed to the Bloomberg session.

    Returns:
        pd.DataFrame: Quote data with columns:
            - ticker: Security identifier
            - time: Quote timestamp
            - event_type: BID, ASK, or TRADE
            - price: Quote price
            - size: Quote size
            - broker_buy: Broker code for bid (if available)
            - broker_sell: Broker code for ask (if available)

    Examples:
        Basic usage with date offset (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Get quotes from last 2 days
        >>> df = blp.bqr("AAPL 3.45 02/09/45@MSG1 Corp", date_offset="-2d")  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        Using ISIN with pricing source:

        >>> df = blp.bqr("/isin/US037833BA77@MSG1", date_offset="-2d")  # doctest: +SKIP

        Using explicit date range:

        >>> df = blp.bqr(  # doctest: +SKIP
        ...     "AAPL 3.45 02/09/45@MSG1 Corp",
        ...     start_date="2024-01-15",
        ...     end_date="2024-01-17"
        ... )

        Get only trade events:

        >>> df = blp.bqr(  # doctest: +SKIP
        ...     "AAPL 3.45 02/09/45@MSG1 Corp",
        ...     date_offset="-1d",
        ...     event_types=["TRADE"]
        ... )

    Notes:
        - MSG1 is a composite pricing source that aggregates dealer quotes
        - The @MSG1 suffix in the ticker enables dealer-level attribution
        - Without @MSG1, quotes come from the default pricing source
        - Broker codes (broker_buy, broker_sell) are only available with MSG1 source
        - For Excel compatibility, this emulates: =BQR("ticker", "-2d", "", "View=AllQuotes")
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, bqr_pipeline_config

    # Default event types
    if event_types is None:
        event_types = ["BID", "ASK"]

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request
    request = (
        RequestBuilder()
        .ticker(ticker)
        .date("today")  # Required by builder, but not used by BQR
        .context(split.infra)
        .cache_policy(enabled=False)  # BQR typically not cached
        .request_opts(
            ticker=ticker,
            date_offset=date_offset,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
            include_broker_codes=include_broker_codes,
            include_condition_codes=include_condition_codes,
            include_exchange_codes=include_exchange_codes,
        )
        .override_kwargs(**split.override_like)
        .with_output(backend, format)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bqr_pipeline_config())
    return pipeline.run(request)
