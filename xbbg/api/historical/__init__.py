"""Historical data API module.

This module provides Bloomberg historical data functionality using a pipeline-based architecture.
"""

# pyright: reportImportCycles=false

from . import historical as historical  # noqa: F401
from .historical import *


def bdh(*args, **kwargs):
    """Forward to historical.bdh to keep runtime lookup patchable."""
    return historical.bdh(*args, **kwargs)
