"""xbbg - Intuitive Bloomberg data API.

This package provides a high-level API for Bloomberg data access,
powered by a high-performance Rust backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# Lazy import of the Rust module to avoid import errors when it's not built
if TYPE_CHECKING:
    from . import _core

# Guard flag to prevent recursion in __getattr__
_importing_core = False
_core_module = None
_sdk_info: dict | None = None
_manual_sdk_path: Path | None = None


def _get_lib_version(lib_path: Path) -> str | None:
    """Extract version from a shared library using lief.

    Supports PE (Windows) and ELF (Linux) binaries.
    """
    try:
        import lief

        binary = lief.parse(str(lib_path))
        if binary is None:
            return None

        # Windows PE: check version resources
        if isinstance(binary, lief.PE.Binary):
            rm = binary.resources_manager
            if rm.has_version and rm.version:
                ffi = rm.version[0].file_info
                if ffi:
                    major = (ffi.product_version_ms >> 16) & 0xFFFF
                    minor = ffi.product_version_ms & 0xFFFF
                    build = (ffi.product_version_ls >> 16) & 0xFFFF
                    revision = ffi.product_version_ls & 0xFFFF
                    return f"{major}.{minor}.{build}.{revision}"

        # Linux ELF: check for version in strings or SONAME
        if isinstance(binary, lief.ELF.Binary):
            import re

            # Try to find version in .rodata section strings
            for section in binary.sections:
                if section.name == ".rodata":
                    content = bytes(section.content)
                    text = content.decode("latin-1", errors="ignore")
                    # Look for Bloomberg version pattern
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
                    if match and match.group(1).startswith("3."):
                        return match.group(1)
    except Exception:
        pass

    return None


def _find_sdk_lib(sdk_path: Path) -> Path | None:
    """Find the blpapi DLL/SO in an SDK directory."""
    import sys

    if sys.platform == "win32":
        candidates = ["blpapi3_64.dll", "blpapi3_32.dll", "lib/blpapi3_64.dll", "lib/blpapi3_32.dll"]
    else:  # Linux
        candidates = ["libblpapi3_64.so", "libblpapi3.so", "lib/libblpapi3_64.so", "lib/libblpapi3.so"]

    for candidate in candidates:
        full_path = sdk_path / candidate
        if full_path.is_file():
            return full_path
    return None


def get_sdk_info() -> dict:
    """Detect all available Bloomberg SDK sources and versions.

    Returns a dict with:
        - sources: list of all detected SDK sources
        - active: the source that will be used (first available)

    Each source entry contains:
        - name: "blpapi_python", "dapi", or "sdk_env"
        - version: version string if detectable
        - path: Path to the SDK

    Example:
        >>> import xbbg
        >>> xbbg.get_sdk_info()
        {'sources': [{'name': 'blpapi_python', 'version': '3.25.11.1', ...}], 'active': 'blpapi_python'}
    """
    import os
    import sys

    global _sdk_info
    if _sdk_info is not None:
        return _sdk_info

    sources: list[dict] = []

    # Check 0: Manually set SDK path (highest priority)
    if _manual_sdk_path is not None:
        manual_version = None
        lib_path = _find_sdk_lib(_manual_sdk_path)
        if lib_path:
            manual_version = _get_lib_version(lib_path)
        sources.append(
            {
                "name": "manual",
                "version": manual_version,
                "path": _manual_sdk_path,
            }
        )

    # Check 1: blpapi Python package (most common for pip users)
    try:
        import blpapi

        blpapi_file = getattr(blpapi, "__file__", None)
        sources.append(
            {
                "name": "blpapi_python",
                "version": getattr(blpapi, "__version__", None),
                "path": Path(blpapi_file) if blpapi_file else None,
            }
        )
    except ImportError:
        pass

    # Check 2: DAPI (Bloomberg Terminal installation)
    if sys.platform == "win32":
        dapi_paths = [
            Path(r"C:\blp\DAPI"),
            Path(os.path.expandvars(r"%LOCALAPPDATA%\Bloomberg\DAPI")),
        ]
    else:  # Linux
        dapi_paths = [
            Path.home() / "blp" / "DAPI",
            Path("/opt/bloomberg/DAPI"),
        ]

    for dapi_path in dapi_paths:
        if dapi_path.is_dir():
            dapi_version = None
            lib_path = _find_sdk_lib(dapi_path)
            if lib_path:
                dapi_version = _get_lib_version(lib_path)
            sources.append(
                {
                    "name": "dapi",
                    "version": dapi_version,
                    "path": dapi_path,
                }
            )
            break  # Only add first found DAPI path

    # Check 3: BLPAPI_ROOT environment variable
    blpapi_root = os.environ.get("BLPAPI_ROOT")
    if blpapi_root:
        sdk_path = Path(blpapi_root)
        if sdk_path.is_dir():
            sdk_version = None
            lib_path = _find_sdk_lib(sdk_path)
            if lib_path:
                sdk_version = _get_lib_version(lib_path)
            sources.append(
                {
                    "name": "sdk_env",
                    "version": sdk_version,
                    "path": sdk_path,
                }
            )

    info = {
        "sources": sources,
        "active": sources[0]["name"] if sources else None,
    }
    _sdk_info = info
    return info


def set_sdk_path(path: str | Path) -> None:
    """Manually set the Bloomberg SDK path.

    This takes precedence over all auto-detected sources (blpapi_python, dapi, sdk_env).
    The path should point to a directory containing the Bloomberg SDK shared library.

    Args:
        path: Path to the SDK directory (e.g., "C:/blpapi_cpp_3.25.11.1" or Path object)

    Example:
        >>> import xbbg
        >>> xbbg.set_sdk_path("C:/custom/blpapi")
        >>> xbbg.get_sdk_info()["active"]
        'manual'
    """
    from pathlib import Path as PathClass

    global _manual_sdk_path, _sdk_info

    sdk_path = PathClass(path) if isinstance(path, str) else path
    if not sdk_path.is_dir():
        raise ValueError(f"SDK path does not exist or is not a directory: {sdk_path}")

    lib_path = _find_sdk_lib(sdk_path)
    if not lib_path:
        raise ValueError(f"Could not find Bloomberg SDK library in: {sdk_path}")

    _manual_sdk_path = sdk_path
    _sdk_info = None  # Clear cached info to refresh on next get_sdk_info() call


def clear_sdk_path() -> None:
    """Clear the manually set SDK path and revert to auto-detection.

    Example:
        >>> import xbbg
        >>> xbbg.set_sdk_path("C:/custom/blpapi")
        >>> xbbg.clear_sdk_path()  # Back to auto-detection
    """
    global _manual_sdk_path, _sdk_info
    _manual_sdk_path = None
    _sdk_info = None  # Clear cached info to refresh on next get_sdk_info() call


def _add_sdk_to_dll_search_path() -> None:
    """Add all detected SDK library paths to Windows DLL search path.

    This must be called before importing the native extension (_core).
    Checks all SDK sources: manual path, blpapi package, DAPI, BLPAPI_ROOT.

    All operations are wrapped in try/except to handle permission errors
    gracefully (e.g., no admin access, restricted folders).
    """
    import os
    from pathlib import Path

    added_dirs: set[str] = set()

    def try_add_dir(sdk_path: Path | None) -> None:
        """Try to add SDK library directory to DLL search path. Silently fails on errors."""
        if sdk_path is None:
            return
        try:
            lib_path = _find_sdk_lib(sdk_path)
            if lib_path:
                lib_dir = str(lib_path.parent)
                if lib_dir not in added_dirs:
                    os.add_dll_directory(lib_dir)
                    added_dirs.add(lib_dir)
        except (OSError, PermissionError, ValueError):
            pass  # Can't access directory or add to DLL search path

    # 1. Manual SDK path (highest priority)
    if _manual_sdk_path is not None:
        try_add_dir(_manual_sdk_path)

    # 2. blpapi Python package
    try:
        import blpapi

        blpapi_file = getattr(blpapi, "__file__", None)
        if blpapi_file:
            try_add_dir(Path(blpapi_file).parent)
    except (ImportError, OSError):
        pass

    # 3. DAPI (Bloomberg Terminal) - typically already in PATH but add as fallback
    dapi_paths = [
        Path(r"C:\blp\DAPI"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Bloomberg\DAPI")),
    ]
    for dapi_path in dapi_paths:
        try:
            if dapi_path.is_dir():
                try_add_dir(dapi_path)
                break
        except (OSError, PermissionError):
            continue  # Can't access this path, try next

    # 4. BLPAPI_ROOT environment variable
    blpapi_root = os.environ.get("BLPAPI_ROOT")
    if blpapi_root:
        try_add_dir(Path(blpapi_root))


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
    "bfld",
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
    "abfld",
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
    # Extensions module
    "ext",
]


def __getattr__(name: str):
    """Lazy attribute access for deferred imports."""
    global _importing_core, _core_module
    if name == "__version__":
        # Version from git describe, embedded at compile time
        from . import _core

        return _core.__version__
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
                _add_sdk_to_dll_search_path()

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
        "bfld",
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
        "abfld",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose public attributes for tab completion."""
    return __all__
