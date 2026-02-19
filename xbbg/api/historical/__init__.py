"""Historical data API module.

This module provides Bloomberg historical data functionality using a pipeline-based architecture.
"""

# pyright: reportImportCycles=false
from __future__ import annotations

from . import historical as historical
from .historical import *


def bdh(*args, **kwargs):
    """Forward to historical.bdh to keep runtime lookup patchable."""
    return historical.bdh(*args, **kwargs)
