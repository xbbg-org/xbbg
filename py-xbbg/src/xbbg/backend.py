"""Backend enum and availability infrastructure for xbbg.

This module provides the canonical ``Backend`` enum for selecting
DataFrame output backends, along with availability checking, version
validation, and format compatibility helpers.

The Rust layer returns Arrow tables; this module is a Python-only
concern that governs how those tables are converted to the user's
preferred DataFrame type.

Ported from ``release/0.x`` ``xbbg/backend.py``.
"""

from __future__ import annotations

from enum import Enum
import logging
import sys
from typing import Any

from xbbg.services import Format

logger = logging.getLogger(__name__)


# =============================================================================
# Backend Enum
# =============================================================================


class Backend(str, Enum):
    """Enum for selecting the data processing backend.

    The backend determines which library is used for data manipulation
    and storage.  Each backend has different performance characteristics
    and memory usage patterns.

    **Eager backends** (full API support):

    - ``NARWHALS`` – Backend-agnostic DataFrame API
    - ``PANDAS`` – Most widely used DataFrame library
    - ``POLARS`` – High-performance Rust-based DataFrames
    - ``PYARROW`` – Apache Arrow columnar format
    - ``CUDF`` – GPU-accelerated DataFrames (NVIDIA RAPIDS)
    - ``MODIN`` – Distributed pandas-like DataFrames

    **Lazy backends** (deferred execution):

    - ``NARWHALS_LAZY`` – Narwhals with lazy evaluation
    - ``POLARS_LAZY`` – Polars LazyFrame for query optimisation
    - ``DUCKDB`` – Embedded analytical SQL database
    - ``DASK`` – Parallel computing with task scheduling
    - ``IBIS`` – Portable DataFrame expressions (SQL backends)
    - ``PYSPARK`` – Apache Spark distributed DataFrames
    - ``SQLFRAME`` – SQL-based DataFrame abstraction
    """

    # Eager backends (full API support)
    NARWHALS = "narwhals"
    PANDAS = "pandas"
    POLARS = "polars"
    PYARROW = "pyarrow"
    CUDF = "cudf"
    MODIN = "modin"

    # Lazy backends (deferred execution)
    NARWHALS_LAZY = "narwhals_lazy"
    POLARS_LAZY = "polars_lazy"
    DUCKDB = "duckdb"
    DASK = "dask"
    IBIS = "ibis"
    PYSPARK = "pyspark"
    SQLFRAME = "sqlframe"

    @classmethod
    def _missing_(cls, value: object) -> Backend | None:
        if isinstance(value, str):
            lowered = value.lower()
            for member in cls:
                if member.value == lowered:
                    return member
        return None


# =============================================================================
# Version Requirements & Package Mappings
# =============================================================================

# Minimum version requirements per backend.
# Format: ``(major, minor)`` or ``(major, minor, patch)``.
MIN_VERSIONS: dict[Backend, tuple[int, ...]] = {
    Backend.PANDAS: (2, 0),
    Backend.POLARS: (0, 20),
    Backend.POLARS_LAZY: (0, 20),
    Backend.PYARROW: (13, 0),  # narwhals minimum; xbbg requires >=22.0
    Backend.DUCKDB: (1, 0),
    Backend.CUDF: (24, 10),
    Backend.MODIN: (0, 25),
    Backend.DASK: (2024, 1),
    Backend.IBIS: (6, 0),
    Backend.PYSPARK: (3, 5),
    Backend.SQLFRAME: (3, 22),
}

# Package names for ``pip install`` instructions.
PACKAGE_NAMES: dict[Backend, str] = {
    Backend.PANDAS: "pandas",
    Backend.POLARS: "polars",
    Backend.POLARS_LAZY: "polars",
    Backend.PYARROW: "pyarrow",
    Backend.DUCKDB: "duckdb",
    Backend.CUDF: "cudf-cu12",
    Backend.MODIN: "modin[all]",
    Backend.DASK: "dask[dataframe]",
    Backend.IBIS: "ibis-framework",
    Backend.PYSPARK: "pyspark",
    Backend.SQLFRAME: "sqlframe",
}

# Module names to ``import`` (may differ from the PyPI package name).
MODULE_NAMES: dict[Backend, str] = {
    Backend.PANDAS: "pandas",
    Backend.POLARS: "polars",
    Backend.POLARS_LAZY: "polars",
    Backend.PYARROW: "pyarrow",
    Backend.DUCKDB: "duckdb",
    Backend.CUDF: "cudf",
    Backend.MODIN: "modin",
    Backend.DASK: "dask",
    Backend.IBIS: "ibis",
    Backend.PYSPARK: "pyspark",
    Backend.SQLFRAME: "sqlframe",
    Backend.NARWHALS: "narwhals",
    Backend.NARWHALS_LAZY: "narwhals",
}


# =============================================================================
# Format Compatibility
# =============================================================================

# Which ``Format`` variants each backend supports.
#
# * LONG / SEMI_LONG / LONG_TYPED / LONG_WITH_METADATA — universally supported
#   for all backends.
SUPPORTED_FORMATS: dict[Backend, frozenset[Format]] = {
    # Eager backends — full format support
    Backend.PANDAS: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.POLARS: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.PYARROW: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.NARWHALS: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.CUDF: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.MODIN: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    # Lazy backends
    Backend.NARWHALS_LAZY: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.POLARS_LAZY: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.DUCKDB: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.DASK: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.IBIS: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.PYSPARK: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
    Backend.SQLFRAME: frozenset({Format.LONG, Format.SEMI_LONG, Format.LONG_TYPED, Format.LONG_WITH_METADATA}),
}


# =============================================================================
# Internal Helpers
# =============================================================================


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple of ints.

    Strips pre-release suffixes (``a1``, ``b2``, ``rc1``, ``+local``).

    >>> _parse_version("2.0.1")
    (2, 0, 1)
    >>> _parse_version("0.20.4a1")
    (0, 20, 4)
    """
    version_str = version_str.split("+")[0]  # remove local
    version_str = version_str.split("a")[0]  # remove alpha
    version_str = version_str.split("b")[0]  # remove beta
    version_str = version_str.split("rc")[0]  # remove rc

    parts: list[int] = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts)


def _format_version(version: tuple[int, ...]) -> str:
    """Format a version tuple as a dotted string."""
    return ".".join(str(v) for v in version)


def _get_module(backend: Backend) -> Any | None:
    """Return the backend's module if it has already been imported.

    Checks ``sys.modules`` without triggering an import, following
    the narwhals convention.
    """
    module_name = MODULE_NAMES.get(backend)
    if module_name is None:
        return None
    return sys.modules.get(module_name)


def _get_module_version(module: Any) -> tuple[int, ...] | None:
    """Return a module's ``__version__`` as a parsed tuple, or ``None``."""
    version_str = getattr(module, "__version__", None)
    if version_str is None:
        version_str = getattr(module, "VERSION", None)
    if version_str is None:
        return None
    return _parse_version(str(version_str))


# =============================================================================
# Backend Availability
# =============================================================================


def is_backend_available(backend: Backend | str) -> bool:
    """Check whether a backend is installed and importable.

    Core dependencies (narwhals, pyarrow) always return ``True``.

    Args:
        backend: A :class:`Backend` member or its string value.

    Returns:
        ``True`` when the backend package can be imported.
    """
    if isinstance(backend, str):
        backend = Backend(backend)

    # Core dependencies — always available.
    if backend in (Backend.NARWHALS, Backend.NARWHALS_LAZY):
        return True
    if backend == Backend.PYARROW:
        return True

    module_name = MODULE_NAMES.get(backend)
    if module_name is None:
        return False

    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def check_backend(backend: Backend | str, *, raise_on_error: bool = True) -> bool:
    """Check that a backend is available *and* meets minimum version requirements.

    Provides actionable error messages with ``pip install`` instructions.

    Args:
        backend: A :class:`Backend` member or its string value.
        raise_on_error: Raise on failure instead of returning ``False``.

    Returns:
        ``True`` when the backend is usable.

    Raises:
        ImportError: Package not installed (when *raise_on_error*).
        ValueError: Installed version too old (when *raise_on_error*).
    """
    if isinstance(backend, str):
        backend = Backend(backend)

    # Core dependencies — always OK.
    if backend in (Backend.NARWHALS, Backend.NARWHALS_LAZY, Backend.PYARROW):
        return True

    module_name = MODULE_NAMES.get(backend)
    if module_name is None:
        msg = f"Unknown backend: {backend.value}"
        if raise_on_error:
            raise ValueError(msg)
        logger.warning(msg)
        return False

    package_name = PACKAGE_NAMES.get(backend, module_name)
    min_version = MIN_VERSIONS.get(backend)

    # Try to import.
    try:
        module = __import__(module_name)
    except ImportError:
        msg = (
            f"Backend '{backend.value}' requires the '{package_name}' package, "
            f"which is not installed.\n\n"
            f"To install, run:\n"
            f"    pip install {package_name}"
        )
        if min_version:
            msg += f">={_format_version(min_version)}"
        msg += "\n\nOr install with xbbg extras:\n"
        msg += f"    pip install xbbg[{backend.value}]"

        if raise_on_error:
            raise ImportError(msg) from None
        logger.warning(msg)
        return False

    # Version check.
    if min_version:
        version = _get_module_version(module)
        if version is None:
            logger.debug("Could not determine version for %s", module_name)
        elif version < min_version:
            msg = (
                f"Backend '{backend.value}' requires {package_name} >= "
                f"{_format_version(min_version)}, but version "
                f"{_format_version(version)} is installed.\n\n"
                f"To upgrade, run:\n"
                f"    pip install --upgrade {package_name}>={_format_version(min_version)}"
            )
            if raise_on_error:
                raise ValueError(msg)
            logger.warning(msg)
            return False

    return True


def get_available_backends() -> list[Backend]:
    """Return every :class:`Backend` whose package is currently importable."""
    return [b for b in Backend if is_backend_available(b)]


def print_backend_status() -> None:
    """Print a diagnostic table of all backends to the logger.

    Shows installed/missing status, current version, and minimum
    requirement for each backend.
    """
    logger.info("xbbg Backend Status")
    logger.info("=" * 60)
    logger.info("")

    for backend in Backend:
        module_name = MODULE_NAMES.get(backend, "")

        if backend in (Backend.NARWHALS, Backend.NARWHALS_LAZY, Backend.PYARROW):
            module = _get_module(backend) or __import__(module_name)
            version = _get_module_version(module)
            status = "OK (core)"
            version_info = f"v{_format_version(version)}" if version else ""
        elif is_backend_available(backend):
            module = __import__(module_name)
            version = _get_module_version(module)
            min_ver = MIN_VERSIONS.get(backend)

            if version and min_ver and version < min_ver:
                status = "OUTDATED"
                version_info = f"v{_format_version(version)} (need >={_format_version(min_ver)})"
            else:
                status = "OK"
                version_info = f"v{_format_version(version)}" if version else ""
        else:
            status = "NOT INSTALLED"
            package = PACKAGE_NAMES.get(backend, module_name or "?")
            version_info = f"pip install {package}"

        logger.info("  %s %s %s", f"{backend.value:15}", f"{status:15}", version_info)

    logger.info("")
    logger.info("=" * 60)


# =============================================================================
# Format Compatibility Checking
# =============================================================================


def is_format_supported(backend: Backend | str, fmt: Format | str) -> bool:
    """Check whether *backend* supports *fmt*.

    Args:
        backend: Backend to check.
        fmt: Output format to check.

    Returns:
        ``True`` if the format is supported.
    """
    if isinstance(backend, str):
        backend = Backend(backend)
    if isinstance(fmt, str):
        fmt = Format(fmt)
    return fmt in SUPPORTED_FORMATS.get(backend, frozenset())


def get_supported_formats(backend: Backend | str) -> frozenset[Format]:
    """Return the set of :class:`~xbbg.services.Format` variants supported by *backend*."""
    if isinstance(backend, str):
        backend = Backend(backend)
    return SUPPORTED_FORMATS.get(backend, frozenset({Format.LONG, Format.SEMI_LONG}))


def check_format_compatibility(
    backend: Backend | str,
    fmt: Format | str,
    *,
    raise_on_error: bool = True,
) -> bool:
    """Validate that *backend* supports *fmt*, with actionable messages.

    Args:
        backend: Backend to use.
        fmt: Desired output format.
        raise_on_error: Raise :class:`ValueError` on mismatch.

    Returns:
        ``True`` if compatible.

    Raises:
        ValueError: When *raise_on_error* and the combination is unsupported.
    """
    if isinstance(backend, str):
        backend = Backend(backend)
    if isinstance(fmt, str):
        fmt = Format(fmt)

    if is_format_supported(backend, fmt):
        return True

    supported = get_supported_formats(backend)
    supported_str = ", ".join(f.value for f in sorted(supported, key=lambda x: x.value))

    msg = (
        f"Backend '{backend.value}' does not support format '{fmt.value}'.\n\n"
        f"Supported formats for {backend.value}: {supported_str}\n\n"
    )

    if fmt in (Format.LONG_TYPED, Format.LONG_WITH_METADATA):
        msg += "Hint: LONG_TYPED and LONG_WITH_METADATA are v1.0 preview formats."

    if raise_on_error:
        raise ValueError(msg)

    logger.warning(msg)
    return False


def validate_backend_format(
    backend: Backend | str | None,
    fmt: Format | str | None,
    *,
    raise_on_error: bool = True,
) -> tuple[Backend, Format]:
    """Normalise and validate a backend/format pair.

    This is the main entry-point for API functions.  It:

    1. Converts string values to enums.
    2. Falls back to the session defaults (``set_backend`` / ``set_format``).
    3. Checks backend availability and version.
    4. Checks format compatibility.

    Args:
        backend: Backend enum, string, or ``None`` for the session default.
        fmt: Format enum, string, or ``None`` for the session default.
        raise_on_error: Raise on invalid combinations.

    Returns:
        A ``(Backend, Format)`` tuple of validated values.

    Raises:
        ImportError: Backend package missing.
        ValueError: Version too old or format unsupported.
    """
    # Lazy import to avoid circular dependency (blp → backend → blp).
    from xbbg.blp import get_backend as _get_backend

    # Normalise backend.
    if backend is None:
        backend = _get_backend() or Backend.NARWHALS
    elif isinstance(backend, str):
        backend = Backend(backend)

    # Normalise format.
    if fmt is None:
        fmt = Format.LONG
    elif isinstance(fmt, str):
        fmt = Format(fmt)

    # Validate.
    check_backend(backend, raise_on_error=raise_on_error)
    check_format_compatibility(backend, fmt, raise_on_error=raise_on_error)

    return backend, fmt
