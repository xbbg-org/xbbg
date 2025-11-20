"""Unit tests for cache adapters."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.io.cache import BarCacheAdapter, get_cache_root


class TestGetCacheRoot:
    """Test get_cache_root() function."""

    def test_get_cache_root_with_bbg_root_set(self):
        """Test that get_cache_root() returns BBG_ROOT when set."""
        with patch.dict(os.environ, {'BBG_ROOT': '/custom/path'}):
            result = get_cache_root()
            assert result == '/custom/path'

    def test_get_cache_root_without_bbg_root_uses_default(self, caplog):
        """Test that get_cache_root() returns default location when BBG_ROOT not set."""
        with patch.dict(os.environ, {}, clear=True):
            if 'BBG_ROOT' in os.environ:
                del os.environ['BBG_ROOT']

            # Reset the module-level flag to allow logging
            import xbbg.io.cache as cache_module
            cache_module._default_cache_logged = False

            # Mock Path.home() to avoid issues in test environment
            # Use a Windows-style path for cross-platform compatibility
            import sys
            if sys.platform == 'win32':
                test_home = Path('C:/test/home')
            else:
                test_home = Path('/test/home')
            with patch('pathlib.Path.home', return_value=test_home):
                with caplog.at_level(logging.INFO, logger='xbbg.io.cache'):
                    result = get_cache_root()

                # Should return a default path
                assert result
                # On Windows, check that path is valid (not just is_absolute)
                result_path = Path(result)
                assert result_path.as_posix()  # Just verify it's a valid path string

                # Should log INFO message about default location
                info_messages = [record.message for record in caplog.records if record.levelname == 'INFO']
                default_cache_msgs = [msg for msg in info_messages if 'default cache location' in msg.lower() or 'BBG_ROOT not set' in msg]
                assert len(default_cache_msgs) > 0, f"Expected INFO message about default cache location. Got: {info_messages}"


class TestBarCacheAdapter:
    """Test BarCacheAdapter save and load methods."""

    def test_save_without_bbg_root_uses_default_cache(self, caplog, tmp_path):
        """Test that save() uses default cache location when BBG_ROOT is not set."""
        # Ensure BBG_ROOT is not set
        with patch.dict(os.environ, {}, clear=True):
            if 'BBG_ROOT' in os.environ:
                del os.environ['BBG_ROOT']

            # Reset the module-level flag to allow logging
            import xbbg.io.cache as cache_module
            cache_module._default_cache_logged = False

            # Mock get_cache_root to return tmp_path to avoid actual file I/O
            with patch('xbbg.io.cache.get_cache_root', return_value=str(tmp_path)):
                adapter = BarCacheAdapter()

                # Create a test request
                request = DataRequest(
                    ticker='AAPL US Equity',
                    dt=datetime(2025, 11, 19),
                    event_type='TRADE',
                )

                # Create a valid session window
                session_window = SessionWindow(
                    start_time='2025-11-19T14:30:00',
                    end_time='2025-11-19T21:00:00',
                    session_name='day',
                )

                # Create test data as DataFrame (not Series)
                test_data = pd.DataFrame({
                    'AAPL US Equity': [100.0, 101.0, 102.0],
                }, index=pd.date_range('2025-11-19 14:30:00', periods=3, freq='1h'))

                # Mock save_intraday to avoid actual file operations
                with patch('xbbg.io.cache.save_intraday'):
                    # Set logging level to INFO to see default cache message
                    with caplog.at_level(logging.INFO, logger='xbbg.io.cache'):
                        adapter.save(test_data, request, session_window)

                    # Verify no WARNING messages about BBG_ROOT were logged
                    warning_messages = [record.message for record in caplog.records if record.levelname == 'WARNING']
                    bbg_root_warnings = [msg for msg in warning_messages if 'BBG_ROOT' in msg and 'not set' in msg]
                    assert len(bbg_root_warnings) == 0, f"Found unexpected WARNING messages: {bbg_root_warnings}"

    def test_save_with_empty_data_logs_warning(self, caplog):
        """Test that save() logs WARNING when data is empty."""
        adapter = BarCacheAdapter()

        # Create a test request
        request = DataRequest(
            ticker='AAPL US Equity',
            dt=datetime(2025, 11, 19),
            event_type='TRADE',
        )

        # Create a valid session window
        session_window = SessionWindow(
            start_time='2025-11-19T14:30:00',
            end_time='2025-11-19T21:00:00',
            session_name='day',
        )

        # Create empty test data
        test_data = pd.DataFrame()

        with caplog.at_level(logging.WARNING):
            adapter.save(test_data, request, session_window)

        # Verify WARNING message was logged for empty data
        warning_messages = [record.message for record in caplog.records if record.levelname == 'WARNING']
        empty_data_warnings = [msg for msg in warning_messages if 'No data to save' in msg]
        assert len(empty_data_warnings) > 0, "Expected WARNING message about empty data"

