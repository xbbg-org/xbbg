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

    Works cross-platform for PE (Windows) and ELF (Linux) binaries.
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
    else:
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
    else:
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


__all__ = [
    "__version__",
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
    "get_sdk_info",
    "set_sdk_path",
    "clear_sdk_path",
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
            import os
            import sys

            # Add SDK library path to DLL search path before importing
            sdk_lib_dir = None
            if _manual_sdk_path is not None:
                lib_path = _find_sdk_lib(_manual_sdk_path)
                if lib_path:
                    sdk_lib_dir = lib_path.parent

            if sdk_lib_dir and sys.platform == "win32":
                # Windows: add to DLL search path
                os.add_dll_directory(str(sdk_lib_dir))
            elif sdk_lib_dir:
                # Linux/macOS: prepend to LD_LIBRARY_PATH for subprocess, but for
                # current process we need ctypes.CDLL or it's too late
                pass  # blpapi Python package handles this on Linux

            mod = importlib.import_module("xbbg._core")
            _core_module = mod
            return mod
        except ImportError as e:
            if "DLL load failed" in str(e) or "cannot open shared object" in str(e):
                raise ImportError(
                    f"{e}\n\n"
                    "The xbbg native extension requires the Bloomberg C++ SDK shared library.\n"
                    "You can provide it from any of these sources:\n"
                    "  1. xbbg.set_sdk_path('/path/to/sdk') - manually set SDK path\n"
                    "  2. Bloomberg Terminal (DAPI) - automatically available if installed\n"
                    "  3. blpapi Python package: pip install blpapi --index-url "
                    "https://blpapi.bloomberg.com/repository/releases/python/simple/\n"
                    "  4. Bloomberg C++ SDK: download from Bloomberg and set BLPAPI_ROOT"
                ) from e
            raise
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
