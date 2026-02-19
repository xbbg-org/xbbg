"""ETF holdings and related securities utilities.

This module provides functionality for ETF holdings, preferred stocks,
and corporate bonds lookups.
"""

from __future__ import annotations

import logging
from typing import Any

from xbbg.api.screening import bql
from xbbg.backend import Backend, Format
from xbbg.io.convert import is_empty, rename_columns

logger = logging.getLogger(__name__)

__all__ = ["etf_holdings", "preferreds", "corporate_bonds"]


def etf_holdings(
    etf_ticker: str,
    fields: list[str] | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> Any:
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
        DataFrame: ETF holdings data with columns for ISIN, weights, position IDs,
            and any additional requested fields.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Get holdings for an ETF
        >>> df = blp.etf_holdings("SPY US Equity")  # doctest: +SKIP
        >>> df is not None  # doctest: +SKIP
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
) -> Any:
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
        DataFrame: Preferred stock data with columns for ticker, name, and any
            additional requested fields. Returns empty DataFrame if no preferreds found.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Find preferred stocks for Bank of America
        >>> df = blp.preferreds("BAC US Equity")  # doctest: +SKIP
        >>> df is not None  # doctest: +SKIP
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
) -> Any:
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
        DataFrame: Corporate bond data with columns for ticker and any
            additional requested fields. Returns empty DataFrame if no bonds found.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Find USD corporate bonds for Apple
        >>> df = blp.corporate_bonds("AAPL")  # doctest: +SKIP
        >>> df is not None  # doctest: +SKIP
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
