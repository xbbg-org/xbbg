"""Optional integration with pandas_market_calendars (PMC) for session times.

This module provides helpers to map internal exchange names (from exch.yml)
to pandas_market_calendars calendars and extract per-date session windows.

If PMC is not installed or a calendar is not found, callers should fall back
to the existing exch.yml-based logic.
"""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

try:
    import pandas_market_calendars as mcal  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mcal = None  # type: ignore

# Minimal initial mapping. Expand as needed.
PMC_EXCH_MAP: dict[str, str] = {
    # US equities
    'EquityUS': 'NYSE',
    'IndexUS': 'NYSE',  # indices often share the NYSE day session window
    # UK/London
    'EquityLondon': 'LSE',
    'IndexLondon': 'LSE',
    # CME futures (equity)
    'CME': 'CME_Equity',
}


def pmc_calendar_name(exch_name: str) -> Optional[str]:
    """Map internal exchange name to a pandas_market_calendars name."""
    return PMC_EXCH_MAP.get(exch_name)


def _tzname_from_cal(cal) -> str:
    try:
        return getattr(cal.tz, 'zone', str(cal.tz))
    except Exception:
        return 'UTC'


def session_times_from_pmc(
    exch_name: str,
    dt,
    session: str = 'day',
) -> Optional[Tuple[str, str, str]]:
    """Return (tz, start_hhmm, end_hhmm) from PMC for a given exchange and date.

    Args:
        exch_name: Internal exchange identifier (e.g., 'EquityUS').
        dt: Date-like input.
        session: 'allday' or 'day'. Other sessions fall back to 'day'.

    Returns:
        Optional tuple of (timezone_name, start_hhmm, end_hhmm). None if unavailable.
    """
    if mcal is None:
        return None

    cal_name = pmc_calendar_name(exch_name)
    if not cal_name:
        return None

    try:
        cal = mcal.get_calendar(cal_name)
    except Exception:
        return None

    date_str = pd.Timestamp(dt).strftime('%Y-%m-%d')

    # Try to include pre and post columns when available
    try:
        sch = cal.schedule(start_date=date_str, end_date=date_str, start='pre', end='post')
    except TypeError:
        # Older versions do not accept start/end; fall back
        sch = cal.schedule(start_date=date_str, end_date=date_str)

    if sch.empty:
        return None

    tz_name = _tzname_from_cal(cal)
    row = sch.iloc[0]

    def to_local_hhmm(ts: pd.Timestamp) -> str:
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')
        return ts.tz_convert(tz_name).strftime('%H:%M')

    # Base day window
    start_day = to_local_hhmm(pd.Timestamp(row.get('market_open')))
    end_day = to_local_hhmm(pd.Timestamp(row.get('market_close')))

    if session != 'allday':
        return tz_name, start_day, end_day

    # Attempt to extend with pre/post when present
    pre_ts = row.get('pre')
    post_ts = row.get('post')
    start_all = to_local_hhmm(pd.Timestamp(pre_ts)) if pd.notna(pre_ts) else start_day
    end_all = to_local_hhmm(pd.Timestamp(post_ts)) if pd.notna(post_ts) else end_day

    return tz_name, start_all, end_all


