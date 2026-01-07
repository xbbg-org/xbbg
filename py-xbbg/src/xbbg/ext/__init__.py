"""Extension functions for xbbg.

This module contains convenience wrappers built on top of the core API.
These are pure Python functions that compose core operations (bdp, bds, bdh, bql)
for common use cases.

Extension Categories:
    - historical: dividend(), earning(), turnover(), etf_holdings()
    - futures: fut_ticker(), active_futures(), cdx_ticker(), active_cdx()
    - currency: adjust_ccy()

Example::

    from xbbg import ext

    # Get dividend history
    df = ext.dividend("AAPL US Equity")

    # Get ETF holdings
    df = ext.etf_holdings("SPY US Equity")

    # Resolve futures ticker
    ticker = ext.fut_ticker("ES1 Index", "2024-01-15")

    # Convert currency
    df_usd = ext.adjust_ccy(df, ccy="USD")
"""

from __future__ import annotations

from xbbg.ext.currency import adjust_ccy
from xbbg.ext.futures import active_cdx, active_futures, cdx_ticker, fut_ticker
from xbbg.ext.historical import dividend, earning, etf_holdings, turnover

__all__ = [
    # Historical extensions
    "dividend",
    "earning",
    "turnover",
    "etf_holdings",
    # Futures extensions
    "fut_ticker",
    "active_futures",
    "cdx_ticker",
    "active_cdx",
    # Currency extensions
    "adjust_ccy",
]
