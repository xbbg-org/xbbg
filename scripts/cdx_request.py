#!/usr/bin/env python
"""CDX index resolution and analytics verification script.

Tests ticker resolution (IG + HY), active series selection, and all CDX
analytics functions against a live Bloomberg terminal.

Usage:
    uv run python -X utf8 scripts/cdx_request.py

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
    from xbbg.ext.cdx import (
        _CDX_FIELDS,
        active_cdx,
        cdx_basis,
        cdx_cashflows,
        cdx_curve,
        cdx_default_prob,
        cdx_defaults,
        cdx_info,
        cdx_pricing,
        cdx_risk,
        cdx_ticker,
    )
except ImportError:
    print("xbbg not installed. Run: pip install -e .")
    sys.exit(1)


# --- Test tickers ---
GEN_IG = "CDX IG CDSI GEN 5Y Corp"
GEN_HY = "CDX HY CDSI GEN 5Y Corp"
RESOLVE_DATE = "2026-02-16"


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
# 1. Ticker resolution
# ------------------------------------------------------------------


def test_ticker_resolution() -> tuple[str, str]:
    """Resolve IG (no version) and HY (with version) generic tickers."""
    _section("TICKER RESOLUTION")

    # IG -- expect: CDX IG CDSI S45 5Y Corp (VERSION=1, no V token)
    ig = cdx_ticker(gen_ticker=GEN_IG, dt=RESOLVE_DATE)
    print(f"\nIG: {GEN_IG}")
    print(f" ->  {ig!r}")

    # HY -- expect: CDX HY CDSI S45 V2 5Y Corp (VERSION>1, separate V token)
    hy = cdx_ticker(gen_ticker=GEN_HY, dt=RESOLVE_DATE)
    print(f"\nHY: {GEN_HY}")
    print(f" ->  {hy!r}")

    return ig, hy


# ------------------------------------------------------------------
# 2. Active CDX
# ------------------------------------------------------------------


def test_active_cdx() -> tuple[str, str]:
    """Test active_cdx for both IG and HY."""
    _section("ACTIVE CDX")

    ig_active = active_cdx(gen_ticker=GEN_IG, dt=RESOLVE_DATE)
    print(f"\nIG active: {GEN_IG}")
    print(f"        ->  {ig_active!r}")

    hy_active = active_cdx(gen_ticker=GEN_HY, dt=RESOLVE_DATE)
    print(f"\nHY active: {GEN_HY}")
    print(f"        ->  {hy_active!r}")

    return ig_active, hy_active


# ------------------------------------------------------------------
# 3. CDX Info
# ------------------------------------------------------------------


def test_cdx_info(ig_ticker: str, hy_ticker: str) -> None:
    _section("CDX INFO")

    print(f"\n--- cdx_info({ig_ticker}) ---")
    _safe_print(cdx_info(ig_ticker))

    print(f"\n--- cdx_info({hy_ticker}) ---")
    _safe_print(cdx_info(hy_ticker))


# ------------------------------------------------------------------
# 4. CDX Defaults
# ------------------------------------------------------------------


def test_cdx_defaults(hy_ticker: str) -> None:
    _section("CDX DEFAULTS (HY only)")

    print(f"\n--- cdx_defaults({hy_ticker}) ---")
    _safe_print(cdx_defaults(hy_ticker))


# ------------------------------------------------------------------
# 5. CDX Pricing
# ------------------------------------------------------------------


def test_cdx_pricing(ig_ticker: str, hy_ticker: str) -> None:
    _section("CDX PRICING")

    print(f"\n--- cdx_pricing({ig_ticker}) ---")
    _safe_print(cdx_pricing(ig_ticker))

    print(f"\n--- cdx_pricing({hy_ticker}) ---")
    _safe_print(cdx_pricing(hy_ticker))

    # Default HY recovery rate is 0.30; try both to show the override works
    print(f"\n--- cdx_pricing({hy_ticker}, recovery_rate=0.30) [same as default] ---")
    _safe_print(cdx_pricing(hy_ticker, recovery_rate=0.30))

    print(f"\n--- cdx_pricing({hy_ticker}, recovery_rate=0.50) [override to 50%] ---")
    _safe_print(cdx_pricing(hy_ticker, recovery_rate=0.50))


# ------------------------------------------------------------------
# 6. CDX Risk
# ------------------------------------------------------------------


def test_cdx_risk(ig_ticker: str) -> None:
    _section("CDX RISK")

    print(f"\n--- cdx_risk({ig_ticker}) ---")
    _safe_print(cdx_risk(ig_ticker))


# ------------------------------------------------------------------
# 7. CDX Basis
# ------------------------------------------------------------------


def test_cdx_basis(ig_ticker: str) -> None:
    _section("CDX BASIS")

    print(f"\n--- cdx_basis({ig_ticker}) ---")
    _safe_print(cdx_basis(ig_ticker))


# ------------------------------------------------------------------
# 8. CDX Default Probability
# ------------------------------------------------------------------


def test_cdx_default_prob(ig_ticker: str) -> None:
    _section("CDX DEFAULT PROBABILITY")

    print(f"\n--- cdx_default_prob({ig_ticker}) ---")
    _safe_print(cdx_default_prob(ig_ticker))


# ------------------------------------------------------------------
# 9. CDX Cashflows
# ------------------------------------------------------------------


def test_cdx_cashflows(ig_ticker: str) -> None:
    _section("CDX CASHFLOWS")

    print(f"\n--- cdx_cashflows({ig_ticker}) ---")
    _safe_print(cdx_cashflows(ig_ticker))


# ------------------------------------------------------------------
# 10. CDX Curve
# ------------------------------------------------------------------


def test_cdx_curve() -> None:
    _section("CDX CURVE")

    print(f"\n--- cdx_curve({GEN_IG}, tenors=['3Y','5Y','7Y','10Y']) ---")
    _safe_print(cdx_curve(GEN_IG))


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    print(f"IG generic  : {GEN_IG}")
    print(f"HY generic  : {GEN_HY}")
    print(f"Resolve date: {RESOLVE_DATE}\n")

    # 1. Ticker resolution (IG + HY)
    ig, hy = test_ticker_resolution()

    # 2. Active CDX
    ig_active, hy_active = test_active_cdx()

    # Use active tickers for remaining tests
    ig_t = ig_active or ig
    hy_t = hy_active or hy

    # 3-9. Analytics functions
    test_cdx_info(ig_t, hy_t)
    test_cdx_defaults(hy_t)
    test_cdx_pricing(ig_t, hy_t)
    test_cdx_risk(ig_t)
    test_cdx_basis(ig_t)
    test_cdx_default_prob(ig_t)
    test_cdx_cashflows(ig_t)
    test_cdx_curve()

    _section("ALL TESTS COMPLETE")


if __name__ == "__main__":
    main()
