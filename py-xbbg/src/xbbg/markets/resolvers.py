"""Backwards-compatible market resolvers re-export."""

from __future__ import annotations

from xbbg._core import ext_get_futures_months
from xbbg.ext.futures import active_cdx, active_futures, cdx_ticker, fut_ticker

MONTH_CODE_MAP = ext_get_futures_months()

__all__ = [
    "MONTH_CODE_MAP",
    "fut_ticker",
    "active_futures",
    "cdx_ticker",
    "active_cdx",
]
