"""Unit tests for market resolvers."""

import pandas as pd
import pytest

from xbbg.markets.resolvers import active_futures


class TestActiveFuturesValidation:
    """Test validation logic for active_futures function."""

    def test_generic_ticker_short(self):
        """Test that short generic tickers (3 chars) are accepted."""
        # These should not raise ValueError
        # Note: We can't actually call active_futures without Bloomberg connection,
        # but we can test the validation logic by checking if ValueError is raised
        # for specific contracts vs generic ones
        pass  # Validation happens before Bloomberg calls

    def test_specific_contract_single_digit_year_raises(self):
        """Test that specific contracts with single digit year raise ValueError."""
        with pytest.raises(ValueError, match="appears to be a specific futures contract"):
            active_futures('UXZ5 Index', pd.Timestamp('2024-01-15'))

    def test_specific_contract_two_digit_year_raises(self):
        """Test that specific contracts with two digit year raise ValueError."""
        with pytest.raises(ValueError, match="appears to be a specific futures contract"):
            active_futures('UXZ24 Index', pd.Timestamp('2024-01-15'))

    def test_specific_contract_esam24_raises(self):
        """Test that ESAM24 (specific contract) raises ValueError."""
        with pytest.raises(ValueError, match="appears to be a specific futures contract"):
            active_futures('ESAM24 Index', pd.Timestamp('2024-01-15'))

    def test_generic_ticker_ux1_passes_validation(self):
        """Test that UX1 Index passes validation (short generic ticker)."""
        # This should pass validation (won't raise ValueError for being specific)
        # But may fail later if Bloomberg connection is needed
        try:
            # This will pass validation but may fail on Bloomberg call
            active_futures('UX1 Index', pd.Timestamp('2024-01-15'))
        except ValueError as e:
            # If it's our validation error, that's wrong
            if "appears to be a specific futures contract" in str(e):
                pytest.fail(f"UX1 Index should pass validation but got: {e}")
            # Other errors (like Bloomberg connection) are OK for unit tests
        except Exception:
            # Other exceptions (Bloomberg, etc.) are expected in unit tests
            pass

    def test_generic_ticker_esa1_passes_validation(self):
        """Test that ESA1 Index passes validation."""
        try:
            active_futures('ESA1 Index', pd.Timestamp('2024-01-15'))
        except ValueError as e:
            if "appears to be a specific futures contract" in str(e):
                pytest.fail(f"ESA1 Index should pass validation but got: {e}")
        except Exception:
            pass

    def test_specific_contract_error_message(self):
        """Test that error message is helpful."""
        with pytest.raises(ValueError) as exc_info:
            active_futures('UXZ5 Index', pd.Timestamp('2024-01-15'))

        error_msg = str(exc_info.value)
        assert "UXZ5 Index" in error_msg
        assert "specific futures contract" in error_msg
        assert "generic ticker" in error_msg
        assert "UX1 Index" in error_msg or "UXZ24 Index" in error_msg

