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
    bond_info: Bond reference metadata
    bond_risk: Bond duration, convexity, DV01 analytics
    bond_spreads: Bond spread analytics (OAS, Z-spread, I-spread, ASW)
    bond_cashflows: Bond cash flow schedule
    bond_key_rates: Bond key rate durations and risks
    bond_curve: Multi-bond relative value analytics
    PutCall: Enum for option chain put/call filter
    ChainPeriodicity: Enum for option chain expiry periodicity
    StrikeRef: Enum for option chain strike reference
    ExerciseType: Enum for option chain exercise type
    ExpiryMatch: Enum for option chain expiry matching
    option_info: Option contract metadata
    option_greeks: Option Greeks and implied volatility
    option_pricing: Option pricing, value decomposition, and activity
    option_chain: Option chain via CHAIN_TICKERS with overrides
    option_chain_bql: Option chain via BQL with rich filtering
    option_screen: Multi-option comparison analytics
"""

from __future__ import annotations

from xbbg.ext.bonds import (
    bond_cashflows,
    bond_curve,
    bond_info,
    bond_key_rates,
    bond_risk,
    bond_spreads,
)
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
from xbbg.ext.options import (
    ChainPeriodicity,
    ExerciseType,
    ExpiryMatch,
    PutCall,
    StrikeRef,
    option_chain,
    option_chain_bql,
    option_greeks,
    option_info,
    option_pricing,
    option_screen,
)
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
    # Fixed income -- YAS
    "yas",
    "YieldType",
    # Fixed income -- Bond analytics
    "bond_info",
    "bond_risk",
    "bond_spreads",
    "bond_cashflows",
    "bond_key_rates",
    "bond_curve",
    # Options -- Enums
    "PutCall",
    "ChainPeriodicity",
    "StrikeRef",
    "ExerciseType",
    "ExpiryMatch",
    # Options -- Analytics
    "option_info",
    "option_greeks",
    "option_pricing",
    "option_chain",
    "option_chain_bql",
    "option_screen",
]
