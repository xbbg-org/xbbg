"""Bloomberg exchange metadata query module.

This module provides functions to query Bloomberg for exchange metadata including
timezone, MIC code, and trading hours. It serves as one layer in the exchange
resolution waterfall:

1. Runtime Override → User-set via function call
2. Cache → ~/.xbbg/cache/exchanges.parquet
3. Bloomberg Query → This module
4. PMC Calendar → Use MIC from Bloomberg
5. Country Inference → Infer timezone from COUNTRY_ISO
6. Hardcoded Fallback → Minimal defaults

Design:
- Queries Bloomberg for exchange-related fields via bdp API.
- Parses trading hours from Bloomberg format to session dict.
- Falls back to country-based timezone inference when IANA_TIME_ZONE unavailable.
- Provides both async and sync interfaces.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

# Bloomberg fields to query for exchange metadata
EXCHANGE_FIELDS = [
    "IANA_TIME_ZONE",  # Primary timezone source (e.g., "America/New_York")
    "TIME_ZONE_NUM",  # UTC offset fallback (e.g., -5.0)
    "ID_MIC_PRIM_EXCH",  # MIC code for PMC lookup (e.g., "XNYS")
    "EXCH_CODE",  # Bloomberg exchange code (e.g., "US")
    "COUNTRY_ISO",  # For timezone inference if IANA_TIME_ZONE missing
    "TRADING_DAY_START_TIME_EOD",  # Regular session start (e.g., "0930")
    "TRADING_DAY_END_TIME_EOD",  # Regular session end (e.g., "1600")
    "FUT_TRADING_HRS",  # Futures hours (e.g., "18:00-17:00")
]

# Comprehensive country ISO code to IANA timezone mapping
# Used as fallback when IANA_TIME_ZONE field is not available from Bloomberg
COUNTRY_TIMEZONE_MAP: dict[str, str] = {
    # North America
    "US": "America/New_York",
    "CA": "America/Toronto",
    "MX": "America/Mexico_City",
    # Europe
    "GB": "Europe/London",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "CH": "Europe/Zurich",
    "NL": "Europe/Amsterdam",
    "BE": "Europe/Brussels",
    "IT": "Europe/Rome",
    "ES": "Europe/Madrid",
    "PT": "Europe/Lisbon",
    "AT": "Europe/Vienna",
    "IE": "Europe/Dublin",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "PL": "Europe/Warsaw",
    "CZ": "Europe/Prague",
    "HU": "Europe/Budapest",
    "GR": "Europe/Athens",
    "RU": "Europe/Moscow",
    "TR": "Europe/Istanbul",
    # Asia Pacific
    "JP": "Asia/Tokyo",
    "HK": "Asia/Hong_Kong",
    "SG": "Asia/Singapore",
    "CN": "Asia/Shanghai",
    "TW": "Asia/Taipei",
    "KR": "Asia/Seoul",
    "IN": "Asia/Kolkata",
    "AU": "Australia/Sydney",
    "NZ": "Pacific/Auckland",
    "TH": "Asia/Bangkok",
    "MY": "Asia/Kuala_Lumpur",
    "ID": "Asia/Jakarta",
    "PH": "Asia/Manila",
    "VN": "Asia/Ho_Chi_Minh",
    "PK": "Asia/Karachi",
    "BD": "Asia/Dhaka",
    "LK": "Asia/Colombo",
    # Middle East
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
    "IL": "Asia/Jerusalem",
    "QA": "Asia/Qatar",
    "KW": "Asia/Kuwait",
    "BH": "Asia/Bahrain",
    "OM": "Asia/Muscat",
    # Africa
    "ZA": "Africa/Johannesburg",
    "EG": "Africa/Cairo",
    "NG": "Africa/Lagos",
    "KE": "Africa/Nairobi",
    "MA": "Africa/Casablanca",
    # South America
    "BR": "America/Sao_Paulo",
    "AR": "America/Buenos_Aires",
    "CL": "America/Santiago",
    "CO": "America/Bogota",
    "PE": "America/Lima",
    "VE": "America/Caracas",
}


@dataclass
class ExchangeInfo:
    """Exchange metadata from Bloomberg.

    Attributes:
        ticker: The ticker symbol queried.
        mic: MIC code (e.g., XNYS) from ID_MIC_PRIM_EXCH.
        exch_code: Bloomberg exchange code (e.g., US) from EXCH_CODE.
        timezone: IANA timezone (e.g., America/New_York) from IANA_TIME_ZONE.
        utc_offset: UTC offset in hours from TIME_ZONE_NUM.
        sessions: Trading sessions as {session_name: (start, end)} from trading hours fields.
        source: Data source indicator ('override' | 'cache' | 'bloomberg' | 'pmc' | 'inferred' | 'fallback').
        cached_at: Timestamp when data was cached.
    """

    ticker: str
    mic: str | None = None
    exch_code: str | None = None
    timezone: str = "UTC"
    utc_offset: float | None = None
    sessions: dict[str, tuple[str, str]] = field(default_factory=dict)
    source: str = "fallback"
    cached_at: datetime | None = None


def _parse_hhmm(time_str: str | None) -> str | None:
    """Parse Bloomberg time format (HHMM or HH:MM) to HH:MM format.

    Args:
        time_str: Time string in HHMM or HH:MM format.

    Returns:
        Time string in HH:MM format, or None if invalid.
    """
    if not time_str or pd.isna(time_str):
        return None

    time_str = str(time_str).strip()
    if not time_str:
        return None

    # Handle HH:MM format
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) >= 2:
            try:
                hh = int(parts[0])
                mm = int(parts[1])
                return f"{hh:02d}:{mm:02d}"
            except ValueError:
                return None

    # Handle HHMM format (e.g., "0930", "1600")
    if time_str.isdigit() and len(time_str) == 4:
        try:
            hh = int(time_str[:2])
            mm = int(time_str[2:])
            return f"{hh:02d}:{mm:02d}"
        except ValueError:
            return None

    return None


def _parse_futures_hours(fut_hours: str | None) -> dict[str, tuple[str, str]]:
    """Parse Bloomberg FUT_TRADING_HRS field to session dict.

    Bloomberg returns futures hours in format like "18:00-17:00" which may span days.

    Args:
        fut_hours: Futures trading hours string from Bloomberg.

    Returns:
        Dict with session name and (start, end) tuple.
    """
    if not fut_hours or pd.isna(fut_hours):
        return {}

    fut_hours = str(fut_hours).strip()
    if not fut_hours:
        return {}

    # Pattern: HH:MM-HH:MM or HHMM-HHMM
    pattern = r"(\d{1,2}:\d{2}|\d{4})\s*-\s*(\d{1,2}:\d{2}|\d{4})"
    match = re.match(pattern, fut_hours)
    if match:
        start = _parse_hhmm(match.group(1))
        end = _parse_hhmm(match.group(2))
        if start and end:
            return {"futures": (start, end)}

    return {}


def _convert_est_to_local(time_str: str, local_tz: str) -> str:
    """Convert a time string from EST to local timezone.

    Bloomberg returns trading hours in EST (America/New_York).
    This function converts them to the exchange's local timezone.

    Args:
        time_str: Time in HH:MM format (EST).
        local_tz: IANA timezone of the exchange.

    Returns:
        Time in HH:MM format in local timezone.
    """
    if local_tz in ("America/New_York", "US/Eastern", "EST", "EDT"):
        # Already in EST, no conversion needed
        return time_str

    try:
        # Use a reference date for conversion (timezone offset may vary by date)
        # Use a recent date to get current offset
        ref_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        # Create timestamp in EST
        est_ts = pd.Timestamp(f"{ref_date} {time_str}", tz="America/New_York")

        # Convert to local timezone
        local_ts = est_ts.tz_convert(local_tz)

        return local_ts.strftime("%H:%M")
    except Exception as e:
        logger.debug("Failed to convert time %s from EST to %s: %s", time_str, local_tz, e)
        return time_str


def _parse_trading_hours(
    start_time: str | None,
    end_time: str | None,
    fut_hours: str | None,
    local_tz: str = "America/New_York",
) -> dict[str, tuple[str, str]]:
    """Parse Bloomberg trading hours fields into sessions dict.

    Bloomberg returns times in EST (America/New_York). This function parses
    them and converts to the exchange's local timezone.

    Args:
        start_time: TRADING_DAY_START_TIME_EOD value (in EST).
        end_time: TRADING_DAY_END_TIME_EOD value (in EST).
        fut_hours: FUT_TRADING_HRS value (in EST).
        local_tz: IANA timezone of the exchange for conversion.

    Returns:
        Dict mapping session names to (start, end) tuples in local time.
    """
    sessions: dict[str, tuple[str, str]] = {}

    # Parse regular trading hours
    start = _parse_hhmm(start_time)
    end = _parse_hhmm(end_time)
    if start and end:
        # Convert from EST to local timezone
        local_start = _convert_est_to_local(start, local_tz)
        local_end = _convert_est_to_local(end, local_tz)
        sessions["regular"] = (local_start, local_end)

    # Parse futures hours
    # Note: FUT_TRADING_HRS is typically already in the exchange's local timezone,
    # unlike TRADING_DAY_START_TIME_EOD which is in EST. So we don't convert futures hours.
    futures_sessions = _parse_futures_hours(fut_hours)
    sessions.update(futures_sessions)

    return sessions


def _infer_timezone_from_country(country_iso: str | None) -> str | None:
    """Infer IANA timezone from country ISO code.

    Args:
        country_iso: Two-letter country ISO code.

    Returns:
        IANA timezone string or None if not found.
    """
    if not country_iso or pd.isna(country_iso):
        return None

    country = str(country_iso).strip().upper()
    return COUNTRY_TIMEZONE_MAP.get(country)


def _extract_value(df: pd.DataFrame, field: str) -> str | float | None:
    """Extract a single value from Bloomberg response DataFrame.

    Args:
        df: DataFrame from bdp call.
        field: Field name to extract.

    Returns:
        Field value or None if not found/empty.
    """
    if df.empty:
        return None

    # Match field name case-insensitively (Bloomberg returns UPPERCASE columns)
    field_lower = field.lower()
    col_map = {c.lower(): c for c in df.columns}
    if field_lower not in col_map:
        return None

    actual_col = col_map[field_lower]
    val = df.iloc[0][actual_col]
    if pd.isna(val):
        return None

    return val


def _build_exchange_info_from_response(
    ticker: str,
    df: pd.DataFrame,
) -> ExchangeInfo:
    """Build ExchangeInfo from Bloomberg response DataFrame.

    Args:
        ticker: The ticker that was queried.
        df: DataFrame from bdp call.

    Returns:
        ExchangeInfo populated from Bloomberg data.
    """
    if df.empty:
        logger.warning("Empty response from Bloomberg for ticker %s, using fallback", ticker)
        return ExchangeInfo(ticker=ticker, source="fallback")

    # Extract raw values
    iana_tz = _extract_value(df, "IANA_TIME_ZONE")
    tz_num = _extract_value(df, "TIME_ZONE_NUM")
    mic = _extract_value(df, "ID_MIC_PRIM_EXCH")
    exch_code = _extract_value(df, "EXCH_CODE")
    country_iso = _extract_value(df, "COUNTRY_ISO")
    start_time = _extract_value(df, "TRADING_DAY_START_TIME_EOD")
    end_time = _extract_value(df, "TRADING_DAY_END_TIME_EOD")
    fut_hours = _extract_value(df, "FUT_TRADING_HRS")

    # Determine timezone with fallback chain
    timezone: str = "UTC"
    source: str = "bloomberg"

    if iana_tz and isinstance(iana_tz, str):
        timezone = iana_tz
        source = "bloomberg"
    elif country_iso:
        inferred_tz = _infer_timezone_from_country(str(country_iso))
        if inferred_tz:
            timezone = inferred_tz
            source = "inferred"
            logger.debug(
                "IANA_TIME_ZONE not available for %s, inferred %s from country %s",
                ticker,
                timezone,
                country_iso,
            )
        else:
            logger.warning(
                "Could not infer timezone for %s (country: %s), using UTC fallback",
                ticker,
                country_iso,
            )
            source = "fallback"
    else:
        logger.warning(
            "No timezone or country data available for %s, using UTC fallback",
            ticker,
        )
        source = "fallback"

    # Parse trading hours (Bloomberg returns times in EST, convert to local)
    sessions = _parse_trading_hours(
        str(start_time) if start_time else None,
        str(end_time) if end_time else None,
        str(fut_hours) if fut_hours else None,
        local_tz=timezone,
    )

    # Build ExchangeInfo
    return ExchangeInfo(
        ticker=ticker,
        mic=str(mic) if mic else None,
        exch_code=str(exch_code) if exch_code else None,
        timezone=timezone,
        utc_offset=float(tz_num) if tz_num is not None else None,
        sessions=sessions,
        source=source,
        cached_at=None,
    )


async def afetch_exchange_info(
    ticker: str,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> ExchangeInfo:
    """Async fetch exchange metadata from Bloomberg.

    Queries Bloomberg for exchange-related fields and returns structured
    ExchangeInfo. Falls back gracefully if data is unavailable.

    Args:
        ticker: Ticker symbol to query (e.g., "AAPL US Equity").
        ctx: Bloomberg context with infrastructure settings. If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Additional kwargs passed to bdp call.

    Returns:
        ExchangeInfo with exchange metadata. Source field indicates data origin:
        - 'bloomberg': Data from IANA_TIME_ZONE field
        - 'inferred': Timezone inferred from COUNTRY_ISO
        - 'fallback': Using UTC default
    """
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra
        ctx_kwargs = ctx.to_kwargs()
    else:
        ctx_kwargs = ctx.to_kwargs()

    try:
        # Import bdp from API module
        from xbbg.api.reference import bdp

        # Run bdp in thread pool to avoid blocking
        df = await asyncio.to_thread(
            bdp,
            tickers=ticker,
            flds=EXCHANGE_FIELDS,
            **ctx_kwargs,
        )

        return _build_exchange_info_from_response(ticker, df)

    except Exception as e:
        logger.error(
            "Failed to fetch exchange info from Bloomberg for %s: %s",
            ticker,
            e,
        )
        return ExchangeInfo(ticker=ticker, source="fallback")


def fetch_exchange_info(
    ticker: str,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> ExchangeInfo:
    """Sync fetch exchange metadata from Bloomberg.

    Synchronous wrapper for afetch_exchange_info. Queries Bloomberg for
    exchange-related fields and returns structured ExchangeInfo.

    Args:
        ticker: Ticker symbol to query (e.g., "AAPL US Equity").
        ctx: Bloomberg context with infrastructure settings. If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Additional kwargs passed to bdp call.

    Returns:
        ExchangeInfo with exchange metadata. Source field indicates data origin:
        - 'bloomberg': Data from IANA_TIME_ZONE field
        - 'inferred': Timezone inferred from COUNTRY_ISO
        - 'fallback': Using UTC default

    Examples:
        >>> from xbbg.markets.bloomberg import fetch_exchange_info
        >>> info = fetch_exchange_info("AAPL US Equity")  # doctest: +SKIP
        >>> print(info.timezone)  # doctest: +SKIP
        America/New_York
        >>> print(info.mic)  # doctest: +SKIP
        XNGS
    """
    return asyncio.run(afetch_exchange_info(ticker, ctx, **kwargs))
