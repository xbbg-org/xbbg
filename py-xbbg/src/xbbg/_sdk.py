"""SDK detection and management utilities for Bloomberg libraries."""

from __future__ import annotations

from pathlib import Path

_sdk_info: dict | None = None
_manual_sdk_path: Path | None = None


def _get_lib_version(_lib_path: Path) -> str | None:
    """Get the version of the linked Bloomberg C SDK at runtime."""
    try:
        from . import _core

        major, minor, patch, build = _core.sdk_version()
        return f"{major}.{minor}.{patch}.{build}"
    except Exception:
        return None


def _find_sdk_lib(sdk_path: Path) -> Path | None:
    """Find the blpapi DLL/SO in an SDK directory.

    Bloomberg ships `libblpapi3_64.so` (not `.dylib`) on macOS as well as
    Linux, so the non-Windows candidate list is the same for both.
    """
    import sys

    if sys.platform == "win32":
        candidates = ["blpapi3_64.dll", "blpapi3_32.dll", "lib/blpapi3_64.dll", "lib/blpapi3_32.dll"]
    else:  # macOS and Linux
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

    runtime_version = None
    try:
        from . import _core

        major, minor, patch, build = _core.sdk_version()
        runtime_version = f"{major}.{minor}.{patch}.{build}"
    except Exception:
        pass

    info = {
        "sources": sources,
        "active": sources[0]["name"] if sources else None,
        "runtime_version": runtime_version,
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


def _collect_sdk_candidate_dirs() -> list[Path]:
    """Walk all SDK sources in priority order and return existing directories.

    Priority: manual path → blpapi Python package → DAPI → BLPAPI_ROOT.
    Duplicates (by resolved path) are removed.
    """
    import os
    import sys

    seen: set[str] = set()
    result: list[Path] = []

    def add(candidate: Path | None) -> None:
        if candidate is None:
            return
        try:
            if not candidate.is_dir():
                return
            key = str(candidate.resolve())
        except (OSError, PermissionError):
            return
        if key in seen:
            return
        seen.add(key)
        result.append(candidate)

    # 1. Manual SDK path (highest priority)
    if _manual_sdk_path is not None:
        add(_manual_sdk_path)

    # 2. blpapi Python package (most common for pip users)
    try:
        import blpapi

        blpapi_file = getattr(blpapi, "__file__", None)
        if blpapi_file:
            add(Path(blpapi_file).parent)
    except (ImportError, OSError):
        pass

    # 3. DAPI (Bloomberg Terminal)
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
        try:
            if dapi_path.is_dir():
                add(dapi_path)
                break
        except (OSError, PermissionError):
            continue

    # 4. BLPAPI_ROOT environment variable
    blpapi_root = os.environ.get("BLPAPI_ROOT")
    if blpapi_root:
        add(Path(blpapi_root))

    return result


def _add_sdk_to_dll_search_path() -> None:
    """Windows: add each detected SDK library directory to the DLL search path.

    Must be called before importing the native extension (_core). Errors are
    swallowed so permission issues or missing directories don't block import.
    """
    import os

    for sdk_dir in _collect_sdk_candidate_dirs():
        lib_path = _find_sdk_lib(sdk_dir)
        if lib_path is None:
            continue
        try:
            os.add_dll_directory(str(lib_path.parent))  # type: ignore[unresolved-attribute]
        except (OSError, PermissionError, ValueError):
            continue


def _preload_sdk_library() -> bool:
    """macOS/Linux: dlopen libblpapi so @rpath refs in _core resolve via install-name match.

    The pyo3 cdylib (_core) declares `@rpath/libblpapi3_64.so` as a dynamic
    dependency but ships with no LC_RPATH entries. On macOS, once any image
    with LC_ID_DYLIB `@rpath/libblpapi3_64.so` is loaded into the process,
    dyld satisfies subsequent `@rpath/libblpapi3_64.so` references by
    install-name match — no rpath search occurs. This is the same pattern
    Bloomberg's own `blpapi/internals.py::_loadLibrary` uses to load its
    `ffiutils.cpython-*-darwin.so` extension, which also ships with no rpath.

    On Linux, loading with RTLD_GLOBAL ensures the library's symbols are
    available to subsequently loaded modules, avoiding a second DT_NEEDED
    search (which may fail if `site-packages/blpapi` isn't on `LD_LIBRARY_PATH`).

    Returns True on first successful preload, False if nothing could be
    loaded. Failure is non-fatal — `_import_core` still surfaces the
    friendly error message if the C extension can't open the library.
    """
    import ctypes

    for sdk_dir in _collect_sdk_candidate_dirs():
        lib_path = _find_sdk_lib(sdk_dir)
        if lib_path is None:
            continue
        try:
            ctypes.CDLL(str(lib_path), mode=ctypes.RTLD_GLOBAL)
            return True
        except OSError:
            continue
    return False


def _prepare_sdk_for_core_import() -> None:
    """Prepare the current process to load xbbg._core on any platform.

    Dispatches to the correct per-platform mechanism:

    - Windows: add each detected SDK directory to the DLL search path.
    - macOS/Linux: dlopen libblpapi so _core's `@rpath/libblpapi3_64.so`
      dependency resolves via dyld's install-name match (macOS) or is
      already in the process's loaded image list (Linux).

    All errors are swallowed; `_import_core()` surfaces the friendly error
    message if no SDK can be found at the point the native extension is
    actually imported.
    """
    import sys

    try:
        if sys.platform == "win32":
            _add_sdk_to_dll_search_path()
        else:
            _preload_sdk_library()
    except Exception:
        pass
