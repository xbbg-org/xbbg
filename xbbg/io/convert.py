"""Output conversion layer for xbbg.

This module provides functions to convert Arrow tables to various backends
and output formats (LONG, SEMI_LONG, WIDE).
"""

from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.backend import Backend, Format


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
            try:
                pdf[col] = pd.to_numeric(pdf[col])
            except (ValueError, TypeError):
                pass  # Keep original values if conversion fails

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
                    try:
                        pivoted[col] = pd.to_numeric(pivoted[col])
                    except (ValueError, TypeError):
                        pass  # Keep original values if conversion fails
                return pivoted
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
        # Create combined ticker_field column and pivot
        wide_frame = long_frame.with_columns((nw.col(ticker_col) + "_" + nw.col("field")).alias("ticker_field")).pivot(
            on="ticker_field",
            index=date_col,
            values="value",
        )
        return _convert_backend(wide_frame, backend)

    raise ValueError(f"Unsupported format: {format}")
