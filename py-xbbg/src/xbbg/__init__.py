"""xbbg - Intuitive Bloomberg data API.

This package provides a high-level API for Bloomberg data access,
powered by a high-performance Rust backend.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

# Lazy import of the Rust module to avoid import errors when it's not built
if TYPE_CHECKING:
    from . import _core

# Minimum required blpapi version (must match SDK version used to build the extension)
_REQUIRED_BLPAPI_VERSION = "3.25.0"

# Guard flag to prevent recursion in __getattr__
_checking_blpapi = False
_importing_core = False
_core_module = None


def _check_blpapi_version() -> None:
    """Check if blpapi version is compatible and warn if not."""
    try:
        import blpapi

        installed = getattr(blpapi, "__version__", "unknown")
        if installed != "unknown":
            from packaging.version import Version

            try:
                if Version(installed) < Version(_REQUIRED_BLPAPI_VERSION):
                    warnings.warn(
                        f"blpapi version {installed} is older than required {_REQUIRED_BLPAPI_VERSION}. "
                        f"The xbbg native extension may not load correctly. "
                        f"Install the latest blpapi from: "
                        f"https://blpapi.bloomberg.com/repository/releases/python/simple/",
                        UserWarning,
                        stacklevel=3,
                    )
            except Exception:
                pass  # packaging not available or version parse failed
    except ImportError:
        warnings.warn(
            "blpapi package not found. The xbbg native extension requires blpapi to be installed. "
            "Install from: https://blpapi.bloomberg.com/repository/releases/python/simple/",
            UserWarning,
            stacklevel=3,
        )

__all__ = [
    "_core",
    "Backend",
    # Sync API
    "bdp",
    "bds",
    "bdh",
    "bdib",
    "bdtick",
    # Async API
    "abdp",
    "abds",
    "abdh",
    "abdib",
    "abdtick",
    "set_backend",
    "get_backend",
]


def __getattr__(name: str):
    """Lazy attribute access for deferred imports."""
    global _checking_blpapi, _importing_core, _core_module
    if name == "_core":
        # Return cached module if already imported
        if _core_module is not None:
            return _core_module
        # Guard against recursive import
        if _importing_core:
            raise ImportError("Recursive import of _core detected")
        _importing_core = True
        try:
            # Only check blpapi version once to avoid recursion
            if not _checking_blpapi:
                _checking_blpapi = True
                try:
                    _check_blpapi_version()
                finally:
                    _checking_blpapi = False
            # Import the actual extension module directly
            import importlib

            mod = importlib.import_module("xbbg._core")
            _core_module = mod
            return mod
        finally:
            _importing_core = False
    if name in (
        "Backend",
        "bdp",
        "bds",
        "bdh",
        "bdib",
        "bdtick",
        "abdp",
        "abds",
        "abdh",
        "abdib",
        "abdtick",
        "set_backend",
        "get_backend",
    ):
        from . import blp

        return getattr(blp, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose public attributes for tab completion."""
    return __all__
