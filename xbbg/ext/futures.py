"""Futures contract resolution utilities.

This module provides functions for resolving generic futures tickers to specific
contract tickers and selecting active futures contracts based on volume.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
import logging
import re
from typing import TYPE_CHECKING

import narwhals as nw

from xbbg import const
from xbbg.backend import Backend, Format
from xbbg.io.convert import is_empty

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = ["fut_ticker", "active_futures"]

# Month code to month number mapping for futures contracts
MONTH_CODE_MAP = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}


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


def _parse_generic_ticker(gen_ticker: str) -> tuple[str, int, str]:
    """Parse a generic futures ticker into components.

    Args:
        gen_ticker: Generic ticker like 'ES1 Index', 'CL2 Comdty', '7203 1 JT Equity'

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


def _get_cycle_months(gen_ticker: str) -> str:
    """Get the contract cycle months from Bloomberg.

    Args:
        gen_ticker: Generic futures ticker like 'ES1 Index'

    Returns:
        String of month codes (e.g., 'HMUZ' for quarterly, 'FGHJKMNQUVXZ' for monthly)
    """
    from xbbg.api.reference import bdp

    result = bdp(gen_ticker, "FUT_GEN_MONTH", backend=Backend.NARWHALS, format=Format.SEMI_LONG)
    if is_empty(result):
        logger.warning("Could not get FUT_GEN_MONTH for %s", gen_ticker)
        return ""

    # Get the value from narwhals DataFrame using vectorized operations
    nw_result = nw.from_native(result, eager_only=True)

    # Try to get FUT_GEN_MONTH column, fallback to fut_gen_month or value
    for col_name in ["FUT_GEN_MONTH", "fut_gen_month", "value"]:
        if col_name in nw_result.columns:
            val = nw_result.select(col_name).drop_nulls().head(1)
            if len(val) > 0:
                return str(val.item(0, 0))

    return ""


def _construct_contract_ticker(
    root: str, month_code: str, year: int, asset_type: str, use_single_digit_year: bool = False
) -> str:
    """Construct a specific futures contract ticker.

    Args:
        root: Ticker root (e.g., 'ES', 'CL')
        month_code: Month code (e.g., 'H', 'M', 'U', 'Z')
        year: Full year (e.g., 2024)
        asset_type: Asset type (e.g., 'Index', 'Comdty')
        use_single_digit_year: If True, use single digit year (e.g., 'ESH5' instead of 'ESH25')

    Returns:
        Contract ticker (e.g., 'ESH24 Index')
    """
    year_str = str(year)[-1] if use_single_digit_year else str(year)[-2:]
    return f"{root}{month_code}{year_str} {asset_type}"


def active_futures(ticker: str, dt, **kwargs) -> str:
    """Active futures contract.

    Determines the most actively traded futures contract by comparing volume
    between the front-month and second-month contracts.

    Args:
        ticker: Generic futures ticker, i.e., UX1 Index, ESA Index, Z A Index, CLA Comdty, etc.
            Must be a generic contract (e.g., UX1 Index), not a specific contract (e.g., UXZ5 Index).
        dt: date
        **kwargs: Passed through to downstream resolvers (e.g., logging).

    Returns:
        str: ticker name

    Raises:
        ValueError: If ticker is a specific contract instead of a generic one.
    """
    from xbbg.api.historical import bdh
    from xbbg.api.reference import bdp

    dt_parsed = _parse_date(dt)

    # Check if ticker is already a specific contract (contains month codes)
    month_codes = set(const.Futures.values())  # {'F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'}
    ticker_base = ticker.rsplit(" ", 1)[0]  # Remove asset type (Index, Comdty, etc.)

    # Generic tickers end with just a number (1, 2, etc.) like UX1, ESA1, ZA1
    # Specific contracts end with month code + year digits like UXZ5, UXZ24, ESAM24
    # Pattern: ends with [month_code][1-2 digits] where month_code is immediately before digits
    month_code_pattern = rf"[{re.escape(''.join(month_codes))}]"
    # Match pattern: [anything][month_code][1-2 digits] at the end
    match = re.search(rf"(.+)({month_code_pattern})(\d{{1,2}})$", ticker_base)
    if match:
        prefix, month_char, digits = match.groups()
        # If it ends with [month_code][2 digits] it's definitely specific
        # If it ends with [month_code][1 digit], check length: very short (3 chars) is likely generic
        if len(digits) == 2:
            # Two digit year = definitely specific contract
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract (ends with month code + 2-digit year), "
                f"not a generic one. Please use a generic ticker (e.g., 'UX1 Index' instead of 'UXZ24 Index'). "
                f"Generic tickers end with a number (1, 2, etc.) before the asset type."
            )
        # Single digit: could be generic (UX1) or specific (UXZ5)
        # Check length: very short (3 chars) with single digit is likely generic
        if len(digits) == 1 and len(ticker_base) > 3:
            # Longer ticker ending in [month_code][digit] is likely specific (e.g., "UXZ5", "ESAM4")
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract, not a generic one. "
                f"Please use a generic ticker (e.g., 'UX1 Index' instead of 'UXZ5 Index'). "
                f"Generic tickers end with a number (1, 2, etc.) before the asset type."
            )

    t_info = ticker.split()
    prefix, asset = " ".join(t_info[:-1]), t_info[-1]

    # Construct the generic tickers for front and second month
    f1, f2 = f"{prefix[:-1]}1 {asset}", f"{prefix[:-1]}2 {asset}"

    # Get specific contracts using Bloomberg-based resolution
    fut_1 = fut_ticker(gen_ticker=f1, dt=dt, **kwargs)
    fut_2 = fut_ticker(gen_ticker=f2, dt=dt, **kwargs)

    if not fut_1:
        logger.error("Failed to resolve front-month contract for %s", f1)
        return ""

    if not fut_2:
        # If we can't get second month, just return front month
        return fut_1

    fut_tk = bdp(
        tickers=[fut_1, fut_2],
        flds="last_tradeable_dt",
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
    )

    if is_empty(fut_tk):
        return fut_1

    # Parse the result to get last_tradeable_dt for fut_1 using vectorized operations
    nw_fut = nw.from_native(fut_tk, eager_only=True)
    first_matu = None

    # Filter for fut_1 ticker and get the expiry date value
    # SEMI_LONG format returns columns: ticker, field, value
    fut_1_data = nw_fut.filter(nw.col("ticker") == fut_1).select(nw.col("value").alias("exp_date")).head(1)

    if fut_1_data.shape[0] > 0:
        val = fut_1_data.item(0, 0)
        if val:
            with contextlib.suppress(ValueError, TypeError):
                first_matu = _parse_date(val)

    if first_matu is None:
        return fut_1

    if dt_parsed.month < first_matu.month:
        return fut_1

    # Get volume for last ~10 business days (request 15 calendar days to be safe)
    start_date = dt_parsed - timedelta(days=15)
    end_date = dt_parsed

    volume = bdh(
        tickers=[fut_1, fut_2],
        flds="volume",
        start_date=start_date,
        end_date=end_date,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
    )

    if is_empty(volume):
        return fut_1

    # Find ticker with highest volume on most recent date using vectorized operations
    nw_vol = nw.from_native(volume, eager_only=True)

    # Normalize volume column name (handle both 'volume' and 'VOLUME')
    vol_col = "volume" if "volume" in nw_vol.columns else "VOLUME"

    # Get the most recent date and volume for each ticker
    latest_volumes = {}
    for ticker in [fut_1, fut_2]:
        ticker_data = (
            nw_vol.filter(nw.col("ticker") == ticker)
            .select(["date", vol_col])
            .drop_nulls(subset=[vol_col])
            .sort("date", descending=True)
            .head(1)
        )
        if len(ticker_data) > 0:
            vol_val = ticker_data.item(0, 1)
            if vol_val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    latest_volumes[ticker] = float(vol_val)

    if not latest_volumes:
        return fut_1

    # Return ticker with highest volume
    return max(latest_volumes, key=lambda k: latest_volumes.get(k, 0))


def fut_ticker(gen_ticker: str, dt, **kwargs) -> str:
    """Get specific futures contract ticker from generic ticker.

    Uses Bloomberg's FUT_GEN_MONTH field to determine the contract cycle,
    then constructs candidate contracts and queries their expiration dates.

    Args:
        gen_ticker: Generic ticker (e.g., 'ES1 Index', 'CL2 Comdty')
        dt: Date to resolve for
        **kwargs: Passed through to Bloomberg calls (e.g., timeout).

    Returns:
        Specific contract ticker (e.g., 'ESH24 Index')
    """
    from xbbg.api.reference import bdp

    dt_parsed = _parse_date(dt)
    today = datetime.today()

    # Parse the generic ticker
    try:
        root, n, asset_type = _parse_generic_ticker(gen_ticker)
    except ValueError as e:
        logger.error(str(e))
        return ""

    # Get cycle months from Bloomberg
    cycle_months = _get_cycle_months(gen_ticker)
    if not cycle_months:
        logger.error("Could not determine contract cycle for %s", gen_ticker)
        return ""

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Contract cycle for %s: %s", gen_ticker, cycle_months)

    # Determine if we should use single-digit year (for current year contracts)
    use_single_digit_year = (today.month == dt_parsed.month) and (today.year == dt_parsed.year)

    # Generate candidate contracts for a range of years
    start_year = dt_parsed.year - 1
    end_year = dt_parsed.year + 3

    candidates = []
    for year in range(start_year, end_year + 1):
        for month_code in cycle_months:
            ticker = _construct_contract_ticker(root, month_code, year, asset_type, use_single_digit_year)
            candidates.append(ticker)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Generated %d candidate contracts for %s", len(candidates), gen_ticker)

    # Query expiration dates from Bloomberg
    try:
        exp_dates = bdp(
            tickers=candidates,
            flds="last_tradeable_dt",
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
        )
    except Exception as e:
        logger.error("Failed to query expiration dates for %s: %s", gen_ticker, e)
        return ""

    if is_empty(exp_dates):
        logger.warning("No valid futures contracts found for %s", gen_ticker)
        return ""

    # Parse results and build list of (ticker, expiration_date) tuples using vectorized operations
    nw_exp = nw.from_native(exp_dates, eager_only=True)
    valid_contracts = []

    # Get ticker and expiration date columns, handling both 'value' and 'last_tradeable_dt' column names
    exp_col = "value" if "value" in nw_exp.columns else "last_tradeable_dt"

    # Filter for non-null tickers and expiration dates using drop_nulls
    exp_data = nw_exp.select(["ticker", exp_col]).drop_nulls(subset=["ticker", exp_col])

    # Convert to list of tuples
    for row in exp_data.iter_rows(named=True):
        ticker = row.get("ticker")
        exp_val = row.get(exp_col)
        if ticker and exp_val:
            try:
                exp_dt = _parse_date(exp_val)
                valid_contracts.append((ticker, exp_dt))
            except (ValueError, TypeError):
                continue

    if not valid_contracts:
        logger.warning("No valid futures contracts found for %s", gen_ticker)
        return ""

    # Sort by expiration date
    valid_contracts.sort(key=lambda x: x[1])

    # Filter contracts expiring after dt
    future_contracts = [(t, d) for t, d in valid_contracts if d > dt_parsed]

    if len(future_contracts) < n:
        logger.warning(
            "Not enough contracts expiring after %s for %s (need %d, found %d)",
            dt_parsed.date(),
            gen_ticker,
            n,
            len(future_contracts),
        )
        return ""

    # Return the Nth contract (1-indexed, so n-1 for 0-indexed)
    result = future_contracts[n - 1][0]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Resolved %s @ %s -> %s", gen_ticker, dt_parsed.date(), result)

    return result
