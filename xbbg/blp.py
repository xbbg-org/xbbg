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
from xbbg.api.intraday import bdib, bdtick
from xbbg.api.realtime import live as _live, stream, subscribe as _subscribe
from xbbg.api.reference import (
    abdp,
    abds,
    bdp,
    bds,
    fieldInfo as _fieldInfo,
    fieldSearch as _fieldSearch,
    getBlpapiVersion as _getBlpapiVersion,
    getPortfolio as _getPortfolio,
    lookupSecurity as _lookupSecurity,
)
from xbbg.api.screening import (
    beqs,
    bql,
    bqr,
    bsrch,
    corporate_bonds as _corporate_bonds,
    etf_holdings as _etf_holdings,
    preferreds as _preferreds,
)
from xbbg.api.technical import bta, bta_studies as _bta_studies, refresh_studies as _refresh_studies
from xbbg.core.infra.conn import connect as _connect, disconnect as _disconnect
from xbbg.deprecation import (
    warn_active_cdx,
    warn_active_futures,
    warn_adjust_ccy,
    warn_bta_studies,
    warn_cdx_ticker,
    warn_connect,
    warn_corporate_bonds,
    warn_disconnect,
    warn_dividend,
    warn_earning,
    warn_etf_holdings,
    warn_fieldInfo,
    warn_fieldSearch,
    warn_fut_ticker,
    warn_getBlpapiVersion,
    warn_getPortfolio,
    warn_live,
    warn_lookupSecurity,
    warn_preferreds,
    warn_refresh_studies,
    warn_subscribe,
    warn_turnover,
    warn_yas,
)
from xbbg.markets import resolvers as _res

logger = logging.getLogger(__name__)


# =============================================================================
# Deprecated function wrappers - REMOVED in v1.0
# =============================================================================


def connect(*args, **kwargs):
    """DEPRECATED: Connect to Bloomberg.

    In v1.0, the engine auto-initializes. Use xbbg.configure() for custom host/port.
    """
    warn_connect()
    return _connect(*args, **kwargs)


def disconnect(*args, **kwargs):
    """DEPRECATED: Disconnect from Bloomberg.

    In v1.0, the engine manages connections automatically. Remove this call.
    """
    warn_disconnect()
    return _disconnect(*args, **kwargs)


def getBlpapiVersion(*args, **kwargs):
    """DEPRECATED: Get Bloomberg API version.

    In v1.0, use xbbg.get_sdk_info() instead.
    """
    warn_getBlpapiVersion()
    return _getBlpapiVersion(*args, **kwargs)


def lookupSecurity(*args, **kwargs):
    """DEPRECATED: Lookup security by name.

    In v1.0, use xbbg.blkp() instead. Note: yellowkey format changed to 'YK_FILTER_*'.
    """
    warn_lookupSecurity()
    return _lookupSecurity(*args, **kwargs)


# =============================================================================
# Deprecated function wrappers - RENAMED in v1.0
# =============================================================================


def fieldInfo(*args, **kwargs):
    """DEPRECATED: Get field metadata.

    In v1.0, renamed to bfld().
    """
    warn_fieldInfo()
    return _fieldInfo(*args, **kwargs)


def fieldSearch(*args, **kwargs):
    """DEPRECATED: Search for fields.

    In v1.0, merged into bfld(). Use bfld(search_spec='keyword') for field search.
    """
    warn_fieldSearch()
    return _fieldSearch(*args, **kwargs)


def bta_studies(*args, **kwargs):
    """DEPRECATED: List technical analysis studies.

    In v1.0, renamed to ta_studies().
    """
    warn_bta_studies()
    return _bta_studies(*args, **kwargs)


def refresh_studies(*args, **kwargs):
    """DEPRECATED: Refresh technical analysis studies cache.

    In v1.0, this function is removed with no direct replacement.
    """
    warn_refresh_studies()
    return _refresh_studies(*args, **kwargs)


def getPortfolio(*args, **kwargs):
    """DEPRECATED: Get portfolio data.

    In v1.0, renamed to bport()/abport().
    """
    warn_getPortfolio()
    return _getPortfolio(*args, **kwargs)


# =============================================================================
# Deprecated function wrappers - MOVED to xbbg.ext in v1.0
# =============================================================================


def dividend(*args, **kwargs):
    """DEPRECATED: Get dividend history.

    In v1.0, moved to xbbg.ext.dividend().
    """
    warn_dividend()
    return _dividend(*args, **kwargs)


def earning(*args, **kwargs):
    """DEPRECATED: Get earnings data.

    In v1.0, moved to xbbg.ext.earning().
    """
    warn_earning()
    return _earning(*args, **kwargs)


def turnover(*args, **kwargs):
    """DEPRECATED: Get turnover data.

    In v1.0, moved to xbbg.ext.turnover().
    """
    warn_turnover()
    return _turnover(*args, **kwargs)


def adjust_ccy(*args, **kwargs):
    """DEPRECATED: Adjust currency.

    In v1.0, moved to xbbg.ext.adjust_ccy().
    """
    warn_adjust_ccy()
    return _adjust_ccy(*args, **kwargs)


def etf_holdings(*args, **kwargs):
    """DEPRECATED: Get ETF holdings.

    In v1.0, moved to xbbg.ext.etf_holdings().
    """
    warn_etf_holdings()
    return _etf_holdings(*args, **kwargs)


def preferreds(*args, **kwargs):
    """DEPRECATED: Find preferred stocks for an equity ticker.

    In v1.0, moved to xbbg.ext.preferreds().
    """
    warn_preferreds()
    return _preferreds(*args, **kwargs)


def corporate_bonds(*args, **kwargs):
    """DEPRECATED: Find active corporate bonds for a ticker.

    In v1.0, moved to xbbg.ext.corporate_bonds().
    """
    warn_corporate_bonds()
    return _corporate_bonds(*args, **kwargs)


def yas(*args, **kwargs):
    """DEPRECATED: Bloomberg Yield & Spread Analysis (YAS) data.

    In v1.0, moved to xbbg.ext.yas().
    """
    warn_yas()
    return _yas(*args, **kwargs)


# Resolver functions - moved to xbbg.ext


def fut_ticker(*args, **kwargs):
    """DEPRECATED: Resolve futures ticker.

    In v1.0, moved to xbbg.ext.fut_ticker().
    """
    warn_fut_ticker()
    return _res.fut_ticker(*args, **kwargs)


def active_futures(*args, **kwargs):
    """DEPRECATED: Get active futures contract.

    In v1.0, moved to xbbg.ext.active_futures().
    """
    warn_active_futures()
    return _res.active_futures(*args, **kwargs)


def cdx_ticker(*args, **kwargs):
    """DEPRECATED: Resolve CDX ticker.

    In v1.0, moved to xbbg.ext.cdx_ticker().
    """
    warn_cdx_ticker()
    return _res.cdx_ticker(*args, **kwargs)


def active_cdx(*args, **kwargs):
    """DEPRECATED: Get active CDX contract.

    In v1.0, moved to xbbg.ext.active_cdx().
    """
    warn_active_cdx()
    return _res.active_cdx(*args, **kwargs)


# =============================================================================
# Deprecated function wrappers - SIGNATURE CHANGED in v1.0
# =============================================================================


def live(*args, **kwargs):
    """DEPRECATED: Subscribe to live market data.

    In v1.0, replaced by asubscribe()/stream() which return Subscription object,
    not async generator. Yields DataFrames instead of dicts.
    """
    warn_live()
    return _live(*args, **kwargs)


def subscribe(*args, **kwargs):
    """DEPRECATED: Subscribe to real-time data.

    In v1.0, no longer a context manager. Returns Subscription object with
    dynamic add/remove support. Use stream() for simple iteration.
    """
    warn_subscribe()
    return _subscribe(*args, **kwargs)


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
    "bdtick",
    "beqs",
    "bsrch",
    "bql",
    "bqr",
    "bta",
    "stream",
]
