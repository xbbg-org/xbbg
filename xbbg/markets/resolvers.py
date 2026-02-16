"""Resolvers for market-specific ticker transformations and helpers.

This module re-exports functions from xbbg.ext for backwards compatibility.
The actual implementations are now in xbbg.ext.futures and xbbg.ext.cdx.

DEPRECATION NOTICE: Import directly from xbbg.ext instead of this module.
"""

from __future__ import annotations

# Re-export from ext modules for backwards compatibility
from xbbg.ext.cdx import active_cdx, cdx_ticker
from xbbg.ext.futures import active_futures, fut_ticker

__all__ = [
    "fut_ticker",
    "active_futures",
    "cdx_ticker",
    "active_cdx",
]
