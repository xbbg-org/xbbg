"""Shared utility functions for ext modules.

This module contains utility functions extracted from multiple ext modules
to eliminate duplication and improve maintainability.

Functions:
    - _pivot_bdp_to_wide(): Pivot bdp result from long to wide format
    - _fmt_date(): Format date to string using Rust utilities
    - _apply_settle_override(): Apply settle date override to overrides dict
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from datetime import date
import functools
from typing import Any, ParamSpec, TypeVar

import narwhals.stable.v1 as nw

_P = ParamSpec("_P")
_T = TypeVar("_T")


def _syncify(async_func: Callable[_P, Coroutine[Any, Any, _T]]) -> Callable[_P, _T]:
    """Create a synchronous wrapper for an async function."""

    @functools.wraps(async_func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper


async def _abdp_fields(
    tickers: str | Sequence[str],
    fields: str | Sequence[str],
    **kwargs,
) -> Any:
    """Run abdp with shared field-query boilerplate."""
    from xbbg.blp import abdp

    return await abdp(tickers=tickers, flds=fields, **kwargs)


async def _abds_field(
    tickers: str | Sequence[str],
    field: str,
    **kwargs,
) -> Any:
    """Run abds with shared field-query boilerplate."""
    from xbbg.blp import abds

    return await abds(tickers=tickers, flds=field, **kwargs)


def _pivot_bdp_to_wide(nw_df):
    """Pivot bdp result from long format (ticker, field, value) to wide format.

    If the dataframe already has the expected columns (not in long format),
    returns it unchanged.
    """
    # Check if already in wide format (has columns other than ticker/field/value)
    if set(nw_df.columns) != {"ticker", "field", "value"}:
        return nw_df

    if len(nw_df) == 0:
        return nw_df

    # Pivot from long to wide: each unique field becomes a column
    # Group by ticker and create dict of field -> value
    rows_by_ticker: dict[str, dict[str, str]] = {}
    for row in nw_df.iter_rows(named=True):
        ticker = row["ticker"]
        field = row["field"]
        value = row["value"]
        if ticker not in rows_by_ticker:
            rows_by_ticker[ticker] = {"ticker": ticker}
        rows_by_ticker[ticker][field] = value

    # Build wide dataframe
    if not rows_by_ticker:
        return nw_df

    # Get all unique fields for column names
    all_fields = set()
    for row_data in rows_by_ticker.values():
        all_fields.update(k for k in row_data if k != "ticker")

    # Create lists for each column
    columns: dict[str, list[Any]] = {"ticker": []}
    for field in all_fields:
        columns[field] = []

    for ticker, row_data in rows_by_ticker.items():
        columns["ticker"].append(ticker)
        for field in all_fields:
            columns[field].append(row_data.get(field))

    # Create new dataframe using native namespace
    native_ns = nw.get_native_namespace(nw_df)
    result_cols = {k: nw.new_series(k, v, native_namespace=native_ns) for k, v in columns.items()}

    # Build dataframe from series
    first_series = next(iter(result_cols.values()))
    result_df = first_series.to_frame()
    for _name, series in list(result_cols.items())[1:]:
        result_df = result_df.with_columns(series)

    return result_df


def _apply_settle_override(overrides: dict, settle_dt) -> None:
    """Apply a settle date override to the overrides dict in place.

    If settle_dt is not None and can be formatted, sets overrides["SETTLE_DT"].

    Args:
        overrides: Mutable dict of Bloomberg overrides to update.
        settle_dt: Settlement date as string, date object, or None.
    """
    if settle_dt is not None:
        formatted_settle = _fmt_date(settle_dt)
        if formatted_settle is not None:
            overrides["SETTLE_DT"] = formatted_settle


def _fmt_date(dt: str | date | None, fmt: str = "%Y%m%d") -> str | None:
    """Format date to string using Rust.

    Args:
        dt: Date as string, date object, or None
        fmt: Format string for output (default: "%Y%m%d")

    Returns:
        Formatted date string or None if input is None
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        # Try to parse and reformat using Rust
        from xbbg._core import ext_fmt_date, ext_parse_date

        try:
            year, month, day = ext_parse_date(dt)
            return ext_fmt_date(year, month, day, fmt)
        except ValueError:
            return dt  # Return as-is if can't parse
    # datetime or date object
    from xbbg._core import ext_fmt_date

    return ext_fmt_date(dt.year, dt.month, dt.day, fmt)
