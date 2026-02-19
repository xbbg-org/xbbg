"""Reference data API module.

This module provides Bloomberg reference data functionality using a pipeline-based architecture.
"""

# pyright: reportImportCycles=false

from . import lookup as lookup, reference as reference  # noqa: F401
from .lookup import *
from .reference import *


def bdp(*args, **kwargs):
    """Forward to reference.bdp to keep runtime lookup patchable."""
    return reference.bdp(*args, **kwargs)
