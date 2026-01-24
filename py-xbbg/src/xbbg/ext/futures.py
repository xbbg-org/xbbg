"""Futures and CDX resolver extension functions.

Functions for resolving generic futures/CDX tickers to specific contracts.
Uses high-performance Rust utilities from xbbg._core for parsing and resolution.

Sync functions (wrap async with asyncio.run):
    - fut_ticker(): Resolve generic futures ticker to specific contract
    - active_futures(): Get most active futures contract for a date
    - cdx_ticker(): Resolve generic CDX ticker to specific series
    - active_cdx(): Get most active CDX contract for a date

Async functions (primary implementation):
    - afut_ticker(): Async resolve generic futures ticker
    - aactive_futures(): Async get most active futures contract
    - acdx_ticker(): Async resolve generic CDX ticker
    - aactive_cdx(): Async get most active CDX contract
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import narwhals.stable.v1 as nw

# Import Rust ext utilities for max performance
from xbbg._core import (
    ext_contract_index,
    ext_cdx_gen_to_specific,
    ext_generate_futures_candidates,
    ext_parse_date,
    ext_previous_cdx_series,
    ext_validate_generic_ticker,
)

if TYPE_CHECKING:
    from datetime import date


def _parse_date(dt: str | date) -> datetime:
    """Parse date string or date object to datetime using Rust."""
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        year, month, day = ext_parse_date(dt)
        return datetime(year, month, day)
    # date object
    if hasattr(dt, "year"):
        return datetime(dt.year, dt.month, dt.day)
    raise ValueError(f"Cannot parse date: {dt}")


def _pivot_bdp_to_wide(nw_df: nw.DataFrame) -> nw.DataFrame:
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
    columns: dict[str, list] = {"ticker": []}
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


# =============================================================================
# Async implementations (primary)
# =============================================================================


async def afut_ticker(
    gen_ticker: str,
    dt: str | date,
    freq: str = "M",
    **kwargs,
) -> str:
    """Async resolve generic futures ticker to specific contract.

    Maps a generic futures ticker (e.g., 'ES1 Index') to the specific
    contract for a given date. Uses Rust for candidate generation.

    Args:
        gen_ticker: Generic futures ticker (e.g., 'ES1 Index', 'CL1 Comdty').
        dt: Reference date for contract resolution.
        freq: Roll frequency - 'M' (monthly), 'Q' (quarterly).
        **kwargs: Additional arguments passed to abdp.

    Returns:
        Specific contract ticker (e.g., 'ESH24 Index').

    Example::

        import asyncio
        from xbbg.ext.futures import afut_ticker


        async def main():
            # Get March 2024 E-mini S&P contract
            ticker = await afut_ticker("ES1 Index", "2024-01-15")
            # Returns: 'ESH24 Index'

            # Get quarterly contract
            ticker = await afut_ticker("ES1 Index", "2024-01-15", freq="Q")


        asyncio.run(main())
    """
    from xbbg import abdp

    dt_parsed = _parse_date(dt)

    # Get contract index (0-based) using Rust
    try:
        idx = ext_contract_index(gen_ticker)
    except ValueError:
        return ""

    # Determine asset type for candidate count
    t_info = gen_ticker.split()
    asset = t_info[-1] if t_info else ""
    month_ext = 4 if asset == "Comdty" else 2
    count = max(idx + month_ext, 3)

    # Generate futures candidates using Rust (high performance)
    try:
        candidates = ext_generate_futures_candidates(
            gen_ticker,
            dt_parsed.year,
            dt_parsed.month,
            dt_parsed.day,
            freq.upper(),
            count,
        )
    except ValueError:
        return ""

    if not candidates:
        return ""

    fut_candidates = [c[0] for c in candidates]  # Extract ticker strings

    # Get maturity dates from Bloomberg
    try:
        fut_matu = await abdp(tickers=fut_candidates, flds="last_tradeable_dt", **kwargs)
    except Exception:
        # Try with fewer candidates
        try:
            fut_matu = await abdp(tickers=fut_candidates[:-1], flds="last_tradeable_dt", **kwargs)
        except Exception:
            return ""

    # Convert to narwhals and pivot from long to wide format
    nw_df = nw.from_native(fut_matu)
    nw_df = _pivot_bdp_to_wide(nw_df)

    if len(nw_df) == 0 or "last_tradeable_dt" not in nw_df.columns:
        return ""

    # Parse maturity dates and filter to those after dt
    matu_dates = nw_df["last_tradeable_dt"].to_list()
    tickers = nw_df["ticker"].to_list()

    # Build list of (ticker, parsed_date) and filter/sort
    valid_contracts: list[tuple[str, datetime]] = []
    for ticker_val, matu_str in zip(tickers, matu_dates, strict=False):
        if matu_str is None:
            continue
        try:
            matu_dt = _parse_date(matu_str)
            if matu_dt > dt_parsed:
                valid_contracts.append((ticker_val, matu_dt))
        except (ValueError, TypeError):
            continue

    if len(valid_contracts) <= idx:
        return ""

    # Sort by maturity date and return the contract at idx
    valid_contracts.sort(key=lambda x: x[1])
    return valid_contracts[idx][0]


async def aactive_futures(
    ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Async get the most active futures contract for a date.

    Selects the most active contract based on volume, typically choosing
    between the front month and second month contract.

    Args:
        ticker: Generic futures ticker (e.g., 'ES1 Index', 'CL1 Comdty').
            Must be a generic contract (e.g., 'ES1'), not specific (e.g., 'ESH24').
        dt: Reference date.
        **kwargs: Additional arguments passed to abdp/abdh.

    Returns:
        Most active contract ticker based on recent volume.

    Raises:
        ValueError: If ticker appears to be a specific contract instead of generic.

    Example::

        import asyncio
        from xbbg.ext.futures import aactive_futures


        async def main():
            # Get most active E-mini S&P contract
            ticker = await aactive_futures("ES1 Index", "2024-01-15")


        asyncio.run(main())
    """
    from xbbg import abdh, abdp

    # Validate that ticker is generic using Rust
    ext_validate_generic_ticker(ticker)

    dt_parsed = _parse_date(dt)

    # Parse ticker components
    t_info = ticker.split()
    prefix, asset = " ".join(t_info[:-1]), t_info[-1]

    # Get front and second month contracts
    f1 = f"{prefix[:-1]}1 {asset}"
    f2 = f"{prefix[:-1]}2 {asset}"

    # Resolve to specific contracts
    freq = kwargs.pop("freq", "M")
    fut_1 = await afut_ticker(gen_ticker=f1, dt=dt_parsed, freq=freq, **kwargs)
    fut_2 = await afut_ticker(gen_ticker=f2, dt=dt_parsed, freq=freq, **kwargs)

    if not fut_1:
        return ""

    if not fut_2:
        return fut_1

    # Get maturity dates
    fut_tk = await abdp(tickers=[fut_1, fut_2], flds="last_tradeable_dt", **kwargs)
    nw_tk = nw.from_native(fut_tk)
    nw_tk = _pivot_bdp_to_wide(nw_tk)

    if len(nw_tk) == 0 or "last_tradeable_dt" not in nw_tk.columns:
        return fut_1

    # If current date is before first contract's maturity month, use front month
    first_row = nw_tk.filter(nw.col("ticker") == fut_1)
    if len(first_row) > 0:
        first_matu = first_row["last_tradeable_dt"][0]
        if isinstance(first_matu, str):
            first_matu = _parse_date(first_matu)
        if hasattr(first_matu, "month") and dt_parsed.month < first_matu.month:
            return fut_1

    # Otherwise, compare volume over last 10 days
    start = dt_parsed - timedelta(days=10)
    volume = await abdh(tickers=[fut_1, fut_2], flds="volume", start_date=start, end_date=dt_parsed, **kwargs)
    nw_vol = nw.from_native(volume)

    if len(nw_vol) == 0:
        return fut_1

    # Get last row's volume for each contract and return the one with higher volume
    last_row = nw_vol.tail(1)
    vol_cols = [c for c in last_row.columns if "volume" in c.lower()]

    if not vol_cols:
        return fut_1

    # Find which contract has higher volume
    max_vol = 0
    best_ticker = fut_1
    for col in vol_cols:
        vol = last_row[col][0]
        if vol and vol > max_vol:
            max_vol = vol
            # Extract ticker from column name
            if fut_1 in col:
                best_ticker = fut_1
            elif fut_2 in col:
                best_ticker = fut_2

    return best_ticker


async def acdx_ticker(
    gen_ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Async resolve generic CDX ticker to specific series.

    Maps a generic CDX index ticker to the specific series for a date.
    Uses Rust for CDX ticker parsing and series resolution.

    Args:
        gen_ticker: Generic CDX ticker (e.g., 'CDX IG CDSI GEN 5Y Corp').
        dt: Reference date.
        **kwargs: Additional arguments passed to abdp.

    Returns:
        Specific series ticker (e.g., 'CDX IG CDSI S45 5Y Corp').

    Example::

        import asyncio
        from xbbg.ext.futures import acdx_ticker


        async def main():
            ticker = await acdx_ticker("CDX IG CDSI GEN 5Y Corp", "2024-01-15")


        asyncio.run(main())
    """
    from xbbg import abdp

    dt_parsed = _parse_date(dt)

    # Get CDX metadata
    try:
        info = await abdp(
            tickers=gen_ticker,
            flds=["rolling_series", "on_the_run_current_bd_indicator", "cds_first_accrual_start_date"],
            **kwargs,
        )
    except Exception:
        return ""

    nw_info = nw.from_native(info)
    nw_info = _pivot_bdp_to_wide(nw_info)

    if len(nw_info) == 0 or "rolling_series" not in nw_info.columns:
        return ""

    series = nw_info["rolling_series"][0]
    try:
        series = int(series)
    except (ValueError, TypeError):
        return ""

    # Convert generic to specific using Rust
    try:
        resolved = ext_cdx_gen_to_specific(gen_ticker, series)
    except ValueError:
        return ""

    # Check if dt is before first accrual date of current series
    if "cds_first_accrual_start_date" in nw_info.columns:
        try:
            start_dt = _parse_date(nw_info["cds_first_accrual_start_date"][0])
            if dt_parsed < start_dt and series > 1:
                # Use prior series via Rust
                try:
                    resolved = ext_cdx_gen_to_specific(gen_ticker, series - 1)
                except ValueError:
                    pass
        except Exception:
            pass

    return resolved


async def aactive_cdx(
    gen_ticker: str,
    dt: str | date,
    lookback_days: int = 10,
    **kwargs,
) -> str:
    """Async get the most active CDX contract for a date.

    Selects the most active CDX series based on recent trading activity.

    Args:
        gen_ticker: Generic CDX ticker (e.g., 'CDX IG CDSI GEN 5Y Corp').
        dt: Reference date.
        lookback_days: Number of days to look back for activity (default: 10).
        **kwargs: Additional arguments passed to abdp/abdh.

    Returns:
        Most active CDX series ticker.

    Example::

        import asyncio
        from xbbg.ext.futures import aactive_cdx


        async def main():
            ticker = await aactive_cdx("CDX IG CDSI GEN 5Y Corp", "2024-01-15")


        asyncio.run(main())
    """
    from xbbg import abdh, abdp

    # Get current series
    cur = await acdx_ticker(gen_ticker=gen_ticker, dt=dt, **kwargs)
    if not cur:
        return ""

    dt_parsed = _parse_date(dt)

    # Get previous series using Rust
    try:
        prev = ext_previous_cdx_series(cur)
    except ValueError:
        prev = None

    if not prev:
        return cur

    # Check if dt is before current series' accrual start
    try:
        cur_meta = await abdp(cur, ["cds_first_accrual_start_date"], **kwargs)
        nw_meta = nw.from_native(cur_meta)
        nw_meta = _pivot_bdp_to_wide(nw_meta)
        if len(nw_meta) > 0 and "cds_first_accrual_start_date" in nw_meta.columns:
            cur_start = _parse_date(nw_meta["cds_first_accrual_start_date"][0])
            if dt_parsed < cur_start:
                return prev
    except Exception:
        pass

    # Compare activity based on PX_LAST availability
    end = dt_parsed
    start = dt_parsed - timedelta(days=lookback_days)

    try:
        px = await abdh([cur, prev], ["PX_LAST"], start_date=start, end_date=end, **kwargs)
        nw_px = nw.from_native(px)

        if len(nw_px) == 0:
            return cur

        # Check which has more recent non-null prices
        last_row = nw_px.tail(1)
        for col in last_row.columns:
            if cur in col and last_row[col][0] is not None:
                return cur
            if prev in col and last_row[col][0] is not None:
                return prev

    except Exception:
        pass

    return cur


# =============================================================================
# Sync wrappers
# =============================================================================


def fut_ticker(
    gen_ticker: str,
    dt: str | date,
    freq: str = "M",
    **kwargs,
) -> str:
    """Resolve generic futures ticker to specific contract.

    Sync wrapper for afut_ticker(). See afut_ticker() for full documentation.

    Example::

        from xbbg import ext

        # Get March 2024 E-mini S&P contract
        ticker = ext.fut_ticker("ES1 Index", "2024-01-15")
    """
    return asyncio.run(afut_ticker(gen_ticker=gen_ticker, dt=dt, freq=freq, **kwargs))


def active_futures(
    ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Get the most active futures contract for a date.

    Sync wrapper for aactive_futures(). See aactive_futures() for full documentation.

    Example::

        from xbbg import ext

        # Get most active E-mini S&P contract
        ticker = ext.active_futures("ES1 Index", "2024-01-15")
    """
    return asyncio.run(aactive_futures(ticker=ticker, dt=dt, **kwargs))


def cdx_ticker(
    gen_ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Resolve generic CDX ticker to specific series.

    Sync wrapper for acdx_ticker(). See acdx_ticker() for full documentation.

    Example::

        from xbbg import ext

        ticker = ext.cdx_ticker("CDX IG CDSI GEN 5Y Corp", "2024-01-15")
    """
    return asyncio.run(acdx_ticker(gen_ticker=gen_ticker, dt=dt, **kwargs))


def active_cdx(
    gen_ticker: str,
    dt: str | date,
    lookback_days: int = 10,
    **kwargs,
) -> str:
    """Get the most active CDX contract for a date.

    Sync wrapper for aactive_cdx(). See aactive_cdx() for full documentation.

    Example::

        from xbbg import ext

        ticker = ext.active_cdx("CDX IG CDSI GEN 5Y Corp", "2024-01-15")
    """
    return asyncio.run(aactive_cdx(gen_ticker=gen_ticker, dt=dt, lookback_days=lookback_days, **kwargs))
