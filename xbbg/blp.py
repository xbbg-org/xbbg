"""High-level Bloomberg data API: reference, historical, intraday, and live.

This module maintains backward compatibility by re-exporting functions from
the new modular API structure in xbbg.api.
"""

from __future__ import annotations

import logging

from xbbg import __version__
from xbbg.api.helpers import adjust_ccy
from xbbg.api.historical import bdh, dividend, earning, turnover
from xbbg.api.intraday import bdib, bdtick
from xbbg.api.realtime import live, subscribe
from xbbg.api.reference import bdp, bds
from xbbg.api.screening import beqs, bql, bsrch
from xbbg.core.infra.conn import connect
from xbbg.markets import resolvers as _res

logger = logging.getLogger(__name__)

# Re-export resolver functions
active_futures = _res.active_futures
fut_ticker = _res.fut_ticker
cdx_ticker = _res.cdx_ticker
active_cdx = _res.active_cdx

__all__ = [
    '__version__',
    'connect',
    'bdp',
    'bds',
    'bdh',
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
    'active_futures',
    'fut_ticker',
    'cdx_ticker',
    'active_cdx',
]
