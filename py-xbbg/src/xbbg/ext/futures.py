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
import logging
from typing import TYPE_CHECKING

import narwhals.stable.v1 as nw

# Import Rust ext utilities for max performance
from xbbg._core import (
    ext_contract_index,
    ext_filter_candidates_by_cycle,
    ext_filter_valid_contracts,
    ext_generate_futures_candidates,
    ext_parse_date,
    ext_validate_generic_ticker,
)
from xbbg.ext._utils import _pivot_bdp_to_wide

logger = logging.getLogger(__name__)

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


_FLD_ROLLING_SERIES = "ROLLING_SERIES"
_FLD_OTR_INDICATOR = "ON_THE_RUN_CURRENT_BD_INDICATOR"
_FLD_ACCRUAL_START = "CDS_FIRST_ACCRUAL_START_DATE"
_FLD_VERSION = "VERSION"

_CDX_FIELDS = [_FLD_ROLLING_SERIES, _FLD_OTR_INDICATOR, _FLD_ACCRUAL_START, _FLD_VERSION]


def _extract_field_value(nw_df, field_name: str):
    """Extract a scalar value from a SEMI_LONG frame by field name."""
    field_upper = field_name.upper()

    # LONG / SEMI_LONG format: ticker, field, value
    if "field" in nw_df.columns and "value" in nw_df.columns:
        rows = nw_df.filter(nw.col("field").str.to_uppercase() == field_upper).select("value")
        if len(rows) == 0:
            return None
        return rows.item(0, 0)

    # Wide fallback
    if field_name in nw_df.columns and len(nw_df) > 0:
        return nw_df[field_name][0]

    lower_name = field_name.lower()
    if lower_name in nw_df.columns and len(nw_df) > 0:
        return nw_df[lower_name][0]

    return None


def _parse_series_token(tok: str) -> int | None:
    """Parse ``S{n}`` token and return series number."""
    if not tok.startswith("S"):
        return None
    digits = tok[1:]
    if not digits.isdigit():
        return None
    return int(digits)


def _find_series_token_index(tokens: list[str]) -> int | None:
    """Find series token index (``S{n}``) in tokenized CDX ticker."""
    for idx, token in enumerate(tokens):
        if _parse_series_token(token) is not None:
            return idx
    return None


def _append_version_to_ticker(ticker: str, version: int) -> str:
    """Insert ``V{version}`` token after series token."""
    tokens = ticker.split()
    series_idx = _find_series_token_index(tokens)
    if series_idx is None:
        return ticker

    if series_idx + 1 < len(tokens) and tokens[series_idx + 1].startswith("V") and tokens[series_idx + 1][1:].isdigit():
        tokens.pop(series_idx + 1)

    tokens.insert(series_idx + 1, f"V{version}")
    return " ".join(tokens)


def _strip_version_from_ticker(ticker: str) -> str:
    """Remove ``V{n}`` token from resolved CDX ticker if present."""
    tokens = ticker.split()
    series_idx = _find_series_token_index(tokens)
    if series_idx is None:
        return ticker

    if series_idx + 1 < len(tokens) and tokens[series_idx + 1].startswith("V") and tokens[series_idx + 1][1:].isdigit():
        tokens.pop(series_idx + 1)
    return " ".join(tokens)


async def _resolve_version_for_ticker(ticker: str, **kwargs) -> str:
    """Resolve CDX version for a series ticker and append ``V{n}`` when needed."""
    from xbbg import abdp

    try:
        meta = await abdp(tickers=ticker, flds=[_FLD_VERSION], **kwargs)
    except (ValueError, TypeError, KeyError):
        return ticker

    nw_meta = nw.from_native(meta)
    if len(nw_meta) == 0:
        return ticker

    version_raw = _extract_field_value(nw_meta, _FLD_VERSION)
    if version_raw is None:
        return ticker

    try:
        version = int(version_raw)
    except (TypeError, ValueError):
        return ticker

    if version > 1:
        return _append_version_to_ticker(ticker, version)
    return ticker


# =============================================================================
# Async implementations (primary)
# =============================================================================


def _filter_valid_contracts_from_df(
    nw_df,
    dt_parsed: datetime,
) -> list[str]:
    """Filter and sort futures contracts by maturity date using Rust.

    Extracts (ticker, maturity_date_str) pairs from a pivoted BDP DataFrame
    and delegates filtering/sorting to the Rust implementation.

    Args:
        nw_df: Pivoted DataFrame with ``ticker`` and ``last_tradeable_dt`` columns.
        dt_parsed: Reference date; contracts maturing on or before this date
            are excluded.

    Returns:
        Sorted list of ticker strings for contracts maturing after *dt_parsed*.
    """
    matu_dates = nw_df["last_tradeable_dt"].to_list()
    tickers = nw_df["ticker"].to_list()

    # Build (ticker, maturity_str) pairs for Rust
    contracts = [(str(t), str(m)) for t, m in zip(tickers, matu_dates, strict=False) if m is not None]

    return ext_filter_valid_contracts(contracts, dt_parsed.year, dt_parsed.month, dt_parsed.day)


async def afut_ticker(
    gen_ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Async resolve generic futures ticker to specific contract.

    Maps a generic futures ticker (e.g., 'ES1 Index') to the specific
    contract for a given date. Queries Bloomberg for FUT_GEN_MONTH to
    determine the actual trading cycle, then uses Rust for candidate
    generation and filtering.

    Args:
        gen_ticker: Generic futures ticker (e.g., 'ES1 Index', 'CL1 Comdty').
        dt: Reference date for contract resolution.
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


        asyncio.run(main())
    """
    from xbbg import abdp

    dt_parsed = _parse_date(dt)

    # Get contract index (0-based) using Rust
    try:
        idx = ext_contract_index(gen_ticker)
    except ValueError:
        return ""

    # Determine candidate count — enough to cover the index + buffer
    t_info = gen_ticker.split()
    asset = t_info[-1] if t_info else ""
    month_ext = 4 if asset == "Comdty" else 2
    count = max(idx + month_ext, 3)

    # Query Bloomberg for the actual trading cycle (e.g., "HMUZ")
    try:
        cycle_data = await abdp(tickers=gen_ticker, flds="fut_gen_month", **kwargs)
        cycle_nw = nw.from_native(cycle_data)
        cycle_nw = _pivot_bdp_to_wide(cycle_nw)
        cycle = cycle_nw["fut_gen_month"][0] if len(cycle_nw) > 0 and "fut_gen_month" in cycle_nw.columns else ""
    except (ValueError, TypeError, KeyError, IndexError):
        cycle = ""

    # Generate monthly candidates using Rust, then filter by Bloomberg cycle
    try:
        candidates = ext_generate_futures_candidates(
            gen_ticker,
            dt_parsed.year,
            dt_parsed.month,
            dt_parsed.day,
            "M",  # always monthly — Bloomberg cycle handles filtering
            count * 3,  # generate extra so filtering still yields enough
        )
    except ValueError:
        return ""

    if not candidates:
        return ""

    # Filter by the cycle Bloomberg gave us
    if cycle:
        candidates = ext_filter_candidates_by_cycle(candidates, cycle)
        if not candidates:
            return ""

    # Trim to needed count
    candidates = candidates[:count]

    fut_candidates = [c[0] for c in candidates]  # Extract ticker strings

    # Get maturity dates from Bloomberg
    try:
        fut_matu = await abdp(tickers=fut_candidates, flds="last_tradeable_dt", **kwargs)
    except (ValueError, TypeError, KeyError):
        logger.warning("Failed to get maturity data for futures candidates")
        # Try with fewer candidates
        try:
            fut_matu = await abdp(tickers=fut_candidates[:-1], flds="last_tradeable_dt", **kwargs)
        except (ValueError, TypeError, KeyError):
            logger.warning("Failed to get maturity data with fewer candidates")
            return ""

    # Convert to narwhals and pivot from long to wide format
    nw_df = nw.from_native(fut_matu)
    nw_df = _pivot_bdp_to_wide(nw_df)

    if len(nw_df) == 0 or "last_tradeable_dt" not in nw_df.columns:
        return ""

    # Filter and sort using Rust (high performance)
    valid_tickers = _filter_valid_contracts_from_df(nw_df, dt_parsed)

    if len(valid_tickers) <= idx:
        return ""

    return valid_tickers[idx]


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
    fut_1 = await afut_ticker(gen_ticker=f1, dt=dt_parsed, **kwargs)
    fut_2 = await afut_ticker(gen_ticker=f2, dt=dt_parsed, **kwargs)

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

    # If current date is before first contract's maturity, use front month
    first_row = nw_tk.filter(nw.col("ticker") == fut_1)
    if len(first_row) > 0:
        first_matu = first_row["last_tradeable_dt"][0]
        if isinstance(first_matu, str):
            first_matu = _parse_date(first_matu)
        if hasattr(first_matu, "year") and dt_parsed < first_matu:
            return fut_1

    # Otherwise, compare volume over last 10 days
    # abdh returns LONG format: {ticker, date, field, value}
    start = dt_parsed - timedelta(days=10)
    volume = await abdh(tickers=[fut_1, fut_2], flds="volume", start_date=start, end_date=dt_parsed, **kwargs)
    nw_vol = nw.from_native(volume)

    if len(nw_vol) == 0:
        return fut_1

    # LONG format: filter to volume rows, get latest value per ticker
    if "field" in nw_vol.columns and "value" in nw_vol.columns:
        vol_rows = nw_vol.filter(nw.col("field").str.to_lowercase() == "volume")
        if len(vol_rows) == 0:
            return fut_1

        # Sort by date desc, take latest per ticker
        if "date" in vol_rows.columns:
            vol_rows = vol_rows.sort("date", descending=True)

        best_ticker = fut_1
        max_vol = 0.0
        for tk in [fut_1, fut_2]:
            tk_rows = vol_rows.filter(nw.col("ticker") == tk)
            if len(tk_rows) > 0:
                try:
                    vol = float(tk_rows["value"][0])
                    if vol > max_vol:
                        max_vol = vol
                        best_ticker = tk
                except (ValueError, TypeError):
                    pass
        return best_ticker

    return fut_1


async def acdx_ticker(
    gen_ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Async resolve generic CDX ticker to specific series.

    Methodology matches the release/0.x resolver logic:
    - Fetch ``ROLLING_SERIES``, ``VERSION``, ``ON_THE_RUN_CURRENT_BD_INDICATOR``,
      and ``CDS_FIRST_ACCRUAL_START_DATE``.
    - Resolve ``GEN`` to ``S{series}``.
    - Append ``V{n}`` token when ``VERSION > 1``.
    - If the requested date is before accrual start, fall back to prior series.

    Args:
        gen_ticker: Generic CDX ticker (e.g., 'CDX IG CDSI GEN 5Y Corp').
        dt: Reference date.
        **kwargs: Additional arguments passed to abdp.

    Returns:
        Specific series ticker (e.g., ``CDX IG CDSI S45 5Y Corp`` or
        ``CDX HY CDSI S44 V2 5Y Corp``).

    Example::

        import asyncio
        from xbbg.ext.futures import acdx_ticker


        async def main():
            ticker = await acdx_ticker("CDX IG CDSI GEN 5Y Corp", "2024-01-15")


        asyncio.run(main())
    """
    from xbbg import abdp

    dt_parsed = _parse_date(dt)

    try:
        info = await abdp(tickers=gen_ticker, flds=_CDX_FIELDS, **kwargs)
    except (ValueError, TypeError, KeyError):
        logger.warning("Failed to get CDX info")
        return ""

    nw_info = nw.from_native(info)

    if len(nw_info) == 0:
        return ""

    ticker_data = nw_info
    if "ticker" in nw_info.columns:
        ticker_data = nw_info.filter(nw.col("ticker") == gen_ticker)
        if len(ticker_data) == 0:
            ticker_data = nw_info

    otr = _extract_field_value(ticker_data, _FLD_OTR_INDICATOR)
    if otr is not None and str(otr).upper() != "Y":
        logger.warning(
            "Generic ticker %s has ON_THE_RUN_CURRENT_BD_INDICATOR=%r (expected 'Y')",
            gen_ticker,
            otr,
        )

    series_raw = _extract_field_value(ticker_data, _FLD_ROLLING_SERIES)
    if series_raw is None:
        return ""

    try:
        series = int(series_raw)
    except (ValueError, TypeError):
        return ""

    version: int | None = None
    version_raw = _extract_field_value(ticker_data, _FLD_VERSION)
    if version_raw is not None:
        try:
            version = int(version_raw)
        except (ValueError, TypeError):
            version = None

    start_dt = None
    start_dt_raw = _extract_field_value(ticker_data, _FLD_ACCRUAL_START)
    if start_dt_raw is not None:
        try:
            start_dt = _parse_date(start_dt_raw)
        except (ValueError, TypeError):
            start_dt = None

    tokens = gen_ticker.split()
    if "GEN" not in tokens:
        logger.warning("Generic ticker %s does not contain GEN token", gen_ticker)
        return ""

    gen_idx = tokens.index("GEN")
    tokens[gen_idx] = f"S{series}"
    if version is not None and version > 1:
        tokens.insert(gen_idx + 1, f"V{version}")
    resolved = " ".join(tokens)

    # If request date is before current-series accrual start, use previous series
    if start_dt is not None and dt_parsed < start_dt and series > 1:
        prev_tokens = _strip_version_from_ticker(resolved).split()
        series_idx = _find_series_token_index(prev_tokens)
        if series_idx is not None:
            prev_tokens[series_idx] = f"S{series - 1}"
            resolved = " ".join(prev_tokens)

    return resolved


async def aactive_cdx(
    gen_ticker: str,
    dt: str | date,
    lookback_days: int = 10,
    **kwargs,
) -> str:
    """Async get the most active CDX contract for a date.

    Methodology matches release/0.x:
    1) resolve current series via ``acdx_ticker``
    2) derive previous series candidate (version-aware)
    3) prefer previous if date is before current accrual start
    4) otherwise compare recency of ``PX_LAST`` over lookback window
    """
    from xbbg import abdh, abdp

    cur = await acdx_ticker(gen_ticker=gen_ticker, dt=dt, **kwargs)
    if not cur:
        return ""

    dt_parsed = _parse_date(dt)

    prev = ""
    prev_base = _strip_version_from_ticker(cur)
    parts = prev_base.split()
    idx = _find_series_token_index(parts)
    if idx is not None:
        series = _parse_series_token(parts[idx])
        if series is not None and series > 1:
            parts[idx] = f"S{series - 1}"
            prev = " ".join(parts)

    if not prev:
        return cur

    prev = await _resolve_version_for_ticker(prev, **kwargs)

    # Before accrual start, prior series should be active
    try:
        cur_meta = await abdp(tickers=cur, flds=[_FLD_ACCRUAL_START], **kwargs)
        nw_meta = nw.from_native(cur_meta)
        cur_start_raw = _extract_field_value(nw_meta, _FLD_ACCRUAL_START)
        if cur_start_raw is not None:
            cur_start = _parse_date(cur_start_raw)
            if dt_parsed < cur_start:
                return prev
    except (ValueError, TypeError):
        logger.debug("Failed to check CDX metadata")

    # Compare activity using latest non-null PX_LAST date
    start = dt_parsed - timedelta(days=lookback_days)
    end = dt_parsed

    try:
        px = await abdh(tickers=[cur, prev], flds=["PX_LAST"], start_date=start, end_date=end, **kwargs)
        nw_px = nw.from_native(px)

        if len(nw_px) == 0:
            return cur

        latest_dates: dict[str, str] = {}

        # LONG format: ticker/date/field/value
        if "field" in nw_px.columns and "value" in nw_px.columns:
            px_rows = nw_px.filter(nw.col("field").str.to_uppercase() == "PX_LAST")
            px_rows = px_rows.filter(~nw.col("value").is_null())
            px_rows = px_rows.filter(nw.col("value") != "")

            if len(px_rows) == 0 or "date" not in px_rows.columns:
                return cur

            for ticker in [cur, prev]:
                tk_rows = px_rows.filter(nw.col("ticker") == ticker).sort("date", descending=True)
                if len(tk_rows) > 0:
                    latest_dates[ticker] = str(tk_rows["date"][0])

        # Wide format: ticker/date/PX_LAST
        else:
            px_col = None
            if "PX_LAST" in nw_px.columns:
                px_col = "PX_LAST"
            elif "px_last" in nw_px.columns:
                px_col = "px_last"

            if px_col is None or "date" not in nw_px.columns:
                return cur

            px_rows = nw_px.filter(~nw.col(px_col).is_null())
            for ticker in [cur, prev]:
                tk_rows = px_rows.filter(nw.col("ticker") == ticker).sort("date", descending=True)
                if len(tk_rows) > 0:
                    latest_dates[ticker] = str(tk_rows["date"][0])

        best_ticker = cur
        best_date = latest_dates.get(cur, "")
        if prev in latest_dates and latest_dates[prev] > best_date:
            best_ticker = prev
        return best_ticker

    except (ValueError, TypeError, KeyError):
        logger.debug("Failed to compare CDX activity")

    return cur


# =============================================================================
# Sync wrappers
# =============================================================================


def fut_ticker(
    gen_ticker: str,
    dt: str | date,
    **kwargs,
) -> str:
    """Resolve generic futures ticker to specific contract.

    Sync wrapper for afut_ticker(). See afut_ticker() for full documentation.

    Example::

        from xbbg import ext

        # Get March 2024 E-mini S&P contract
        ticker = ext.fut_ticker("ES1 Index", "2024-01-15")
    """
    return asyncio.run(afut_ticker(gen_ticker=gen_ticker, dt=dt, **kwargs))


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
