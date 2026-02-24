"""Extension functions for xbbg.

This module contains convenience wrappers built on top of the core API.
These are pure Python functions that compose core operations (bdp, bds, bdh, bql)
for common use cases.

Extension Categories:
    - historical: dividend(), earnings(), turnover(), etf_holdings()
    - futures: fut_ticker(), active_futures(), cdx_ticker(), active_cdx()
    - currency: convert_ccy()
    - fixed_income: yas(), preferreds(), corporate_bonds(), bqr()
    - bonds: bond_info(), bond_risk(), bond_spreads(), bond_cashflows(), bond_key_rates(), bond_curve()
    - options: option_info(), option_greeks(), option_pricing(), option_chain(), option_chain_bql(), option_screen()
    - cdx: cdx_info(), cdx_defaults(), cdx_pricing(), cdx_risk(), cdx_basis(), cdx_default_prob(), cdx_cashflows(), cdx_curve()

Async versions (primary implementations):
    - historical: adividend(), aearnings(), aturnover(), aetf_holdings()
    - futures: afut_ticker(), aactive_futures(), acdx_ticker(), aactive_cdx()
    - currency: aconvert_ccy()
    - fixed_income: ayas(), apreferreds(), acorporate_bonds(), abqr()
    - bonds: abond_info(), abond_risk(), abond_spreads(), abond_cashflows(), abond_key_rates(), abond_curve()
    - options: aoption_info(), aoption_greeks(), aoption_pricing(), aoption_chain(), aoption_chain_bql(), aoption_screen()
    - cdx: acdx_info(), acdx_defaults(), acdx_pricing(), acdx_risk(), acdx_basis(), acdx_default_prob(), acdx_cashflows(), acdx_curve()

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

    # Bond analytics
    df = ext.bond_info("T 4.5 05/15/38 Govt")
    df = ext.bond_risk("T 4.5 05/15/38 Govt")
    df = ext.bond_spreads("T 4.5 05/15/38 Govt")

    # Options analytics
    df = ext.option_info("AAPL US 01/17/25 C200 Equity")
    df = ext.option_greeks("AAPL US 01/17/25 C200 Equity")
    chain = ext.option_chain("AAPL US Equity")

    # CDX analytics
    df = ext.cdx_info("CDX IG CDSI GEN 5Y Corp")
    df = ext.cdx_pricing("CDX IG CDSI GEN 5Y Corp")

    # Async example
    import asyncio


    async def main():
        df = await ext.adividend("AAPL US Equity")
        print(df)


    asyncio.run(main())
"""

from __future__ import annotations

# Sync functions
# Async functions
from xbbg.ext.bonds import (
    abond_cashflows,
    abond_curve,
    abond_info,
    abond_key_rates,
    abond_risk,
    abond_spreads,
    bond_cashflows,
    bond_curve,
    bond_info,
    bond_key_rates,
    bond_risk,
    bond_spreads,
)
from xbbg.ext.cdx import (
    acdx_basis,
    acdx_cashflows,
    acdx_curve,
    acdx_default_prob,
    acdx_defaults,
    acdx_info,
    acdx_pricing,
    acdx_risk,
    cdx_basis,
    cdx_cashflows,
    cdx_curve,
    cdx_default_prob,
    cdx_defaults,
    cdx_info,
    cdx_pricing,
    cdx_risk,
)
from xbbg.ext.currency import aconvert_ccy, convert_ccy
from xbbg.ext.fixed_income import (
    YieldType,
    abqr,
    acorporate_bonds,
    apreferreds,
    ayas,
    bqr,
    corporate_bonds,
    preferreds,
    yas,
)
from xbbg.ext.futures import (
    aactive_cdx,
    aactive_futures,
    acdx_ticker,
    active_cdx,
    active_futures,
    afut_ticker,
    cdx_ticker,
    fut_ticker,
)
from xbbg.ext.historical import (
    adividend,
    aearnings,
    aetf_holdings,
    aturnover,
    dividend,
    earnings,
    etf_holdings,
    turnover,
)
from xbbg.ext.options import (
    ChainPeriodicity,
    ExerciseType,
    ExpiryMatch,
    PutCall,
    StrikeRef,
    aoption_chain,
    aoption_chain_bql,
    aoption_greeks,
    aoption_info,
    aoption_pricing,
    aoption_screen,
    option_chain,
    option_chain_bql,
    option_greeks,
    option_info,
    option_pricing,
    option_screen,
)

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
    # Bond analytics (sync)
    "bond_info",
    "bond_risk",
    "bond_spreads",
    "bond_cashflows",
    "bond_key_rates",
    "bond_curve",
    # Bond analytics (async)
    "abond_info",
    "abond_risk",
    "abond_spreads",
    "abond_cashflows",
    "abond_key_rates",
    "abond_curve",
    # Options analytics enums
    "PutCall",
    "ChainPeriodicity",
    "StrikeRef",
    "ExerciseType",
    "ExpiryMatch",
    # Options analytics (sync)
    "option_info",
    "option_greeks",
    "option_pricing",
    "option_chain",
    "option_chain_bql",
    "option_screen",
    # Options analytics (async)
    "aoption_info",
    "aoption_greeks",
    "aoption_pricing",
    "aoption_chain",
    "aoption_chain_bql",
    "aoption_screen",
    # CDX analytics (sync)
    "cdx_info",
    "cdx_defaults",
    "cdx_pricing",
    "cdx_risk",
    "cdx_basis",
    "cdx_default_prob",
    "cdx_cashflows",
    "cdx_curve",
    # CDX analytics (async)
    "acdx_info",
    "acdx_defaults",
    "acdx_pricing",
    "acdx_risk",
    "acdx_basis",
    "acdx_default_prob",
    "acdx_cashflows",
    "acdx_curve",
]
