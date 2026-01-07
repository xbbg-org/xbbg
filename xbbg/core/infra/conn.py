"""Connection helpers for Bloomberg blpapi sessions and services.

Provides utilities to create and reuse `blpapi.Session` objects, open
services, and send requests with sensible defaults.
"""

import logging
from threading import Lock
from typing import Any

from xbbg.core.infra.blpapi_wrapper import blpapi

logger = logging.getLogger(__name__)

_PORT_ = 8194


class SessionManager:
    """Manages Bloomberg sessions and services (Singleton pattern).

    Thread-safe manager for Bloomberg API sessions and services.
    Replaces the previous globals()-based approach for better testability.

    Supports a "default session" that can be set via ``connect()`` and will
    be used for all subsequent API calls unless explicitly overridden.
    """

    _instance: Any = None
    _lock = Lock()

    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: dict[str, blpapi.Session] = {}
                    cls._instance._services: dict[str, blpapi.Service] = {}
                    cls._instance._default_session: blpapi.Session | None = None
        return cls._instance

    def set_default_session(self, session: blpapi.Session, server_host: str = "localhost", port: int = _PORT_) -> None:
        """Set the default session for all subsequent API calls.

        Args:
            session: Bloomberg session to use as default.
            server_host: Server hostname (for cache key).
            port: Port number (for cache key).
        """
        self._default_session = session
        # Also store in cache for consistency
        con_key = f"//{server_host}:{port}"
        self._sessions[con_key] = session

    def get_default_session(self) -> blpapi.Session | None:
        """Get the default session if set and valid.

        Returns:
            Default session or None if not set/invalid.
        """
        # Check if session exists and handle is still valid
        if self._default_session is not None and getattr(self._default_session, "_Session__handle", None) is None:
            self._default_session = None
        return self._default_session

    def clear_default_session(self) -> None:
        """Clear the default session."""
        self._default_session = None

    def get_session(self, port: int = _PORT_, **kwargs) -> blpapi.Session:
        """Get or create a Bloomberg session.

        Session lookup priority:
        1. If no server_host specified, use default session (if set)
        2. Look up by server_host:port in cache
        3. Create new session

        Args:
            port: Port number (default 8194).
            **kwargs: Additional session options including:
                - server_host: Server hostname
                - server: Alternative name for server_host

        Returns:
            Bloomberg session instance.
        """
        server_host = kwargs.get("server_host") or kwargs.get("server", "")

        # If no specific server requested, try default session first
        if not server_host:
            default_sess = self.get_default_session()
            if default_sess is not None:
                return default_sess
            # Fall back to localhost
            server_host = "localhost"

        con_key = f"//{server_host}:{port}"

        # Check if session exists and is valid
        if con_key in self._sessions:
            session = self._sessions[con_key]
            # Check if session handle is still valid
            if getattr(session, "_Session__handle", None) is None:
                del self._sessions[con_key]
            else:
                return session

        # Create new session
        self._sessions[con_key] = connect_bbg(port=port, server_host=server_host, **kwargs)
        return self._sessions[con_key]

    def remove_session(self, port: int = _PORT_, server_host: str = "localhost") -> None:
        """Remove a session from the manager.

        Args:
            port: Port number (default 8194).
            server_host: Server hostname (default 'localhost').
        """
        con_key = f"//{server_host}:{port}"
        if con_key in self._sessions:
            del self._sessions[con_key]

    def get_service(self, service: str, port: int = _PORT_, **kwargs) -> blpapi.Service:
        """Get or create a Bloomberg service.

        Args:
            service: Service name (e.g., '//blp/refdata').
            port: Port number (default 8194).
            **kwargs: Additional session options.

        Returns:
            Bloomberg service instance.
        """
        server_host = kwargs.get("server_host") or kwargs.get("server", "localhost")
        serv_key = f"//{server_host}:{port}{service}"

        # Check if service exists and is valid
        if serv_key in self._services:
            svc = self._services[serv_key]
            # Check if service handle is still valid
            if getattr(svc, "_Service__handle", None) is None:
                del self._services[serv_key]
            else:
                return svc

        # Create new service
        session = self.get_session(port=port, **kwargs)
        session.openService(service)
        self._services[serv_key] = session.getService(service)
        return self._services[serv_key]


# Global singleton instance
_session_manager = SessionManager()


def connect(max_attempt=3, auto_restart=True, **kwargs) -> blpapi.Session:
    """Connect to Bloomberg using alternative auth options.

    If a session object is passed via ``sess``, ``max_attempt`` and
    ``auto_restart`` are ignored.

    The session created by this function is stored as the default session,
    so all subsequent API calls (bdp, bdh, etc.) will use it automatically.

    Args:
        max_attempt: Number of start attempts for the session.
        auto_restart: Whether to auto-restart on disconnection.
        **kwargs: Optional connection and authentication settings:
            - sess: Existing ``blpapi.Session`` to reuse.
            - auth_method: One of {'user', 'app', 'userapp', 'dir', 'manual'}.
            - app_name: Application name for app/userapp/manual auth.
            - dir_property: Active Directory property for ``dir`` auth.
            - user_id: User ID for ``manual`` auth.
            - ip_address: IP address for ``manual`` auth.
            - server_host: Server hostname.
            - server_port: Server port.
            - tls_options: ``blpapi.TlsOptions`` instance for TLS.

    Returns:
        blpapi.Session: A started Bloomberg session.

    Example::

        # Connect to B-Pipe server
        blp.connect(
            auth_method="app",
            server_host="bpipe-server.example.com",
            server_port=8195,
            app_name="myapp",
        )
        # All subsequent calls use the B-Pipe connection
        px = blp.bdp("SPX Index", "PX_LAST")
    """
    server_host = kwargs.get("server_host", "localhost")
    server_port = kwargs.get("server_port", _PORT_)

    if isinstance(kwargs.get("sess"), blpapi.Session):
        session = kwargs["sess"]
        # Start session if not already started
        if not session.start():
            raise ConnectionError("Cannot start provided Bloomberg session")
        # Store as default session
        _session_manager.set_default_session(session, server_host=server_host, port=server_port)
        return session

    sess_opts = blpapi.SessionOptions()
    sess_opts.setNumStartAttempts(numStartAttempts=max_attempt)
    sess_opts.setAutoRestartOnDisconnection(autoRestart=auto_restart)

    if isinstance(kwargs.get("auth_method"), str):
        auth_method = kwargs["auth_method"]
        auth = None

        if auth_method == "user":
            user = blpapi.AuthUser.createWithLogonName()
            auth = blpapi.AuthOptions.createWithUser(user=user)
        elif auth_method == "app":
            auth = blpapi.AuthOptions.createWithApp(appName=kwargs["app_name"])
        elif auth_method == "userapp":
            user = blpapi.AuthUser.createWithLogonName()
            auth = blpapi.AuthOptions.createWithUserAndApp(user=user, appName=kwargs["app_name"])
        elif auth_method == "dir":
            user = blpapi.AuthUser.createWithActiveDirectoryProperty(propertyName=kwargs["dir_property"])
            auth = blpapi.AuthOptions.createWithUser(user=user)
        elif auth_method == "manual":
            user = blpapi.AuthUser.createWithManualOptions(userId=kwargs["user_id"], ipAddress=kwargs["ip_address"])
            auth = blpapi.AuthOptions.createWithUserAndApp(user=user, appName=kwargs["app_name"])
        else:
            raise ValueError(
                "Received invalid value for auth_method. "
                "auth_method must be one of followings: user, app, userapp, dir, manual"
            )

        sess_opts.setSessionIdentityOptions(authOptions=auth)

    if isinstance(server_host, str) and server_host != "localhost":
        sess_opts.setServerHost(serverHost=server_host)

    if isinstance(server_port, int) and server_port != _PORT_:
        sess_opts.setServerPort(serverPort=server_port)

    if isinstance(kwargs.get("tls_options"), blpapi.TlsOptions):
        sess_opts.setTlsOptions(tlsOptions=kwargs["tls_options"])

    # Create and start the session
    session = blpapi.Session(sess_opts)
    if not session.start():
        raise ConnectionError(f"Cannot connect to Bloomberg at {server_host}:{server_port}")

    # Store as default session for all subsequent API calls
    _session_manager.set_default_session(session, server_host=server_host, port=server_port)
    logger.debug("Set default Bloomberg session: %s:%d", server_host, server_port)

    return session


def disconnect() -> None:
    """Clear the default Bloomberg session.

    Call this to reset the connection state, allowing subsequent API calls
    to create a new connection (either to localhost or via a new ``connect()`` call).

    Example::

        blp.connect(server_host="bpipe-server", server_port=8195, ...)
        px = blp.bdp("SPX Index", "PX_LAST")  # Uses B-Pipe
        blp.disconnect()
        px = blp.bdp("SPX Index", "PX_LAST")  # Creates new localhost connection
    """
    _session_manager.clear_default_session()
    logger.debug("Cleared default Bloomberg session")


def connect_bbg(**kwargs) -> blpapi.Session:
    """Create and connect a Bloomberg session.

    Args:
        **kwargs:
            port: port number (default 8194)
            server: server hostname or IP address (default 'localhost')
            server_host: alternative name for server parameter
            sess: existing blpapi.Session to reuse
    """
    logger = logging.getLogger(__name__)

    # Register blpapi logging callback if not already registered (only once)
    try:
        from xbbg.core.infra import blpapi_logging

        if blpapi_logging and not hasattr(connect_bbg, "_blpapi_logging_registered"):
            blpapi_logging.register_blpapi_logging_callback()
            connect_bbg._blpapi_logging_registered = True  # type: ignore[attr-defined]
    except ImportError:
        pass

    if isinstance(kwargs.get("sess"), blpapi.Session):
        session = kwargs["sess"]
        logger.debug("Reusing existing Bloomberg session: %s", session)
    else:
        sess_opts = blpapi.SessionOptions()
        server_host = kwargs.get("server") or kwargs.get("server_host", "localhost")
        sess_opts.setServerHost(server_host)
        sess_opts.setServerPort(kwargs.get("port", _PORT_))
        session = blpapi.Session(sess_opts)

    server_host = kwargs.get("server") or kwargs.get("server_host", "localhost")
    port = kwargs.get("port", _PORT_)
    logger.debug("Establishing connection to Bloomberg Terminal (%s:%d)", server_host, port)
    if session.start():
        logger.debug("Successfully connected to Bloomberg Terminal")
        return session
    logger.error(
        "Failed to start Bloomberg session - check Terminal is running and %s:%d is accessible", server_host, port
    )
    raise ConnectionError("Cannot connect to Bloomberg")


def bbg_session(**kwargs) -> blpapi.Session:
    """Bloomberg session - initiate if not given.

    Args:
        **kwargs:
            port: port number (default 8194)
            server: server hostname or IP address (default 'localhost')
            server_host: alternative name for server parameter
            restart: whether to restart session
            sess: existing blpapi.Session to reuse

    Returns:
        Bloomberg session instance
    """
    # If an existing session is provided, return it directly
    if isinstance(kwargs.get("sess"), blpapi.Session):
        return kwargs["sess"]

    port = kwargs.get("port", _PORT_)
    return _session_manager.get_session(port=port, **kwargs)


def bbg_service(service: str, **kwargs) -> blpapi.Service:
    """Initiate service.

    Args:
        service: service name
        **kwargs:
            port: port number
            server: server hostname or IP address (default 'localhost')
            server_host: alternative name for server parameter

    Returns:
        Bloomberg service
    """
    port = kwargs.get("port", _PORT_)
    return _session_manager.get_service(service=service, port=port, **kwargs)


def event_types() -> dict:
    """Bloomberg event types."""
    return {getattr(blpapi.Event, ev_typ): ev_typ for ev_typ in dir(blpapi.Event) if ev_typ.isupper()}


def send_request(request: blpapi.Request, **kwargs):
    """Send a request via the Bloomberg session.

    Args:
        request: Bloomberg request to send.
        service: Optional service name for logging purposes (e.g., '//blp/refdata').
        event_queue: Optional ``blpapi.EventQueue`` to receive events. Created if not provided.
        correlation_id: Optional ``blpapi.CorrelationId`` for the request. Created if not provided.
        **kwargs: Additional options forwarded to session retrieval (for example, ``port``).

    Returns:
        dict: A mapping with ``event_queue`` and ``correlation_id``.
    """
    logger = logging.getLogger(__name__)

    # Always use per-request EventQueue and CorrelationId by default
    event_queue = kwargs.get("event_queue") or blpapi.EventQueue()
    correlation_id = kwargs.get("correlation_id") or blpapi.CorrelationId()

    sess = bbg_session(**kwargs)
    try:
        # Only log request details if DEBUG enabled (avoid overhead)
        if logger.isEnabledFor(logging.DEBUG):
            # Service name is passed explicitly since Request objects don't have service() method
            service_name = kwargs.get("service")
            if service_name:
                logger.debug("Sending Bloomberg API request (service: %s)", service_name)
            else:
                logger.debug("Sending Bloomberg API request")
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Bloomberg API request sent successfully")
    except blpapi.InvalidStateException as e:
        # Log exception with stack trace (important error, rare)
        logger.exception("Error sending Bloomberg request: %s", e)

        # Remove invalid session and retry
        port = kwargs.get("port", _PORT_)
        _session_manager.remove_session(port=port)

        sess = bbg_session(**kwargs)
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)

    return {"event_queue": event_queue, "correlation_id": correlation_id}
