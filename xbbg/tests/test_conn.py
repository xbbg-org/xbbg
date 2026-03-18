"""Comprehensive unit tests for xbbg.core.infra.conn module.

Tests Bloomberg session/connection management including:
- SessionManager singleton and caching behavior
- bbg_session and bbg_service public functions
- connect_bbg connection handling
- arequest / request async I/O pipeline
- aget_session / aget_service async session management
- _run_sync sync-to-async bridge
- End-to-end connection flow tests
- Regression tests for bug fixes
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

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

        SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            # This should NOT raise TypeError: got multiple values for keyword argument 'port'
            result = bbg_session(port=8195)

        assert result is mock_session

    def test_bbg_service_with_port_kwarg_no_duplicate(self):
        """Bug 1b: bbg_service("//blp/refdata", port=8195) must NOT raise TypeError.

        Same issue as bbg_session - port must be popped, not just read.
        """
        from xbbg.core.infra.conn import SessionManager, bbg_service

        SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        mock_service = MagicMock()
        mock_service.isValid.return_value = True
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
        mock_stale_session.isValid.return_value = False  # Stale: handle is None

        con_key = "//localhost:8194"
        manager._sessions[con_key] = mock_stale_session

        mock_new_session = MagicMock()
        mock_new_session.isValid.return_value = True

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_new_session):
            manager.get_session(port=8194)

        mock_stale_session.stop.assert_called_once()

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
        mock_session.isValid.return_value = True

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
        mock_session.isValid.return_value = True
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
        mock_default.isValid.return_value = True
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
        mock_session.isValid.return_value = False  # Stale
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
    """Test public module functions: bbg_session, bbg_service, etc."""

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

        SessionManager()

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
        mock_session.isValid.return_value = True
        mock_service = MagicMock()
        mock_service.isValid.return_value = True
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
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        mock_service = MagicMock()
        mock_service.isValid.return_value = True
        manager._services["//localhost:8194//blp/refdata"] = mock_service

        result = manager.get_service("//blp/refdata", port=8194, server_host="localhost")

        mock_session.openService.assert_not_called()
        assert result is mock_service


class TestEdgeCasesFromIssues:
    """Edge case tests from GitHub issues #164, #154, #53 and general coverage gaps."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_connect_stores_session_as_default(self):
        """Issue #164: connect(sess=mock_session) stores session as default.

        Verifies that a user-provided session is stored as the default
        and subsequent bbg_session() calls return it.
        """
        from xbbg.core.infra.conn import _session_manager, bbg_session, connect

        # Create a mock that is an instance of the mock blpapi.Session
        mock_session = MagicMock(spec=blpapi.Session)
        mock_session.start.return_value = True
        mock_session.isValid.return_value = True

        result = connect(sess=mock_session)

        assert result is mock_session
        assert _session_manager._default_session is mock_session
        # Subsequent call should return the same session (via default session)
        assert bbg_session() is mock_session

    def test_connect_with_existing_session_reuses_it(self):
        """Issue #164: connect(sess=existing) reuses it without creating new session.

        Verifies that when an existing session is passed, no new session is created
        and the existing session's start() is called.
        """
        from xbbg.core.infra.conn import connect

        # Create a mock session that passes isinstance check
        mock_session = MagicMock(spec=blpapi.Session)
        mock_session.start.return_value = True

        # Patch only Session class constructor, not the whole module
        with patch("xbbg.core.infra.conn.blpapi.SessionOptions") as mock_opts_class:
            result = connect(sess=mock_session)

        # Should not create SessionOptions (no new session created)
        mock_opts_class.assert_not_called()
        # Should call start on the provided session
        mock_session.start.assert_called_once()
        assert result is mock_session

    def test_disconnect_resets_state(self):
        """Issue #164: disconnect() clears default session and removes from cache.

        Verifies that disconnect() properly resets all session state.
        """
        from xbbg.core.infra.conn import _session_manager, disconnect

        mock_session = MagicMock()
        _session_manager.set_default_session(mock_session, server_host="localhost", port=8194)

        # Verify setup
        assert _session_manager._default_session is mock_session
        assert "//localhost:8194" in _session_manager._sessions

        disconnect()

        # Verify cleanup
        assert _session_manager._default_session is None
        assert "//localhost:8194" not in _session_manager._sessions

    def test_connect_auth_method_user(self):
        """Issue #154: connect(auth_method='user') uses AuthUser.createWithLogonName.

        Verifies that user authentication is properly configured.
        """
        from xbbg.core.infra.conn import connect

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = True
        mock_user = MagicMock()
        mock_auth = MagicMock()

        mock_blpapi = MagicMock()
        mock_blpapi.SessionOptions.return_value = mock_opts
        mock_blpapi.Session.return_value = mock_session
        mock_blpapi.AuthUser.createWithLogonName.return_value = mock_user
        mock_blpapi.AuthOptions.createWithUser.return_value = mock_auth
        # Preserve real type for isinstance check (no sess passed, so Session type not used)
        mock_blpapi.Session = blpapi.Session
        mock_blpapi.TlsOptions = blpapi.TlsOptions

        # Use a callable that returns mock_session when blpapi.Session is instantiated
        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        mock_blpapi.Session = MockSessionClass

        with patch("xbbg.core.infra.conn.blpapi", mock_blpapi):
            connect(auth_method="user")

        mock_blpapi.AuthUser.createWithLogonName.assert_called_once()
        mock_blpapi.AuthOptions.createWithUser.assert_called_once_with(user=mock_user)
        mock_opts.setSessionIdentityOptions.assert_called_once_with(authOptions=mock_auth)

    def test_connect_auth_method_app(self):
        """Issue #154: connect(auth_method='app', app_name='myapp') uses createWithApp.

        Verifies that application authentication is properly configured.
        """
        from xbbg.core.infra.conn import connect

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = True
        mock_auth = MagicMock()

        mock_blpapi = MagicMock()
        mock_blpapi.SessionOptions.return_value = mock_opts
        mock_blpapi.AuthOptions.createWithApp.return_value = mock_auth
        mock_blpapi.TlsOptions = blpapi.TlsOptions

        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        mock_blpapi.Session = MockSessionClass

        with patch("xbbg.core.infra.conn.blpapi", mock_blpapi):
            connect(auth_method="app", app_name="myapp")

        mock_blpapi.AuthOptions.createWithApp.assert_called_once_with(appName="myapp")
        mock_opts.setSessionIdentityOptions.assert_called_once_with(authOptions=mock_auth)

    def test_connect_invalid_auth_method_raises(self):
        """Issue #154: connect(auth_method='invalid') raises ValueError.

        Verifies that invalid auth methods are rejected with a clear error message.
        """
        from xbbg.core.infra.conn import connect

        mock_opts = MagicMock()
        mock_blpapi = MagicMock()
        mock_blpapi.SessionOptions.return_value = mock_opts
        mock_blpapi.Session = blpapi.Session  # Real type for isinstance
        mock_blpapi.TlsOptions = blpapi.TlsOptions

        with (
            patch("xbbg.core.infra.conn.blpapi", mock_blpapi),
            pytest.raises(ValueError, match="auth_method must be one of"),
        ):
            connect(auth_method="invalid")

    def test_connect_bbg_custom_server_ip(self):
        """Issue #53: connect_bbg(server_host='192.168.1.100', port=18194) sets custom host/port.

        Verifies that custom server IP and port are properly configured.
        """
        from xbbg.core.infra.conn import connect_bbg

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = True

        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        mock_blpapi = MagicMock()
        mock_blpapi.Session = MockSessionClass
        mock_blpapi.SessionOptions.return_value = mock_opts

        with patch("xbbg.core.infra.conn.blpapi", mock_blpapi):
            connect_bbg(server_host="192.168.1.100", port=18194)

        mock_opts.setServerHost.assert_called_once_with("192.168.1.100")
        mock_opts.setServerPort.assert_called_once_with(18194)

    def test_get_service_stale_handle_recreates(self):
        """General: Stale service with isValid()=False triggers recreation.

        Verifies that a cached service with an invalid handle is recreated.
        """
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        # Create a stale service with handle=None
        mock_stale_service = MagicMock()
        mock_stale_service.isValid.return_value = False
        manager._services["//localhost:8194//blp/refdata"] = mock_stale_service

        # New service to be returned
        mock_new_service = MagicMock()
        mock_new_service.isValid.return_value = True
        mock_session.getService.return_value = mock_new_service

        result = manager.get_service("//blp/refdata", port=8194, server_host="localhost")

        # Should have called openService to recreate
        mock_session.openService.assert_called_once_with("//blp/refdata")
        assert result is mock_new_service

    def test_event_types_returns_dict(self):
        """General: event_types() returns a dict.

        Verifies that the event_types function returns the expected type.
        """
        from xbbg.core.infra.conn import event_types

        result = event_types()

        assert isinstance(result, dict)

    def test_connect_with_tls_options(self):
        """B-Pipe: connect(tls_options=mock_tls) calls setTlsOptions.

        Verifies that TLS options are properly configured for B-Pipe connections.
        """
        from xbbg.core.infra.conn import connect

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = True
        mock_tls = MagicMock(spec=blpapi.TlsOptions)

        mock_blpapi = MagicMock()
        mock_blpapi.SessionOptions.return_value = mock_opts
        mock_blpapi.TlsOptions = blpapi.TlsOptions  # Real type for isinstance check

        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        mock_blpapi.Session = MockSessionClass

        with patch("xbbg.core.infra.conn.blpapi", mock_blpapi):
            connect(tls_options=mock_tls)

        mock_opts.setTlsOptions.assert_called_once_with(tlsOptions=mock_tls)

    def test_connect_start_failure_raises_connection_error(self):
        """General: connect() raises ConnectionError when session.start() returns False.

        Verifies proper error handling when connection fails.
        """
        from xbbg.core.infra.conn import connect

        mock_opts = MagicMock()
        mock_session = MagicMock()
        mock_session.start.return_value = False

        mock_blpapi = MagicMock()
        mock_blpapi.SessionOptions.return_value = mock_opts
        mock_blpapi.Session = blpapi.Session  # Real type for isinstance
        mock_blpapi.TlsOptions = blpapi.TlsOptions

        class MockSessionClass(blpapi.Session):
            def __new__(cls, *args, **kwargs):
                return mock_session

        mock_blpapi.Session = MockSessionClass

        with (
            patch("xbbg.core.infra.conn.blpapi", mock_blpapi),
            pytest.raises(ConnectionError),
        ):
            connect()


class TestArequest:
    """Tests for arequest() -- the async foundation for all Bloomberg I/O."""

    def setup_method(self):
        """Reset SessionManager state before each test."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def _make_event(self, event_type, messages):
        """Create a mock Bloomberg event with given type and messages."""
        ev = MagicMock()
        ev.eventType.return_value = event_type
        ev.__iter__ = MagicMock(return_value=iter(messages))
        return ev

    def test_arequest_happy_path(self):
        """arequest sends request, polls events, returns processed results."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()

        # Simulate: first tryNextEvent returns None (polling), then RESPONSE
        msg = MagicMock()
        response_event = self._make_event(blpapi.Event.RESPONSE, [msg])

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.side_effect = [None, response_event]

        def process_func(msg, **kwargs):
            return [{"ticker": "SPX Index", "PX_LAST": 5000.0}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func, service="//blp/refdata"))

        assert results == [{"ticker": "SPX Index", "PX_LAST": 5000.0}]
        mock_session.sendRequest.assert_called_once()

    def test_arequest_partial_then_response(self):
        """arequest accumulates results across PARTIAL_RESPONSE and RESPONSE events."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()
        msg1 = MagicMock()
        msg2 = MagicMock()

        partial_event = self._make_event(blpapi.Event.PARTIAL_RESPONSE, [msg1])
        final_event = self._make_event(blpapi.Event.RESPONSE, [msg2])

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.side_effect = [partial_event, final_event]

        call_count = [0]

        def process_func(msg, **kwargs):
            call_count[0] += 1
            return [{"row": call_count[0]}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func))

        assert results == [{"row": 1}, {"row": 2}]

    def test_arequest_retries_on_invalid_state(self):
        """arequest removes stale session and retries on InvalidStateException."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        # blpapi exceptions expect (description, errorCode) in __str__
        exc = blpapi.InvalidStateException("Session not started", 0)

        # First sendRequest raises, second succeeds
        mock_session.sendRequest.side_effect = [exc, None]

        mock_request = MagicMock()
        msg = MagicMock()
        response_event = self._make_event(blpapi.Event.RESPONSE, [msg])

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.return_value = response_event

        def process_func(msg, **kwargs):
            return [{"retried": True}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_mgr.remove_session = MagicMock()
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.InvalidStateException = blpapi.InvalidStateException
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func))

        mock_mgr.remove_session.assert_called_once()
        assert results == [{"retried": True}]

    def test_arequest_skips_timeout_events(self):
        """arequest ignores TIMEOUT events and continues polling."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()
        msg = MagicMock()

        timeout_event = self._make_event(blpapi.Event.TIMEOUT, [])
        response_event = self._make_event(blpapi.Event.RESPONSE, [msg])

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.side_effect = [timeout_event, response_event]

        def process_func(msg, **kwargs):
            return [{"data": 42}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func))

        assert results == [{"data": 42}]

    def test_arequest_handles_session_terminated(self):
        """arequest returns partial results on SessionTerminated event."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()

        # Create a SessionTerminated message
        term_msg = MagicMock()
        term_msg.messageType.return_value = blpapi.Name("SessionTerminated")

        # Use an event type that's not RESPONSE/PARTIAL_RESPONSE/TIMEOUT
        # to hit the else branch
        terminated_event = MagicMock()
        terminated_event.eventType.return_value = 999  # Unknown event type
        terminated_event.__iter__ = MagicMock(return_value=iter([term_msg]))

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.return_value = terminated_event

        def process_func(msg, **kwargs):
            return []

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT
            mock_blpapi.Name = blpapi.Name

            results = asyncio.run(arequest(mock_request, process_func))

        assert results == []

    def test_arequest_slow_request_warning(self, caplog):
        """arequest logs a warning when response takes longer than slow_warn_seconds."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()
        msg = MagicMock()
        response_event = self._make_event(blpapi.Event.RESPONSE, [msg])

        call_count = [0]

        def mock_try_next():
            call_count[0] += 1
            if call_count[0] <= 2:
                return None  # Simulate polling
            return response_event

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.side_effect = mock_try_next

        def process_func(msg, **kwargs):
            return [{"result": True}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
            patch("time.time") as mock_time,
            caplog.at_level(logging.WARNING, logger="xbbg.core.infra.conn"),
        ):
            # Simulate time passing: start=0, then 0, then 20s (past slow_warn), then 20s
            mock_time.side_effect = [0.0, 0.0, 20.0, 20.0]
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func, slow_warn_seconds=15.0))

        assert results == [{"result": True}]
        assert any("taking" in r.message and "seconds" in r.message for r in caplog.records)


class TestRequestSync:
    """Tests for request() -- the synchronous wrapper around arequest()."""

    def setup_method(self):
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_request_calls_arequest_via_run_sync(self):
        """request() delegates to arequest() via _run_sync()."""
        from xbbg.core.infra.conn import request

        mock_request = MagicMock()

        def process_func(msg, **kwargs):
            return [{"sync": True}]

        # Patch arequest to return a real coroutine that yields the expected result
        async def fake_arequest(*args, **kwargs):
            return [{"sync": True}]

        with patch("xbbg.core.infra.conn.arequest", side_effect=fake_arequest):
            result = request(mock_request, process_func, service="//blp/refdata")

        assert result == [{"sync": True}]


class TestAgetSession:
    """Tests for aget_session / aget_service -- async session management."""

    def setup_method(self):
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_aget_session_creates_new(self):
        """aget_session() creates new session when cache is empty."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            result = asyncio.run(manager.aget_session(port=8194))

        assert result is mock_session
        assert "//localhost:8194" in manager._sessions

    def test_aget_session_returns_cached(self):
        """aget_session() returns cached session without creating a new one."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = asyncio.run(manager.aget_session(port=8194))

        mock_connect.assert_not_called()
        assert result is mock_session

    def test_aget_session_replaces_stale(self):
        """aget_session() replaces stale session (handle=None) with a new one."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_stale = MagicMock()
        mock_stale.isValid.return_value = False
        manager._sessions["//localhost:8194"] = mock_stale

        mock_new = MagicMock()
        mock_new.isValid.return_value = True

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_new):
            result = asyncio.run(manager.aget_session(port=8194))

        mock_stale.stop.assert_called_once()
        assert result is mock_new

    def test_aget_session_uses_default(self):
        """aget_session() returns default session when no server specified."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_default = MagicMock()
        mock_default.isValid.return_value = True
        manager._default_session = mock_default

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = asyncio.run(manager.aget_session(port=8194))

        mock_connect.assert_not_called()
        assert result is mock_default

    def test_aget_service_creates_and_caches(self):
        """aget_service() creates session, opens service, and caches it."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        mock_service = MagicMock()
        mock_service.isValid.return_value = True
        mock_session.getService.return_value = mock_service

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            result = asyncio.run(manager.aget_service("//blp/refdata", port=8194))

        mock_session.openService.assert_called_once_with("//blp/refdata")
        assert result is mock_service
        assert "//localhost:8194//blp/refdata" in manager._services

    def test_aget_service_returns_cached(self):
        """aget_service() returns cached service with valid handle."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        mock_service = MagicMock()
        mock_service.isValid.return_value = True
        manager._services["//localhost:8194//blp/refdata"] = mock_service

        result = asyncio.run(manager.aget_service("//blp/refdata", port=8194))

        mock_session.openService.assert_not_called()
        assert result is mock_service

    def test_aget_service_replaces_stale(self):
        """aget_service() recreates stale service (handle=None)."""
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        manager._sessions["//localhost:8194"] = mock_session

        mock_stale_svc = MagicMock()
        mock_stale_svc.isValid.return_value = False
        manager._services["//localhost:8194//blp/refdata"] = mock_stale_svc

        mock_new_svc = MagicMock()
        mock_new_svc.isValid.return_value = True
        mock_session.getService.return_value = mock_new_svc

        result = asyncio.run(manager.aget_service("//blp/refdata", port=8194))

        mock_session.openService.assert_called_once_with("//blp/refdata")
        assert result is mock_new_svc


class TestRunSync:
    """Tests for _run_sync() -- the sync-to-async bridge."""

    def test_run_sync_executes_coroutine(self):
        """_run_sync runs a coroutine and returns its result."""
        from xbbg.core.infra.conn import _run_sync

        async def coro():
            return 42

        assert _run_sync(coro()) == 42

    def test_run_sync_with_timeout(self):
        """_run_sync passes timeout to asyncio.wait_for."""
        from xbbg.core.infra.conn import _run_sync

        async def fast_coro():
            return "fast"

        assert _run_sync(fast_coro(), timeout=5.0) == "fast"

    def test_run_sync_timeout_raises(self):
        """_run_sync raises TimeoutError when coroutine exceeds timeout."""
        from xbbg.core.infra.conn import _run_sync

        async def slow_coro():
            await asyncio.sleep(10)
            return "never"

        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            _run_sync(slow_coro(), timeout=0.01)


class TestConnectionFlows:
    """End-to-end flow tests: connect -> use -> disconnect lifecycle."""

    def setup_method(self):
        from xbbg.core.infra.conn import SessionManager

        manager = SessionManager()
        manager._sessions.clear()
        manager._services.clear()
        manager._default_session = None

    def test_connect_then_bbg_session_uses_default(self):
        """After connect(), bbg_session() returns the same session without creating a new one."""
        from xbbg.core.infra.conn import bbg_session, connect

        mock_session = MagicMock(spec=blpapi.Session)
        mock_session.start.return_value = True
        mock_session.isValid.return_value = True

        session = connect(sess=mock_session)

        with patch("xbbg.core.infra.conn.connect_bbg") as mock_connect:
            result = bbg_session()

        mock_connect.assert_not_called()
        assert result is session

    def test_connect_disconnect_reconnect(self):
        """After disconnect(), a new bbg_session() call creates a fresh session."""
        from xbbg.core.infra.conn import _session_manager, bbg_session, connect, disconnect

        # Connect
        mock_session1 = MagicMock(spec=blpapi.Session)
        mock_session1.start.return_value = True
        mock_session1.isValid.return_value = True
        connect(sess=mock_session1)

        assert bbg_session() is mock_session1

        # Disconnect
        disconnect()
        assert _session_manager._default_session is None

        # Reconnect -- should create a new session
        mock_session2 = MagicMock()
        mock_session2.isValid.return_value = True

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session2):
            result = bbg_session()

        assert result is mock_session2
        assert result is not mock_session1

    def test_bbg_service_auto_creates_session(self):
        """bbg_service() creates a session automatically if none exists."""
        from xbbg.core.infra.conn import bbg_service

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        mock_service = MagicMock()
        mock_service.isValid.return_value = True
        mock_session.getService.return_value = mock_service

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session):
            result = bbg_service("//blp/refdata")

        mock_session.openService.assert_called_once_with("//blp/refdata")
        assert result is mock_service

    def test_multiple_services_share_session(self):
        """Multiple bbg_service() calls reuse the same underlying session."""
        from xbbg.core.infra.conn import _session_manager, bbg_service

        mock_session = MagicMock()
        mock_session.isValid.return_value = True
        mock_refdata = MagicMock()
        mock_refdata.isValid.return_value = True
        mock_mktbar = MagicMock()
        mock_mktbar.isValid.return_value = True

        mock_session.getService.side_effect = [mock_refdata, mock_mktbar]

        with patch("xbbg.core.infra.conn.connect_bbg", return_value=mock_session) as mock_connect:
            svc1 = bbg_service("//blp/refdata")
            svc2 = bbg_service("//blp/mktbar")

        # connect_bbg called only once (session reused)
        mock_connect.assert_called_once()
        assert svc1 is mock_refdata
        assert svc2 is mock_mktbar
        # Same session for both
        assert len(_session_manager._sessions) == 1

    def test_connect_with_bpipe_server_stores_correct_key(self):
        """connect() with server_host stores session under correct cache key."""
        from xbbg.core.infra.conn import _session_manager, connect

        mock_session = MagicMock(spec=blpapi.Session)
        mock_session.start.return_value = True
        mock_session.isValid.return_value = True

        connect(sess=mock_session, server_host="bpipe.corp.com", server_port=8195)

        assert "//bpipe.corp.com:8195" in _session_manager._sessions
        assert _session_manager._default_session is mock_session

    def test_arequest_full_flow_with_session_creation(self):
        """arequest() creates session, sends request, processes response end-to-end."""
        from xbbg.core.infra.conn import arequest

        mock_session = MagicMock()
        mock_session.isValid.return_value = True

        mock_request = MagicMock()
        msg = MagicMock()

        response_event = MagicMock()
        response_event.eventType.return_value = blpapi.Event.RESPONSE
        response_event.__iter__ = MagicMock(return_value=iter([msg]))

        mock_queue = MagicMock()
        mock_queue.tryNextEvent.return_value = response_event

        def process_func(msg, **kwargs):
            return [{"field": "PX_LAST", "value": 100.0}]

        with (
            patch("xbbg.core.infra.conn._session_manager") as mock_mgr,
            patch("xbbg.core.infra.conn.blpapi") as mock_blpapi,
        ):
            mock_mgr.aget_session = AsyncMock(return_value=mock_session)
            mock_blpapi.EventQueue.return_value = mock_queue
            mock_blpapi.CorrelationId.return_value = MagicMock()
            mock_blpapi.InvalidStateException = blpapi.InvalidStateException
            mock_blpapi.Event.PARTIAL_RESPONSE = blpapi.Event.PARTIAL_RESPONSE
            mock_blpapi.Event.RESPONSE = blpapi.Event.RESPONSE
            mock_blpapi.Event.TIMEOUT = blpapi.Event.TIMEOUT

            results = asyncio.run(arequest(mock_request, process_func))

        assert len(results) == 1
        assert results[0]["field"] == "PX_LAST"
        assert results[0]["value"] == 100.0
