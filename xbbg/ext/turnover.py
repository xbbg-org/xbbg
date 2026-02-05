"""Turnover data utilities.

This module provides trading turnover functionality.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from typing import Any

import narwhals as nw
import pyarrow as pa

from xbbg.api.historical import bdh
from xbbg.backend import Backend, Format
from xbbg.core.utils import utils
from xbbg.ext.currency import adjust_ccy
from xbbg.io.convert import _convert_backend, is_empty
from xbbg.options import get_backend

__all__ = ["turnover"]


def _get_business_date(offset_days: int = 0) -> str:
    """Get a business date with optional offset.

    Args:
        offset_days: Number of business days to offset (negative for past).

    Returns:
        Date string in YYYY-MM-DD format.
    """
    # Simple business day calculation (skip weekends)
    date = datetime.now()
    days_moved = 0
    direction = 1 if offset_days >= 0 else -1
    target = abs(offset_days)

    while days_moved < target:
        date += timedelta(days=direction)
        if date.weekday() < 5:  # Monday = 0, Friday = 4
            days_moved += 1

    # If current day is weekend, move to Friday
    while date.weekday() >= 5:
        date -= timedelta(days=1)

    return date.strftime("%Y-%m-%d")


def _get_month_start(end_date: str, months_back: int = 1) -> str:
    """Get the start of month N months before end_date.

    Args:
        end_date: End date string (YYYY-MM-DD or similar).
        months_back: Number of months to go back.

    Returns:
        Date string in YYYY-MM-DD format.
    """
    # Parse end date
    if isinstance(end_date, str):
        try:
            dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
        except ValueError:
            dt = datetime.now()
    else:
        dt = datetime.now()

    # Go back N months
    year = dt.year
    month = dt.month - months_back
    while month <= 0:
        month += 12
        year -= 1

    return f"{year:04d}-{month:02d}-01"


def turnover(
    tickers: str | list[str],
    flds: str = "Turnover",
    start_date: str | None = None,
    end_date: str | None = None,
    ccy: str = "USD",
    factor: float = 1e6,
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Currency adjusted turnover (in million).

    Args:
        tickers: ticker or list of tickers.
        flds: override ``flds``.
        start_date: start date, default 1 month prior to ``end_date``.
        end_date: end date, default T - 1.
        ccy: currency - 'USD' (default), any currency, or 'local' (no adjustment).
        factor: adjustment factor, default 1e6 - return values in millions.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Additional options.

    Returns:
        DataFrame.
    """
    # Handle default dates
    if end_date is None:
        end_date = _get_business_date(-1)  # T-1
    if start_date is None:
        start_date = _get_month_start(end_date, months_back=1)

    tickers = utils.normalize_tickers(tickers)
    actual_backend = backend if backend is not None else get_backend()

    # Get turnover data using narwhals backend
    data = bdh(
        tickers=tickers,
        flds=flds,
        start_date=start_date,
        end_date=end_date,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
    )

    # Check which tickers have turnover data
    tickers_with_data = set()
    if not is_empty(data):
        tickers_with_data = set(data.select("ticker").unique().get_column("ticker").to_list())

    # Calculate turnover from volume * VWAP for tickers without direct turnover
    vol_tickers = [t for t in tickers if t not in tickers_with_data]
    volume_data_rows = []

    if isinstance(flds, str) and flds.lower() == "turnover" and vol_tickers:
        vol_data = bdh(
            tickers=vol_tickers,
            flds=["eqy_weighted_avg_px", "volume"],
            start_date=start_date,
            end_date=end_date,
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
        )

        if not is_empty(vol_data):
            # Group by ticker and date, calculate turnover = vwap * volume using narwhals
            vol_df = (
                vol_data.group_by(["ticker", "date"])
                .agg(
                    [
                        nw.col("eqy_weighted_avg_px").first().alias("vwap"),
                        nw.col("volume").first().alias("volume"),
                    ]
                )
                .with_columns((nw.col("vwap") * nw.col("volume")).alias("Turnover"))
                .select(["ticker", "date", "Turnover"])
            )

            # Convert to list of dicts for compatibility
            for row in vol_df.iter_rows(named=True):
                if row.get("Turnover") is not None:
                    volume_data_rows.append(row)

    # Apply currency adjustment to turnover data
    adjusted_rows = []

    if not is_empty(data):
        # Apply currency adjustment
        adjusted_data = adjust_ccy(data, ccy=ccy, backend=Backend.NARWHALS)
        if not is_empty(adjusted_data):
            # Get all numeric columns (exclude ticker and date)
            numeric_cols = [col for col in adjusted_data.columns if col not in ("ticker", "date")]

            # Apply factor to all numeric columns using with_columns
            if numeric_cols:
                adjusted_data = adjusted_data.with_columns([(nw.col(col) / factor).alias(col) for col in numeric_cols])

            # Convert to list of dicts for compatibility
            for row in adjusted_data.iter_rows(named=True):
                adjusted_rows.append(row)

    # Add volume-calculated turnover rows
    for row in volume_data_rows:
        if row.get("Turnover") is not None:
            with contextlib.suppress(ValueError, TypeError):
                row["Turnover"] = float(row["Turnover"]) / factor
        adjusted_rows.append(row)

    if not adjusted_rows:
        return _convert_backend(nw.from_native(pa.table({})), actual_backend)

    # Convert to arrow table and return in requested backend
    result_table = pa.Table.from_pylist(adjusted_rows)
    return _convert_backend(nw.from_native(result_table), actual_backend)
