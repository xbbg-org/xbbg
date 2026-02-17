"""Output conversion layer for xbbg.

This module provides functions to convert Arrow tables to various backends
and output formats (LONG, SEMI_LONG, WIDE).

Note: pandas is an optional dependency. It is only required when:
- Using backend="pandas"
- Using format="wide" (which requires pandas MultiIndex)
"""

from __future__ import annotations

import contextlib
from typing import Any, TypeVar

import narwhals as nw
from narwhals.typing import IntoFrame
import pyarrow as pa

from xbbg.backend import Backend, Format

# Type variable for generic DataFrame operations
FrameT = TypeVar("FrameT", bound=IntoFrame)

# =============================================================================
# Backend-agnostic DataFrame utilities
# =============================================================================


def _is_pandas_frame(obj: Any) -> bool:
    """Check if object is a pandas DataFrame without importing pandas."""
    return type(obj).__module__.startswith("pandas")


def _is_polars_frame(obj: Any) -> bool:
    """Check if object is a polars DataFrame/LazyFrame without importing polars."""
    return "polars" in type(obj).__module__


def _is_pyarrow_table(obj: Any) -> bool:
    """Check if object is a PyArrow Table."""
    return isinstance(obj, pa.Table)


def is_empty(df: Any) -> bool:
    """Check if a DataFrame is empty, works with any backend.

    Parameters
    ----------
    df : Any
        DataFrame from any supported backend (pandas, polars, pyarrow, etc.)

    Returns:
    -------
    bool
        True if the DataFrame has no rows, False otherwise.
    """
    if df is None:
        return True

    # pandas DataFrame/Series (has .empty property)
    if hasattr(df, "empty"):
        return df.empty

    # polars DataFrame/LazyFrame
    if hasattr(df, "is_empty"):
        # polars LazyFrame needs to be collected first, but is_empty() works on DataFrame
        if hasattr(df, "collect"):
            # It's a LazyFrame - check shape instead to avoid collecting
            return False  # LazyFrames are never "empty" until collected
        return df.is_empty()

    # pyarrow Table
    if hasattr(df, "num_rows"):
        return df.num_rows == 0

    # narwhals DataFrame
    if hasattr(df, "shape"):
        return df.shape[0] == 0

    # Fallback: try len()
    try:
        return len(df) == 0
    except TypeError:
        return False


def concat_frames(frames: list[Any], backend: Backend | None = None) -> Any:
    """Concatenate DataFrames, works with any backend.

    Parameters
    ----------
    frames : list[Any]
        List of DataFrames to concatenate.
    backend : Backend | None
        Target backend. If None, inferred from first frame.

    Returns:
    -------
    Any
        Concatenated DataFrame in the same backend as input.
    """
    if not frames:
        return pa.table({})

    # Filter out empty frames
    non_empty = [f for f in frames if not is_empty(f)]
    if not non_empty:
        return frames[0] if frames else pa.table({})

    first = non_empty[0]

    # Detect backend from first frame
    if _is_polars_frame(first):
        import polars as pl

        return pl.concat(non_empty)

    if _is_pyarrow_table(first):
        return pa.concat_tables(non_empty)

    if _is_pandas_frame(first):
        import pandas as pd

        # Preserve index (important for BDS data where ticker is the index)
        return pd.concat(non_empty, ignore_index=False)

    # Try narwhals concat
    try:
        return nw.concat(non_empty)
    except Exception:
        pass

    # Fallback: convert to arrow and concat
    arrow_frames = [f.to_arrow() if hasattr(f, "to_arrow") else pa.table({}) for f in non_empty]
    return pa.concat_tables(arrow_frames)


def to_pandas(df: Any) -> Any:
    """Convert any DataFrame to pandas DataFrame.

    Parameters
    ----------
    df : Any
        DataFrame from any supported backend (pandas, polars, pyarrow, narwhals).

    Returns:
    -------
    pd.DataFrame
        pandas DataFrame.

    Note:
        Requires pandas to be installed. This function is provided for
        compatibility with code that needs pandas-specific operations.
    """
    import pandas as pd

    if df is None:
        return pd.DataFrame()

    # Already pandas
    if _is_pandas_frame(df):
        return df

    # polars DataFrame/LazyFrame
    if _is_polars_frame(df):
        if hasattr(df, "collect"):  # LazyFrame
            return df.collect().to_pandas()
        return df.to_pandas()

    # pyarrow Table
    if _is_pyarrow_table(df):
        return df.to_pandas()

    # narwhals DataFrame
    if hasattr(df, "to_pandas"):
        return df.to_pandas()

    # Fallback - try to wrap in narwhals and convert
    try:
        return nw.from_native(df).to_pandas()
    except Exception:
        return pd.DataFrame()


def to_arrow(df: Any) -> pa.Table:
    """Convert any DataFrame to PyArrow Table.

    Parameters
    ----------
    df : Any
        DataFrame from any supported backend.

    Returns:
    -------
    pa.Table
        PyArrow Table.
    """
    if _is_pyarrow_table(df):
        return df

    # Has to_arrow method (polars, narwhals, etc.)
    if hasattr(df, "to_arrow") and not _is_pandas_frame(df):
        return df.to_arrow()

    # polars LazyFrame - collect first
    if hasattr(df, "collect"):
        return df.collect().to_arrow()

    # pandas DataFrame - use PyArrow's from_pandas
    if _is_pandas_frame(df):
        return pa.Table.from_pandas(df)

    # narwhals DataFrame
    if hasattr(df, "to_arrow"):
        return df.to_arrow()

    # Fallback - wrap in narwhals and convert
    try:
        return nw.from_native(df).to_arrow()
    except Exception:
        # Last resort - try to create arrow table from dict-like
        return pa.table({})


def rename_columns(df: Any, rename_map: dict[str, str]) -> Any:
    """Rename columns in a DataFrame, works with any backend.

    Parameters
    ----------
    df : Any
        DataFrame from any supported backend.
    rename_map : dict[str, str]
        Mapping of old column names to new column names.

    Returns:
    -------
    Any
        DataFrame with renamed columns in the same backend as input.
    """
    if df is None or is_empty(df):
        return df

    # pandas DataFrame
    if _is_pandas_frame(df):
        return df.rename(columns=rename_map)

    # polars DataFrame/LazyFrame
    if _is_polars_frame(df):
        return df.rename(rename_map)

    # pyarrow Table
    if _is_pyarrow_table(df):
        names = df.column_names
        new_names = [rename_map.get(n, n) for n in names]
        return df.rename_columns(new_names)

    # narwhals DataFrame
    if hasattr(df, "rename"):
        return df.rename(rename_map)

    # Fallback: try to use narwhals
    try:
        nw_frame = nw.from_native(df)
        return nw_frame.rename(rename_map)
    except Exception:
        return df


def _convert_backend(nw_frame: nw.DataFrame, backend: Backend) -> Any:
    """Convert a narwhals DataFrame to the requested backend.

    Parameters
    ----------
    nw_frame : nw.DataFrame
        The narwhals DataFrame to convert.
    backend : Backend
        The target backend to convert to.

    Returns:
    -------
    Any
        The DataFrame in the requested backend format.

    Raises:
    ------
    ValueError
        If an unsupported backend is specified.
    ImportError
        If the required backend package is not installed.

    Supported Backends:
    ------------------
    Eager (full API):
        - narwhals: Returns narwhals DataFrame (passthrough)
        - pandas: Returns pandas DataFrame
        - polars: Returns polars DataFrame
        - pyarrow: Returns PyArrow Table
        - cudf: Returns cuDF DataFrame (GPU-accelerated)
        - modin: Returns Modin DataFrame (distributed pandas)

    Lazy (deferred execution):
        - narwhals_lazy: Returns narwhals LazyFrame
        - polars_lazy: Returns polars LazyFrame
        - duckdb: Returns DuckDB relation
        - dask: Returns Dask DataFrame
        - ibis: Returns Ibis Table expression
        - pyspark: Returns PySpark DataFrame
        - sqlframe: Returns SQLFrame DataFrame
    """
    from xbbg.backend import check_backend

    # Ensure backend is an enum (handle string values)
    if isinstance(backend, str):
        backend = Backend(backend)

    # Check backend availability (raises ImportError if not installed)
    check_backend(backend, raise_on_error=True)

    # Use value comparison for robustness across different import contexts
    backend_value = backend.value if isinstance(backend, Backend) else backend

    # Get Arrow table for conversions
    arrow_table = nw_frame.to_arrow()

    # =========================================================================
    # Eager backends (full API support)
    # =========================================================================
    if backend_value == "narwhals":
        return nw_frame

    if backend_value == "pandas":
        return nw_frame.to_pandas()

    if backend_value == "polars":
        import polars as pl

        return pl.from_arrow(arrow_table)

    if backend_value == "pyarrow":
        return arrow_table

    if backend_value == "cudf":
        import cudf

        return cudf.DataFrame.from_arrow(arrow_table)

    if backend_value == "modin":
        import modin.pandas as mpd

        # Modin can read from Arrow via pandas conversion
        # (Modin wraps pandas operations)
        return mpd.DataFrame(arrow_table.to_pandas())

    # =========================================================================
    # Lazy backends (deferred execution)
    # =========================================================================
    if backend_value == "narwhals_lazy":
        # Convert to polars lazy via narwhals
        import polars as pl

        return nw.from_native(pl.from_arrow(arrow_table).lazy())

    if backend_value == "polars_lazy":
        import polars as pl

        return pl.from_arrow(arrow_table).lazy()

    if backend_value == "duckdb":
        import duckdb

        return duckdb.from_arrow(arrow_table)

    if backend_value == "dask":
        import dask.dataframe as dd

        # Dask can be created from pandas DataFrame
        pdf = arrow_table.to_pandas()
        return dd.from_pandas(pdf, npartitions=1)

    if backend_value == "ibis":
        import ibis

        # Create an in-memory Ibis table from Arrow using memtable
        # This creates a lazy table expression that can be computed on any backend
        return ibis.memtable(arrow_table)

    if backend_value == "pyspark":
        from pyspark.sql import SparkSession

        # Get or create Spark session
        spark = SparkSession.builder.getOrCreate()
        # Convert Arrow to Spark DataFrame
        pdf = arrow_table.to_pandas()
        return spark.createDataFrame(pdf)

    if backend_value == "sqlframe":
        # SQLFrame wraps various SQL engines
        # Use DuckDB backend for in-memory operations
        from sqlframe.duckdb import DuckDBSession

        session = DuckDBSession()
        pdf = arrow_table.to_pandas()
        return session.createDataFrame(pdf)

    raise ValueError(f"Unsupported backend: {backend}")


def _apply_multiindex(
    df: nw.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
) -> Any:
    """Pivot a narwhals DataFrame to pandas with MultiIndex columns (ticker, field).

    This function is used for WIDE format output with pandas backend.
    Requires pandas to be installed.

    Parameters
    ----------
    df : nw.DataFrame
        The narwhals DataFrame in semi-long format.
    ticker_col : str
        Name of the column containing ticker symbols.
    date_col : str
        Name of the column containing dates/timestamps.
    field_cols : List[str]
        List of field column names to pivot.

    Returns:
    -------
    pd.DataFrame
        A pandas DataFrame with MultiIndex columns (ticker, field) and
        date as the index.
    """
    import pandas as pd

    pdf = df.to_pandas()

    # Convert field columns to numeric where possible (values may come as strings from pipeline)
    for col in field_cols:
        if col in pdf.columns:
            with contextlib.suppress(ValueError, TypeError):
                pdf[col] = pd.to_numeric(pdf[col])

    # Get unique tickers
    tickers = pdf[ticker_col].unique()

    # Build MultiIndex columns DataFrame
    frames = []
    for ticker in tickers:
        ticker_data = pdf[pdf[ticker_col] == ticker].set_index(date_col)[field_cols]
        ticker_data.columns = pd.MultiIndex.from_product([[ticker], field_cols], names=[ticker_col, "field"])
        frames.append(ticker_data)

    if not frames:
        # Return empty DataFrame with proper structure
        return pd.DataFrame()

    return pd.concat(frames, axis=1)


def _pivot_reference_data_wide(nw_frame: nw.DataFrame, ticker_col: str, backend: Backend) -> Any:
    """Pivot reference data to wide format.

    Requires pandas for the pivot operation.

    Parameters
    ----------
    nw_frame : nw.DataFrame
        The narwhals DataFrame with ticker, field, value columns.
    ticker_col : str
        Name of the column containing ticker symbols.
    backend : Backend
        The target backend to convert to.

    Returns:
    -------
    Any
        Pivoted DataFrame in the requested backend format.
    """
    import pandas as pd

    pdf = nw_frame.to_pandas()
    pivoted = pdf.pivot(index=ticker_col, columns="field", values="value")

    # Flatten column names if they're a simple Index
    if isinstance(pivoted.columns, pd.Index) and not isinstance(pivoted.columns, pd.MultiIndex):
        pivoted.columns = pivoted.columns.tolist()

    # Convert numeric columns to numeric types
    for col in pivoted.columns:
        with contextlib.suppress(ValueError, TypeError):
            pivoted[col] = pd.to_numeric(pivoted[col])

    # Convert to requested backend (pivoted is pandas with ticker as index)
    if backend == Backend.PANDAS:
        return pivoted

    # For other backends, reset index and convert
    pivoted_reset = pivoted.reset_index()
    return _convert_backend(nw.from_native(pivoted_reset), backend)


def _pivot_wide_non_pandas(
    nw_frame: nw.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
    backend: Backend,
) -> Any:
    """Pivot to wide format for non-pandas backends.

    Requires pandas for the pivot operation, then converts to target backend.

    Parameters
    ----------
    nw_frame : nw.DataFrame
        The narwhals DataFrame in semi-long format.
    ticker_col : str
        Name of the column containing ticker symbols.
    date_col : str
        Name of the column containing dates/timestamps.
    field_cols : list[str]
        List of field column names.
    backend : Backend
        The target backend to convert to.

    Returns:
    -------
    Any
        Pivoted DataFrame in the requested backend format.
    """
    # First unpivot, then pivot by ticker
    long_frame = nw_frame.unpivot(
        on=field_cols,
        index=[ticker_col, date_col],
        variable_name="field",
        value_name="value",
    )
    # Create combined ticker_field column using concat_str
    # (+ operator fails with pyarrow backend)
    long_frame = long_frame.with_columns(
        nw.concat_str([nw.col(ticker_col), nw.col("field")], separator="_").alias("ticker_field")
    )
    # Pivot using pandas (most reliable for this operation)
    pdf = long_frame.to_pandas()
    pivoted = pdf.pivot(index=date_col, columns="ticker_field", values="value")
    pivoted = pivoted.reset_index()

    # Convert back to target backend
    if backend == Backend.NARWHALS:
        return nw.from_native(pivoted)
    return _convert_backend(nw.from_native(pivoted), backend)


def _classify_arrow_dtype(arrow_type: pa.DataType) -> str:
    """Map an Arrow type to a LONG_TYPED value-column suffix.

    Returns one of: 'f64', 'i64', 'str', 'bool', 'date', 'ts'.
    """
    if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
        return "f64"
    if pa.types.is_integer(arrow_type):
        return "i64"
    if pa.types.is_boolean(arrow_type):
        return "bool"
    if pa.types.is_date(arrow_type):
        return "date"
    if pa.types.is_timestamp(arrow_type):
        return "ts"
    # string, binary, large_string, etc.
    return "str"


# Canonical column order for LONG_TYPED value columns
_TYPED_VALUE_COLS = ["value_f64", "value_i64", "value_str", "value_bool", "value_date", "value_ts"]


def _to_long_typed(
    nw_frame: nw.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
    backend: Backend,
) -> Any:
    """Unpivot to LONG_TYPED format with one value column per Arrow type.

    Output columns: ticker, date, field, value_f64, value_i64, value_str,
    value_bool, value_date, value_ts.  Each row populates exactly one
    typed value column; the rest are null.
    """
    import pandas as pd

    arrow_table = nw_frame.to_arrow()
    schema = arrow_table.schema

    # Build per-field classification
    field_type_map: dict[str, str] = {}
    for col_name in field_cols:
        idx = schema.get_field_index(col_name)
        arrow_type = schema.field(idx).type if idx >= 0 else pa.string()
        field_type_map[col_name] = _classify_arrow_dtype(arrow_type)

    pdf = nw_frame.to_pandas()
    rows: list[dict[str, Any]] = []
    index_cols = [ticker_col, date_col]

    for _, row in pdf.iterrows():
        base = {c: row[c] for c in index_cols}
        for field_name in field_cols:
            entry = {**base, "field": field_name}
            # Initialize all value columns to None
            for vc in _TYPED_VALUE_COLS:
                entry[vc] = None
            # Populate the matching value column
            suffix = field_type_map[field_name]
            entry[f"value_{suffix}"] = row[field_name]
            rows.append(entry)

    result = pd.DataFrame(rows, columns=index_cols + ["field"] + _TYPED_VALUE_COLS)
    return _convert_backend(nw.from_native(result), backend)


def _to_long_with_metadata(
    nw_frame: nw.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
    backend: Backend,
) -> Any:
    """Unpivot to LONG_WITH_METADATA format: string value + dtype column.

    Output columns: ticker, date, field, value, dtype.
    The *dtype* column contains the Arrow type name of the original column
    (e.g. ``float64``, ``int64``, ``large_string``).
    """
    arrow_table = nw_frame.to_arrow()
    schema = arrow_table.schema

    # Build per-field Arrow type name map
    field_dtype_map: dict[str, str] = {}
    for col_name in field_cols:
        idx = schema.get_field_index(col_name)
        arrow_type = schema.field(idx).type if idx >= 0 else pa.string()
        field_dtype_map[col_name] = str(arrow_type)

    # Unpivot to long (cast all to string so the merge always works)
    cast_exprs = [nw.col(c).cast(nw.String).alias(c) for c in field_cols]
    long_frame = nw_frame.with_columns(cast_exprs).unpivot(
        on=field_cols,
        index=[ticker_col, date_col],
        variable_name="field",
        value_name="value",
    )

    # Add dtype column by mapping field name -> Arrow type string
    pdf = long_frame.to_pandas()
    pdf["dtype"] = pdf["field"].map(field_dtype_map)
    return _convert_backend(nw.from_native(pdf), backend)


def to_output(
    arrow_table: pa.Table,
    backend: Backend,
    format: Format,
    ticker_col: str,
    date_col: str,
    field_cols: list[str] | None = None,
) -> Any:
    """Convert an Arrow table to the requested backend and format.

    This is the main conversion function that applies format transformation
    and backend conversion.

    Parameters
    ----------
    arrow_table : pa.Table
        The input Arrow table to convert.
    backend : Backend
        The target backend to convert to.
    format : Format
        The output format (LONG, SEMI_LONG, or WIDE).
    ticker_col : str
        Name of the column containing ticker symbols.
    date_col : str
        Name of the column containing dates/timestamps.
    field_cols : List[str]
        List of field column names.

    Returns:
    -------
    Any
        The converted DataFrame in the requested backend and format.

    Raises:
    ------
    ValueError
        If an unsupported format is specified.
    """
    # Handle empty table
    if arrow_table.num_rows == 0:
        return _convert_backend(nw.from_native(pa.table({})), backend)

    # Wrap arrow_table with narwhals
    nw_frame = nw.from_native(arrow_table)
    columns = nw_frame.columns

    # Check if expected columns exist for format transformation
    has_ticker_col = ticker_col in columns
    has_date_col = date_col in columns

    # Handle reference data (BDP/BDS) which has ticker but no date column
    if has_ticker_col and not has_date_col:
        # Reference data case - check if it's already in long format (ticker, field, value)
        if "field" in columns and "value" in columns:
            if format == Format.WIDE:
                # Pivot reference data: ticker as index, fields as columns
                # This requires pandas for the pivot operation
                return _pivot_reference_data_wide(nw_frame, ticker_col, backend)
            # For LONG/SEMI_LONG, return as-is
            return _convert_backend(nw_frame, backend)

        # BDS data case: has ticker, field, and data columns (no 'value' column)
        # This is block data like INDX_MEMBERS which returns structured array data
        if "field" in columns:
            if format == Format.WIDE or format is None:
                # v0.10.x backward compatible format:
                # - Drop 'field' column (it's redundant for single-field BDS queries)
                # - Use ticker as index (for pandas) or column (for other backends)
                # Note: Column names are already snake_case from BlockDataTransformer
                pdf = nw_frame.to_pandas()

                # Drop the field column
                if "field" in pdf.columns:
                    pdf = pdf.drop(columns=["field"])

                # Convert to requested backend
                if backend == Backend.PANDAS:
                    # For pandas: set ticker as index (v0.10.x behavior)
                    if ticker_col in pdf.columns:
                        pdf = pdf.set_index(ticker_col)
                        pdf.index.name = None  # Remove index name for cleaner output
                    return pdf
                # For other backends: keep ticker as a column
                return _convert_backend(nw.from_native(pdf), backend)

            # For LONG format, return as-is (new v0.11.x behavior)
            return _convert_backend(nw_frame, backend)

        # Data has ticker but no standard field/value structure - passthrough
        return _convert_backend(nw_frame, backend)

    if not has_ticker_col or not has_date_col:
        # Data doesn't have expected structure (e.g., BQL results)
        # Just convert to requested backend without format transformation
        return _convert_backend(nw_frame, backend)

    # Infer field columns if not provided
    if field_cols is None:
        field_cols = [c for c in columns if c not in (ticker_col, date_col)]

    if format == Format.LONG:
        # Unpivot field columns to long format.
        # When all fields share a compatible type (e.g. all numeric), the unpivot
        # preserves the native dtype.  When types are mixed (e.g. tick data with
        # float 'value' + string 'typ'/'cond'/'exch'), Arrow cannot merge them,
        # so we fall back to casting every field column to string first.
        try:
            nw_frame = nw_frame.unpivot(
                on=field_cols,
                index=[ticker_col, date_col],
                variable_name="field",
                value_name="value",
            )
        except Exception:
            cast_exprs = [nw.col(c).cast(nw.String).alias(c) for c in field_cols]
            nw_frame = nw_frame.with_columns(cast_exprs)
            nw_frame = nw_frame.unpivot(
                on=field_cols,
                index=[ticker_col, date_col],
                variable_name="field",
                value_name="value",
            )
        return _convert_backend(nw_frame, backend)

    if format == Format.SEMI_LONG:
        # Passthrough - no transformation needed
        return _convert_backend(nw_frame, backend)

    if format == Format.WIDE:
        # For WIDE format, apply MultiIndex for pandas
        if backend == Backend.PANDAS:
            return _apply_multiindex(nw_frame, ticker_col, date_col, field_cols)
        # For non-pandas backends, pivot to wide format (requires pandas for pivot)
        return _pivot_wide_non_pandas(nw_frame, ticker_col, date_col, field_cols, backend)

    if format == Format.LONG_TYPED:
        return _to_long_typed(nw_frame, ticker_col, date_col, field_cols, backend)

    if format == Format.LONG_WITH_METADATA:
        return _to_long_with_metadata(nw_frame, ticker_col, date_col, field_cols, backend)

    raise ValueError(f"Unsupported format: {format}")
