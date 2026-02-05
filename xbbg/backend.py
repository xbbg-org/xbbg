"""Backend and Format enums for xbbg v1 migration.

This module provides enums for selecting the data processing backend
and output format, matching the Rust v1 branch API for compatibility.

Also includes backend availability checking with helpful warnings when
a backend package is not installed or has an incompatible version.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import sys
from typing import Any
import warnings

logger = logging.getLogger(__name__)


class Backend(str, Enum):
    """Enum for selecting the data processing backend.

    The backend determines which library is used for data manipulation
    and storage. Each backend has different performance characteristics
    and memory usage patterns.

    Backends are categorized by their evaluation mode:

    **Eager backends** (full API support):
        - NARWHALS: Backend-agnostic DataFrame API
        - PANDAS: Most widely used DataFrame library
        - POLARS: High-performance Rust-based DataFrames
        - PYARROW: Apache Arrow columnar format
        - CUDF: GPU-accelerated DataFrames (NVIDIA RAPIDS)
        - MODIN: Distributed pandas-like DataFrames

    **Lazy backends** (deferred execution):
        - NARWHALS_LAZY: Narwhals with lazy evaluation
        - POLARS_LAZY: Polars LazyFrame for query optimization
        - DUCKDB: Embedded analytical SQL database
        - DASK: Parallel computing with task scheduling
        - IBIS: Portable DataFrame expressions (SQL backends)
        - PYSPARK: Apache Spark distributed DataFrames
        - SQLFRAME: SQL-based DataFrame abstraction

    Attributes:
        NARWHALS: Use Narwhals as the backend. Narwhals provides a unified
            DataFrame API that works across multiple backends (pandas, polars,
            etc.), enabling backend-agnostic code.
        NARWHALS_LAZY: Use Narwhals with lazy evaluation. Returns a LazyFrame
            that can be collected when needed.
        PANDAS: Use pandas as the backend. Pandas is the most widely used
            DataFrame library in Python with extensive ecosystem support.
            Best for compatibility with existing code and libraries.
        POLARS: Use Polars as the backend. Polars is a fast DataFrame library
            written in Rust, offering excellent performance for large datasets
            with eager evaluation.
        POLARS_LAZY: Use Polars with lazy evaluation. Lazy evaluation allows
            Polars to optimize the query plan before execution, potentially
            improving performance for complex operations.
        PYARROW: Use PyArrow as the backend. PyArrow provides efficient
            columnar data structures based on Apache Arrow, ideal for
            interoperability and zero-copy data sharing.
        DUCKDB: Use DuckDB as the backend. DuckDB is an embedded analytical
            database that excels at SQL queries and can efficiently process
            larger-than-memory datasets.
        CUDF: Use cuDF as the backend. cuDF is a GPU-accelerated DataFrame
            library from NVIDIA RAPIDS, offering massive speedups for
            data processing on compatible hardware.
        MODIN: Use Modin as the backend. Modin provides a drop-in replacement
            for pandas that parallelizes operations across all CPU cores,
            speeding up pandas workflows with minimal code changes.
        DASK: Use Dask as the backend. Dask provides parallel computing
            with task scheduling, enabling larger-than-memory computations
            and distributed processing. Returns a Dask DataFrame (lazy).
        IBIS: Use Ibis as the backend. Ibis provides portable DataFrame
            expressions that can execute on various SQL backends including
            DuckDB, PostgreSQL, BigQuery, and Spark. Returns an Ibis Table (lazy).
        PYSPARK: Use PySpark as the backend. PySpark provides distributed
            DataFrame processing on Apache Spark clusters, ideal for
            big data workloads. Returns a Spark DataFrame (lazy).
        SQLFRAME: Use SQLFrame as the backend. SQLFrame provides a SQL-based
            DataFrame abstraction that works with multiple SQL engines.
            Returns a SQLFrame DataFrame (lazy).
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


class Format(str, Enum):
    """Enum for selecting the output data format.

    The format determines how the data is structured in the resulting
    DataFrame. Different formats are suited for different analysis tasks.

    Attributes:
        LONG: Long format (default in v1). Each observation is a separate row
            with columns for ticker, field, date/time, and value. This is the
            most normalized form and is ideal for:
            - Time series analysis across multiple securities
            - Grouping and aggregation operations
            - Database storage and joins
            - Plotting with libraries that expect tidy data

        LONG_TYPED: Long format with typed value columns (v1.0 preview).
            Columns: ticker, field, value_f64, value_i64, value_str, value_bool, value_date, value_ts
            Each row populates one value column based on the field's data type.

        LONG_WITH_METADATA: Long format with string values and dtype metadata column (v1.0 preview).
            Columns: ticker, field, value, dtype
            The dtype column contains the Arrow type name (float64, int64, string, etc.)

        SEMI_LONG: Semi-long format. A hybrid format where each row represents
            a single timestamp for a single security, but different fields are
            in separate columns. This provides a balance between normalization
            and readability, useful for:
            - Comparing multiple fields for the same security/time
            - Calculations involving multiple fields (e.g., OHLC data)
            - Moderate denormalization for easier analysis

        WIDE: Wide format. Each row represents a single timestamp, with
            separate columns for each ticker-field combination. This is the
            most denormalized form, suited for:
            - Quick visual inspection of data
            - Cross-sectional analysis at specific time points
            - Correlation analysis between securities
            - Spreadsheet-style viewing
    """

    LONG = "long"
    LONG_TYPED = "long_typed"
    LONG_WITH_METADATA = "long_metadata"
    SEMI_LONG = "semi_long"
    WIDE = "wide"


@dataclass
class EngineConfig:
    """Configuration for the xbbg Engine (v1.0 preview).

    All settings have sensible defaults - you only need to specify what you want to change.

    Note: This configuration is a preview of the v1.0 API. In the current version,
    only host and port are used by connect(). The pool size settings will take
    effect in v1.0 with the Rust backend.

    Attributes:
        host: Bloomberg server host (default: "localhost")
        port: Bloomberg server port (default: 8194)
        request_pool_size: Number of pre-warmed request workers (default: 2).
        subscription_pool_size: Number of pre-warmed subscription sessions (default: 4).
    """

    host: str = "localhost"
    port: int = 8194
    request_pool_size: int = 2
    subscription_pool_size: int = 4


# Global configuration storage
_config: EngineConfig | None = None
_configured: bool = False


def configure(
    config: EngineConfig | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    request_pool_size: int | None = None,
    subscription_pool_size: int | None = None,
) -> None:
    """Configure the xbbg engine (v1.0 preview).

    This function provides forward-compatible configuration for xbbg v1.0.
    In the current version, only host and port affect behavior.

    Args:
        config: An EngineConfig object with all settings.
        host: Bloomberg server host (default: "localhost")
        port: Bloomberg server port (default: 8194)
        request_pool_size: Number of pre-warmed request workers (default: 2).
        subscription_pool_size: Number of pre-warmed subscription sessions (default: 4).
    """
    global _config, _configured

    if config is not None:
        _config = EngineConfig(
            host=host if host is not None else config.host,
            port=port if port is not None else config.port,
            request_pool_size=request_pool_size if request_pool_size is not None else config.request_pool_size,
            subscription_pool_size=subscription_pool_size
            if subscription_pool_size is not None
            else config.subscription_pool_size,
        )
    else:
        _config = EngineConfig(
            host=host if host is not None else "localhost",
            port=port if port is not None else 8194,
            request_pool_size=request_pool_size if request_pool_size is not None else 2,
            subscription_pool_size=subscription_pool_size if subscription_pool_size is not None else 4,
        )

    _configured = True

    if request_pool_size is not None or subscription_pool_size is not None:
        warnings.warn(
            "request_pool_size and subscription_pool_size are preview settings for xbbg v1.0. "
            "They will take effect when the Rust backend is available.",
            FutureWarning,
            stacklevel=2,
        )


def get_config() -> EngineConfig:
    """Get the current engine configuration."""
    if _config is None:
        return EngineConfig()
    return _config


# =============================================================================
# Backend Availability Checking
# =============================================================================

# Minimum version requirements for each backend (matching narwhals)
# Format: (major, minor, patch) - patch is optional
MIN_VERSIONS: dict[Backend, tuple[int, ...]] = {
    Backend.PANDAS: (2, 0),  # xbbg requires pandas 2.0+
    Backend.POLARS: (0, 20),
    Backend.POLARS_LAZY: (0, 20),
    Backend.PYARROW: (13, 0),  # narwhals minimum, xbbg requires 22.0
    Backend.DUCKDB: (1, 0),
    Backend.CUDF: (24, 10),
    Backend.MODIN: (0, 25),  # Recent stable version
    Backend.DASK: (2024, 1),
    Backend.IBIS: (6, 0),
    Backend.PYSPARK: (3, 5),
    Backend.SQLFRAME: (3, 22),
}

# Package names for pip install instructions
PACKAGE_NAMES: dict[Backend, str] = {
    Backend.PANDAS: "pandas",
    Backend.POLARS: "polars",
    Backend.POLARS_LAZY: "polars",
    Backend.PYARROW: "pyarrow",
    Backend.DUCKDB: "duckdb",
    Backend.CUDF: "cudf-cu12",  # CUDA 12 version
    Backend.MODIN: "modin[all]",
    Backend.DASK: "dask[dataframe]",
    Backend.IBIS: "ibis-framework",
    Backend.PYSPARK: "pyspark",
    Backend.SQLFRAME: "sqlframe",
}

# Module names to check in sys.modules (may differ from package name)
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


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    Args:
        version_str: Version string like "2.0.1", "0.20.4", "2024.8.1"

    Returns:
        Tuple of version components as integers.
    """
    # Strip any suffix like 'a1', 'b2', 'rc1', etc.
    version_str = version_str.split("+")[0]  # Remove local version
    version_str = version_str.split("a")[0]  # Remove alpha
    version_str = version_str.split("b")[0]  # Remove beta
    version_str = version_str.split("rc")[0]  # Remove rc

    parts = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            # Handle things like "1.0.dev0"
            break
    return tuple(parts)


def _format_version(version: tuple[int, ...]) -> str:
    """Format a version tuple as a string."""
    return ".".join(str(v) for v in version)


def _get_module(backend: Backend) -> Any | None:
    """Get a backend module if it's already imported.

    This follows narwhals' pattern of checking sys.modules without
    triggering an import. The module must be imported by user code first.

    Args:
        backend: The backend to check.

    Returns:
        The module if already imported, None otherwise.
    """
    module_name = MODULE_NAMES.get(backend)
    if module_name is None:
        return None
    return sys.modules.get(module_name)


def _get_module_version(module: Any) -> tuple[int, ...] | None:
    """Get the version of a module as a tuple.

    Args:
        module: The module to check.

    Returns:
        Version tuple or None if version cannot be determined.
    """
    version_str = getattr(module, "__version__", None)
    if version_str is None:
        # Some packages use VERSION instead
        version_str = getattr(module, "VERSION", None)
    if version_str is None:
        return None
    return _parse_version(str(version_str))


def is_backend_available(backend: Backend) -> bool:
    """Check if a backend is available (installed and importable).

    This performs an actual import attempt, unlike _get_module which only
    checks sys.modules.

    Args:
        backend: The backend to check.

    Returns:
        True if the backend is available, False otherwise.
    """
    # narwhals is always available (core dependency)
    if backend in (Backend.NARWHALS, Backend.NARWHALS_LAZY):
        return True

    # pyarrow is always available (core dependency)
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


def check_backend(backend: Backend, *, raise_on_error: bool = True) -> bool:
    """Check if a backend is available with the required version.

    This function checks if the requested backend package is installed
    and meets the minimum version requirements. If the package is not
    available or has an incompatible version, it provides helpful
    error messages with installation instructions.

    Args:
        backend: The backend to check.
        raise_on_error: If True, raise an error if the backend is not
            available. If False, return False and log a warning.

    Returns:
        True if the backend is available and meets version requirements.

    Raises:
        ImportError: If raise_on_error is True and the backend is not available.
        ValueError: If raise_on_error is True and the backend version is too old.
    """
    # narwhals and pyarrow are always available (core dependencies)
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

    # Try to import the module
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

    # Check version if we have a minimum requirement
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
    """Get a list of all currently available backends.

    This checks which backend packages are installed and can be imported.
    Useful for diagnostic purposes or auto-selecting a backend.

    Returns:
        List of available Backend enum values.
    """
    available = []
    for backend in Backend:
        if is_backend_available(backend):
            available.append(backend)
    return available


def print_backend_status() -> None:
    """Print the status of all backends for diagnostic purposes.

    Shows which backends are available, their versions, and minimum
    requirements. Useful for troubleshooting backend issues.
    """
    print("xbbg Backend Status")
    print("=" * 60)
    print()

    for backend in Backend:
        status = "?"
        version_info = ""
        module_name = MODULE_NAMES.get(backend, "")

        if backend in (Backend.NARWHALS, Backend.NARWHALS_LAZY, Backend.PYARROW):
            # Core dependencies - always available
            module = _get_module(backend) or __import__(module_name)
            version = _get_module_version(module)
            status = "OK (core)"
            if version:
                version_info = f"v{_format_version(version)}"
        elif is_backend_available(backend):
            module = __import__(module_name)
            version = _get_module_version(module)
            min_ver = MIN_VERSIONS.get(backend)

            if version and min_ver and version < min_ver:
                status = "OUTDATED"
                version_info = f"v{_format_version(version)} (need >={_format_version(min_ver)})"
            else:
                status = "OK"
                if version:
                    version_info = f"v{_format_version(version)}"
        else:
            status = "NOT INSTALLED"
            package = PACKAGE_NAMES.get(backend, module_name or "?")
            version_info = f"pip install {package}"

        print(f"  {backend.value:15} {status:15} {version_info}")

    print()
    print("=" * 60)


# =============================================================================
# Format Compatibility
# =============================================================================

# Supported formats per backend
# - LONG/SEMI_LONG: universally supported (tidy data)
# - WIDE: requires pivot operation, pandas MultiIndex or flattened columns
# - LONG_TYPED/LONG_WITH_METADATA: v1.0 preview formats
SUPPORTED_FORMATS: dict[Backend, set[Format]] = {
    # Eager backends - full format support
    Backend.PANDAS: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    Backend.POLARS: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    Backend.PYARROW: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    Backend.NARWHALS: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    Backend.CUDF: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    Backend.MODIN: {Format.LONG, Format.SEMI_LONG, Format.WIDE, Format.LONG_TYPED, Format.LONG_WITH_METADATA},
    # Lazy backends - no WIDE support (can't pivot lazy frames efficiently)
    Backend.NARWHALS_LAZY: {Format.LONG, Format.SEMI_LONG},
    Backend.POLARS_LAZY: {Format.LONG, Format.SEMI_LONG},
    Backend.DUCKDB: {Format.LONG, Format.SEMI_LONG},
    Backend.DASK: {Format.LONG, Format.SEMI_LONG},
    Backend.IBIS: {Format.LONG, Format.SEMI_LONG},
    Backend.PYSPARK: {Format.LONG, Format.SEMI_LONG},
    Backend.SQLFRAME: {Format.LONG, Format.SEMI_LONG},
}


def is_format_supported(backend: Backend, format: Format) -> bool:
    """Check if a format is supported by a backend.

    Args:
        backend: The backend to check.
        format: The format to check.

    Returns:
        True if the format is supported by the backend.
    """
    supported = SUPPORTED_FORMATS.get(backend, set())
    return format in supported


def get_supported_formats(backend: Backend) -> set[Format]:
    """Get the set of formats supported by a backend.

    Args:
        backend: The backend to check.

    Returns:
        Set of supported Format values.
    """
    return SUPPORTED_FORMATS.get(backend, {Format.LONG, Format.SEMI_LONG})


def check_format_compatibility(backend: Backend, format: Format, *, raise_on_error: bool = True) -> bool:
    """Check if a backend supports a format, with helpful error messages.

    Args:
        backend: The backend to use.
        format: The desired output format.
        raise_on_error: If True, raise ValueError for unsupported combinations.

    Returns:
        True if compatible, False otherwise.

    Raises:
        ValueError: If raise_on_error is True and format is not supported.
    """
    if is_format_supported(backend, format):
        return True

    supported = get_supported_formats(backend)
    supported_str = ", ".join(f.value for f in sorted(supported, key=lambda x: x.value))

    msg = (
        f"Backend '{backend.value}' does not support format '{format.value}'.\n\n"
        f"Supported formats for {backend.value}: {supported_str}\n\n"
    )

    if format == Format.WIDE:
        msg += (
            "Hint: WIDE format requires pivot operations which are not efficient "
            "for lazy backends. Consider using SEMI_LONG format instead, or switch "
            "to an eager backend like 'pandas' or 'polars'."
        )
    elif format in (Format.LONG_TYPED, Format.LONG_WITH_METADATA):
        msg += "Hint: LONG_TYPED and LONG_WITH_METADATA are v1.0 preview formats."

    if raise_on_error:
        raise ValueError(msg)

    logger.warning(msg)
    return False


def validate_backend_format(
    backend: Backend | str | None,
    format: Format | str | None,
    *,
    raise_on_error: bool = True,
) -> tuple[Backend, Format]:
    """Validate and normalize backend and format parameters.

    This is the main validation function that should be called at the start
    of API functions. It:
    1. Converts string values to enums
    2. Checks backend availability
    3. Checks format compatibility
    4. Returns validated enum values

    Args:
        backend: Backend enum, string value, or None for default.
        format: Format enum, string value, or None for default.
        raise_on_error: If True, raise errors for invalid combinations.

    Returns:
        Tuple of (Backend, Format) validated enum values.

    Raises:
        ImportError: If backend package is not installed.
        ValueError: If backend version is too old or format not supported.
    """
    # Import here to avoid circular imports
    from xbbg.options import get_backend, get_format

    # Normalize backend
    if backend is None:
        backend = get_backend()
    elif isinstance(backend, str):
        backend = Backend(backend)

    # Normalize format
    if format is None:
        format = get_format()
    elif isinstance(format, str):
        format = Format(format)

    # Check backend availability
    check_backend(backend, raise_on_error=raise_on_error)

    # Check format compatibility
    check_format_compatibility(backend, format, raise_on_error=raise_on_error)

    return backend, format
