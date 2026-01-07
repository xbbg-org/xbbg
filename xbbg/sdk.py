"""SDK detection and version information.

This module provides utilities for detecting Bloomberg SDK installations
and retrieving version information.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


def get_sdk_info() -> dict[str, Any]:
    """Detect all available Bloomberg SDK sources and versions.

    This is the v1.0 replacement for getBlpapiVersion().

    Returns a dict with:
        - sources: list of all detected SDK sources
        - active: the source that will be used (first available)

    Each source entry contains:
        - name: "blpapi_python", "dapi", or "sdk_env"
        - version: version string if detectable
        - path: Path to the SDK (if available)

    Example::

        >>> import xbbg
        >>> info = xbbg.get_sdk_info()  # doctest: +SKIP
        >>> info['active']  # doctest: +SKIP
        'blpapi_python'

    Note:
        In xbbg v1.0, this replaces getBlpapiVersion() which is deprecated.
    """
    import os

    sources: list[dict[str, Any]] = []

    # Check 1: blpapi Python package (most common for pip users)
    try:
        import blpapi

        blpapi_file = getattr(blpapi, "__file__", None)
        sources.append(
            {
                "name": "blpapi_python",
                "version": getattr(blpapi, "__version__", None),
                "path": Path(blpapi_file).parent if blpapi_file else None,
            }
        )
    except ImportError:
        pass

    # Check 2: DAPI (Bloomberg Terminal installation - Windows only)
    if sys.platform == "win32":
        dapi_paths = [
            Path(r"C:lp\DAPI"),
            Path(os.path.expandvars(r"%LOCALAPPDATA%\Bloomberg\DAPI")),
        ]
        for dapi_path in dapi_paths:
            if dapi_path.exists():
                sources.append(
                    {
                        "name": "dapi",
                        "version": None,  # Version detection requires parsing DLL
                        "path": dapi_path,
                    }
                )
                break

    # Check 3: BLPAPI_ROOT environment variable
    blpapi_root = os.environ.get("BLPAPI_ROOT")
    if blpapi_root:
        root_path = Path(blpapi_root)
        if root_path.exists():
            sources.append(
                {
                    "name": "sdk_env",
                    "version": None,
                    "path": root_path,
                }
            )

    # Determine active source (first available)
    active = sources[0]["name"] if sources else None

    return {
        "sources": sources,
        "active": active,
    }
