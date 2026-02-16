"""High-level Bloomberg data API: reference, historical, intraday, and live.

This module maintains backward compatibility by re-exporting functions from
the new modular API structure in xbbg.api.

DEPRECATION NOTICE: Many functions in this module are deprecated and will be
removed or renamed in v1.0. See the FutureWarning messages for migration guidance.
"""

from __future__ import annotations

import logging

from xbbg import __version__
from xbbg.api.fixed_income import yas as _yas

# Import implementations with underscore prefix for wrapping
from xbbg.api.helpers import adjust_ccy as _adjust_ccy
from xbbg.api.historical import abdh, bdh, dividend as _dividend, earning as _earning, turnover as _turnover
from xbbg.api.intraday import abdib, abdtick, bdib, bdtick, exchange_tz
from xbbg.api.realtime import live as _live, stream, subscribe as _subscribe
from xbbg.api.reference import (
    abdp,
    abds,
    # v1.0 names (no deprecation)
    abfld,
    ablkp,
    afieldInfo,
    afieldSearch,
    alookupSecurity,
    bdp,
    bds,
    bfld,
    blkp,
    bport,
    # legacy names (for deprecation wrappers)
    fieldInfo as _fieldInfo,
    fieldSearch as _fieldSearch,
    getBlpapiVersion as _getBlpapiVersion,
    getPortfolio as _getPortfolio,
    lookupSecurity as _lookupSecurity,
)
from xbbg.api.screening import (
    abeqs,
    abql,
    abqr,
    absrch,
    beqs,
    bql,
    bqr,
    bsrch,
    corporate_bonds as _corporate_bonds,
    etf_holdings as _etf_holdings,
    preferreds as _preferreds,
)
from xbbg.api.technical import abta, bta, bta_studies as _bta_studies, refresh_studies as _refresh_studies, ta_studies
from xbbg.core.infra.conn import connect as _connect, disconnect as _disconnect
from xbbg.deprecation import deprecated_alias, get_warn_func
from xbbg.markets import resolvers as _res

logger = logging.getLogger(__name__)


# =============================================================================
# Deprecated function wrappers - REMOVED in v1.0
# =============================================================================

_DEPRECATED_EXPORTS = {
    # Removed in v1.0
    "connect": _connect,
    "disconnect": _disconnect,
    "getBlpapiVersion": _getBlpapiVersion,
    "lookupSecurity": _lookupSecurity,
    # Renamed in v1.0
    "fieldInfo": _fieldInfo,
    "fieldSearch": _fieldSearch,
    "bta_studies": _bta_studies,
    "refresh_studies": _refresh_studies,
    "getPortfolio": _getPortfolio,
    # Moved to ext in v1.0
    "dividend": _dividend,
    "earning": _earning,
    "turnover": _turnover,
    "adjust_ccy": _adjust_ccy,
    "etf_holdings": _etf_holdings,
    "preferreds": _preferreds,
    "corporate_bonds": _corporate_bonds,
    "yas": _yas,
    "fut_ticker": _res.fut_ticker,
    "active_futures": _res.active_futures,
    "cdx_ticker": _res.cdx_ticker,
    "active_cdx": _res.active_cdx,
    # Signature changed in v1.0
    "live": _live,
    "subscribe": _subscribe,
}

for _old_name, _impl in _DEPRECATED_EXPORTS.items():
    globals()[_old_name] = deprecated_alias(_old_name, _impl, get_warn_func(_old_name))


# =============================================================================
# Non-deprecated exports (stable API)
# =============================================================================

# These are re-exported directly without deprecation warnings:
# - bdp, bds, abdp, abds (reference data)
# - bdh, abdh (historical data)
# - bdib, bdtick (intraday data)
# - beqs, bsrch, bql (screening)
# - bta (technical analysis)
# - stream (real-time - new API)


__all__ = [
    "__version__",
    # Deprecated - removed in v1.0
    "connect",
    "disconnect",
    "getBlpapiVersion",
    "lookupSecurity",
    # Deprecated - renamed in v1.0
    "fieldInfo",
    "fieldSearch",
    "bta_studies",
    "refresh_studies",
    "getPortfolio",
    # Deprecated - moved to ext in v1.0
    "dividend",
    "earning",
    "turnover",
    "adjust_ccy",
    "etf_holdings",
    "preferreds",
    "corporate_bonds",
    "yas",
    "fut_ticker",
    "active_futures",
    "cdx_ticker",
    "active_cdx",
    # Deprecated - signature changed in v1.0
    "live",
    "subscribe",
    # Stable API (no deprecation)
    "bdp",
    "bds",
    "abdp",
    "abds",
    "bdh",
    "abdh",
    "bdib",
    "abdib",
    "bdtick",
    "abdtick",
    "exchange_tz",
    "beqs",
    "abeqs",
    "bsrch",
    "absrch",
    "bql",
    "abql",
    "bqr",
    "abqr",
    "bta",
    "abta",
    "stream",
    # v1.0 names (new, no deprecation)
    "ta_studies",
    "bfld",
    "abfld",
    "blkp",
    "ablkp",
    "bport",
    # async variants
    "afieldInfo",
    "afieldSearch",
    "alookupSecurity",
]
