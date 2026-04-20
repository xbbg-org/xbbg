"""Live verification for issue #295: overrides support in bdtick / bdib.

Requires an active Bloomberg Terminal or B-PIPE connection. Run with:

    pytest py-xbbg/tests/live/test_issue_295_overrides.py -s -v

These tests hit Bloomberg — they're marked ``live`` so CI skips them.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from xbbg import blp


def _recent_trading_window() -> tuple[str, str]:
    """Pick a small intraday window on the most recent weekday."""
    now = datetime.now()
    day = now - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    start = day.replace(hour=14, minute=30, second=0, microsecond=0)
    end = start + timedelta(minutes=5)
    return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")


@pytest.mark.live
def test_bdtick_respects_points_override():
    start, end = _recent_trading_window()

    # No override: however many ticks Bloomberg returns in the window.
    full = blp.bdtick(
        ticker="ES1 Index",
        start_datetime=start,
        end_datetime=end,
        event_types=["TRADE"],
    )

    # With Points=1, Bloomberg should cap the response.
    limited = blp.bdtick(
        ticker="ES1 Index",
        start_datetime=start,
        end_datetime=end,
        event_types=["TRADE"],
        overrides={"Points": 1},
    )

    print(f"\nfull rows:    {len(full)}")
    print(f"limited rows: {len(limited)}")

    assert len(limited) < len(full), (
        "Points=1 override did not reduce the response — "
        "fix may not be wired through to Bloomberg."
    )


@pytest.mark.live
def test_bdib_respects_points_override():
    start, end = _recent_trading_window()

    full = blp.bdib(
        ticker="ES1 Index",
        start_datetime=start,
        end_datetime=end,
        typ="TRADE",
        interval=1,
    )

    limited = blp.bdib(
        ticker="ES1 Index",
        start_datetime=start,
        end_datetime=end,
        typ="TRADE",
        interval=1,
        overrides={"Points": 1},
    )

    print(f"\nfull rows:    {len(full)}")
    print(f"limited rows: {len(limited)}")

    assert len(limited) < len(full), (
        "Points=1 override did not reduce the response — "
        "fix may not be wired through to Bloomberg."
    )
