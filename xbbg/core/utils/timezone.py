"""Timezone utilities for converting and resolving exchange timezones.

Provides helpers to map tickers/shorthands to tz names and convert
datetime-like values between timezones.
"""

import logging

import pandas as pd
import pytz

logger = logging.getLogger(__name__)

# Use UTC as default timezone instead of system local time
# This ensures consistent behavior across different server locations
DEFAULT_TZ = pytz.UTC


def get_tz(tz) -> str:
    """Convert tz from ticker/shorthands to a timezone string.

    Args:
        tz: ticker or timezone shorthands

    Returns:
        str: Python timezone.

    Examples:
        >>> get_tz('NY')
        'America/New_York'
        >>> get_tz(TimeZone.NY)
        'America/New_York'
        >>> get_tz('BHP AU Equity')  # doctest: +SKIP
        'Australia/Sydney'
    """
    from xbbg.const import exch_info

    if tz is None:
        return 'UTC'

    to_tz = tz
    if isinstance(tz, str):
        if hasattr(TimeZone, tz):
            to_tz = getattr(TimeZone, tz)
        else:
            exch = exch_info(ticker=tz)
            if 'tz' in exch.index:
                to_tz = exch.tz

    return to_tz


def tz_convert(dt, to_tz, from_tz=None) -> str:
    """Convert datetime-like value to a target timezone.

    Args:
        dt: date time
        to_tz: to tz
        from_tz: from tz - will be ignored if tz from dt is given

    Returns:
        str: date & time

    Examples:
        >>> dt_1 = pd.Timestamp('2018-09-10 16:00', tz='Asia/Hong_Kong')
        >>> tz_convert(dt_1, to_tz='NY')
        '2018-09-10 04:00:00-04:00'
        >>> dt_2 = pd.Timestamp('2018-01-10 16:00')
        >>> tz_convert(dt_2, to_tz='HK', from_tz='NY')
        '2018-01-11 05:00:00+08:00'
        >>> dt_3 = '2018-09-10 15:00'
        >>> tz_convert(dt_3, to_tz='NY', from_tz='JP')
        '2018-09-10 02:00:00-04:00'
    """
    f_tz, t_tz = get_tz(from_tz), get_tz(to_tz)

    from_dt = pd.Timestamp(str(dt), tz=f_tz)
    logger.debug('Converting datetime %s from timezone %s to %s', from_dt, f_tz, t_tz)
    return str(pd.Timestamp(str(from_dt), tz=t_tz))


class TimeZone:
    """Python timezones."""
    NY = 'America/New_York'
    AU = 'Australia/Sydney'
    JP = 'Asia/Tokyo'
    SK = 'Asia/Seoul'
    HK = 'Asia/Hong_Kong'
    SH = 'Asia/Shanghai'
    TW = 'Asia/Taipei'
    SG = 'Asia/Singapore'
    IN = 'Asia/Calcutta'
    DB = 'Asia/Dubai'
    UK = 'Europe/London'

