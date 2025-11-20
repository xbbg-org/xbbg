"""Reference data API module.

This module provides Bloomberg reference data functionality using a pipeline-based architecture.
"""

from xbbg.api.reference.reference import abdp, abds, bdp, bds

__all__ = ['bdp', 'bds', 'abdp', 'abds']

