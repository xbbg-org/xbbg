from __future__ import annotations

import asyncio


def test_engine_exchange_resolution_live():
    from xbbg._core import (
        PyEngine,
        ext_clear_exchange_override,
        ext_get_exchange_override,
        ext_session_times_to_utc,
        ext_set_exchange_override,
    )

    start_utc, end_utc = ext_session_times_to_utc(
        "09:30",
        "16:00",
        "America/New_York",
        "2026-02-24",
    )
    assert start_utc == "2026-02-24T14:30:00"
    assert end_utc == "2026-02-24T21:00:00"

    ext_clear_exchange_override()
    try:
        ext_set_exchange_override(
            "AAPL US Equity",
            timezone="UTC",
            day=("00:00", "23:59"),
        )
        override = ext_get_exchange_override("AAPL US Equity")
        assert override is not None
        assert override["source"] == "override"
        assert override["timezone"] == "UTC"
        assert override["day"] == ("00:00", "23:59")
    finally:
        ext_clear_exchange_override()

    async def run_live_checks() -> None:
        engine = PyEngine()

        exchange = await asyncio.wait_for(engine.resolve_exchange("AAPL US Equity"), timeout=45)
        assert exchange["timezone"]
        assert exchange["day"] is not None
        assert exchange["source"] != "fallback"

        market_info = await asyncio.wait_for(engine.fetch_market_info("AAPL US Equity"), timeout=45)
        assert market_info["exch"] or market_info["tz"]

        timing_utc = await asyncio.wait_for(
            engine.market_timing("AAPL US Equity", "2026-02-24", "EOD", "UTC"),
            timeout=45,
        )
        assert isinstance(timing_utc, str)
        assert "+" in timing_utc

    asyncio.run(run_live_checks())


def test_treasury_futures_exchange_resolution_live_issue_198():
    """Regression for #198: futures/commodities resolve exchange metadata dynamically."""
    from xbbg._core import PyEngine

    async def run_live_checks() -> None:
        engine = PyEngine()
        exchange = await asyncio.wait_for(engine.resolve_exchange("TY1 Comdty"), timeout=45)

        assert exchange["timezone"]
        assert exchange["day"] is not None
        assert exchange["source"] != "fallback"

        market_info = await asyncio.wait_for(engine.fetch_market_info("TY1 Comdty"), timeout=45)
        assert market_info["exch"] or market_info["tz"]

    asyncio.run(run_live_checks())


def test_japan_equity_close_live_issue_160():
    """Regression for #160: Japan equity EOD resolves to 15:30 Asia/Tokyo."""
    from xbbg._core import PyEngine

    async def run_live_checks() -> None:
        engine = PyEngine()
        timing_utc = await asyncio.wait_for(
            engine.market_timing("7203 JP Equity", "2026-02-24", "EOD", "UTC"),
            timeout=45,
        )

        assert "06:30:00+00:00" in timing_utc

    asyncio.run(run_live_checks())
