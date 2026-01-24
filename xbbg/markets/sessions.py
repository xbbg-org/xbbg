"""Session derivation from Bloomberg data.

This module derives trading session windows (allday, day, pre, post, am, pm)
from Bloomberg's regular trading hours based on market-specific rules.

Derives sessions dynamically from Bloomberg API data.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xbbg.markets.bloomberg import ExchangeInfo

logger = logging.getLogger(__name__)


@dataclass
class SessionWindows:
    """Trading session windows for a security."""

    day: tuple[str, str] | None = None  # Regular trading hours
    allday: tuple[str, str] | None = None  # Extended hours (pre + day + post)
    pre: tuple[str, str] | None = None  # Pre-market
    post: tuple[str, str] | None = None  # Post-market / after-hours
    am: tuple[str, str] | None = None  # Morning session (Asian markets)
    pm: tuple[str, str] | None = None  # Afternoon session (Asian markets)

    def to_dict(self) -> dict[str, tuple[str, str]]:
        """Convert to dict, excluding None values."""
        result = {}
        if self.day:
            result["day"] = self.day
        if self.allday:
            result["allday"] = self.allday
        if self.pre:
            result["pre"] = self.pre
        if self.post:
            result["post"] = self.post
        if self.am:
            result["am"] = self.am
        if self.pm:
            result["pm"] = self.pm
        return result


# =============================================================================
# Market Rules by MIC Code
# =============================================================================


@dataclass
class MarketRule:
    """Rule for deriving sessions from regular trading hours.

    All times are relative offsets in minutes from day_start or day_end.
    """

    # Pre-market: starts this many minutes before day_start
    pre_minutes: int = 0

    # Post-market: ends this many minutes after day_end
    post_minutes: int = 0

    # Lunch break for Asian markets (minutes from day_start)
    # am session ends at day_start + lunch_start_minutes
    # pm session starts at day_start + lunch_end_minutes
    lunch_start_minutes: int | None = None
    lunch_end_minutes: int | None = None

    # For 23-hour futures markets - no extended hours concept
    is_continuous: bool = False


# Minutes constants for readability
MINUTES_30 = 30
MINUTES_60 = 60
MINUTES_90 = 90
MINUTES_150 = 150  # 2.5 hours
MINUTES_210 = 210  # 3.5 hours
MINUTES_240 = 240  # 4 hours
MINUTES_330 = 330  # 5.5 hours (US pre-market: 4:00 AM to 9:30 AM)

# Rules by MIC code
MIC_RULES: dict[str, MarketRule] = {
    # =========================================================================
    # US Equities - Extended hours: 5.5h pre-market, 4h post-market
    # Day: 9:30-16:00, Pre: 4:00-9:30, Post: 16:00-20:00
    # =========================================================================
    "XNYS": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "XNGS": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "XASE": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "ARCX": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "BATS": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "IEXG": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    # =========================================================================
    # Japanese Equities - Lunch break 11:30-12:30 (150 min from 9:00 open)
    # Day: 9:00-15:00, AM: 9:00-11:30, PM: 12:30-15:00
    # Pre: 8:00-9:00 (60 min), Post: 15:00-15:30 (30 min)
    # =========================================================================
    "XTKS": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    "XOSE": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    "XNGO": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    "XFKA": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    "XSAP": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    # =========================================================================
    # Hong Kong - Lunch break 12:00-13:00 (150 min from 9:30 open)
    # Day: 9:30-16:00, AM: 9:30-12:00, PM: 13:00-16:00
    # Pre: 8:45-9:30 (45 min), Post: 16:00-16:15 (15 min)
    # =========================================================================
    "XHKG": MarketRule(pre_minutes=45, post_minutes=15, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210),
    # =========================================================================
    # China - Lunch break 11:30-13:00 (120 min from 9:30 open)
    # Day: 9:30-15:00, AM: 9:30-11:30, PM: 13:00-15:00
    # Pre: 9:15-9:30 (15 min)
    # =========================================================================
    "XSHG": MarketRule(pre_minutes=15, lunch_start_minutes=120, lunch_end_minutes=MINUTES_210),
    "XSHE": MarketRule(pre_minutes=15, lunch_start_minutes=120, lunch_end_minutes=MINUTES_210),
    # =========================================================================
    # South Korea - Post only
    # Day: 9:00-15:20, Post: 15:20-15:35 (15 min)
    # =========================================================================
    "XKRX": MarketRule(post_minutes=15),
    "XKOS": MarketRule(post_minutes=15),
    # =========================================================================
    # Taiwan - Post only
    # Day: 9:00-13:25, Post: 13:25-13:35 (10 min)
    # =========================================================================
    "XTAI": MarketRule(post_minutes=10),
    # =========================================================================
    # Australia - Post only
    # Day: 10:00-16:00, Post: 16:00-16:16 (16 min)
    # =========================================================================
    "XASX": MarketRule(post_minutes=16),
    # =========================================================================
    # UK / London - Post only
    # Day: 8:00-16:30, Post: 16:30-17:00 (30 min)
    # =========================================================================
    "XLON": MarketRule(post_minutes=MINUTES_30),
    # =========================================================================
    # Germany / Xetra - No extended hours
    # =========================================================================
    "XETR": MarketRule(),
    # =========================================================================
    # Netherlands - Post only
    # =========================================================================
    "XAMS": MarketRule(post_minutes=MINUTES_30),
    # =========================================================================
    # France - Post only
    # =========================================================================
    "XPAR": MarketRule(post_minutes=MINUTES_30),
    # =========================================================================
    # Other European - Post only
    # =========================================================================
    "XMAD": MarketRule(post_minutes=MINUTES_30),  # Spain
    "XMIL": MarketRule(),  # Italy
    "XSWX": MarketRule(),  # Switzerland
    "XSTO": MarketRule(post_minutes=MINUTES_30),  # Sweden
    # =========================================================================
    # India - Post only
    # Day: 9:00-15:30, Post: 15:30-17:10 (100 min)
    # =========================================================================
    "XNSE": MarketRule(post_minutes=100),
    "XBOM": MarketRule(post_minutes=100),
    # =========================================================================
    # Futures - Continuous trading (no extended hours concept)
    # =========================================================================
    "XCME": MarketRule(is_continuous=True),
    "XCBT": MarketRule(is_continuous=True),
    "XCEC": MarketRule(is_continuous=True),
    "XNYM": MarketRule(is_continuous=True),
    "IFEU": MarketRule(is_continuous=True),
    "IFUS": MarketRule(is_continuous=True),
    "XEUR": MarketRule(is_continuous=True),
}

# Fallback rules by exchange code (Bloomberg's EXCH_CODE field)
EXCH_CODE_RULES: dict[str, MarketRule] = {
    # US
    "US": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "UN": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "UW": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    "UA": MarketRule(pre_minutes=MINUTES_330, post_minutes=MINUTES_240),
    # Japan
    "JT": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    "JP": MarketRule(
        pre_minutes=MINUTES_60, post_minutes=MINUTES_30, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210
    ),
    # Hong Kong
    "HK": MarketRule(pre_minutes=45, post_minutes=15, lunch_start_minutes=MINUTES_150, lunch_end_minutes=MINUTES_210),
    # China
    "CH": MarketRule(pre_minutes=15, lunch_start_minutes=120, lunch_end_minutes=MINUTES_210),
    "CG": MarketRule(pre_minutes=15, lunch_start_minutes=120, lunch_end_minutes=MINUTES_210),
    "CS": MarketRule(pre_minutes=15, lunch_start_minutes=120, lunch_end_minutes=MINUTES_210),
    # Korea
    "KS": MarketRule(post_minutes=15),
    # Taiwan
    "TT": MarketRule(post_minutes=10),
    # Australia
    "AU": MarketRule(post_minutes=16),
    # UK
    "LN": MarketRule(post_minutes=MINUTES_30),
    # Germany
    "GY": MarketRule(),
    # France
    "FP": MarketRule(post_minutes=MINUTES_30),
    # India
    "IN": MarketRule(post_minutes=100),
    "IS": MarketRule(post_minutes=100),
    "IB": MarketRule(post_minutes=100),
    # Futures exchanges - continuous
    "CME": MarketRule(is_continuous=True),
    "CBT": MarketRule(is_continuous=True),
    "CMX": MarketRule(is_continuous=True),
    "NYM": MarketRule(is_continuous=True),
    "ICE": MarketRule(is_continuous=True),
    "EUX": MarketRule(is_continuous=True),
    "OSE": MarketRule(is_continuous=True),
    "SFE": MarketRule(is_continuous=True),
}


def _parse_time(time_str: str | None) -> tuple[int, int] | None:
    """Parse time string to (hours, minutes) tuple."""
    if not time_str:
        return None

    time_str = str(time_str).strip()

    try:
        # HH:MM:SS or HH:MM
        if ":" in time_str:
            parts = time_str.split(":")
            return (int(parts[0]), int(parts[1]))

        # HHMM
        if len(time_str) == 4 and time_str.isdigit():
            return (int(time_str[:2]), int(time_str[2:]))

        # HMM
        if len(time_str) == 3 and time_str.isdigit():
            return (int(time_str[0]), int(time_str[1:]))

    except (ValueError, IndexError):
        pass

    return None


def _format_time(hours: int, minutes: int) -> str:
    """Format hours and minutes to HH:MM string."""
    # Handle wraparound
    hours = hours % 24
    minutes = minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _add_minutes(time_tuple: tuple[int, int], minutes: int) -> tuple[int, int]:
    """Add minutes to a time tuple, handling day wraparound."""
    h, m = time_tuple
    total_minutes = h * 60 + m + minutes
    new_h = (total_minutes // 60) % 24
    new_m = total_minutes % 60
    return (new_h, new_m)


def _subtract_minutes(time_tuple: tuple[int, int], minutes: int) -> tuple[int, int]:
    """Subtract minutes from a time tuple, handling day wraparound."""
    return _add_minutes(time_tuple, -minutes)


def derive_sessions(exchange_info: ExchangeInfo) -> SessionWindows:
    """Derive session windows from Bloomberg exchange info.

    Args:
        exchange_info: ExchangeInfo from Bloomberg query.

    Returns:
        SessionWindows with derived session times.
    """
    # Get regular trading hours from Bloomberg
    regular = exchange_info.sessions.get("regular")
    futures = exchange_info.sessions.get("futures")

    # Use futures hours if no regular hours (for futures contracts)
    base_session = regular or futures
    if not base_session:
        logger.debug("No regular/futures session in exchange_info for %s", exchange_info.ticker)
        return SessionWindows()

    day_start = _parse_time(base_session[0])
    day_end = _parse_time(base_session[1])

    if not day_start or not day_end:
        return SessionWindows()

    # Look up market rule by MIC first, then by exchange code
    rule = None
    if exchange_info.mic:
        rule = MIC_RULES.get(exchange_info.mic)

    if not rule and exchange_info.exch_code:
        rule = EXCH_CODE_RULES.get(exchange_info.exch_code)

    # Format day session
    day_start_str = _format_time(*day_start)
    day_end_str = _format_time(*day_end)

    windows = SessionWindows(day=(day_start_str, day_end_str))

    if rule:
        if rule.is_continuous:
            # Continuous trading (futures) - allday = day
            windows.allday = windows.day
        else:
            # Calculate pre-market
            if rule.pre_minutes > 0:
                pre_start = _subtract_minutes(day_start, rule.pre_minutes)
                windows.pre = (_format_time(*pre_start), day_start_str)

            # Calculate post-market
            if rule.post_minutes > 0:
                post_start = _add_minutes(day_end, 1)  # day_end + 1 minute
                post_end = _add_minutes(day_end, rule.post_minutes)
                windows.post = (_format_time(*post_start), _format_time(*post_end))

            # Calculate allday (pre_start to post_end, or day if no extended)
            if windows.pre or windows.post:
                allday_start = windows.pre[0] if windows.pre else day_start_str
                allday_end = windows.post[1] if windows.post else day_end_str
                windows.allday = (allday_start, allday_end)
            else:
                windows.allday = windows.day

            # Calculate AM/PM sessions (lunch break)
            if rule.lunch_start_minutes is not None and rule.lunch_end_minutes is not None:
                am_end = _add_minutes(day_start, rule.lunch_start_minutes)
                pm_start = _add_minutes(day_start, rule.lunch_end_minutes)
                windows.am = (day_start_str, _format_time(*am_end))
                windows.pm = (_format_time(*pm_start), day_end_str)
    else:
        # No rule found - allday = day
        windows.allday = windows.day
        logger.debug(
            "No session rule for MIC=%s, exch_code=%s - using day as allday",
            exchange_info.mic,
            exchange_info.exch_code,
        )

    return windows


def get_session_windows(
    ticker: str,
    mic: str | None = None,
    exch_code: str | None = None,
    regular_hours: tuple[str, str] | None = None,
) -> SessionWindows:
    """Get session windows for a ticker.

    This is a convenience function that creates a minimal ExchangeInfo
    and derives sessions from it.

    Args:
        ticker: Ticker symbol.
        mic: MIC code (e.g., "XNYS").
        exch_code: Bloomberg exchange code (e.g., "US").
        regular_hours: Regular trading hours as (start, end).

    Returns:
        SessionWindows with derived session times.
    """
    from xbbg.markets.bloomberg import ExchangeInfo

    sessions = {}
    if regular_hours:
        sessions["regular"] = regular_hours

    info = ExchangeInfo(
        ticker=ticker,
        mic=mic,
        exch_code=exch_code,
        sessions=sessions,
    )
    return derive_sessions(info)
