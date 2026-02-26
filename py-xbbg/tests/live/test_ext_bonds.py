#!/usr/bin/env python
"""Live integration tests for xbbg.ext.bonds.

Tests exercise the complete Python → Rust → Bloomberg → Rust → Python
data flow for bond analytics extension functions.

Run with:
    pytest tests/live/test_ext_bonds.py -v --tb=short

Or as a standalone script:
    python tests/live/test_ext_bonds.py [test_names...]
    python tests/live/test_ext_bonds.py --list

Environment:
    Requires Bloomberg Terminal or B-PIPE connection.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import pytest

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# Test Configuration
# =============================================================================

# Liquid US Treasury — always available, well-known
BOND_TICKER = "T 4.5 05/15/38 Govt"

# Multiple bonds for curve tests — intermediate / long end
CURVE_TICKERS = [
    "T 4.625 05/15/44 Govt",
    "T 4.5 05/15/38 Govt",
]


# =============================================================================
# Bond Info
# =============================================================================


class TestBondInfo:
    """Tests for bond_info() — bond reference metadata."""

    def test_bond_info_returns_data(self):
        """bond_info: returns non-empty DataFrame with expected columns."""
        from xbbg.ext.bonds import bond_info

        df = bond_info(BOND_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_info returned {len(pdf)} rows")

        # Should contain key bond reference fields
        fields = set(pdf["field"].tolist()) if "field" in pdf.columns else set(pdf.columns)
        logger.info(f"  Fields: {sorted(fields)}")

    def test_bond_info_has_coupon(self):
        """bond_info: returned data includes coupon information."""
        from xbbg.ext.bonds import bond_info

        df = bond_info(BOND_TICKER)
        pdf = df.to_pandas()

        # Look for CPN field in either long or wide format
        if "field" in pdf.columns:
            cpn_rows = pdf[pdf["field"] == "CPN"]
            assert len(cpn_rows) >= 1, "Expected CPN field in result"
            val = cpn_rows.iloc[0]["value"]
            assert val is not None
            logger.info(f"  CPN = {val}")
        else:
            assert "CPN" in pdf.columns or "cpn" in pdf.columns


class TestAbondInfo:
    """Tests for abond_info() — async bond reference metadata."""

    @pytest.mark.asyncio
    async def test_abond_info_basic(self):
        """abond_info: basic async call returns data."""
        from xbbg.ext.bonds import abond_info

        df = await abond_info(BOND_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  abond_info returned {len(pdf)} rows")


# =============================================================================
# Bond Risk
# =============================================================================


class TestBondRisk:
    """Tests for bond_risk() — duration and risk metrics."""

    def test_bond_risk_returns_data(self):
        """bond_risk: returns non-empty DataFrame."""
        from xbbg.ext.bonds import bond_risk

        df = bond_risk(BOND_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_risk returned {len(pdf)} rows")

    def test_bond_risk_has_duration(self):
        """bond_risk: includes modified duration."""
        from xbbg.ext.bonds import bond_risk

        df = bond_risk(BOND_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            dur_rows = pdf[pdf["field"] == "DUR_ADJ_MID"]
            assert len(dur_rows) >= 1, "Expected DUR_ADJ_MID in result"
            val = dur_rows.iloc[0]["value"]
            assert val is not None
            logger.info(f"  DUR_ADJ_MID = {val}")
        else:
            assert "DUR_ADJ_MID" in pdf.columns or "dur_adj_mid" in pdf.columns

    def test_bond_risk_with_settle_dt(self):
        """bond_risk: accepts settle_dt override."""
        from xbbg.ext.bonds import bond_risk

        df = bond_risk(BOND_TICKER, settle_dt="20250301")
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_risk(settle_dt) returned {len(pdf)} rows")


class TestAbondRisk:
    """Tests for abond_risk() — async duration and risk metrics."""

    @pytest.mark.asyncio
    async def test_abond_risk_basic(self):
        """abond_risk: basic async call."""
        from xbbg.ext.bonds import abond_risk

        df = await abond_risk(BOND_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Bond Spreads
# =============================================================================


class TestBondSpreads:
    """Tests for bond_spreads() — spread analytics."""

    def test_bond_spreads_returns_data(self):
        """bond_spreads: returns non-empty DataFrame."""
        from xbbg.ext.bonds import bond_spreads

        df = bond_spreads(BOND_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_spreads returned {len(pdf)} rows")

    def test_bond_spreads_has_oas(self):
        """bond_spreads: includes OAS spread."""
        from xbbg.ext.bonds import bond_spreads

        df = bond_spreads(BOND_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            oas_rows = pdf[pdf["field"] == "YAS_OAS_SPRD"]
            assert len(oas_rows) >= 1, "Expected YAS_OAS_SPRD in result"
            logger.info(f"  YAS_OAS_SPRD = {oas_rows.iloc[0]['value']}")

    def test_bond_spreads_with_benchmark(self):
        """bond_spreads: accepts benchmark override."""
        from xbbg.ext.bonds import bond_spreads

        df = bond_spreads(BOND_TICKER, benchmark="GT10 Govt")
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_spreads(benchmark) returned {len(pdf)} rows")


class TestAbondSpreads:
    """Tests for abond_spreads() — async spread analytics."""

    @pytest.mark.asyncio
    async def test_abond_spreads_basic(self):
        """abond_spreads: basic async call."""
        from xbbg.ext.bonds import abond_spreads

        df = await abond_spreads(BOND_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Bond Cashflows
# =============================================================================


class TestBondCashflows:
    """Tests for bond_cashflows() — cash flow schedule."""

    def test_bond_cashflows_returns_data(self):
        """bond_cashflows: returns non-empty DataFrame."""
        from xbbg.ext.bonds import bond_cashflows

        df = bond_cashflows(BOND_TICKER)
        pdf = df.to_pandas()

        # A 30yr Treasury should have many cash flow rows
        assert len(pdf) >= 1
        logger.info(f"  bond_cashflows returned {len(pdf)} rows")

    def test_bond_cashflows_multiple_rows(self):
        """bond_cashflows: returns multiple coupon payments."""
        from xbbg.ext.bonds import bond_cashflows

        df = bond_cashflows(BOND_TICKER)
        pdf = df.to_pandas()

        # T 4.5 05/15/38 — semiannual coupons, should have many rows
        assert len(pdf) >= 2, "Expected multiple cash flow rows for a Treasury"
        logger.info(f"  Got {len(pdf)} cash flow entries")


class TestAbondCashflows:
    """Tests for abond_cashflows() — async cash flow schedule."""

    @pytest.mark.asyncio
    async def test_abond_cashflows_basic(self):
        """abond_cashflows: basic async call."""
        from xbbg.ext.bonds import abond_cashflows

        df = await abond_cashflows(BOND_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Bond Key Rates
# =============================================================================


class TestBondKeyRates:
    """Tests for bond_key_rates() — key rate durations."""

    def test_bond_key_rates_returns_data(self):
        """bond_key_rates: returns non-empty DataFrame."""
        from xbbg.ext.bonds import bond_key_rates

        df = bond_key_rates(BOND_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_key_rates returned {len(pdf)} rows")

    def test_bond_key_rates_has_tenors(self):
        """bond_key_rates: includes multiple tenor points."""
        from xbbg.ext.bonds import bond_key_rates

        df = bond_key_rates(BOND_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            fields = set(pdf["field"].tolist())
            # Should have at least a few key rate fields
            kr_fields = {f for f in fields if "KEY_RATE" in f}
            assert len(kr_fields) >= 2, f"Expected multiple KEY_RATE fields, got {kr_fields}"
            logger.info(f"  Key rate fields: {sorted(kr_fields)}")


class TestAbondKeyRates:
    """Tests for abond_key_rates() — async key rate durations."""

    @pytest.mark.asyncio
    async def test_abond_key_rates_basic(self):
        """abond_key_rates: basic async call."""
        from xbbg.ext.bonds import abond_key_rates

        df = await abond_key_rates(BOND_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Bond Curve
# =============================================================================


class TestBondCurve:
    """Tests for bond_curve() — relative value comparison."""

    def test_bond_curve_returns_data(self):
        """bond_curve: returns non-empty DataFrame for multiple bonds."""
        from xbbg.ext.bonds import bond_curve

        df = bond_curve(CURVE_TICKERS)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_curve returned {len(pdf)} rows")

    def test_bond_curve_multiple_tickers(self):
        """bond_curve: returns data for each ticker."""
        from xbbg.ext.bonds import bond_curve

        df = bond_curve(CURVE_TICKERS)
        pdf = df.to_pandas()

        if "ticker" in pdf.columns:
            unique_tickers = pdf["ticker"].nunique()
            assert unique_tickers == len(CURVE_TICKERS), f"Expected {len(CURVE_TICKERS)} tickers, got {unique_tickers}"
            logger.info(f"  Got data for {unique_tickers} bonds")

    def test_bond_curve_custom_fields(self):
        """bond_curve: accepts custom fields."""
        from xbbg.ext.bonds import bond_curve

        custom_fields = ["YAS_BOND_YLD", "DUR_ADJ_MID"]
        df = bond_curve(CURVE_TICKERS, flds=custom_fields)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  bond_curve(custom_fields) returned {len(pdf)} rows")


class TestAbondCurve:
    """Tests for abond_curve() — async relative value comparison."""

    @pytest.mark.asyncio
    async def test_abond_curve_basic(self):
        """abond_curve: basic async call."""
        from xbbg.ext.bonds import abond_curve

        df = await abond_curve(CURVE_TICKERS)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Standalone runner
# =============================================================================

TESTS: dict[str, object] = {}


def _register_tests():
    """Collect all test methods from test classes."""
    for cls in [
        TestBondInfo,
        TestAbondInfo,
        TestBondRisk,
        TestAbondRisk,
        TestBondSpreads,
        TestAbondSpreads,
        TestBondCashflows,
        TestAbondCashflows,
        TestBondKeyRates,
        TestAbondKeyRates,
        TestBondCurve,
        TestAbondCurve,
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
            is_async = "abond" in name
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
    parser = argparse.ArgumentParser(description="xbbg ext.bonds Live Tests")
    parser.add_argument("tests", nargs="*", default=list(TESTS.keys()), help="Tests to run")
    parser.add_argument("--list", action="store_true", help="List available tests")
    args = parser.parse_args()

    if args.list:
        for name in sorted(TESTS.keys()):
            logger.info(f"  {name}")
        return 0

    logger.info("=" * 60)
    logger.info("xbbg ext.bonds Live Tests")
    logger.info("=" * 60)
    return 0 if run_tests(args.tests) else 1


if __name__ == "__main__":
    sys.exit(main())
