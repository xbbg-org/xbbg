"""Date parsing utilities shared across xbbg modules.

Follows Google-style docstrings as per docs/docstring_style.rst.
"""

from __future__ import annotations

from datetime import datetime


def parse_date(dt) -> datetime:
    """Parse various date formats to datetime.

    Supports ISO format strings, YYYYMMDD strings, datetime objects,
    and any object with year/month/day attributes (e.g., ``date``).

    Args:
        dt: Date in any supported format.

    Returns:
        datetime: Parsed datetime object.

    Raises:
        ValueError: If the date format cannot be parsed.

    Examples:
        >>> parse_date("2024-01-15")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_date("20240115")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_date("2024/01/15")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> from datetime import date
        >>> parse_date(date(2024, 1, 15))
        datetime.datetime(2024, 1, 15, 0, 0)
    """
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
