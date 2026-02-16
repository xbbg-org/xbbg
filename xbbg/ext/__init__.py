"""Extended utilities for xbbg.

This module provides helper functions that were previously part of the core API
but are now moved to this extension module for v1.0 migration.

All functions here are considered "extended" functionality and are not part
of the core Bloomberg API wrapper. They are provided as convenience utilities.

Functions:
    adjust_ccy: Currency conversion for DataFrames
    dividend: Dividend history retrieval
    earning: Earnings breakdown by geography/product
    turnover: Trading volume and turnover calculation
    etf_holdings: ETF holdings via BQL
    preferreds: Preferred stocks lookup via BQL
    corporate_bonds: Corporate bonds lookup via BQL
    fut_ticker: Futures contract ticker resolution
    active_futures: Active futures contract selection
    cdx_ticker: CDX index ticker resolution
    active_cdx: Active CDX contract selection
    yas: Yield & Spread Analysis calculator
    YieldType: Enum for yield calculation types
"""

from __future__ import annotations

from xbbg.ext.cdx import (
    active_cdx,
    cdx_basis,
    cdx_cashflows,
    cdx_curve,
    cdx_default_prob,
    cdx_defaults,
    cdx_info,
    cdx_pricing,
    cdx_risk,
    cdx_ticker,
)
from xbbg.ext.currency import adjust_ccy
from xbbg.ext.dividends import dividend
from xbbg.ext.earnings import earning
from xbbg.ext.futures import active_futures, fut_ticker
from xbbg.ext.holdings import corporate_bonds, etf_holdings, preferreds
from xbbg.ext.turnover import turnover
from xbbg.ext.yas import YieldType, yas

__all__ = [
    # Currency
    "adjust_ccy",
    # Historical helpers
    "dividend",
    "earning",
    "turnover",
    # Holdings/BQL helpers
    "etf_holdings",
    "preferreds",
    "corporate_bonds",
    # Futures resolution
    "fut_ticker",
    "active_futures",
    # CDX resolution
    "cdx_ticker",
    "active_cdx",
    # CDX analytics
    "cdx_info",
    "cdx_defaults",
    "cdx_pricing",
    "cdx_risk",
    "cdx_basis",
    "cdx_default_prob",
    "cdx_cashflows",
    "cdx_curve",
    # Fixed income
    "yas",
    "YieldType",
]
