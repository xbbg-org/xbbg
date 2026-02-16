#!/usr/bin/env python
"""Fixed income bond analytics verification script.

Tests all bond analytics functions (bond_info, bond_risk, bond_spreads,
bond_cashflows, bond_key_rates, bond_curve) and the enhanced yas() function
against a live Bloomberg terminal.

Usage:
    uv run python -X utf8 scripts/fi_request.py

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
    from xbbg.ext import YieldType, yas
    from xbbg.ext.bonds import (
        bond_cashflows,
        bond_curve,
        bond_info,
        bond_key_rates,
        bond_risk,
        bond_spreads,
    )
except ImportError:
    print("xbbg not installed. Run: pip install -e .")
    sys.exit(1)


# --- Test tickers ---
# 10yr US Treasury (confirmed working with all FI fields)
TREASURY_10Y = "/isin/US91282CNC19"
# A second bond for curve comparison
TREASURY_5Y = "T 4 02/28/31 Govt"
# Corporate bond (for spread analysis)
CORP_BOND = "AAPL 4.1 08/08/62 Corp"


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
# 1. Enhanced YAS
# ------------------------------------------------------------------


def test_yas() -> None:
    _section("ENHANCED YAS")

    print(f"\n--- yas({TREASURY_10Y}) [basic yield] ---")
    _safe_print(yas(TREASURY_10Y))

    print(f"\n--- yas({TREASURY_10Y}, flds=['YAS_BOND_YLD', 'YAS_MOD_DUR', 'YAS_ZSPREAD']) ---")
    _safe_print(yas(TREASURY_10Y, ["YAS_BOND_YLD", "YAS_MOD_DUR", "YAS_ZSPREAD"]))

    print(f"\n--- yas({TREASURY_10Y}, flds='YAS_BOND_PX', yield_=4.5) ---")
    _safe_print(yas(TREASURY_10Y, flds="YAS_BOND_PX", yield_=4.5))

    print(f"\n--- yas({TREASURY_10Y}, yield_type=YieldType.YTW) ---")
    _safe_print(yas(TREASURY_10Y, yield_type=YieldType.YTW))


# ------------------------------------------------------------------
# 2. Bond Info
# ------------------------------------------------------------------


def test_bond_info() -> None:
    _section("BOND INFO")

    print(f"\n--- bond_info({TREASURY_10Y}) ---")
    _safe_print(bond_info(TREASURY_10Y))


# ------------------------------------------------------------------
# 3. Bond Risk
# ------------------------------------------------------------------


def test_bond_risk() -> None:
    _section("BOND RISK")

    print(f"\n--- bond_risk({TREASURY_10Y}) ---")
    _safe_print(bond_risk(TREASURY_10Y))


# ------------------------------------------------------------------
# 4. Bond Spreads
# ------------------------------------------------------------------


def test_bond_spreads() -> None:
    _section("BOND SPREADS")

    print(f"\n--- bond_spreads({TREASURY_10Y}) ---")
    _safe_print(bond_spreads(TREASURY_10Y))

    print(f"\n--- bond_spreads({CORP_BOND}) [corporate — richer spread data] ---")
    try:
        _safe_print(bond_spreads(CORP_BOND))
    except Exception as e:
        print(f"  (error: {e} — corporate ticker may need adjustment)")


# ------------------------------------------------------------------
# 5. Bond Cashflows
# ------------------------------------------------------------------


def test_bond_cashflows() -> None:
    _section("BOND CASHFLOWS")

    print(f"\n--- bond_cashflows({TREASURY_10Y}) ---")
    _safe_print(bond_cashflows(TREASURY_10Y))


# ------------------------------------------------------------------
# 6. Bond Key Rates
# ------------------------------------------------------------------


def test_bond_key_rates() -> None:
    _section("BOND KEY RATES")

    print(f"\n--- bond_key_rates({TREASURY_10Y}) ---")
    _safe_print(bond_key_rates(TREASURY_10Y))


# ------------------------------------------------------------------
# 7. Bond Curve
# ------------------------------------------------------------------


def test_bond_curve() -> None:
    _section("BOND CURVE")

    print(f"\n--- bond_curve([{TREASURY_10Y}, {TREASURY_5Y}]) ---")
    _safe_print(bond_curve([TREASURY_10Y, TREASURY_5Y]))


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    print("Fixed Income Bond Analytics Verification")
    print(f"Treasury 10Y: {TREASURY_10Y}")
    print(f"Treasury 5Y : {TREASURY_5Y}")
    print(f"Corporate   : {CORP_BOND}")

    test_yas()
    test_bond_info()
    test_bond_risk()
    test_bond_spreads()
    test_bond_cashflows()
    test_bond_key_rates()
    test_bond_curve()

    _section("ALL TESTS COMPLETE")


if __name__ == "__main__":
    main()
