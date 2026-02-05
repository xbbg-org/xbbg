"""Earnings data utilities.

This module provides earnings breakdown functionality.
"""

from __future__ import annotations

from typing import Any

import narwhals as nw
import pyarrow as pa

from xbbg.api.reference import bds
from xbbg.backend import Backend, Format
from xbbg.io.convert import _convert_backend, is_empty
from xbbg.options import get_backend

__all__ = ["earning"]


def _earning_pct(rows: list[dict[str, Any]], yr: str) -> list[dict[str, Any]]:
    """Calculate % of earnings by year.

    Pure Python implementation without pandas dependency.

    Args:
        rows: List of row dictionaries with 'level' and year columns.
        yr: Year column name (e.g., 'fy2017').

    Returns:
        Updated rows with percentage column added.
    """
    pct_col = f"{yr}_pct"

    # Initialize pct column
    for row in rows:
        row[pct_col] = None

    # Calculate level 1 percentage
    level_1_rows = [r for r in rows if r.get("level") == 1]
    if level_1_rows:
        level_1_sum = sum(r.get(yr, 0) or 0 for r in level_1_rows)
        if level_1_sum != 0:
            for r in level_1_rows:
                val = r.get(yr, 0) or 0
                r[pct_col] = 100 * val / level_1_sum

    # Calculate level 2 percentage (grouped by level 1 parent)
    # Iterate backwards to group level 2 rows by their level 1 parent
    level_2_group = []

    for i in range(len(rows) - 1, -1, -1):
        row_level = rows[i].get("level", 0)
        if row_level > 2:
            continue
        if row_level == 1:
            if level_2_group:
                group_sum = sum(r.get(yr, 0) or 0 for r in level_2_group)
                if group_sum != 0:
                    for r in level_2_group:
                        val = r.get(yr, 0) or 0
                        r[pct_col] = 100 * val / group_sum
            level_2_group = []
        if row_level == 2:
            level_2_group.append(rows[i])

    # Handle remaining level 2 positions at the beginning
    if level_2_group:
        group_sum = sum(r.get(yr, 0) or 0 for r in level_2_group)
        if group_sum != 0:
            for r in level_2_group:
                val = r.get(yr, 0) or 0
                r[pct_col] = 100 * val / group_sum

    return rows


def earning(
    ticker: str,
    by: str = "Geo",
    typ: str = "Revenue",
    ccy: str | None = None,
    level: int | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> Any:
    """Earning exposures by Geo or Products.

    Args:
        ticker: ticker name
        by: [G(eo), P(roduct)]
        typ: type of earning, start with `PG_` in Bloomberg FLDS - default `Revenue`
            `Revenue` - Revenue of the company
            `Operating_Income` - Operating Income (also named as EBIT) of the company
            `Assets` - Assets of the company
            `Gross_Profit` - Gross profit of the company
            `Capital_Expenditures` - Capital expenditures of the company
        ccy: currency of earnings
        level: hierarchy level of earnings
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Additional overrides such as fiscal year and periods.

    Returns:
        DataFrame.
    """
    kwargs.pop("raw", None)
    ovrd = "G" if by[0].upper() == "G" else "P"
    new_kw = {"Product_Geo_Override": ovrd}

    year = kwargs.pop("year", None)
    periods = kwargs.pop("periods", None)
    if year:
        kwargs["Eqy_Fund_Year"] = year
    if periods:
        kwargs["Number_Of_Periods"] = periods

    # Get header and data using narwhals backend
    header = bds(
        tickers=ticker,
        flds="PG_Bulk_Header",
        use_port=False,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **new_kw,
        **kwargs,
    )
    if ccy:
        kwargs["Eqy_Fund_Crncy"] = ccy
    if level:
        kwargs["PG_Hierarchy_Level"] = level
    data = bds(
        tickers=ticker,
        flds=f"PG_{typ}",
        use_port=False,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **new_kw,
        **kwargs,
    )

    actual_backend = backend if backend is not None else get_backend()

    if is_empty(data) or is_empty(header):
        return _convert_backend(nw.from_native(pa.table({})), actual_backend)

    # Extract header values from first row using narwhals
    header_first = header.select([c for c in header.columns if c not in ("ticker", "field")]).row(0, named=True)

    if not header_first:
        return _convert_backend(nw.from_native(pa.table({})), actual_backend)

    # Build header values list
    header_values = [
        str(val).lower().replace(" ", "_").replace("_20", "20") for val in header_first.values() if val is not None
    ]

    # Get data columns (excluding ticker/field)
    data_cols = [c for c in data.columns if c not in ("ticker", "field")]

    if len(data_cols) != len(header_values):
        raise ValueError(f"Inconsistent shape: data has {len(data_cols)} columns, header has {len(header_values)}")

    # Build rename mapping and apply using narwhals
    col_mapping = dict(zip(data_cols, header_values, strict=False))

    # Drop ticker/field columns and rename remaining columns
    renamed_df = data.drop(["ticker", "field"]).rename(col_mapping)

    # Convert to rows for percentage calculation
    renamed_rows = list(renamed_df.iter_rows(named=True))

    if not renamed_rows:
        return _convert_backend(nw.from_native(pa.table({})), actual_backend)

    # Identify fiscal year columns
    fy_cols = [c for c in renamed_df.columns if c.startswith("fy") and not c.endswith("_pct")]

    # Convert level to int, filling nulls with 0
    if "level" in renamed_df.columns:
        renamed_df = renamed_df.with_columns(nw.col("level").cast(nw.Int64).fill_null(0))

    # Convert fiscal year columns to float
    for col in fy_cols:
        if col in renamed_df.columns:
            renamed_df = renamed_df.with_columns(nw.col(col).cast(nw.Float64))

    # Convert back to rows for percentage calculation (requires stateful iteration)
    renamed_rows = list(renamed_df.iter_rows(named=True))

    # Calculate percentages for each fiscal year column
    for yr in fy_cols:
        _earning_pct(renamed_rows, yr)

    # Convert to arrow table and return in requested backend
    result_table = pa.Table.from_pylist(renamed_rows)
    return _convert_backend(nw.from_native(result_table), actual_backend)
