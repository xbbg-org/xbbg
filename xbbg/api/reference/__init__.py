"""Reference data API module.

This module provides Bloomberg reference data functionality using a pipeline-based architecture.
"""

from xbbg.api.reference.lookup import (
    bfld,
    blkp,
    bport,
    fieldInfo,
    fieldSearch,
    getBlpapiVersion,
    getPortfolio,
    lookupSecurity,
)
from xbbg.api.reference.reference import abdp, abds, bdp, bds

__all__ = [
    "bdp",
    "bds",
    "abdp",
    "abds",
    # v1.0 names
    "bfld",
    "blkp",
    "bport",
    # legacy names (backward compatible)
    "fieldInfo",
    "fieldSearch",
    "lookupSecurity",
    "getPortfolio",
    "getBlpapiVersion",
]
