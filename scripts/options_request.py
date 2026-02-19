#!/usr/bin/env python
"""Options analytics verification script.

Tests all options analytics functions (option_info, option_greeks, option_pricing,
option_chain, option_chain_bql, option_screen) against a live Bloomberg terminal.

Usage:
    uv run python -X utf8 scripts/options_request.py

Requires Bloomberg Terminal connection.
"""

from __future__ import annotations

import io
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s %(name)s:%(filename)s:%(lineno)d %(message)s",
)
# Silence noisy loggers
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

try:
    from xbbg.ext.options import (
        PutCall,
        StrikeRef,
        option_chain,
        option_chain_bql,
        option_greeks,
        option_info,
        option_pricing,
        option_screen,
    )
except ImportError:
    print("xbbg not installed. Run: pip install -e .")
    sys.exit(1)


# --- Test tickers ---
# Deep ITM call (confirmed working with all options fields)
OPT_TICKER = "SPY US 03/20/26 C600 Equity"
# Underlying for chain functions
UNDERLYING = "SPY US Equity"


def _to_printable(obj: object) -> object:
    """Convert Narwhals / PyArrow frames to pandas for readable output."""
    to_native = getattr(obj, "to_native", None)
    if callable(to_native):
        obj = to_native()
    to_pandas = getattr(obj, "to_pandas", None)
    if callable(to_pandas):
        obj = to_pandas()
    return obj


def _safe_print(obj: object) -> None:
    """Print with Narwhals-to-native conversion and UTF-8 fallback."""
    obj = _to_printable(obj)
    try:
        print(obj)
    except UnicodeEncodeError:
        buf = io.StringIO()
        print(obj, file=buf)
        sys.stdout.buffer.write(buf.getvalue().encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ------------------------------------------------------------------
# 1. Option Info
# ------------------------------------------------------------------


def test_option_info() -> None:
    _section("OPTION INFO")

    print(f"\n--- option_info({OPT_TICKER}) ---")
    _safe_print(option_info(OPT_TICKER))


# ------------------------------------------------------------------
# 2. Option Greeks
# ------------------------------------------------------------------


def test_option_greeks() -> None:
    _section("OPTION GREEKS")

    print(f"\n--- option_greeks({OPT_TICKER}) ---")
    _safe_print(option_greeks(OPT_TICKER))


# ------------------------------------------------------------------
# 3. Option Pricing
# ------------------------------------------------------------------


def test_option_pricing() -> None:
    _section("OPTION PRICING")

    print(f"\n--- option_pricing({OPT_TICKER}) ---")
    _safe_print(option_pricing(OPT_TICKER))


# ------------------------------------------------------------------
# 4. Option Chain
# ------------------------------------------------------------------


def test_option_chain() -> None:
    _section("OPTION CHAIN")

    print(
        f"\n--- option_chain({UNDERLYING}, put_call=PutCall.CALL, expiry_dt='20260320', strike=StrikeRef.ATM, points=5) ---"
    )
    _safe_print(option_chain(UNDERLYING, put_call=PutCall.CALL, expiry_dt="20260320", strike=StrikeRef.ATM, points=5))


# ------------------------------------------------------------------
# 5. Option Chain BQL
# ------------------------------------------------------------------


def test_option_chain_bql() -> None:
    _section("OPTION CHAIN BQL")

    print(
        f"\n--- option_chain_bql({UNDERLYING}, put_call=PutCall.CALL, expiry_start='2026-03-20', expiry_end='2026-03-20', strike_low=675, strike_high=690, delta_low=0.3, delta_high=0.7, min_open_int=100) ---"
    )
    _safe_print(
        option_chain_bql(
            UNDERLYING,
            put_call=PutCall.CALL,
            expiry_start="2026-03-20",
            expiry_end="2026-03-20",
            strike_low=675,
            strike_high=690,
            delta_low=0.3,
            delta_high=0.7,
            min_open_int=100,
        )
    )


# ------------------------------------------------------------------
# 6. Option Screen
# ------------------------------------------------------------------


def test_option_screen() -> None:
    _section("OPTION SCREEN")

    print("\n--- option_screen(['SPY US 03/20/26 C680 Equity', 'SPY US 03/20/26 P680 Equity']) ---")
    _safe_print(option_screen(["SPY US 03/20/26 C680 Equity", "SPY US 03/20/26 P680 Equity"]))


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    print("Options Analytics Verification")
    print(f"Option Ticker: {OPT_TICKER}")
    print(f"Underlying   : {UNDERLYING}")

    test_option_info()
    test_option_greeks()
    test_option_pricing()
    test_option_chain()
    test_option_chain_bql()
    test_option_screen()

    _section("ALL TESTS COMPLETE")


if __name__ == "__main__":
    main()
