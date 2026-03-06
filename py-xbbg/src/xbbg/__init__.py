"""xbbg - Intuitive Bloomberg data API.

This package provides a high-level API for Bloomberg data access,
powered by a high-performance Rust backend.
"""

from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version
import sys
from typing import TYPE_CHECKING

from ._exports import (
    BACKEND_EXPORTS,
    CORE_EXPORTS,
    EXCEPTION_EXPORTS,
    FIELD_CACHE_EXPORTS,
    MODULE_EXPORTS,
    PACKAGE_BLP_EXPORTS,
    PACKAGE_EXPORTS,
    SCHEMA_LOOKUP_EXPORTS,
    SDK_EXPORTS,
    SERVICE_EXPORTS,
)

# Version from git tags via setuptools_scm (same mechanism as release/0.x)
try:
    __version__ = version("xbbg")
except PackageNotFoundError:
    __version__ = "0+unknown"

# Lazy import of the Rust module to avoid import errors when it's not built
if TYPE_CHECKING:
    from . import _core

# DLL search path setup (Windows)
# MUST run at module level, not inside __getattr__. When Python resolves
# `from xbbg._core import X`, it imports `xbbg` first (here) then loads
# the native extension as a submodule - bypassing __getattr__ entirely.
if sys.platform == "win32":
    try:
        from . import _sdk

        _sdk._add_sdk_to_dll_search_path()
    except Exception:
        pass  # SDK detection failures shouldn't block package import

_importing_core = False
_core_module = None

__all__ = list(PACKAGE_EXPORTS)


def _import_core():
    """Import and cache the native extension with a friendlier DLL error."""
    global _importing_core, _core_module
    if _core_module is not None:
        return _core_module
    if _importing_core:
        raise ImportError("Recursive import of _core detected")

    _importing_core = True
    try:
        mod = importlib.import_module("xbbg._core")
        _core_module = mod
        return mod
    except ImportError as e:
        if "DLL load failed" in str(e) or "cannot open shared object" in str(e):
            raise ImportError(
                f"{e}\n\n"
                "The xbbg native extension requires the Bloomberg C++ SDK shared library.\n"
                "Supported platforms: Linux x64, Windows x64/x86\n\n"
                "You can provide the SDK from any of these sources:\n"
                "  1. blpapi Python package: pip install blpapi --index-url "
                "https://blpapi.bloomberg.com/repository/releases/python/simple/\n"
                "  2. Bloomberg Terminal (DAPI) - automatically detected if installed\n"
                "  3. Bloomberg C++ SDK: set BLPAPI_ROOT environment variable\n"
                "  4. xbbg.set_sdk_path('/path/to/sdk') - manually set SDK path (Windows only)"
            ) from e
        raise
    finally:
        _importing_core = False


def _build_lazy_attr_exports() -> dict[str, tuple[str, str]]:
    exports = {"EngineConfig": ("_core", "PyEngineConfig")}
    module_groups = (
        ("_sdk", SDK_EXPORTS),
        ("_core", CORE_EXPORTS),
        ("blp", PACKAGE_BLP_EXPORTS),
        ("backend", BACKEND_EXPORTS),
        ("field_cache", FIELD_CACHE_EXPORTS),
        ("services", SERVICE_EXPORTS),
        ("schema", SCHEMA_LOOKUP_EXPORTS),
        ("exceptions", EXCEPTION_EXPORTS),
    )

    for module_name, names in module_groups:
        for name in names:
            exports[name] = (module_name, name)

    return exports


_LAZY_ATTR_EXPORTS = _build_lazy_attr_exports()


def __getattr__(name: str):
    """Lazy attribute access for deferred imports."""
    if name == "_core":
        return _import_core()
    if name in MODULE_EXPORTS:
        return importlib.import_module(f"xbbg.{name}")

    target = _LAZY_ATTR_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = _import_core() if module_name == "_core" else importlib.import_module(f"xbbg.{module_name}")
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    """Expose public attributes for tab completion."""
    return list(__all__)
