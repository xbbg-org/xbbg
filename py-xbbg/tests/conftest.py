"""Pytest configuration for xbbg tests."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure the py-xbbg/src package is in path
pkg_root = os.path.dirname(os.path.dirname(__file__))
python_src = os.path.join(pkg_root, "src")
if python_src not in sys.path:
    sys.path.insert(0, python_src)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires Bloomberg connection)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running",
    )
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring a live Bloomberg Terminal or B-PIPE connection",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip live tests when running in CI (no Bloomberg Terminal)."""
    if not os.environ.get("CI"):
        return

    skip_live = pytest.mark.skip(reason="Bloomberg Terminal not available in CI")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def sample_tickers():
    """Fixture providing sample ticker symbols."""
    return ["AAPL US Equity", "MSFT US Equity", "IBM US Equity"]


@pytest.fixture
def sample_fields():
    """Fixture providing sample field names."""
    return ["PX_LAST", "VOLUME", "NAME"]
