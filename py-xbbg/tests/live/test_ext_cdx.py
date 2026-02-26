#!/usr/bin/env python
"""Live integration tests for xbbg.ext.cdx.

Tests exercise the complete Python → Rust → Bloomberg → Rust → Python
data flow for CDX credit default swap index analytics extension functions.

Run with:
    pytest tests/live/test_ext_cdx.py -v --tb=short

Or as a standalone script:
    python tests/live/test_ext_cdx.py [test_names...]
    python tests/live/test_ext_cdx.py --list

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

# Investment-grade CDX — most liquid credit index, always available
CDX_TICKER = "CDX IG CDSI GEN 5Y Corp"

# Generic ticker for curve tests (tenor token = "5Y")
CDX_CURVE_TICKER = "CDX IG CDSI GEN 5Y Corp"


# =============================================================================
# CDX Info
# =============================================================================


class TestCdxInfo:
    """Tests for cdx_info() — CDX reference metadata."""

    def test_cdx_info_returns_data(self):
        """cdx_info: returns non-empty DataFrame."""
        from xbbg.ext.cdx import cdx_info

        df = cdx_info(CDX_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_info returned {len(pdf)} rows")

    def test_cdx_info_has_series(self):
        """cdx_info: includes ROLLING_SERIES field."""
        from xbbg.ext.cdx import cdx_info

        df = cdx_info(CDX_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            series_rows = pdf[pdf["field"] == "ROLLING_SERIES"]
            assert len(series_rows) >= 1, "Expected ROLLING_SERIES in result"
            val = series_rows.iloc[0]["value"]
            assert val is not None
            logger.info(f"  ROLLING_SERIES = {val}")

    def test_cdx_info_has_name(self):
        """cdx_info: includes NAME field."""
        from xbbg.ext.cdx import cdx_info

        df = cdx_info(CDX_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            name_rows = pdf[pdf["field"] == "NAME"]
            assert len(name_rows) >= 1, "Expected NAME in result"
            logger.info(f"  NAME = {name_rows.iloc[0]['value']}")


class TestAcdxInfo:
    """Tests for acdx_info() — async CDX reference metadata."""

    @pytest.mark.asyncio
    async def test_acdx_info_basic(self):
        """acdx_info: basic async call."""
        from xbbg.ext.cdx import acdx_info

        df = await acdx_info(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Defaults
# =============================================================================


class TestCdxDefaults:
    """Tests for cdx_defaults() — default history."""

    def test_cdx_defaults_returns_data(self):
        """cdx_defaults: returns DataFrame (may be empty for IG)."""
        from xbbg.ext.cdx import cdx_defaults

        df = cdx_defaults(CDX_TICKER)
        pdf = df.to_pandas()

        # IG CDX may have no defaults — just verify it returns cleanly
        logger.info(f"  cdx_defaults returned {len(pdf)} rows")


class TestAcdxDefaults:
    """Tests for acdx_defaults() — async default history."""

    @pytest.mark.asyncio
    async def test_acdx_defaults_basic(self):
        """acdx_defaults: basic async call."""
        from xbbg.ext.cdx import acdx_defaults

        df = await acdx_defaults(CDX_TICKER)
        # May be empty for IG — just check it completes
        df.to_pandas()


# =============================================================================
# CDX Pricing
# =============================================================================


class TestCdxPricing:
    """Tests for cdx_pricing() — market pricing."""

    def test_cdx_pricing_returns_data(self):
        """cdx_pricing: returns non-empty DataFrame."""
        from xbbg.ext.cdx import cdx_pricing

        df = cdx_pricing(CDX_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_pricing returned {len(pdf)} rows")

    def test_cdx_pricing_has_spread(self):
        """cdx_pricing: includes PX_LAST."""
        from xbbg.ext.cdx import cdx_pricing

        df = cdx_pricing(CDX_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            px_rows = pdf[pdf["field"] == "PX_LAST"]
            assert len(px_rows) >= 1, "Expected PX_LAST in result"
            logger.info(f"  PX_LAST = {px_rows.iloc[0]['value']}")

    def test_cdx_pricing_with_recovery_rate(self):
        """cdx_pricing: accepts recovery_rate override."""
        from xbbg.ext.cdx import cdx_pricing

        df = cdx_pricing(CDX_TICKER, recovery_rate=40)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_pricing(rr=40) returned {len(pdf)} rows")


class TestAcdxPricing:
    """Tests for acdx_pricing() — async market pricing."""

    @pytest.mark.asyncio
    async def test_acdx_pricing_basic(self):
        """acdx_pricing: basic async call."""
        from xbbg.ext.cdx import acdx_pricing

        df = await acdx_pricing(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Risk
# =============================================================================


class TestCdxRisk:
    """Tests for cdx_risk() — risk metrics."""

    def test_cdx_risk_returns_data(self):
        """cdx_risk: returns non-empty DataFrame."""
        from xbbg.ext.cdx import cdx_risk

        df = cdx_risk(CDX_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_risk returned {len(pdf)} rows")

    def test_cdx_risk_has_duration(self):
        """cdx_risk: includes modified duration."""
        from xbbg.ext.cdx import cdx_risk

        df = cdx_risk(CDX_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            dur_rows = pdf[pdf["field"] == "CDS_SPREAD_MID_MODIFIED_DURATION"]
            assert len(dur_rows) >= 1, "Expected CDS_SPREAD_MID_MODIFIED_DURATION in result"
            logger.info(f"  CDS_SPREAD_MID_MODIFIED_DURATION = {dur_rows.iloc[0]['value']}")

    def test_cdx_risk_with_recovery_rate(self):
        """cdx_risk: accepts recovery_rate override."""
        from xbbg.ext.cdx import cdx_risk

        df = cdx_risk(CDX_TICKER, recovery_rate=40)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_risk(rr=40) returned {len(pdf)} rows")


class TestAcdxRisk:
    """Tests for acdx_risk() — async risk metrics."""

    @pytest.mark.asyncio
    async def test_acdx_risk_basic(self):
        """acdx_risk: basic async call."""
        from xbbg.ext.cdx import acdx_risk

        df = await acdx_risk(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Basis
# =============================================================================


class TestCdxBasis:
    """Tests for cdx_basis() — basis analytics."""

    def test_cdx_basis_returns_data(self):
        """cdx_basis: returns non-empty DataFrame."""
        from xbbg.ext.cdx import cdx_basis

        df = cdx_basis(CDX_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_basis returned {len(pdf)} rows")

    def test_cdx_basis_has_intrinsic(self):
        """cdx_basis: includes intrinsic value."""
        from xbbg.ext.cdx import cdx_basis

        df = cdx_basis(CDX_TICKER)
        pdf = df.to_pandas()

        if "field" in pdf.columns:
            iv_rows = pdf[pdf["field"] == "CDS_INDEX_INTRINSIC_VALUE"]
            assert len(iv_rows) >= 1, "Expected CDS_INDEX_INTRINSIC_VALUE in result"
            logger.info(f"  CDS_INDEX_INTRINSIC_VALUE = {iv_rows.iloc[0]['value']}")


class TestAcdxBasis:
    """Tests for acdx_basis() — async basis analytics."""

    @pytest.mark.asyncio
    async def test_acdx_basis_basic(self):
        """acdx_basis: basic async call."""
        from xbbg.ext.cdx import acdx_basis

        df = await acdx_basis(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Default Probability
# =============================================================================


class TestCdxDefaultProb:
    """Tests for cdx_default_prob() — default probability."""

    def test_cdx_default_prob_returns_data(self):
        """cdx_default_prob: returns DataFrame."""
        from xbbg.ext.cdx import cdx_default_prob

        df = cdx_default_prob(CDX_TICKER)
        pdf = df.to_pandas()

        # Should return probability data
        assert len(pdf) >= 1
        logger.info(f"  cdx_default_prob returned {len(pdf)} rows")


class TestAcdxDefaultProb:
    """Tests for acdx_default_prob() — async default probability."""

    @pytest.mark.asyncio
    async def test_acdx_default_prob_basic(self):
        """acdx_default_prob: basic async call."""
        from xbbg.ext.cdx import acdx_default_prob

        df = await acdx_default_prob(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Cashflows
# =============================================================================


class TestCdxCashflows:
    """Tests for cdx_cashflows() — cash flow schedule."""

    def test_cdx_cashflows_returns_data(self):
        """cdx_cashflows: returns non-empty DataFrame."""
        from xbbg.ext.cdx import cdx_cashflows

        df = cdx_cashflows(CDX_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_cashflows returned {len(pdf)} rows")

    def test_cdx_cashflows_multiple_rows(self):
        """cdx_cashflows: returns multiple payment rows."""
        from xbbg.ext.cdx import cdx_cashflows

        df = cdx_cashflows(CDX_TICKER)
        pdf = df.to_pandas()

        # A 5Y CDX should have quarterly premium payments
        assert len(pdf) >= 2, "Expected multiple cash flow rows for CDX"
        logger.info(f"  Got {len(pdf)} cash flow entries")


class TestAcdxCashflows:
    """Tests for acdx_cashflows() — async cash flow schedule."""

    @pytest.mark.asyncio
    async def test_acdx_cashflows_basic(self):
        """acdx_cashflows: basic async call."""
        from xbbg.ext.cdx import acdx_cashflows

        df = await acdx_cashflows(CDX_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# CDX Curve
# =============================================================================


class TestCdxCurve:
    """Tests for cdx_curve() — term structure."""

    def test_cdx_curve_default_tenors(self):
        """cdx_curve: returns data for default tenors (3Y, 5Y, 7Y, 10Y)."""
        from xbbg.ext.cdx import cdx_curve

        df = cdx_curve(CDX_CURVE_TICKER)
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_curve returned {len(pdf)} rows")

    def test_cdx_curve_multi_tenor(self):
        """cdx_curve: returns data for each requested tenor."""
        from xbbg.ext.cdx import cdx_curve

        tenors = ["3Y", "5Y", "7Y", "10Y"]
        df = cdx_curve(CDX_CURVE_TICKER, tenors=tenors)
        pdf = df.to_pandas()

        if "ticker" in pdf.columns:
            unique_tickers = pdf["ticker"].nunique()
            assert unique_tickers >= 2, f"Expected data for multiple tenors, got {unique_tickers} unique tickers"
            logger.info(f"  Got data for {unique_tickers} tenors")

    def test_cdx_curve_custom_tenors(self):
        """cdx_curve: accepts custom tenor list."""
        from xbbg.ext.cdx import cdx_curve

        df = cdx_curve(CDX_CURVE_TICKER, tenors=["5Y", "10Y"])
        pdf = df.to_pandas()

        assert len(pdf) >= 1
        logger.info(f"  cdx_curve(5Y, 10Y) returned {len(pdf)} rows")


class TestAcdxCurve:
    """Tests for acdx_curve() — async term structure."""

    @pytest.mark.asyncio
    async def test_acdx_curve_basic(self):
        """acdx_curve: basic async call."""
        from xbbg.ext.cdx import acdx_curve

        df = await acdx_curve(CDX_CURVE_TICKER)
        assert len(df.to_pandas()) >= 1


# =============================================================================
# Standalone runner
# =============================================================================

TESTS: dict[str, object] = {}


def _register_tests():
    for cls in [
        TestCdxInfo,
        TestAcdxInfo,
        TestCdxDefaults,
        TestAcdxDefaults,
        TestCdxPricing,
        TestAcdxPricing,
        TestCdxRisk,
        TestAcdxRisk,
        TestCdxBasis,
        TestAcdxBasis,
        TestCdxDefaultProb,
        TestAcdxDefaultProb,
        TestCdxCashflows,
        TestAcdxCashflows,
        TestCdxCurve,
        TestAcdxCurve,
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
            is_async = "acdx" in name
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
    parser = argparse.ArgumentParser(description="xbbg ext.cdx Live Tests")
    parser.add_argument("tests", nargs="*", default=list(TESTS.keys()), help="Tests to run")
    parser.add_argument("--list", action="store_true", help="List available tests")
    args = parser.parse_args()

    if args.list:
        for name in sorted(TESTS.keys()):
            logger.info(f"  {name}")
        return 0

    logger.info("=" * 60)
    logger.info("xbbg ext.cdx Live Tests")
    logger.info("=" * 60)
    return 0 if run_tests(args.tests) else 1


if __name__ == "__main__":
    sys.exit(main())
