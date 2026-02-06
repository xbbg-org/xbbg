"""Comprehensive unit tests for xbbg.core.infra.conn module.

Tests Bloomberg session/connection management including:
- SessionManager singleton and caching behavior
- bbg_session and bbg_service public functions
- connect_bbg connection handling
- send_request retry logic
- Regression tests for bug fixes
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from xbbg.core.infra.blpapi_wrapper import blpapi


class TestBugRegressions:
    """Regression tests for the 5 bugs fixed in conn.py."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_bbg_session_with_port_kwarg_no_duplicate(self):
        """Bug 1: bbg_session(port=8195) must NOT raise TypeError about duplicate kwargs.

        Verifies that .pop() is used instead of .get() so port is consumed and
        not passed twice to get_session().
        """
        from xbbg.core.infra.conn import SessionManager, bbg_session

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            # This should NOT raise TypeError: got multiple values for keyword argument 'port'
            result = bbg_session(port=8195)

        assert result is mock_session

    def test_bbg_service_with_port_kwarg_no_duplicate(self):
        """Bug 1b: bbg_service("//blp/refdata", port=8195) must NOT raise TypeError.

        Same issue as bbg_session - port must be popped, not just read.
        """
        from xbbg.core.infra.conn import SessionManager, bbg_service

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"
        mock_service = MagicMock()
        mock_service._Service__handle = "valid_service_handle"
        mock_session.getService.return_value = mock_service

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            # This should NOT raise TypeError
            result = bbg_service("//blp/refdata", port=8195)

        assert result is mock_service

    def test_clear_default_session_stops_session(self):
        """Bug 2: clear_default_session() must call .stop() on the session."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        manager._default_session = mock_session

        manager.clear_default_session()

        mock_session.stop.assert_called_once()

    def test_clear_default_session_removes_from_sessions_dict(self):
        """Bug 2b: clear_default_session() must remove from BOTH _default_session AND _sessions."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_session
        manager._default_session = mock_session

        manager.clear_default_session()

        assert manager._default_session is None
        assert con_key not in manager._sessions

    def test_remove_session_stops_session(self):
        """Bug 3: remove_session() must call .stop() on the session."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_session

        manager.remove_session(port=8194, server_host="localhost")

        mock_session.stop.assert_called_once()

    def test_remove_session_clears_default_if_same(self):
        """Bug 3b: remove_session() must clear _default_session if same object."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_session
        manager._default_session = mock_session

        manager.remove_session(port=8194, server_host="localhost")

        assert manager._default_session is None

    def test_get_session_stale_handle_stops_session(self):
        """Bug 4: get_session() must call .stop() on stale session before creating new one."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_stale_session = MagicMock()
        mock_stale_session._Session__handle = None  # Stale: handle is None

        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_stale_session

        mock_new_session = MagicMock()
        mock_new_session._Session__handle = "valid_handle"

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_new_session):
            manager.get_session(port=8194)

        mock_stale_session.stop.assert_called_once()

    def test_send_request_retry_passes_server_host(self):
        """Bug 5: send_request retry must pass server_host to remove_session."""
        from xbbg.core.infra.conn import SessionManager, send_request

        manager = SessionManager()

        # Create mock session that raises on first sendRequest, succeeds on second
        mock_session = MagicMock()
        call_count = 0

        def send_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise blpapi.InvalidStateException("Session not started", 0)

        mock_session.sendRequest.side_effect = send_side_effect
        mock_session._Session__handle = "valid_handle"

        mock_request = MagicMock()

        with (
            patch("xbbg.core.infra.conn.bbg_session", return_value=mock_session),
            patch.object(manager, "remove_session") as mock_remove,
        ):
            send_request(mock_request, port=8195, server_host="bpipe.example.com")

        # Verify remove_session was called with BOTH port AND server_host
        mock_remove.assert_called_once_with(port=8195, server_host="bpipe.example.com")

    def test_connect_bbg_stops_session_on_start_failure(self):
        """Bug 6: connect_bbg must call .stop() on session if start() returns False."""
        from xbbg.core.infra.conn import connect_bbg

        mock_session = MagicMock()
        mock_session.start.return_value = False

        # Create a callable class that returns our mock session when instantiated
        # but is still a valid type for isinstance checks
        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        # Create a mock blpapi module
        mock_blpapi = MagicMock()
        mock_blpapi.Session = MockSessionClass
        mock_blpapi.SessionOptions.return_value = MagicMock()

        with (
            patch("xbbg.core.infra.conn.blpapi", mock_blpapi),
            pytest.raises(ConnectionError),
        ):
            connect_bbg(port=8194)

        mock_session.stop.assert_called_once()

    def test_connect_bbg_server_host_order(self):
        """Bug 7: server_host must take precedence over server parameter."""
        from xbbg.core.infra.conn import connect_bbg

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = True

        # Create a callable class that returns our mock session when instantiated
        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        # Create a mock blpapi module
        mock_blpapi = MagicMock()
        mock_blpapi.Session = MockSessionClass
        mock_blpapi.SessionOptions.return_value = mock_opts

        with patch("xbbg.core.infra.conn.blpapi", mock_blpapi):
            connect_bbg(server_host="A", server="B")

        # server_host="A" should win over server="B"
        mock_opts.setServerHost.assert_called_once_with("A")


class TestSessionManagerSingleton:
    """Test SessionManager singleton pattern and basic operations."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_session_manager_singleton(self):
        """SessionManager must be a singleton - same instance returned."""
        from xbbg.core.infra.conn import SessionManager

        manager1 = SessionManager()
        manager2 = SessionManager()

        assert manager1 is manager2

    def test_get_session_creates_new(self):
        """get_session() creates new session when cache is empty."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session) as mock_connect:
            result = manager.get_session(port=8194)

        mock_connect.assert_called_once()
        assert result is mock_session
        assert "//localhost:8194" in manager._sessions

    def test_get_session_returns_cached(self):
        """get_session() returns cached session without calling connect_bbg."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"
        manager._sessions["//localhost:8194"] = mock_session

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = manager.get_session(port=8194)

        mock_connect.assert_not_called()
        assert result is mock_session

    def test_get_session_uses_default_when_no_host(self):
        """get_session() with no server_host returns default session if set."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_default = MagicMock()
        mock_default._Session__handle = "valid_handle"
        manager._default_session = mock_default

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = manager.get_session(port=8194)

        mock_connect.assert_not_called()
        assert result is mock_default

    def test_set_default_session_stores_in_both(self):
        """set_default_session() stores in both _default_session and _sessions."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()

        manager.set_default_session(mock_session, server_host="bpipe.com", port=8195)

        assert manager._default_session is mock_session
        assert manager._sessions["//bpipe.com:8195"] is mock_session

    def test_get_default_session_returns_none_when_stale(self):
        """get_default_session() returns None when session handle is invalid."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = None  # Stale
        manager._default_session = mock_session

        result = manager.get_default_session()

        assert result is None
        assert manager._default_session is None

    def test_remove_session_nonexistent_is_noop(self):
        """remove_session() for non-existent key should not raise error."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        # Should not raise any exception
        manager.remove_session(port=9999, server_host="nonexistent.host")

        # Still empty
        assert len(manager._sessions) == 0


class TestPublicFunctions:
    """Test public module functions: bbg_session, bbg_service, send_request, etc."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_bbg_session_with_existing_sess_kwarg(self):
        """bbg_session with sess=existing_session returns it directly."""
        from xbbg.core.infra.conn import SessionManager, bbg_session

        manager = SessionManager()

        # Create a mock that passes isinstance check for blpapi.Session
        mock_session = MagicMock(spec=blpapi.Session)

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = bbg_session(sess=mock_session)

        mock_connect.assert_not_called()
        assert result is mock_session

    def test_disconnect_calls_clear_default(self):
        """disconnect() must call clear_default_session()."""
        from xbbg.core.infra.conn import SessionManager, disconnect

        manager = SessionManager()

        mock_session = MagicMock()
        manager._default_session = mock_session
        manager._sessions["//localhost:8194"] = mock_session

        with patch.object(manager, "clear_default_session", wraps=manager.clear_default_session) as mock_clear:
            disconnect()

        mock_clear.assert_called_once()


class TestServiceManagement:
    """Test service creation and caching."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_get_service_creates_and_caches(self):
        """get_service() calls openService/getService and caches result."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"
        mock_service = MagicMock()
        mock_service._Service__handle = "valid_service_handle"
        mock_session.getService.return_value = mock_service

        manager._sessions["//localhost:8194"] = mock_session

        result = manager.get_service("//blp/refdata", port=8194, server_host="localhost")

        mock_session.openService.assert_called_once_with("//blp/refdata")
        mock_session.getService.assert_called_once_with("//blp/refdata")
        assert result is mock_service
        assert "//localhost:8194//blp/refdata" in manager._services

    def test_get_service_returns_cached(self):
        """get_service() returns cached service without calling openService again."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session._Session__handle = "valid_handle"
        manager._sessions["//localhost:8194"] = mock_session

        mock_service = MagicMock()
        mock_service._Service__handle = "valid_service_handle"
        manager._services["//localhost:8194//blp/refdata"] = mock_service

        result = manager.get_service("//blp/refdata", port=8194, server_host="localhost")

        mock_session.openService.assert_not_called()
        assert result is mock_service
