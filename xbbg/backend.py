"""
Backend and Format enums for xbbg v1 migration.

This module provides enums for selecting the data processing backend
and output format, matching the Rust v1 branch API for compatibility.
"""

from enum import Enum


class Backend(str, Enum):
    """
    Enum for selecting the data processing backend.

    The backend determines which library is used for data manipulation
    and storage. Each backend has different performance characteristics
    and memory usage patterns.

    Attributes:
        NARWHALS: Use Narwhals as the backend. Narwhals provides a unified
            DataFrame API that works across multiple backends (pandas, polars,
            etc.), enabling backend-agnostic code.
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
    PANDAS = "pandas"
    POLARS = "polars"
    POLARS_LAZY = "polars_lazy"
    PYARROW = "pyarrow"
    DUCKDB = "duckdb"


class Format(str, Enum):
    """
    Enum for selecting the output data format.

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
    SEMI_LONG = "semi_long"
    WIDE = "wide"
