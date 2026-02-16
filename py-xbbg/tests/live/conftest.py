"""Pytest configuration for live Bloomberg tests.

All tests under tests/live/ require a Bloomberg Terminal or B-PIPE connection.
They are automatically marked with ``pytest.mark.live`` and skipped in CI.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark every test collected under live/ as ``live``."""
    for item in items:
        if "/live/" in item.nodeid or "\\live\\" in item.nodeid:
            item.add_marker(pytest.mark.live)
