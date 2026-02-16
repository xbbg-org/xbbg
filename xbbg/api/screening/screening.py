"""Bloomberg screening and query API (BEQS/BSRCH/BQL).

Provides functions for equity screening, search queries, and Bloomberg Query Language.
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg.backend import Backend, Format
from xbbg.core.infra.conn import sync_api
from xbbg.io.convert import is_empty, rename_columns

logger = logging.getLogger(__name__)

__all__ = [
    "beqs",
    "abeqs",
    "bsrch",
    "absrch",
    "bql",
    "abql",
    "bqr",
    "abqr",
    "etf_holdings",
    "preferreds",
    "corporate_bonds",
]


async def abeqs(
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
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import beqs_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

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

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=beqs_pipeline_config())
    result = await pipeline.arun(request)

    # Handle retry logic
    if is_empty(result) and trial == 0:
        return await abeqs(
            screen=screen, asof=asof, typ=typ, group=group, backend=backend, format=format, trial=1, **kwargs
        )

    return result


beqs = sync_api(abeqs)


async def absrch(
    domain: str,
    overrides: dict[str, object] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg SRCH (Search) queries (source of truth).

    Truly non-blocking — uses async event polling via arequest().
    Use ``bsrch()`` for synchronous usage.

    Args:
        domain: Domain string in format <domain>:<search_name>.
            Examples: "FI:YOURSRCH", "comdty:weather", "FI:SRCHEX.@CLOSUB"
        overrides: Optional dict of override name-value pairs for search parameters.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Additional options forwarded to session and logging.

    Returns:
        pd.DataFrame: Search results with columns as returned by the search.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import bsrch_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

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

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=bsrch_pipeline_config())
    return await pipeline.arun(request)


bsrch = sync_api(absrch)


async def abql(
    query: str,
    params: dict[str, object] | None = None,
    overrides: list[tuple[str, object]] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    r"""Async BQL (Bloomberg Query Language) request (source of truth).

    Truly non-blocking — uses async event polling via arequest().
    Use ``bql()`` for synchronous usage.

    Args:
        query: BQL query string. Must be a complete BQL expression.
            **IMPORTANT:** The ``for`` clause must be OUTSIDE the ``get()`` function,
            not inside. Correct: ``get(px_last) for('AAPL US Equity')``.
            Incorrect: ``get(px_last for('AAPL US Equity'))``.
        params: Optional request options for BQL (mapped directly to elements).
        overrides: Optional list of (field, value) overrides for the BQL request.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Session and logging options.

    Returns:
        pd.DataFrame: Parsed tabular results when available; otherwise a flattened view.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import bql_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

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

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=bql_pipeline_config())
    return await pipeline.arun(request)


bql = sync_api(abql)


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
        >>> df = blp.etf_holdings("SPY US Equity")  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Get holdings with additional fields
        >>> df = blp.etf_holdings(  # doctest: +SKIP
        ...     "SPY US Equity", fields=["name", "px_last"]
        ... )

        >>> # Ticker without suffix (will append ' US Equity')
        >>> df = blp.etf_holdings("SPY")  # doctest: +SKIP
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

    logger.debug("ETF holdings BQL query: %s", bql_query)

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
        >>> df = blp.preferreds("BAC US Equity")  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Find preferreds with additional fields
        >>> df = blp.preferreds(  # doctest: +SKIP
        ...     "BAC", fields=["cpn", "maturity"]
        ... )

        >>> # Works with just the ticker symbol
        >>> df = blp.preferreds("WFC")  # doctest: +SKIP

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

    logger.debug("Preferreds BQL query: %s", bql_query)

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
        >>> df = blp.corporate_bonds("AAPL")  # doctest: +SKIP
        >>> isinstance(df, pd.DataFrame)  # doctest: +SKIP
        True

        >>> # Find EUR bonds for AT&T with additional fields
        >>> df = blp.corporate_bonds(  # doctest: +SKIP
        ...     "T", ccy="EUR", fields=["name", "cpn", "maturity", "amt_outstanding"]
        ... )

        >>> # Find all USD bonds for Bank of America
        >>> df = blp.corporate_bonds("BAC", ccy="USD")  # doctest: +SKIP

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

    logger.debug("Corporate bonds BQL query: %s", bql_query)

    # Execute BQL query
    res = bql(query=bql_query, backend=backend, format=format, **kwargs)

    if is_empty(res):
        return res

    # Clean up column names
    col_map = {"ID": "ticker"}
    return rename_columns(res, col_map)


async def abqr(
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
    """Async Bloomberg Quote Request (source of truth).

    Truly non-blocking — uses async event polling via arequest().
    Use ``bqr()`` for synchronous usage.

    Args:
        ticker: Security identifier.
        date_offset: Date offset from now (e.g., "-2d", "-1w", "-3h").
        start_date: Start date for quote range (if date_offset not provided).
        end_date: End date for quote range (defaults to now if not provided).
        event_types: List of event types to retrieve. Defaults to ["BID", "ASK"].
        include_broker_codes: Include broker/dealer codes (default True).
        include_condition_codes: Include trade condition codes (default False).
        include_exchange_codes: Include exchange codes (default False).
        backend: Output backend. Defaults to global setting.
        format: Output format. Defaults to global setting.
        **kwargs: Additional options passed to the Bloomberg session.

    Returns:
        pd.DataFrame: Quote data.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import bqr_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

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

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=bqr_pipeline_config())
    return await pipeline.arun(request)


bqr = sync_api(abqr)
