"""Reference data API module.

This module provides Bloomberg reference data functionality using a pipeline-based architecture.
"""

# pyright: reportImportCycles=false
from __future__ import annotations

from . import lookup as lookup, reference as reference
from .lookup import *
from .reference import *


def bdp(*args, **kwargs):
    """Forward to reference.bdp to keep runtime lookup patchable."""
    return reference.bdp(*args, **kwargs)
