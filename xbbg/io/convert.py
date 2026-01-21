"""Output conversion layer for xbbg.

This module provides functions to convert Arrow tables to various backends
and output formats (LONG, SEMI_LONG, WIDE).
"""

from __future__ import annotations

import contextlib
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.backend import Backend, Format

# =============================================================================
# Backend-agnostic DataFrame utilities
# =============================================================================


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

    # pandas DataFrame/Series
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
        return pd.DataFrame()

    # Filter out empty frames
    non_empty = [f for f in frames if not is_empty(f)]
    if not non_empty:
        return frames[0] if frames else pd.DataFrame()

    first = non_empty[0]

    # Detect backend from first frame
    frame_type = type(first).__module__

    if "polars" in frame_type:
        import polars as pl

        return pl.concat(non_empty)

    if "pyarrow" in frame_type:
        return pa.concat_tables(non_empty)

    if "pandas" in frame_type:
        return pd.concat(non_empty, ignore_index=True)

    # Try narwhals concat
    try:
        return nw.concat(non_empty)
    except Exception:
        pass

    # Fallback: convert to pandas
    pd_frames = [f.to_pandas() if hasattr(f, "to_pandas") else f for f in non_empty]
    return pd.concat(pd_frames, ignore_index=True)


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
    if isinstance(df, pa.Table):
        return df

    # polars DataFrame
    if hasattr(df, "to_arrow") and not isinstance(df, pd.DataFrame):
        return df.to_arrow()

    # polars LazyFrame - collect first
    if hasattr(df, "collect"):
        return df.collect().to_arrow()

    # narwhals DataFrame
    if hasattr(df, "to_arrow"):
        return df.to_arrow()

    # pandas DataFrame
    if isinstance(df, pd.DataFrame):
        return pa.Table.from_pandas(df)

    # Fallback
    return pa.Table.from_pandas(pd.DataFrame(df))


def to_pandas(df: Any) -> pd.DataFrame:
    """Convert any DataFrame to pandas.

    Parameters
    ----------
    df : Any
        DataFrame from any supported backend.

    Returns:
    -------
    pd.DataFrame
        Pandas DataFrame.
    """
    if isinstance(df, pd.DataFrame):
        return df

    if hasattr(df, "to_pandas"):
        return df.to_pandas()

    if hasattr(df, "collect"):
        # polars LazyFrame
        return df.collect().to_pandas()

    # Fallback
    return pd.DataFrame(df)


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

    frame_type = type(df).__module__

    # pandas DataFrame
    if "pandas" in frame_type or isinstance(df, pd.DataFrame):
        return df.rename(columns=rename_map)

    # polars DataFrame/LazyFrame
    if "polars" in frame_type:
        # polars uses .rename() but with different signature
        return df.rename(rename_map)

    # pyarrow Table
    if "pyarrow" in frame_type:
        # Get current column names
        names = df.column_names
        new_names = [rename_map.get(n, n) for n in names]
        return df.rename_columns(new_names)

    # narwhals DataFrame
    if hasattr(df, "rename"):
        return df.rename(rename_map)

    # Fallback: convert to pandas, rename, hope for the best
    if hasattr(df, "to_pandas"):
        return df.to_pandas().rename(columns=rename_map)

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
    """
    # Ensure backend is an enum (handle string values)
    if isinstance(backend, str):
        backend = Backend(backend)

    # Use value comparison for robustness across different import contexts
    backend_value = backend.value if isinstance(backend, Backend) else backend

    if backend_value == "narwhals":
        return nw_frame
    if backend_value == "pandas":
        # Use to_arrow() then to_pandas() to ensure consistent conversion
        # This avoids issues with narwhals to_native() returning the underlying type
        arrow_table = nw_frame.to_arrow()
        return arrow_table.to_pandas()
    if backend_value == "polars":
        import polars as pl

        arrow_table = nw_frame.to_arrow()
        return pl.from_arrow(arrow_table)
    if backend_value == "polars_lazy":
        import polars as pl

        arrow_table = nw_frame.to_arrow()
        return pl.from_arrow(arrow_table).lazy()
    if backend_value == "pyarrow":
        return nw_frame.to_arrow()
    if backend_value == "duckdb":
        import duckdb

        arrow_table = nw_frame.to_arrow()
        return duckdb.from_arrow(arrow_table)
    raise ValueError(f"Unsupported backend: {backend}")


def _apply_multiindex(
    df: nw.DataFrame,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
) -> Any:
    """Pivot a narwhals DataFrame to pandas with MultiIndex columns (ticker, field).

    This function is used for WIDE format output with pandas backend.

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


def to_output(
    arrow_table: pa.Table,
    backend: Backend,
    format: Format,
    ticker_col: str,
    date_col: str,
    field_cols: list[str],
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
        # Use string comparison for robustness
        backend_value = backend.value if isinstance(backend, Backend) else backend
        if backend_value == "pandas":
            return pd.DataFrame()
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
            # For LONG/SEMI_LONG, return as-is
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
        # Unpivot field columns to long format
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
        # For non-pandas backends, pivot to wide format
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
        # Pivot is not supported by all backends (e.g., pyarrow)
        # Fall back to pandas for pivot, then convert to target backend
        pdf = long_frame.to_pandas()
        pivoted = pdf.pivot(index=date_col, columns="ticker_field", values="value")
        pivoted = pivoted.reset_index()
        # Convert back to target backend
        if backend == Backend.NARWHALS:
            return nw.from_native(pivoted)
        return _convert_backend(nw.from_native(pivoted), backend)

    raise ValueError(f"Unsupported format: {format}")
