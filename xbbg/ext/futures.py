"""Futures contract resolution utilities.

Resolves generic futures tickers (e.g. ``ES1 Index``) to specific contracts
(e.g. ``ESH6 Index``) and selects active contracts by volume.

Resolution uses Bloomberg's ``FUT_CHAIN_LAST_TRADE_DATES`` bulk field with a
``CHAIN_DATE`` override, returning all contracts and their expiry dates in a
single ``bds()`` call.  This replaces the previous approach of manually
constructing candidate tickers from ``FUT_GEN_MONTH`` cycle codes.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
import logging
import re

import narwhals as nw
import pandas as pd

from xbbg import const
from xbbg.backend import Backend, Format
from xbbg.core.utils.dates import parse_date as _parse_date
from xbbg.io.convert import is_empty

logger = logging.getLogger(__name__)

__all__ = ["fut_ticker", "active_futures"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_generic_ticker(gen_ticker: str) -> tuple[str, int, str]:
    """Parse a generic futures ticker into components.

    Args:
        gen_ticker: Generic ticker like 'ES1 Index', 'CL2 Comdty',
            '7203 1 JT Equity'.

    Returns:
        Tuple of (root, n, asset_type) where:
        - root: The ticker root (e.g., 'ES', 'CL', '7203')
        - n: The contract number (1 = front month, 2 = second, etc.)
        - asset_type: The asset type (e.g., 'Index', 'Comdty', 'JT Equity')

    Raises:
        ValueError: If the ticker format is not recognized.
    """
    t_info = gen_ticker.split()
    asset = t_info[-1]

    if asset in ["Index", "Curncy", "Comdty"]:
        ticker = " ".join(t_info[:-1])
        root = ticker[:-1]
        n = int(ticker[-1])
        asset_type = asset
    elif asset == "Equity":
        ticker = t_info[0]
        root = ticker[:-1]
        n = int(ticker[-1])
        asset_type = " ".join(t_info[1:])
    else:
        raise ValueError(f"Unknown asset type for generic ticker: {gen_ticker}")

    return root, n, asset_type


def _find_col(columns: list[str], candidates: list[str]) -> str | None:
    """Find first matching column name (case-insensitive)."""
    col_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in col_lower:
            return col_lower[cand.lower()]
    return None


def _resolve_chain(
    gen_ticker: str,
    dt: datetime,
    **kwargs,
) -> list[tuple[str, datetime]]:
    """Get futures chain with expiry dates from Bloomberg.

    Single ``bds()`` call using ``FUT_CHAIN_LAST_TRADE_DATES`` with a
    ``CHAIN_DATE`` override.

    Args:
        gen_ticker: Generic ticker (e.g. ``ES1 Index``).
        dt: Reference date -- only contracts expiring **after** this date are
            returned.
        **kwargs: Forwarded to ``bds()``.

    Returns:
        Sorted list of ``(ticker, expiry_date)`` for contracts expiring after
        *dt*, ordered by expiry ascending.
    """
    from xbbg.api.reference.reference import bds

    chain_date = dt.strftime("%Y%m%d")

    try:
        chain = bds(
            gen_ticker,
            "FUT_CHAIN_LAST_TRADE_DATES",
            CHAIN_DATE=chain_date,
            backend=Backend.PANDAS,
            **kwargs,
        )
    except Exception as e:
        logger.error("Failed to get futures chain for %s: %s", gen_ticker, e)
        return []

    if is_empty(chain):
        logger.warning("Empty futures chain for %s at %s", gen_ticker, chain_date)
        return []

    # Locate ticker and date columns (handle name variations)
    ticker_col = _find_col(
        list(chain.columns),
        ["future's_ticker", "futures_ticker", "security_description", "ticker"],
    )
    date_col = _find_col(
        list(chain.columns),
        ["last_trade_date", "last_tradeable_dt", "date"],
    )

    if ticker_col is None or date_col is None:
        logger.warning(
            "Unexpected columns in FUT_CHAIN_LAST_TRADE_DATES: %s",
            list(chain.columns),
        )
        return []

    # Parse dates, drop nulls, filter for future contracts, sort
    chain[date_col] = pd.to_datetime(chain[date_col], errors="coerce")
    chain = chain.dropna(subset=[ticker_col, date_col])
    future = chain[chain[date_col] > dt].sort_values(date_col)

    return [(str(row[ticker_col]).strip(), row[date_col].to_pydatetime()) for _, row in future.iterrows()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fut_ticker(gen_ticker: str, dt, **kwargs) -> str:
    """Resolve a generic futures ticker to a specific contract.

    Uses Bloomberg's ``FUT_CHAIN_LAST_TRADE_DATES`` bulk field with a
    ``CHAIN_DATE`` override for single-call resolution.

    Args:
        gen_ticker: Generic ticker (e.g. ``'ES1 Index'``, ``'CL2 Comdty'``).
            The trailing digit selects the Nth contract: ``1`` = front month,
            ``2`` = second month, etc.
        dt: Reference date.  The Nth contract *expiring after* this date is
            returned.
        **kwargs: Forwarded to the underlying Bloomberg call.

    Returns:
        Specific contract ticker (e.g. ``'ESH6 Index'``), or empty string on
        failure.
    """
    dt_parsed = _parse_date(dt)

    try:
        _root, n, _asset_type = _parse_generic_ticker(gen_ticker)
    except ValueError as e:
        logger.error(str(e))
        return ""

    contracts = _resolve_chain(gen_ticker, dt_parsed, **kwargs)

    if len(contracts) < n:
        logger.warning(
            "Not enough contracts expiring after %s for %s (need %d, found %d)",
            dt_parsed.date(),
            gen_ticker,
            n,
            len(contracts),
        )
        return ""

    result = contracts[n - 1][0]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Resolved %s @ %s -> %s", gen_ticker, dt_parsed.date(), result)

    return result


def active_futures(ticker: str, dt, **kwargs) -> str:
    """Select the most actively traded futures contract.

    Fetches the futures chain in a single call, then compares recent volume
    between the front-month and second-month contracts to determine which is
    more actively traded.

    Args:
        ticker: Generic futures ticker (e.g. ``'UX1 Index'``, ``'ESA Index'``,
            ``'CLA Comdty'``).  Must be a generic contract, **not** a specific
            one like ``'UXZ5 Index'``.
        dt: Reference date.
        **kwargs: Forwarded to downstream Bloomberg calls.

    Returns:
        Ticker of the most active contract, or empty string on failure.

    Raises:
        ValueError: If *ticker* appears to be a specific contract.
    """
    from xbbg.api.historical import bdh

    dt_parsed = _parse_date(dt)

    # ------------------------------------------------------------------
    # Reject specific contracts
    # ------------------------------------------------------------------
    month_codes = set(const.Futures.values())
    ticker_base = ticker.rsplit(" ", 1)[0]

    month_code_pattern = rf"[{re.escape(''.join(month_codes))}]"
    match = re.search(rf"(.+)({month_code_pattern})(\d{{1,2}})$", ticker_base)
    if match:
        _prefix, _month_char, digits = match.groups()
        if len(digits) == 2:
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract "
                f"(ends with month code + 2-digit year), not a generic one. "
                f"Use a generic ticker like 'UX1 Index' instead of 'UXZ24 Index'."
            )
        if len(digits) == 1 and len(ticker_base) > 3:
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract, "
                f"not a generic one.  Use a generic ticker like "
                f"'UX1 Index' instead of 'UXZ5 Index'."
            )

    # ------------------------------------------------------------------
    # Build the '...1' generic and resolve the full chain once
    # ------------------------------------------------------------------
    t_info = ticker.split()
    prefix, asset = " ".join(t_info[:-1]), t_info[-1]
    gen_1 = f"{prefix[:-1]}1 {asset}"

    contracts = _resolve_chain(gen_1, dt_parsed, **kwargs)

    if not contracts:
        logger.error("Failed to resolve chain for %s", gen_1)
        return ""

    fut_1, fut_1_expiry = contracts[0]

    if len(contracts) < 2:
        return fut_1

    fut_2 = contracts[1][0]

    # If the request date is well before front-month expiry, skip volume check
    if dt_parsed.month < fut_1_expiry.month and dt_parsed.year == fut_1_expiry.year:
        return fut_1

    # ------------------------------------------------------------------
    # Compare volume over the last ~10 business days
    # ------------------------------------------------------------------
    start_date = dt_parsed - timedelta(days=15)

    volume = bdh(
        tickers=[fut_1, fut_2],
        flds="volume",
        start_date=start_date,
        end_date=dt_parsed,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
    )

    if is_empty(volume):
        return fut_1

    nw_vol = nw.from_native(volume, eager_only=True)
    vol_col = "volume" if "volume" in nw_vol.columns else "VOLUME"

    latest_volumes: dict[str, float] = {}
    for tk in [fut_1, fut_2]:
        tk_data = (
            nw_vol.filter(nw.col("ticker") == tk)
            .select(["date", vol_col])
            .drop_nulls(subset=[vol_col])
            .sort("date", descending=True)
            .head(1)
        )
        if len(tk_data) > 0:
            vol_val = tk_data.item(0, 1)
            if vol_val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    latest_volumes[tk] = float(vol_val)

    if not latest_volumes:
        return fut_1

    return max(latest_volumes, key=lambda k: latest_volumes.get(k, 0))
