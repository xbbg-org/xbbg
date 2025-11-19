"""Centralized Bloomberg API (blpapi) wrapper.

This module handles the conditional import of the blpapi library and provides
a single source of truth for its availability. It also handles DLL path
configuration for Windows environments.
"""

import os
from pathlib import Path
import sys
from typing import Any

# Try to import blpapi
blpapi: Any = None
_BLPAPI_AVAILABLE = False

try:
    # Handle Windows DLL path for Python 3.8+
    ver = sys.version_info
    if os.name == 'nt' and f'{ver.major}.{ver.minor}' == '3.8':
        dll_path = os.environ.get('BBG_DLL', 'C:/blp/DAPI')
        if Path(dll_path).exists():
            with os.add_dll_directory(dll_path):
                import blpapi  # type: ignore[reportMissingImports]
        else:
            raise ImportError(
                'Please add BBG_DLL to your PATH variable'
            )
    else:
        import blpapi  # type: ignore[reportMissingImports]

    _BLPAPI_AVAILABLE = True

except (ImportError, AttributeError):
    # Try pytest importorskip as fallback (mostly for testing environments)
    try:
        import pytest  # type: ignore[reportMissingImports]
        blpapi = pytest.importorskip('blpapi')  # type: ignore[assignment]
        _BLPAPI_AVAILABLE = True
    except (ImportError, AttributeError):
        blpapi = None  # type: ignore[assignment]
        _BLPAPI_AVAILABLE = False

def is_available() -> bool:
    """Check if blpapi is available."""
    return _BLPAPI_AVAILABLE

