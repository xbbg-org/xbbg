"""Live verification for #317 native datetime/date acceptance.

Existing live tests already cover string-shaped date inputs across all surfaces
(bdh, bdib, bdtick, bdp overrides, bonds.settle_dt, options.expiry_dt, etc.).
This file ONLY exercises the new native-type paths added in #317:

- ``date`` / ``datetime`` objects as request params
- ``date`` / ``datetime`` values inside override kwargs
- tz-aware datetime in bdtick

Each test issues a small bounded Bloomberg request to keep traffic light.

Run with:

    pytest py-xbbg/tests/live/test_issue_317_native_dates.py -s -v
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from xbbg import blp


def _recent_weekday() -> date:
    """Pick the most recent weekday for date-bounded requests."""
    day = date.today() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


@pytest.mark.live
def test_bdh_accepts_date_objects():
    """bdh start_date/end_date accept datetime.date instead of strings."""
    end = _recent_weekday()
    start = end - timedelta(days=4)

    df = blp.bdh(
        "AAPL US Equity",
        "PX_LAST",
        start_date=start,
        end_date=end,
    )

    assert len(df) >= 1, f"bdh with date objects returned no rows: {df}"


@pytest.mark.live
def test_bdib_accepts_date_for_dt():
    """bdib dt= accepts a date object (date-only single-day shortcut)."""
    df = blp.bdib(
        "AAPL US Equity",
        dt=_recent_weekday(),
        Points=1,
    )

    assert len(df) >= 1, f"bdib with date object returned no rows: {df}"


@pytest.mark.live
def test_bdtick_accepts_naive_datetime():
    """bdtick start/end accept naive datetime objects (tz-naive → UTC default)."""
    day = _recent_weekday()
    start = datetime.combine(day, datetime.min.time()).replace(hour=14, minute=30)
    end = start + timedelta(minutes=2)

    df = blp.bdtick(
        "ES1 Index",
        start_datetime=start,
        end_datetime=end,
        event_types=["TRADE"],
        maxDataPoints=5,
    )

    assert len(df) >= 1, f"bdtick with naive datetimes returned no rows: {df}"


@pytest.mark.live
def test_bdtick_accepts_tz_aware_datetime():
    """bdtick start/end accept tz-aware datetime objects (preserves their tz)."""
    day = _recent_weekday()
    start = datetime.combine(day, datetime.min.time()).replace(hour=14, minute=30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=2)

    df = blp.bdtick(
        "ES1 Index",
        start_datetime=start,
        end_datetime=end,
        event_types=["TRADE"],
        maxDataPoints=5,
    )

    assert len(df) >= 1, f"bdtick with tz-aware datetimes returned no rows: {df}"


@pytest.mark.live
def test_bdp_override_accepts_date_object():
    """Override kwarg values accept date objects (auto-normalized to YYYYMMDD)."""
    settle = _recent_weekday()

    df = blp.bdp(
        "IT0005045270 Corp",
        "SETTLE_DT",
        USER_LOCAL_TRADE_DATE=settle,
    )

    assert len(df) >= 1, (
        f"bdp with date-typed override returned no rows: {df}. "
        "If failing, the override-path normalization hook may not be converting "
        "datetime.date values to YYYYMMDD before forwarding to Bloomberg."
    )
