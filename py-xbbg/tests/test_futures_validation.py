"""Tests for active_futures ticker validation.

Ported from main branch xbbg/tests/test_resolvers.py.
Tests the Rust-backed validation that ensures active_futures() receives
a generic ticker (e.g., 'ES1 Index') rather than a specific contract
(e.g., 'ESH24 Index').

NOTE: The actual active_futures() function requires a Bloomberg connection,
so we only test the synchronous validation layer that raises ValueError
before any Bloomberg call is made. The validation is done by the Rust
function ext_validate_generic_ticker which calls is_specific_contract.
"""

from __future__ import annotations

import pytest

from xbbg._core import ext_validate_generic_ticker


class TestValidateGenericTicker:
    """Test the Rust-backed generic ticker validation."""

    # -------------------------------------------------------------------------
    # Specific contracts that SHOULD be rejected
    # -------------------------------------------------------------------------

    def test_specific_contract_single_digit_year_raises(self):
        """Specific contracts with single digit year should raise ValueError.

        Example: UXZ5 = VIX futures December 2025 (specific contract).
        """
        with pytest.raises(ValueError, match="appears to be a specific contract"):
            ext_validate_generic_ticker("UXZ5 Index")

    def test_specific_contract_two_digit_year_raises(self):
        """Specific contracts with two digit year should raise ValueError.

        Example: UXZ24 = VIX futures December 2024 (specific contract).
        """
        with pytest.raises(ValueError, match="appears to be a specific contract"):
            ext_validate_generic_ticker("UXZ24 Index")

    def test_specific_contract_esam24_raises(self):
        """Multi-letter month codes (e.g., ESAM24) should raise ValueError.

        ESAM24 = E-mini S&P500 June 2024 with 'A' prefix (specific contract).
        """
        with pytest.raises(ValueError, match="appears to be a specific contract"):
            ext_validate_generic_ticker("ESAM24 Index")

    def test_specific_contract_esh24_raises(self):
        """ESH24 (March 2024 E-mini) should raise ValueError."""
        with pytest.raises(ValueError, match="appears to be a specific contract"):
            ext_validate_generic_ticker("ESH24 Index")

    def test_specific_contract_clz24_raises(self):
        """CLZ24 (December 2024 Crude Oil) should raise ValueError."""
        with pytest.raises(ValueError, match="appears to be a specific contract"):
            ext_validate_generic_ticker("CLZ24 Comdty")

    # -------------------------------------------------------------------------
    # Generic tickers that SHOULD pass
    # -------------------------------------------------------------------------

    def test_generic_ticker_es1_passes(self):
        """ES1 Index (generic 1st E-mini) should pass validation."""
        # Should not raise
        ext_validate_generic_ticker("ES1 Index")

    def test_generic_ticker_ux1_passes(self):
        """UX1 Index (generic 1st VIX futures) should pass validation."""
        ext_validate_generic_ticker("UX1 Index")

    def test_generic_ticker_cl1_passes(self):
        """CL1 Comdty (generic 1st Crude Oil) should pass validation."""
        ext_validate_generic_ticker("CL1 Comdty")

    def test_generic_ticker_esa1_passes(self):
        """ESA1 Index (generic 1st E-mini with 'A' prefix) should pass validation."""
        ext_validate_generic_ticker("ESA1 Index")

    def test_generic_ticker_es2_passes(self):
        """ES2 Index (generic 2nd E-mini) should pass validation."""
        ext_validate_generic_ticker("ES2 Index")

    # -------------------------------------------------------------------------
    # Error message quality
    # -------------------------------------------------------------------------

    def test_error_message_includes_ticker(self):
        """Error message should include the offending ticker."""
        with pytest.raises(ValueError) as exc_info:
            ext_validate_generic_ticker("UXZ5 Index")

        error_msg = str(exc_info.value)
        assert "UXZ5 Index" in error_msg

    def test_error_message_mentions_generic(self):
        """Error message should mention using a generic ticker."""
        with pytest.raises(ValueError) as exc_info:
            ext_validate_generic_ticker("ESH24 Index")

        error_msg = str(exc_info.value)
        assert "generic" in error_msg.lower()


class TestActiveFuturesValidation:
    """Test that active_futures() properly validates before making Bloomberg calls.

    These tests verify the validation layer works end-to-end through
    the Python active_futures() function. They will raise ValueError
    from the Rust validation before any Bloomberg call is attempted.
    """

    def test_active_futures_rejects_specific_contract(self):
        """active_futures() should reject specific contracts."""
        from xbbg.ext.futures import active_futures

        with pytest.raises(ValueError, match="appears to be a specific contract"):
            active_futures("UXZ5 Index", "2024-01-15")

    def test_active_futures_rejects_two_digit_year(self):
        """active_futures() should reject contracts with two digit year."""
        from xbbg.ext.futures import active_futures

        with pytest.raises(ValueError, match="appears to be a specific contract"):
            active_futures("UXZ24 Index", "2024-01-15")
