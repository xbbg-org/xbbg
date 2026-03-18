"""Unit tests for logging behavior in critical xbbg paths.

Tests verify that logging occurs at the correct levels for:
- Session/service handle invalidation (conn.py)
- Cache load failures (cache.py)
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestConnLogging:
    """Test logging in xbbg.core.infra.conn module."""

    def test_stale_session_removal_logs_info(self, caplog):
        """Test that removing stale session logs INFO when handle is invalid."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        # Create a mock session with invalid handle
        mock_session = MagicMock()
        mock_session.isValid.return_value = False  # Invalid handle

        # Store in manager's sessions dict
        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_session

        # Call get_session which should detect stale session and log
        with (
            caplog.at_level(logging.INFO, logger="xbbg.core.infra.conn"),
            patch("xbbg.core.infra.conn.connect_bbg") as mock_connect,
        ):
            mock_new_session = MagicMock()
            mock_new_session.isValid.return_value = True
            mock_connect.return_value = mock_new_session

            # This should detect stale session, log INFO, and create new one
            # Use only port parameter to avoid duplicate server_host in kwargs
            manager.get_session(port=8194)

        # Verify INFO message about removing stale session was logged
        info_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        stale_session_msgs = [msg for msg in info_messages if "stale" in msg.lower() and "session" in msg.lower()]
        assert len(stale_session_msgs) > 0, f"Expected INFO about stale session. Got: {info_messages}"
        assert "handle invalidated" in stale_session_msgs[0].lower()

    def test_stale_service_removal_logs_info(self, caplog):
        """Test that removing stale service logs INFO when handle is invalid."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        # Create a mock service with invalid handle
        mock_service = MagicMock()
        mock_service.isValid.return_value = False  # Invalid handle

        # Store in manager's services dict
        serv_key = "//localhost:8194//blp/refdata"
        manager._services[serv_key] = mock_service

        # Create a mock session for get_service to use
        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        with caplog.at_level(logging.INFO, logger="xbbg.core.infra.conn"):
            # Mock session.openService and session.getService
            mock_session.openService = MagicMock()
            mock_new_service = MagicMock()
            mock_new_service.isValid.return_value = True
            mock_session.getService = MagicMock(return_value=mock_new_service)

            # This should detect stale service, log INFO, and create new one
            manager.get_service("//blp/refdata", port=8194, server_host="localhost")

        # Verify INFO message about removing stale service
        info_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        stale_service_msgs = [msg for msg in info_messages if "stale" in msg.lower() and "service" in msg.lower()]
        assert len(stale_service_msgs) > 0, f"Expected INFO about stale service. Got: {info_messages}"
        assert "handle invalidated" in stale_service_msgs[0].lower()

    def test_remove_session_logs_info(self, caplog):
        """Test that explicitly removing a session logs INFO."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        # Store a mock session
        mock_session = MagicMock()
        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_session

        with caplog.at_level(logging.INFO, logger="xbbg.core.infra.conn"):
            manager.remove_session(port=8194, server_host="localhost")

        # Verify INFO message about removing session
        info_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        remove_msgs = [msg for msg in info_messages if "removing" in msg.lower() and "session" in msg.lower()]
        assert len(remove_msgs) > 0, f"Expected INFO about removing session. Got: {info_messages}"


class TestCacheLogging:
    """Test logging in xbbg.io.cache module."""

    def test_cache_load_failure_logs_warning(self, caplog, tmp_path):
        """Test that cache load failure logs WARNING (not DEBUG) for corrupt files."""
        from xbbg.core.domain.contracts import DataRequest, SessionWindow
        from xbbg.io.cache import BarCacheAdapter

        # Create a corrupt parquet file
        corrupt_file = tmp_path / "corrupt.parq"
        corrupt_file.write_bytes(b"not a valid parquet file")

        adapter = BarCacheAdapter()

        # Create a test request
        request = DataRequest(
            ticker="AAPL US Equity",
            dt="2025-01-15",
            event_type="TRADE",
        )

        # Create a valid session window
        session_window = SessionWindow(
            start_time="2025-01-15T14:30:00",
            end_time="2025-01-15T21:00:00",
            session_name="day",
        )

        # Mock bar_file to return our corrupt file path
        with (
            patch("xbbg.io.cache.bar_file", return_value=corrupt_file.as_posix()),
            patch("xbbg.io.cache.Path.exists", return_value=True),
            caplog.at_level(logging.WARNING, logger="xbbg.io.cache"),
        ):
            adapter.load(request, session_window)

        # Verify WARNING message about cache load failure
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        cache_fail_msgs = [msg for msg in warning_messages if "cache load failed" in msg.lower()]
        assert len(cache_fail_msgs) > 0, f"Expected WARNING about cache load failure. Got: {warning_messages}"
        assert "corrupt" in cache_fail_msgs[0].lower()

    def test_multi_day_cache_load_failure_logs_warning(self, caplog, tmp_path):
        """Test that multi-day cache load failure logs WARNING for corrupt files."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.io.cache import BarCacheAdapter

        # Create a corrupt parquet file
        corrupt_file = tmp_path / "corrupt.parq"
        corrupt_file.write_bytes(b"not a valid parquet file")

        adapter = BarCacheAdapter()

        # Create a multi-day test request
        request = DataRequest(
            ticker="AAPL US Equity",
            dt="2025-01-15",
            start_datetime="2025-01-15",
            end_datetime="2025-01-17",
            event_type="TRADE",
        )

        # Mock multi_day_bar_files to return file paths
        mock_day_files = [
            ("2025-01-15", corrupt_file.as_posix()),
            ("2025-01-16", corrupt_file.as_posix()),
            ("2025-01-17", corrupt_file.as_posix()),
        ]

        with (
            patch("xbbg.io.cache.multi_day_bar_files", return_value=mock_day_files),
            patch("xbbg.io.cache.Path.exists", return_value=True),
            caplog.at_level(logging.WARNING, logger="xbbg.io.cache"),
        ):
            adapter._load_multi_day(request)

        # Verify WARNING message about cache load failure
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        cache_fail_msgs = [msg for msg in warning_messages if "failed to load cache file" in msg.lower()]
        assert len(cache_fail_msgs) > 0, f"Expected WARNING about failed cache file. Got: {warning_messages}"
        assert "corrupt" in cache_fail_msgs[0].lower()

    def test_empty_data_save_logs_warning(self, caplog):
        """Test that saving empty data logs WARNING."""
        import pandas as pd

        from xbbg.core.domain.contracts import DataRequest, SessionWindow
        from xbbg.io.cache import BarCacheAdapter

        adapter = BarCacheAdapter()

        # Create a test request
        request = DataRequest(
            ticker="AAPL US Equity",
            dt="2025-01-15",
            event_type="TRADE",
        )

        # Create a valid session window
        session_window = SessionWindow(
            start_time="2025-01-15T14:30:00",
            end_time="2025-01-15T21:00:00",
            session_name="day",
        )

        # Create empty DataFrame
        empty_data = pd.DataFrame()

        with caplog.at_level(logging.WARNING, logger="xbbg.io.cache"):
            adapter.save(empty_data, request, session_window)

        # Verify WARNING message about empty data
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        empty_msgs = [msg for msg in warning_messages if "no data to save" in msg.lower()]
        assert len(empty_msgs) > 0, f"Expected WARNING about empty data. Got: {warning_messages}"


class TestCacheDefaultLocationLogging:
    """Test logging for default cache location in xbbg.io.cache module."""

    def test_default_cache_location_logs_warning_once(self, caplog):
        """Test that default cache location is logged WARNING once when BBG_ROOT not set.

        This is WARNING level because it indicates a meaningful configuration issue:
        users may not realize their cache is going to a default location.
        """
        import os
        import sys

        import xbbg.io.cache as cache_module

        # Reset the module-level flag to allow logging
        cache_module._default_cache_logged = False

        # Ensure BBG_ROOT is not set
        with patch.dict(os.environ, {}, clear=True):
            if "BBG_ROOT" in os.environ:
                del os.environ["BBG_ROOT"]

            # Mock Path.home() to avoid issues in test environment
            if sys.platform == "win32":
                test_home = Path("C:/test/home")
            else:
                test_home = Path("/test/home")

            with (
                patch("pathlib.Path.home", return_value=test_home),
                caplog.at_level(logging.WARNING, logger="xbbg.io.cache"),
            ):
                cache_module.get_cache_root()
                cache_module.get_cache_root()

        # Verify WARNING message was logged exactly once
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        default_cache_msgs = [
            msg
            for msg in warning_messages
            if "default cache location" in msg.lower() or "bbg_root not set" in msg.lower()
        ]
        assert len(default_cache_msgs) == 1, (
            f"Expected exactly 1 WARNING message about default cache location. "
            f"Got {len(default_cache_msgs)}: {default_cache_msgs}"
        )
