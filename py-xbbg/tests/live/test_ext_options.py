#!/usr/bin/env python
"""Live integration tests for xbbg.ext.options.

Tests exercise the complete Python → Rust → Bloomberg → Rust → Python
data flow for options analytics extension functions.

Run with:
    pytest tests/live/test_ext_options.py -v --tb=short

Or as a standalone script:
    python tests/live/test_ext_options.py [test_names...]
    python tests/live/test_ext_options.py --list

Environment:
    Requires Bloomberg Terminal or B-PIPE connection.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
import logging
import sys

import pytest

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# Test Configuration
# =============================================================================

# Underlying for chain tests — highly liquid, always has options
UNDERLYING = "SPY US Equity"

# We dynamically build an option ticker at import time so the test doesn't
# hardcode a specific expiry that may have already passed.  Pick the third
# Friday of the month roughly 2-3 months out (monthly SPY options are very
# liquid).


def _next_monthly_expiry(months_out: int = 2) -> str:
    """Return the 3rd-Friday expiry ~months_out months ahead as MM/DD/YY."""
    today = datetime.now()
    target = today.replace(day=1) + timedelta(days=32 * months_out)
    target = target.replace(day=1)
    # Find first Friday
    day = target
    while day.weekday() != 4:  # Friday
        day += timedelta(days=1)
    # Third Friday = first Friday + 14 days
    third_friday = day + timedelta(days=14)
    return third_friday.strftime("%m/%d/%y")


EXPIRY = _next_monthly_expiry(2)
# ATM-ish strike for SPY — use a round number that's always reasonable
STRIKE = 550
OPTION_TICKER = f"SPY US {EXPIRY} C{STRIKE} Equity"

# Multiple options for screen tests
SCREEN_TICKERS = [
    f"SPY US {EXPIRY} C{STRIKE} Equity",
    f"SPY US {EXPIRY} C{STRIKE + 10} Equity",
    f"SPY US {EXPIRY} P{STRIKE - 10} Equity",
]

# Convert EXPIRY to YYYY-MM-DD for BQL filters
_exp_dt = datetime.strptime(EXPIRY, "%m/%d/%y")
EXPIRY_ISO = _exp_dt.strftime("%Y-%m-%d")


# =============================================================================
# Option Info
# =============================================================================


class TestOptionInfo:
    """Tests for option_info() — contract metadata."""

    def test_option_info_returns_data(self):
        """option_info: returns non-empty DataFrame."""
        from xbbg.ext.options import option_info

        df = option_info(OPTION_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_info returned {len(pdf)} rows for {OPTION_TICKER}")

    def test_option_info_has_strike(self):
        """option_info: includes strike price."""
        from xbbg.ext.options import option_info

        df = option_info(OPTION_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            strike_rows = pdf[pdf["field"] == "OPT_STRIKE_PX"]
            assert len(strike_rows) >= 1, "Expected OPT_STRIKE_PX in result"
            val = strike_rows.iloc[0]["value"]
            assert val is not None
            logger.info(f"  OPT_STRIKE_PX = {val}")


class TestAoptionInfo:
    """Tests for aoption_info() — async contract metadata."""

    @pytest.mark.asyncio
    async def test_aoption_info_basic(self):
        """aoption_info: basic async call."""
        from xbbg.ext.options import aoption_info

        df = await aoption_info(OPTION_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Option Greeks
# =============================================================================


class TestOptionGreeks:
    """Tests for option_greeks() — Greeks and implied volatility."""

    def test_option_greeks_returns_data(self):
        """option_greeks: returns non-empty DataFrame."""
        from xbbg.ext.options import option_greeks

        df = option_greeks(OPTION_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_greeks returned {len(pdf)} rows")

    def test_option_greeks_has_delta(self):
        """option_greeks: includes delta."""
        from xbbg.ext.options import option_greeks

        df = option_greeks(OPTION_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            delta_rows = pdf[pdf["field"] == "DELTA_MID"]
            assert len(delta_rows) >= 1, "Expected DELTA_MID in result"
            logger.info(f"  DELTA_MID = {delta_rows.iloc[0]['value']}")

    def test_option_greeks_has_ivol(self):
        """option_greeks: includes implied volatility."""
        from xbbg.ext.options import option_greeks

        df = option_greeks(OPTION_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            ivol_rows = pdf[pdf["field"] == "IVOL_MID"]
            assert len(ivol_rows) >= 1, "Expected IVOL_MID in result"
            logger.info(f"  IVOL_MID = {ivol_rows.iloc[0]['value']}")


class TestAoptionGreeks:
    """Tests for aoption_greeks() — async Greeks."""

    @pytest.mark.asyncio
    async def test_aoption_greeks_basic(self):
        """aoption_greeks: basic async call."""
        from xbbg.ext.options import aoption_greeks

        df = await aoption_greeks(OPTION_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Option Pricing
# =============================================================================


class TestOptionPricing:
    """Tests for option_pricing() — pricing and value decomposition."""

    def test_option_pricing_returns_data(self):
        """option_pricing: returns non-empty DataFrame."""
        from xbbg.ext.options import option_pricing

        df = option_pricing(OPTION_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_pricing returned {len(pdf)} rows")

    def test_option_pricing_has_last_price(self):
        """option_pricing: includes last price."""
        from xbbg.ext.options import option_pricing

        df = option_pricing(OPTION_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            px_rows = pdf[pdf["field"] == "PX_LAST"]
            assert len(px_rows) >= 1, "Expected PX_LAST in result"
            logger.info(f"  PX_LAST = {px_rows.iloc[0]['value']}")


class TestAoptionPricing:
    """Tests for aoption_pricing() — async pricing."""

    @pytest.mark.asyncio
    async def test_aoption_pricing_basic(self):
        """aoption_pricing: basic async call."""
        from xbbg.ext.options import aoption_pricing

        df = await aoption_pricing(OPTION_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Option Chain (overrides)
# =============================================================================


class TestOptionChain:
    """Tests for option_chain() — chain via CHAIN_TICKERS overrides."""

    def test_option_chain_calls(self):
        """option_chain: get call options filtered by expiry."""
        from xbbg.ext.options import PutCall, option_chain

        df = option_chain(UNDERLYING, put_call=PutCall.CALL, expiry_dt=EXPIRY_ISO)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain(CALL, expiry={EXPIRY_ISO}) returned {len(pdf)} rows")

    def test_option_chain_puts(self):
        """option_chain: get put options filtered by expiry."""
        from xbbg.ext.options import PutCall, option_chain

        df = option_chain(UNDERLYING, put_call=PutCall.PUT, expiry_dt=EXPIRY_ISO)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain(PUT, expiry={EXPIRY_ISO}) returned {len(pdf)} rows")

    def test_option_chain_with_strike(self):
        """option_chain: filter by expiry + strike."""
        from xbbg.ext.options import PutCall, option_chain

        df = option_chain(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_dt=EXPIRY_ISO,
            strike=STRIKE,
            points=5,
        )
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain(strike={STRIKE}, points=5) returned {len(pdf)} rows")


class TestAoptionChain:
    """Tests for aoption_chain() — async chain."""

    @pytest.mark.asyncio
    async def test_aoption_chain_basic(self):
        """aoption_chain: basic async call with expiry filter."""
        from xbbg.ext.options import PutCall, aoption_chain

        df = await aoption_chain(UNDERLYING, put_call=PutCall.CALL, expiry_dt=EXPIRY_ISO)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Option Chain BQL
# =============================================================================


class TestOptionChainBql:
    """Tests for option_chain_bql() — chain via BQL with rich filtering."""

    def test_option_chain_bql_calls(self):
        """option_chain_bql: get calls with tight date + strike range."""
        from xbbg.ext.options import PutCall, option_chain_bql

        df = option_chain_bql(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_start=EXPIRY_ISO,
            expiry_end=EXPIRY_ISO,
            strike_low=STRIKE - 20,
            strike_high=STRIKE + 20,
        )
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain_bql returned {len(pdf)} rows")

    def test_option_chain_bql_delta_filter(self):
        """option_chain_bql: filter by delta range (ATM-ish) with expiry."""
        from xbbg.ext.options import PutCall, option_chain_bql

        df = option_chain_bql(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_start=EXPIRY_ISO,
            expiry_end=EXPIRY_ISO,
            delta_low=0.4,
            delta_high=0.6,
        )
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain_bql(delta 0.4–0.6) returned {len(pdf)} rows")

    def test_option_chain_bql_custom_fields(self):
        """option_chain_bql: custom get_fields with tight filter."""
        from xbbg.ext.options import PutCall, option_chain_bql

        df = option_chain_bql(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_start=EXPIRY_ISO,
            expiry_end=EXPIRY_ISO,
            strike_low=STRIKE - 10,
            strike_high=STRIKE + 10,
            get_fields=["strike_px()", "expire_dt()", "ivol()", "px_last()"],
        )
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_chain_bql(custom fields) returned {len(pdf)} rows")


class TestAoptionChainBql:
    """Tests for aoption_chain_bql() — async BQL chain."""

    @pytest.mark.asyncio
    async def test_aoption_chain_bql_basic(self):
        """aoption_chain_bql: async call with tight filter."""
        from xbbg.ext.options import PutCall, aoption_chain_bql

        df = await aoption_chain_bql(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_start=EXPIRY_ISO,
            expiry_end=EXPIRY_ISO,
            strike_low=STRIKE - 20,
            strike_high=STRIKE + 20,
        )
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Option Screen
# =============================================================================


class TestOptionScreen:
    """Tests for option_screen() — multi-option comparison."""

    def test_option_screen_returns_data(self):
        """option_screen: returns data for multiple options."""
        from xbbg.ext.options import option_screen

        df = option_screen(SCREEN_TICKERS)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_screen returned {len(pdf)} rows for {len(SCREEN_TICKERS)} tickers")

    def test_option_screen_custom_fields(self):
        """option_screen: accepts custom field list."""
        from xbbg.ext.options import option_screen

        custom = ["NAME", "OPT_STRIKE_PX", "PX_LAST", "IVOL_MID", "DELTA_MID"]
        df = option_screen(SCREEN_TICKERS, flds=custom)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  option_screen(custom) returned {len(pdf)} rows")

    def test_option_screen_covers_all_tickers(self):
        """option_screen: returns data for each ticker."""
        from xbbg.ext.options import option_screen

        df = option_screen(SCREEN_TICKERS)
        pdf = df.to_pandas()

        if "ticker" in pdf.columns:
            unique = pdf["ticker"].nunique()
            assert unique == len(SCREEN_TICKERS), f"Expected {len(SCREEN_TICKERS)} tickers, got {unique}"
            logger.info(f"  Screened {unique} option contracts")


class TestAoptionScreen:
    """Tests for aoption_screen() — async multi-option comparison."""

    @pytest.mark.asyncio
    async def test_aoption_screen_basic(self):
        """aoption_screen: basic async call."""
        from xbbg.ext.options import aoption_screen

        df = await aoption_screen(SCREEN_TICKERS)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Standalone runner
# =============================================================================

TESTS: dict[str, object] = {}


def _register_tests():
    for cls in [
        TestOptionInfo,
        TestAoptionInfo,
        TestOptionGreeks,
        TestAoptionGreeks,
        TestOptionPricing,
        TestAoptionPricing,
        TestOptionChain,
        TestAoptionChain,
        TestOptionChainBql,
        TestAoptionChainBql,
        TestOptionScreen,
        TestAoptionScreen,
    ]:
        instance = cls()
        for name in sorted(dir(cls)):
            if name.startswith("test_"):
                TESTS[name] = getattr(instance, name)


_register_tests()


def run_tests(names: list[str]) -> bool:
    passed = failed = skipped = 0
    for name in names:
        if name not in TESTS:
            logger.warning(f"Unknown test: {name}")
            continue
        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"TEST: {name}")
            logger.info("-" * 60)

            test_func = TESTS[name]
            is_async = "aoption" in name
            if is_async:

                async def run_async(fn=test_func):
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result

                asyncio.run(run_async())
            else:
                result = test_func()
                if asyncio.iscoroutine(result):
                    asyncio.run(result)

            passed += 1
            logger.info("PASSED ✓")
        except pytest.skip.Exception as e:
            skipped += 1
            logger.warning(f"SKIPPED: {e}")
        except Exception as e:
            failed += 1
            logger.error(f"FAILED ✗: {e}")
            import traceback

            traceback.print_exc()

    logger.info(f"\n{'=' * 60}")
    logger.info(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    logger.info(f"{'=' * 60}")
    return failed == 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="xbbg ext.options Live Tests")
    parser.add_argument("tests", nargs="*", default=list(TESTS.keys()), help="Tests to run")
    parser.add_argument("--list", action="store_true", help="List available tests")
    args = parser.parse_args()

    if args.list:
        for name in sorted(TESTS.keys()):
            logger.info(f"  {name}")
        return 0

    logger.info("=" * 60)
    logger.info("xbbg ext.options Live Tests")
    logger.info(f"  OPTION_TICKER: {OPTION_TICKER}")
    logger.info(f"  UNDERLYING:    {UNDERLYING}")
    logger.info(f"  EXPIRY:        {EXPIRY_ISO}")
    logger.info("=" * 60)
    return 0 if run_tests(args.tests) else 1


if __name__ == "__main__":
    sys.exit(main())
