"""Backend and Format enums for xbbg v1 migration.

This module provides enums for selecting the data processing backend
and output format, matching the Rust v1 branch API for compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import warnings


class Backend(str, Enum):
    """Enum for selecting the data processing backend.

    The backend determines which library is used for data manipulation
    and storage. Each backend has different performance characteristics
    and memory usage patterns.

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
    """

    NARWHALS = "narwhals"
    NARWHALS_LAZY = "narwhals_lazy"
    PANDAS = "pandas"
    POLARS = "polars"
    POLARS_LAZY = "polars_lazy"
    PYARROW = "pyarrow"
    DUCKDB = "duckdb"


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
