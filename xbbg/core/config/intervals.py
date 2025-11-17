"""Trading session interval utilities.

Defines helpers to derive time windows (open, close, normal, exact)
for an instrument's predefined sessions based on exchange metadata.
"""

from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd

from xbbg import const

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Session:
    """Trading session time interval."""
    start_time: str | None
    end_time: str | None


SessNA = Session(None, None)


def _get_standard_sessions() -> set[str]:
    """Extract standard session names from exch.yml dynamically.

    Sessions are extracted from all exchanges defined in exch.yml.
    This allows new sessions to be added to exch.yml without code changes.

    Returns:
        Set of session names found in exch.yml (excluding 'tz' which is not a session).
    """
    try:
        from xbbg.io import param  # noqa: PLC0415
        exch = param.load_config(cat='exch')
        sessions = set()
        for idx in exch.index:
            row = exch.loc[idx]
            if hasattr(row, 'index'):
                # Extract all keys that are not 'tz' and have list/str values (session definitions)
                sessions.update(
                    k for k in row.index
                    if k != 'tz' and isinstance(row.get(k), (list, str))
                )
        return sessions
    except Exception:
        # Fallback to known sessions if config loading fails
        return {'allday', 'day', 'am', 'pm', 'pre', 'post', 'night'}


# Cache the standard sessions (computed once at module load)
STANDARD_SESSIONS = _get_standard_sessions()


def get_interval(ticker, session, **kwargs) -> Session:
    """Get interval from a defined session.

    Args:
        ticker: ticker
        session: Session name. Sessions are dynamically extracted from ``exch.yml``.
            Common sessions include: ``allday``, ``day``, ``am``, ``pm``, ``pre``, ``post``, ``night``.
            Availability depends on exchange - check ``xbbg/markets/exch.yml`` for specific definitions.

            Also supports compound sessions like ``day_open_30``, ``day_normal_30_20``, etc.
            Raises ``ValueError`` if session is not defined for the ticker's exchange.
        **kwargs: Additional arguments forwarded to exchange resolvers.

    Returns:
        Session of start_time and end_time.

    Raises:
        ValueError: If session is not defined for the ticker's exchange.

    Examples:
        >>> get_interval('005490 KS Equity', 'day_open_30')  # doctest: +SKIP
        Session(start_time='09:00', end_time='09:30')
        >>> get_interval('005490 KS Equity', 'day_normal_30_20')  # doctest: +SKIP
        Session(start_time='09:31', end_time='15:00')
        >>> get_interval('005490 KS Equity', 'day_close_20')  # doctest: +SKIP
        Session(start_time='15:01', end_time='15:20')
        >>> get_interval('700 HK Equity', 'am_open_30')  # doctest: +SKIP
        Session(start_time='09:30', end_time='10:00')
        >>> get_interval('700 HK Equity', 'am_normal_30_30')  # doctest: +SKIP
        Session(start_time='10:01', end_time='11:30')
        >>> get_interval('700 HK Equity', 'am_close_30')  # doctest: +SKIP
        Session(start_time='11:31', end_time='12:00')
        >>> get_interval('ES1 Index', 'day_exact_2130_2230')  # doctest: +SKIP
        Session(start_time=None, end_time=None)
        >>> get_interval('ES1 Index', 'allday_exact_2130_2230')  # doctest: +SKIP
        Session(start_time='21:30', end_time='22:30')
        >>> get_interval('ES1 Index', 'allday_exact_2130_0230')  # doctest: +SKIP
        Session(start_time='21:30', end_time='02:30')
        >>> get_interval('AMLP US', 'day_open_30') is SessNA  # doctest: +SKIP
        True
        >>> get_interval('7974 JP Equity', 'day_normal_180_300') is SessNA  # doctest: +SKIP
        True
        >>> get_interval('Z 1 Index', 'allday_normal_30_30')  # doctest: +SKIP
        Session(start_time='01:31', end_time='20:30')
        >>> get_interval('GBP Curncy', 'day')  # doctest: +SKIP
        Session(start_time='17:01', end_time='17:00')
    """
    if '_' not in session:
        # For bare session names (e.g., 'day', 'allday'), use exact session times
        # instead of defaulting to '_normal_0_0' which adds a 1-minute offset.
        interval = Intervals(ticker=ticker, **kwargs)
        if session in interval.exch:
            ss = interval.exch[session]
            return Session(start_time=str(ss[0]), end_time=str(ss[-1]))

        # Session not found - raise error with helpful message
        available_sessions = [s for s in interval.exch.index if s != 'tz']
        if available_sessions:
            raise ValueError(
                f'Session "{session}" is not defined for ticker {ticker}. '
                f'Available sessions: {", ".join(sorted(available_sessions))}. '
                f'See xbbg/markets/exch.yml for exchange-specific session definitions.'
            )
        raise ValueError(
            f'Session "{session}" is not defined for ticker {ticker} and no sessions found. '
            f'Check that exchange info is correctly configured for this ticker.'
        )
    # Handle compound sessions (e.g., 'day_open_30', 'day_normal_30_20')
    interval = Intervals(ticker=ticker, **kwargs)
    ss_info = session.split('_')
    if len(ss_info) < 2:
        available_sessions = [s for s in interval.exch.index if s != 'tz']
        raise ValueError(
            f'Invalid session format: "{session}". Expected format: "session_type_params" '
            f'(e.g., "day_open_30"). Available base sessions: {", ".join(sorted(available_sessions))}'
        )

    # Check if base session exists before trying compound parsing
    base_session = ss_info[0]
    if base_session not in interval.exch.index:
        # For compound sessions, return SessNA if base session doesn't exist
        # (backward compatibility - bare sessions raise ValueError, compound sessions return SessNA)
        return SessNA

    session_type = ss_info[1]
    method_name = f'market_{session_type}'
    if not hasattr(interval, method_name):
        available_methods = [m.replace('market_', '') for m in dir(interval) if m.startswith('market_')]
        raise ValueError(
            f'Session type "{session_type}" is not supported. '
            f'Supported types: {", ".join(sorted(available_methods))}. '
            f'Session format: "session_type_params" (e.g., "day_open_30", "day_normal_30_20")'
        )
    ss_info.pop(1)  # Remove the session type, leaving base session and params
    return getattr(interval, method_name)(*ss_info)


def shift_time(start_time, mins) -> str:
    """Shift start time by mins.

    Args:
        start_time: start time in terms of HH:MM string
        mins: number of minutes (+ / -)

    Returns:
        End time in terms of HH:MM string.
    """
    s_time = pd.Timestamp(start_time)
    e_time = s_time + np.sign(mins) * pd.Timedelta(f'00:{abs(mins)}:00')
    return e_time.strftime('%H:%M')


class Intervals:
    """Resolver for session-based time intervals."""

    def __init__(self, ticker, **kwargs):
        """Initialize interval resolver.

        Args:
            ticker: Ticker symbol.
            **kwargs: Passed to ``const.exch_info`` to resolve exchange data.
        """
        self.ticker = ticker
        self.exch = const.exch_info(ticker=ticker, **kwargs)

    def market_open(self, session, mins) -> Session:
        """Time intervals for market open.

        Args:
            session: [allday, day, am, pm, night]
            mins: minutes after open.

        Returns:
            Session of start_time and end_time.
        """
        if session not in self.exch: return SessNA
        start_time = self.exch[session][0]
        return Session(start_time, shift_time(start_time, int(mins)))

    def market_close(self, session, mins) -> Session:
        """Time intervals for market close.

        Args:
            session: [allday, day, am, pm, night]
            mins: minutes before close.

        Returns:
            Session of start_time and end_time.
        """
        if session not in self.exch: return SessNA
        end_time = self.exch[session][-1]
        return Session(shift_time(end_time, -int(mins) + 1), end_time)

    def market_normal(self, session, after_open, before_close) -> Session:
        """Time intervals between market.

        Args:
            session: [allday, day, am, pm, night]
            after_open: minutes after open.
            before_close: minutes before close.

        Returns:
            Session of start_time and end_time.
        """
        # Logger is module-level

        if session not in self.exch: return SessNA
        ss = self.exch[session]

        s_time = shift_time(ss[0], int(after_open) + 1)
        e_time = shift_time(ss[-1], -int(before_close))

        request_cross = pd.Timestamp(s_time) >= pd.Timestamp(e_time)
        session_cross = pd.Timestamp(ss[0]) >= pd.Timestamp(ss[1])
        if request_cross and (not session_cross):
            logger.warning('Session end time %s is earlier than start time %s, adjusting to valid range', e_time, s_time)
            return SessNA

        return Session(s_time, e_time)

    def market_exact(self, session, start_time: str, end_time: str) -> Session:
        """Explicitly specify start time and end time.

        Args:
            session: predefined session
            start_time: start time in terms of HHMM string.
            end_time: end time in terms of HHMM string.

        Returns:
            Session of start_time and end_time.
        """
        if session not in self.exch: return SessNA
        ss = self.exch[session]

        same_day = ss[0] < ss[-1]

        from xbbg.io import param  # noqa: PLC0415
        if not start_time: s_time = str(ss[0])
        else:
            s_time = str(param.to_hours(int(start_time)))
            if same_day: s_time = max(s_time, str(ss[0]))

        if not end_time: e_time = str(ss[-1])
        else:
            e_time = str(param.to_hours(int(end_time)))
            if same_day: e_time = min(e_time, str(ss[-1]))

        if same_day and (
            pd.Timestamp(s_time) > pd.Timestamp(e_time)
        ):
            return SessNA
        return Session(start_time=s_time, end_time=e_time)
