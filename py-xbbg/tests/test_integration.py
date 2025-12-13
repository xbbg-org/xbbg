"""Integration tests that require a Bloomberg connection.

These tests are skipped in CI and only run locally with Bloomberg Terminal/BPIPE.
Set XBBG_INTEGRATION_TESTS=1 to enable these tests.
"""

import os

import pytest

# Skip all tests in this module unless XBBG_INTEGRATION_TESTS is set
pytestmark = pytest.mark.skipif(
    os.environ.get("XBBG_INTEGRATION_TESTS") != "1",
    reason="Integration tests require Bloomberg connection (set XBBG_INTEGRATION_TESTS=1)",
)


@pytest.mark.integration
class TestBdpIntegration:
    """Integration tests for bdp function."""

    def test_bdp_single_ticker(self):
        """Test bdp with a single ticker."""
        # TODO: Implement when Bloomberg connection is available
        pytest.skip("Requires Bloomberg connection")

    def test_bdp_multiple_tickers(self):
        """Test bdp with multiple tickers."""
        # TODO: Implement when Bloomberg connection is available
        pytest.skip("Requires Bloomberg connection")


@pytest.mark.integration
class TestBdsIntegration:
    """Integration tests for bds function."""

    def test_bds_index_members(self):
        """Test bds for index members."""
        # TODO: Implement when Bloomberg connection is available
        pytest.skip("Requires Bloomberg connection")


@pytest.mark.integration
class TestBdhIntegration:
    """Integration tests for bdh function."""

    def test_bdh_historical_prices(self):
        """Test bdh for historical prices."""
        # TODO: Implement when Bloomberg connection is available
        pytest.skip("Requires Bloomberg connection")


@pytest.mark.integration
class TestBdibIntegration:
    """Integration tests for bdib function."""

    def test_bdib_intraday_bars(self):
        """Test bdib for intraday bars."""
        # TODO: Implement when Bloomberg connection is available
        pytest.skip("Requires Bloomberg connection")
