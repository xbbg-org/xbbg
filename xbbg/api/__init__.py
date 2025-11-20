"""Bloomberg API modules organized by functionality.

This package contains the main Bloomberg API functions organized into logical modules:
- reference: Reference data (BDP/BDS)
- historical: Historical data (BDH, dividends, earnings, turnover)
- intraday: Intraday bars and tick data
- screening: Screening and query functions (BEQS, BSRCH, BQL)
- realtime: Real-time subscriptions and live data
- helpers: Shared utility functions (currency conversion, etc.)
"""

# Re-export all public functions for convenience
from xbbg.api.helpers import adjust_ccy
from xbbg.api.historical import abdh, bdh, dividend, earning, turnover
from xbbg.api.intraday import bdib, bdtick
from xbbg.api.realtime import live, subscribe
from xbbg.api.reference import (
    abdp,
    abds,
    bdp,
    bds,
    fieldInfo,
    fieldSearch,
    getBlpapiVersion,
    getPortfolio,
    lookupSecurity,
)
from xbbg.api.screening import beqs, bql, bsrch, etf_holdings

__all__ = [
    'bdp',
    'bds',
    'abdp',
    'abds',
    'bdh',
    'abdh',
    'bdib',
    'bdtick',
    'earning',
    'dividend',
    'beqs',
    'bsrch',
    'live',
    'subscribe',
    'adjust_ccy',
    'turnover',
    'bql',
    'etf_holdings',
    'fieldInfo',
    'fieldSearch',
    'lookupSecurity',
    'getPortfolio',
    'getBlpapiVersion',
]

