"""Extension functions for xbbg.

This module contains convenience wrappers built on top of the core API.
These are pure Python functions that compose core operations (bdp, bds, bdh, bql)
for common use cases.

Extension Categories:
    - historical: dividend(), earnings(), turnover(), etf_holdings()
    - futures: fut_ticker(), active_futures(), cdx_ticker(), active_cdx()
    - currency: convert_ccy()
    - fixed_income: yas(), preferreds(), corporate_bonds(), bqr()

Async versions (primary implementations):
    - historical: adividend(), aearnings(), aturnover(), aetf_holdings()
    - futures: afut_ticker(), aactive_futures(), acdx_ticker(), aactive_cdx()
    - currency: aconvert_ccy()
    - fixed_income: ayas(), apreferreds(), acorporate_bonds(), abqr()

Example::

    from xbbg import ext

    # Get dividend history
    df = ext.dividend("AAPL US Equity")

    # Get ETF holdings
    df = ext.etf_holdings("SPY US Equity")

    # Resolve futures ticker
    ticker = ext.fut_ticker("ES1 Index", "2024-01-15")

    # Convert currency
    df_usd = ext.convert_ccy(df, ccy="USD")

    # Yield & spread analysis for bonds
    df = ext.yas("US912810TM69 Govt", "YAS_BOND_YLD")

    # Find preferred stocks
    df = ext.preferreds("BAC US Equity")

    # Find corporate bonds
    df = ext.corporate_bonds("AAPL")

    # Async example
    import asyncio


    async def main():
        df = await ext.adividend("AAPL US Equity")
        print(df)


    asyncio.run(main())
"""

from __future__ import annotations

# Sync functions
from xbbg.ext.currency import convert_ccy
from xbbg.ext.fixed_income import YieldType, bqr, corporate_bonds, preferreds, yas
from xbbg.ext.futures import active_cdx, active_futures, cdx_ticker, fut_ticker
from xbbg.ext.historical import dividend, earnings, etf_holdings, turnover

# Async functions
from xbbg.ext.currency import aconvert_ccy
from xbbg.ext.fixed_income import abqr, acorporate_bonds, apreferreds, ayas
from xbbg.ext.futures import aactive_cdx, aactive_futures, acdx_ticker, afut_ticker
from xbbg.ext.historical import adividend, aearnings, aetf_holdings, aturnover

__all__ = [
    # Historical extensions (sync)
    "dividend",
    "earnings",
    "turnover",
    "etf_holdings",
    # Historical extensions (async)
    "adividend",
    "aearnings",
    "aturnover",
    "aetf_holdings",
    # Futures extensions (sync)
    "fut_ticker",
    "active_futures",
    "cdx_ticker",
    "active_cdx",
    # Futures extensions (async)
    "afut_ticker",
    "aactive_futures",
    "acdx_ticker",
    "aactive_cdx",
    # Currency extensions (sync)
    "convert_ccy",
    # Currency extensions (async)
    "aconvert_ccy",
    # Fixed income extensions (sync)
    "yas",
    "YieldType",
    "preferreds",
    "corporate_bonds",
    "bqr",
    # Fixed income extensions (async)
    "ayas",
    "apreferreds",
    "acorporate_bonds",
    "abqr",
]
