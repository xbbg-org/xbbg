"""Reference data API module.

This module provides Bloomberg reference data functionality using a pipeline-based architecture.
"""

from xbbg.api.reference.lookup import (
    abfld,
    ablkp,
    afieldInfo,
    afieldSearch,
    alookupSecurity,
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
    "abfld",
    "blkp",
    "ablkp",
    "bport",
    # async variants
    "afieldInfo",
    "afieldSearch",
    "alookupSecurity",
    # legacy names (backward compatible)
    "fieldInfo",
    "fieldSearch",
    "lookupSecurity",
    "getPortfolio",
    "getBlpapiVersion",
]
