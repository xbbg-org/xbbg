"""xbbg - Intuitive Bloomberg data API.

This package provides a high-level API for Bloomberg data access,
powered by a high-performance Rust backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Lazy import of the Rust module to avoid import errors when it's not built
if TYPE_CHECKING:
    from . import _core

# Guard flag to prevent recursion in __getattr__
_importing_core = False
_core_module = None


__all__ = [
    "__version__",
    "_core",
    "Backend",
    "EngineConfig",
    # Generic API (power users)
    "arequest",
    "request",
    # Sync API
    "bdp",
    "bds",
    "bdh",
    "bdib",
    "bdtick",
    "bql",
    "bsrch",
    "bflds",
    "beqs",
    "blkp",
    "bport",
    "bcurves",
    "bgovts",
    # Async API
    "abdp",
    "abds",
    "abdh",
    "abdib",
    "abdtick",
    "abql",
    "absrch",
    "abflds",
    "abeqs",
    "ablkp",
    "abport",
    "abcurves",
    "abgovts",
    # Streaming API
    "Tick",
    "Subscription",
    "asubscribe",
    "subscribe",
    "astream",
    "stream",
    # VWAP Streaming
    "avwap",
    "vwap",
    # Streaming Bars
    "amktbar",
    "mktbar",
    # Market Depth (B-PIPE)
    "adepth",
    "depth",
    # Option/Futures Chains (B-PIPE)
    "achains",
    "chains",
    # Technical Analysis
    "abta",
    "bta",
    "ta_studies",
    "ta_study_params",
    "generate_ta_stubs",
    # Config
    "configure",
    "set_backend",
    "get_backend",
    # Lifecycle
    "shutdown",
    "reset",
    "is_connected",
    # Logging control
    "set_log_level",
    "get_log_level",
    # Schema introspection (user-facing)
    "bops",
    "abops",
    "bschema",
    "abschema",
    "get_sdk_info",
    "set_sdk_path",
    "clear_sdk_path",
    # Field type cache
    "FieldTypeCache",
    "FieldInfo",
    "resolve_field_types",
    "aresolve_field_types",
    "cache_field_types",
    "get_field_info",
    "clear_field_cache",
    # Service definitions
    "Service",
    "Operation",
    "OutputMode",
    "RequestParams",
    "ExtractorHint",
    # Schema introspection
    "get_schema",
    "aget_schema",
    "get_operation",
    "aget_operation",
    "list_operations",
    "alist_operations",
    "get_enum_values",
    "aget_enum_values",
    "list_valid_elements",
    "alist_valid_elements",
    "generate_stubs",
    "configure_ide_stubs",
    "ServiceSchema",
    "OperationSchema",
    # Exceptions
    "BlpError",
    "BlpSessionError",
    "BlpRequestError",
    "BlpSecurityError",
    "BlpFieldError",
    "BlpValidationError",
    "BlpTimeoutError",
    "BlpInternalError",
    "BlpBPipeError",
    # Extensions module
    "ext",
    # Markets module
    "markets",
]


def __getattr__(name: str):
    """Lazy attribute access for deferred imports."""
    global _importing_core, _core_module
    if name == "__version__":
        # Version from git describe, embedded at compile time
        from . import _core

        return _core.__version__
    if name in ("get_sdk_info", "set_sdk_path", "clear_sdk_path"):
        from . import _sdk

        return getattr(_sdk, name)
    if name == "_core":
        # Return cached module if already imported
        if _core_module is not None:
            return _core_module
        # Guard against recursive import
        if _importing_core:
            raise ImportError("Recursive import of _core detected")
        _importing_core = True
        try:
            import importlib
            import sys

            # Add all detected SDK library paths to DLL search path before importing
            if sys.platform == "win32":
                from . import _sdk

                _sdk._add_sdk_to_dll_search_path()

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
    # Logging control (direct from _core, no blp dependency)
    if name in ("set_log_level", "get_log_level"):
        from . import _core

        return getattr(_core, name)
    # blp module exports
    if name in (
        "Backend",
        "EngineConfig",
        "arequest",
        "request",
        "bdp",
        "bds",
        "bdh",
        "bdib",
        "bdtick",
        "bql",
        "bsrch",
        "bflds",
        "beqs",
        "blkp",
        "bport",
        "bcurves",
        "bgovts",
        "abdp",
        "abds",
        "abdh",
        "abdib",
        "abdtick",
        "abql",
        "absrch",
        "abflds",
        "abeqs",
        "ablkp",
        "abport",
        "abcurves",
        "abgovts",
        # Streaming API
        "Tick",
        "Subscription",
        "asubscribe",
        "subscribe",
        "astream",
        "stream",
        # VWAP Streaming
        "avwap",
        "vwap",
        # Market Bar Streaming
        "amktbar",
        "mktbar",
        # Market Depth Streaming
        "adepth",
        "depth",
        # Chain Streaming
        "achains",
        "chains",
        # Technical Analysis
        "abta",
        "bta",
        "ta_studies",
        "ta_study_params",
        "generate_ta_stubs",
        # Config
        "configure",
        "set_backend",
        "get_backend",
        # Lifecycle
        "shutdown",
        "reset",
        "is_connected",
        "Service",
        "Operation",
        "OutputMode",
        "RequestParams",
        "ExtractorHint",
        # Schema introspection
        "bops",
        "abops",
        "bschema",
        "abschema",
    ):
        from . import blp

        return getattr(blp, name)
    # Exception exports
    if name in (
        "BlpError",
        "BlpSessionError",
        "BlpRequestError",
        "BlpSecurityError",
        "BlpFieldError",
        "BlpValidationError",
        "BlpTimeoutError",
        "BlpInternalError",
        "BlpBPipeError",
    ):
        from . import exceptions

        return getattr(exceptions, name)
    # Field cache exports
    if name in (
        "FieldTypeCache",
        "FieldInfo",
        "resolve_field_types",
        "aresolve_field_types",
        "cache_field_types",
        "get_field_info",
        "clear_field_cache",
    ):
        from . import field_cache

        return getattr(field_cache, name)
    # Schema exports
    if name in (
        "get_schema",
        "aget_schema",
        "get_operation",
        "aget_operation",
        "list_operations",
        "alist_operations",
        "get_enum_values",
        "aget_enum_values",
        "list_valid_elements",
        "alist_valid_elements",
        "generate_stubs",
        "configure_ide_stubs",
        "ServiceSchema",
        "OperationSchema",
        "ElementInfo",
    ):
        from . import schema

        return getattr(schema, name)
    # Extensions module
    if name == "ext":
        import importlib

        return importlib.import_module("xbbg.ext")
    # Markets module
    if name == "markets":
        import importlib

        return importlib.import_module("xbbg.markets")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose public attributes for tab completion."""
    return __all__
