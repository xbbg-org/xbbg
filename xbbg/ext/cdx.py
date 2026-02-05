"""CDX index resolution utilities.

This module provides functions for resolving generic CDX tickers to specific
series tickers and selecting active CDX contracts.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

import narwhals as nw

from xbbg.backend import Backend, Format
from xbbg.io.convert import is_empty

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

__all__ = ["cdx_ticker", "active_cdx"]


def _parse_date(dt) -> datetime:
    """Parse various date formats to datetime."""
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        # Try ISO format first
        try:
            return datetime.fromisoformat(dt.replace("/", "-"))
        except ValueError:
            pass
        # Try YYYYMMDD format
        if len(dt) == 8 and dt.isdigit():
            return datetime(int(dt[:4]), int(dt[4:6]), int(dt[6:8]))
    # Try to handle date objects
    if hasattr(dt, "year") and hasattr(dt, "month") and hasattr(dt, "day"):
        return datetime(dt.year, dt.month, dt.day)
    raise ValueError(f"Cannot parse date: {dt}")


def cdx_ticker(
    gen_ticker: str,
    dt,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Resolve generic CDX 5Y ticker (e.g., 'CDX IG CDSI GEN 5Y Corp') to concrete series.

    Uses Bloomberg fields:
      - rolling_series: returns current on-the-run series number
      - on_the_run_current_bd_indicator: 'Y' if on-the-run
      - cds_first_accrual_start_date: start date of current series trading

    Args:
        gen_ticker: Generic CDX ticker.
        dt: Date to resolve for.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Resolved ticker string.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    dt_parsed = _parse_date(dt)

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    # Convert context to kwargs for bdp call
    safe_kwargs = ctx.to_kwargs()

    try:
        info = bdp(
            tickers=gen_ticker,
            flds=["rolling_series", "on_the_run_current_bd_indicator", "cds_first_accrual_start_date"],
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
    except Exception as e:
        logger.error("Failed to fetch CDX metadata for generic ticker %s: %s", gen_ticker, e)
        return ""

    if is_empty(info):
        logger.warning("No rolling series configuration found for CDX ticker: %s", gen_ticker)
        return ""

    # Convert to narwhals if needed and get columns
    nw_info = nw.from_native(info, eager_only=True)
    columns = nw_info.columns

    if "rolling_series" not in columns:
        logger.warning("No rolling series configuration found for CDX ticker: %s", gen_ticker)
        return ""

    # Get data for the ticker - build field lookup from SEMI_LONG format
    # bdp SEMI_LONG returns: ticker, field, value (one row per field)
    series = None
    start_dt = None
    faccr_col = "cds_first_accrual_start_date"

    # Filter for the target ticker and extract field values using vectorized operations
    ticker_data = nw_info.filter(nw.col("ticker") == gen_ticker)

    # Extract rolling_series value
    series_rows = ticker_data.filter(nw.col("field").str.to_lowercase() == "rolling_series").select("value")

    if series_rows.shape[0] > 0:
        series = series_rows.item(0, 0)

    # Extract cds_first_accrual_start_date value
    start_dt_rows = ticker_data.filter(nw.col("field").str.to_lowercase() == faccr_col.lower()).select("value")

    if start_dt_rows.shape[0] > 0:
        start_dt_val = start_dt_rows.item(0, 0)
        if start_dt_val is not None:
            try:
                start_dt = _parse_date(start_dt_val)
            except (ValueError, TypeError):
                start_dt = None

    if series is None:
        logger.warning("No rolling series found for CDX ticker: %s", gen_ticker)
        return ""

    with contextlib.suppress(ValueError, TypeError):
        series = int(series)

    tokens = gen_ticker.split()
    if "GEN" not in tokens:
        logger.warning("Generic ticker %s does not contain expected GEN token for CDX resolution", gen_ticker)
        return ""
    tokens[tokens.index("GEN")] = f"S{series}"
    resolved = " ".join(tokens)

    # If dt is before first accrual date of current series, use prior series
    if (start_dt is not None) and (dt_parsed < start_dt) and isinstance(series, int) and series > 1:
        tokens[tokens.index(f"S{series}")] = f"S{series - 1}"
        resolved = " ".join(tokens)

    return resolved


def active_cdx(
    gen_ticker: str,
    dt,
    lookback_days: int = 10,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Choose active CDX series for a date, preferring on-the-run unless it's not started yet.

    If ambiguous, prefer the series with recent non-empty PX_LAST over the lookback window.

    Args:
        gen_ticker: Generic CDX ticker.
        dt: Date to resolve for.
        lookback_days: Number of days to look back for activity.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Active ticker string.
    """
    from xbbg.api.historical import bdh
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    dt_parsed = _parse_date(dt)

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    cur = cdx_ticker(gen_ticker=gen_ticker, dt=dt, ctx=ctx)
    if not cur:
        return ""

    # Compute previous series candidate
    parts = cur.split()
    prev = ""
    for i, tok in enumerate(parts):
        if tok.startswith("S") and tok[1:].isdigit():
            s = int(tok[1:])
            if s > 1:
                parts[i] = f"S{s - 1}"
                prev = " ".join(parts)
            break

    # If no prev candidate, return current
    if not prev:
        return cur

    # Convert context to kwargs for bdp/bdh calls
    safe_kwargs = ctx.to_kwargs()

    # If dt is before accrual start, prefer prev
    try:
        cur_meta = bdp(
            cur,
            ["cds_first_accrual_start_date"],
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
        cur_start = None
        if not is_empty(cur_meta):
            nw_meta = nw.from_native(cur_meta, eager_only=True)
            # Extract first non-null value using vectorized filter
            meta_values = nw_meta.filter(~nw.col("value").is_null()).select("value")
            if meta_values.shape[0] > 0:
                val = meta_values.item(0, 0)
                with contextlib.suppress(ValueError, TypeError):
                    cur_start = _parse_date(val)
    except Exception:
        cur_start = None

    if (cur_start is not None) and (dt_parsed < cur_start):
        return prev

    # Otherwise, pick one with recent activity (PX_LAST availability)
    end_date = dt_parsed
    start_date = dt_parsed - timedelta(days=lookback_days)

    try:
        px = bdh(
            [cur, prev],
            ["PX_LAST"],
            start_date=start_date,
            end_date=end_date,
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
        if is_empty(px):
            return cur

        # Find ticker with most recent non-null PX_LAST value using vectorized operations
        nw_px = nw.from_native(px, eager_only=True)

        # Normalize column name (handle both PX_LAST and px_last)
        px_col = "PX_LAST" if "PX_LAST" in nw_px.columns else "px_last"

        # Filter for non-null prices and group by ticker to get max date
        ticker_latest = (
            nw_px.filter(~nw.col(px_col).is_null()).group_by("ticker").agg(nw.col("date").max().alias("latest_date"))
        )

        if ticker_latest.shape[0] == 0:
            return cur

        # Convert to dict for comparison
        latest_dates: dict[str, str] = {}
        for row in ticker_latest.iter_rows(named=True):
            ticker = row.get("ticker")
            date_val = row.get("latest_date")
            if ticker and date_val:
                latest_dates[ticker] = str(date_val)

        # Find ticker with most recent date
        best_ticker = cur
        best_date = latest_dates.get(cur, "")

        if prev in latest_dates and latest_dates[prev] > best_date:
            best_ticker = prev

        return best_ticker

    except Exception:
        return cur
