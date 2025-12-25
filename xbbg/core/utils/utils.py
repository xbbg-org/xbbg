"""Utility helpers for dates, formatting, dynamic import, and strings.

Follows Google-style docstrings as per docs/docstring_style.rst.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytz


def flatten(
    iterable: Any,
    maps: dict[Any, Any] | None = None,
    unique: bool = False,
) -> list[Any]:
    """Flatten any array of items to list.

    Args:
        iterable: any array or value
        maps: map items to values
        unique: drop duplicates

    Returns:
        list: flattened list

    References:
        https://stackoverflow.com/a/40857703/1332656

    Examples:
        >>> flatten('abc')
        ['abc']
        >>> flatten(1)
        [1]
        >>> flatten(1.)
        [1.0]
        >>> flatten(['ab', 'cd', ['xy', 'zz']])
        ['ab', 'cd', 'xy', 'zz']
        >>> flatten(['ab', ['xy', 'zz']], maps={'xy': '0x'})
        ['ab', '0x', 'zz']
    """
    if iterable is None: return []
    if maps is None: maps = {}

    if isinstance(iterable, (str, int, float)):
        return [maps.get(iterable, iterable)]

    x = [maps.get(item, item) for item in _to_gen_(iterable)]
    return list(set(x)) if unique else x


def _to_gen_(iterable: Any) -> Any:
    """Recursively iterate lists and tuples."""
    from collections.abc import Iterable

    for elm in iterable:
        if isinstance(elm, Iterable) and not isinstance(elm, (str, bytes)):
            yield from _to_gen_(elm)
        else:
            yield elm


def fmt_dt(
    dt: str | pd.Timestamp | datetime.date | Any,
    fmt: str = '%Y-%m-%d',
) -> str:
    """Format date string (wrapper around pd.Timestamp.strftime).

    Args:
        dt: any date format
        fmt: output date format

    Returns:
        str: Date in the requested format.

    Examples:
        >>> fmt_dt(dt='2018-12')
        '2018-12-01'
        >>> fmt_dt(dt='2018-12-31', fmt='%Y%m%d')
        '20181231'
    """
    return pd.Timestamp(dt).strftime(fmt)


def cur_time(
    typ: str = 'date',
    tz: str | pytz.BaseTzInfo | None = None,
) -> datetime.date | str | pd.Timestamp:
    """Current time.

    Args:
        typ: one of ['date', 'time', 'time_path', 'raw', '']
        tz: timezone (defaults to UTC if None for consistency)

    Returns:
        Relevant current time or date.

    Examples:
        >>> cur_dt = pd.Timestamp('now', tz='UTC')
        >>> cur_time(typ='date') == cur_dt.strftime('%Y-%m-%d')
        True
        >>> cur_time(typ='time') == cur_dt.strftime('%Y-%m-%d %H:%M:%S')
        True
        >>> cur_time(typ='time_path') == cur_dt.strftime('%Y-%m-%d/%H-%M-%S')
        True
        >>> isinstance(cur_time(typ='raw', tz='Europe/London'), pd.Timestamp)
        True
        >>> cur_time(typ='') == cur_dt.date()
        True
    """
    # Use UTC by default for consistency across server locations
    if tz is None:
        tz = 'UTC'

    dt = pd.Timestamp('now', tz=tz)

    if typ == 'date': return dt.strftime('%Y-%m-%d')
    if typ == 'time': return dt.strftime('%Y-%m-%d %H:%M:%S')
    if typ == 'time_path': return dt.strftime('%Y-%m-%d/%H-%M-%S')
    if typ == 'raw': return dt

    return dt.date()


def to_str(
    data: dict[str, Any],
    fmt: str = '{key}={value}',
    sep: str = ', ',
    public_only: bool = True,
) -> str:
    """Convert dict to string.

    Args:
        data: dict
        fmt: how key and value being represented
        sep: how pairs of key and value are seperated
        public_only: if display public members only

    Returns:
        str: String representation of dict.

    Examples:
        >>> test_dict = dict(b=1, a=0, c=2, _d=3)
        >>> to_str(test_dict)
        '{b=1, a=0, c=2}'
        >>> to_str(test_dict, sep='|')
        '{b=1|a=0|c=2}'
        >>> to_str(test_dict, public_only=False)
        '{b=1, a=0, c=2, _d=3}'
    """
    keys = list(filter(lambda vv: vv[0] != '_', data.keys())) if public_only else list(data.keys())
    return '{' + sep.join([
        to_str(data=v, fmt=fmt, sep=sep)
        if isinstance(v, dict) else fmt.format(key=k, value=v)
        for k, v in data.items() if k in keys
    ]) + '}'


# Bloomberg-specific normalization helpers
# These functions normalize Bloomberg API inputs (tickers, fields) to consistent formats.


def normalize_tickers(tickers: str | list[str]) -> list[str]:
    """Normalize tickers to a list.

    Args:
        tickers: Single ticker string or list of tickers.

    Returns:
        list[str]: List of tickers (always a list).
    """
    return [tickers] if isinstance(tickers, str) else tickers


def normalize_flds(flds: str | list[str] | None) -> list[str]:
    """Normalize fields to a list.

    Args:
        flds: Single field string, list of fields, or None.

    Returns:
        list[str]: List of fields (always a list).
    """
    if flds is None:
        return []
    return [flds] if isinstance(flds, str) else flds


def check_empty_result(res: pd.DataFrame, required_cols: list[str] | None = None) -> bool:
    """Check if result DataFrame is empty or missing required columns.

    Args:
        res: Result DataFrame to check.
        required_cols: List of required column names. If None, no column check.

    Returns:
        bool: True if empty or missing required columns, False otherwise.
    """
    if res.empty:
        return True
    if required_cols:
        return any(col not in res for col in required_cols)
    return False


# Valid Bloomberg identifier types for B-Pipe subscriptions
# Reference: Bloomberg B-Pipe symbology enforcement (effective Dec 31, 2025)
BPIPE_IDENTIFIER_TYPES = frozenset({
    'ticker', 'isin', 'cusip', 'sedol', 'figi', 'bbgid',
    'buid', 'cats', 'cins', 'common', 'naics', 'sicovam',
    'svm', 'wpk', 'trace',
})


def parse_subscription_topic(ticker: str) -> str:
    """Parse ticker and build Bloomberg subscription topic with correct symbology.

    Bloomberg B-Pipe subscriptions require an identifier type prefix in the topic.
    This function detects the identifier type from the ticker format and builds
    the appropriate topic string.

    Supported formats:
        - Standard ticker: 'IBM US Equity' -> '//blp/mktdata/TICKER/IBM US Equity'
        - ISIN: '/isin/US0378331005' -> '//blp/mktdata/ISIN/US0378331005'
        - CUSIP: '/cusip/037833100' -> '//blp/mktdata/CUSIP/037833100'
        - SEDOL: '/sedol/1234567' -> '//blp/mktdata/SEDOL/1234567'
        - FIGI: '/figi/BBG000B9XRY4' -> '//blp/mktdata/FIGI/BBG000B9XRY4'
        - BBGID: '/bbgid/BBG000B9XRY4' -> '//blp/mktdata/BBGID/BBG000B9XRY4'

    Args:
        ticker: Ticker string, optionally prefixed with identifier type (e.g., '/isin/...').

    Returns:
        str: Full subscription topic string with identifier type prefix.

    Examples:
        >>> parse_subscription_topic('IBM US Equity')
        '//blp/mktdata/TICKER/IBM US Equity'
        >>> parse_subscription_topic('/isin/US0378331005')
        '//blp/mktdata/ISIN/US0378331005'
        >>> parse_subscription_topic('/cusip/037833100')
        '//blp/mktdata/CUSIP/037833100'
        >>> parse_subscription_topic('/figi/BBG000B9XRY4')
        '//blp/mktdata/FIGI/BBG000B9XRY4'
    """
    # Check for identifier prefix format: /type/identifier
    if ticker.startswith('/'):
        parts = ticker.split('/', 2)  # Split into ['', 'type', 'identifier']
        if len(parts) >= 3:
            id_type = parts[1].lower()
            identifier = parts[2]
            if id_type in BPIPE_IDENTIFIER_TYPES:
                return f'//blp/mktdata/{id_type.upper()}/{identifier}'

    # Default to TICKER for standard Bloomberg ticker format
    return f'//blp/mktdata/TICKER/{ticker}'
