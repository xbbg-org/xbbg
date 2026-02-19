"""Connection helpers for Bloomberg blpapi sessions and services.

Provides utilities to create and reuse `blpapi.Session` objects, open
services, and send requests with sensible defaults.
"""

from __future__ import annotations  # Required: defer annotation evaluation when blpapi unavailable

import asyncio
from collections.abc import Callable
import concurrent.futures
import functools
import logging
from threading import Lock
from typing import Any

from xbbg.core.infra.blpapi_wrapper import blpapi

logger = logging.getLogger(__name__)

_PORT_ = 8194
_blpapi_logging_registered = False


def _stop_session_quietly(session: Any) -> None:
    """Stop a Bloomberg session, suppressing any errors."""
    try:
        session.stop()
    except Exception:  # noqa: BLE001
        logger.debug("Error stopping Bloomberg session (ignored)", exc_info=True)


class SessionManager:
    """Manages Bloomberg sessions and services (Singleton pattern).

    Thread-safe manager for Bloomberg API sessions and services.
    Replaces the previous globals()-based approach for better testability.

    Supports a "default session" that can be set via ``connect()`` and will
    be used for all subsequent API calls unless explicitly overridden.
    """

    _instance: Any = None
    _lock = Lock()
    _sessions: dict[str, Any] = {}
    _services: dict[str, Any] = {}
    _default_session: Any | None = None
    _async_lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions = {}
                    cls._instance._services = {}
                    cls._instance._default_session = None
                    cls._instance._async_lock = asyncio.Lock()
        return cls._instance

    def set_default_session(self, session: Any, server_host: str = "localhost", port: int = _PORT_) -> None:
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

    def get_default_session(self) -> Any | None:
        """Get the default session if set and valid.

        Returns:
            Default session or None if not set/invalid.
        """
        # Check if session exists and handle is still valid
        if self._default_session is not None and getattr(self._default_session, "_Session__handle", None) is None:
            self._default_session = None
        return self._default_session

    def clear_default_session(self) -> None:
        """Clear the default session and stop it."""
        session = self._default_session
        self._default_session = None
        # Also remove from _sessions cache (set_default_session stores it in both)
        if session is not None:
            keys_to_remove = [k for k, v in self._sessions.items() if v is session]
            for k in keys_to_remove:
                del self._sessions[k]
            _stop_session_quietly(session)

    def get_session(self, port: int = _PORT_, **kwargs) -> Any:
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
                logger.info("Removing stale Bloomberg session (handle invalidated): %s", con_key)
                del self._sessions[con_key]
                _stop_session_quietly(session)
            else:
                return session

        # Create new session
        self._sessions[con_key] = connect_bbg(port=port, server_host=server_host, **kwargs)
        return self._sessions[con_key]

    def remove_session(self, port: int = _PORT_, server_host: str = "localhost") -> None:
        """Remove a session from the manager and stop it.

        Args:
            port: Port number (default 8194).
            server_host: Server hostname (default 'localhost').
        """
        con_key = f"//{server_host}:{port}"
        session = self._sessions.pop(con_key, None)
        if session is not None:
            logger.info("Removing Bloomberg session from manager: %s", con_key)
            # Also clear default if it's the same session object
            if self._default_session is session:
                self._default_session = None
            _stop_session_quietly(session)

    def get_service(self, service: str, port: int = _PORT_, **kwargs) -> Any:
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
                logger.info("Removing stale Bloomberg service (handle invalidated): %s", serv_key)
                del self._services[serv_key]
            else:
                return svc

        # Create new service
        session = self.get_session(port=port, **kwargs)
        logger.debug("Opening Bloomberg service: %s", service)
        session.openService(service)
        self._services[serv_key] = session.getService(service)
        logger.debug("Successfully opened Bloomberg service: %s", serv_key)
        return self._services[serv_key]

    async def aget_session(self, port: int = _PORT_, **kwargs) -> Any:
        """Get or create a Bloomberg session (async-safe).

        Wraps blocking session.start() in asyncio.to_thread().
        """
        server_host = kwargs.get("server_host") or kwargs.get("server", "")

        if not server_host:
            default_sess = self.get_default_session()
            if default_sess is not None:
                return default_sess
            server_host = "localhost"

        con_key = f"//{server_host}:{port}"

        async_lock = self._async_lock
        if async_lock is None:
            async_lock = asyncio.Lock()
            self._async_lock = async_lock

        async with async_lock:
            # Check again inside lock
            if con_key in self._sessions:
                session = self._sessions[con_key]
                if getattr(session, "_Session__handle", None) is None:
                    logger.info("Removing stale Bloomberg session (handle invalidated): %s", con_key)
                    del self._sessions[con_key]
                    _stop_session_quietly(session)
                else:
                    return session

            # Create new session - blocking start() runs in thread
            self._sessions[con_key] = await asyncio.to_thread(connect_bbg, port=port, server_host=server_host, **kwargs)
            return self._sessions[con_key]

    async def aget_service(self, service: str, port: int = _PORT_, **kwargs) -> Any:
        """Get or create a Bloomberg service (async-safe)."""
        server_host = kwargs.get("server_host") or kwargs.get("server", "localhost")
        serv_key = f"//{server_host}:{port}{service}"

        if serv_key in self._services:
            svc = self._services[serv_key]
            if getattr(svc, "_Service__handle", None) is not None:
                return svc
            logger.info("Removing stale Bloomberg service (handle invalidated): %s", serv_key)
            del self._services[serv_key]

        session = await self.aget_session(port=port, **kwargs)
        logger.debug("Opening Bloomberg service: %s", service)
        await asyncio.to_thread(session.openService, service)
        self._services[serv_key] = session.getService(service)
        logger.debug("Successfully opened Bloomberg service: %s", serv_key)
        return self._services[serv_key]


# Global singleton instance
_session_manager = SessionManager()


def connect(max_attempt=3, auto_restart=True, **kwargs) -> Any:
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


def connect_bbg(**kwargs) -> Any:
    """Create and connect a Bloomberg session.

    Args:
        **kwargs:
            port: port number (default 8194)
            server: server hostname or IP address (default 'localhost')
            server_host: alternative name for server parameter
            sess: existing blpapi.Session to reuse
    """
    logger = logging.getLogger(__name__)

    global _blpapi_logging_registered

    # Register blpapi logging callback if not already registered (only once)
    try:
        from xbbg.core.infra import blpapi_logging

        if blpapi_logging and not _blpapi_logging_registered:
            blpapi_logging.register_blpapi_logging_callback()
            _blpapi_logging_registered = True
    except ImportError:
        pass

    if isinstance(kwargs.get("sess"), blpapi.Session):
        session = kwargs["sess"]
        logger.debug("Reusing existing Bloomberg session: %s", session)
    else:
        sess_opts = blpapi.SessionOptions()
        server_host = kwargs.get("server_host") or kwargs.get("server", "localhost")
        sess_opts.setServerHost(server_host)
        sess_opts.setServerPort(kwargs.get("port", _PORT_))
        session = blpapi.Session(sess_opts)

    server_host = kwargs.get("server_host") or kwargs.get("server", "localhost")
    port = kwargs.get("port", _PORT_)
    logger.debug("Establishing connection to Bloomberg Terminal (%s:%d)", server_host, port)
    if session.start():
        logger.debug("Successfully connected to Bloomberg Terminal")
        return session
    # start() failed -- clean up the session before raising
    _stop_session_quietly(session)
    logger.error(
        "Failed to start Bloomberg session - check Terminal is running and %s:%d is accessible", server_host, port
    )
    raise ConnectionError("Cannot connect to Bloomberg")


def bbg_session(**kwargs) -> Any:
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

    port = kwargs.pop("port", _PORT_)
    return _session_manager.get_session(port=port, **kwargs)


def bbg_service(service: str, **kwargs) -> Any:
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
    port = kwargs.pop("port", _PORT_)
    return _session_manager.get_service(service=service, port=port, **kwargs)


def event_types() -> dict[Any, str]:
    """Bloomberg event types."""
    return {getattr(blpapi.Event, ev_typ): ev_typ for ev_typ in dir(blpapi.Event) if ev_typ.isupper()}


def _run_sync(coro, timeout=None):
    """Run an async coroutine synchronously.

    Handles both script context (no event loop) and Jupyter/async framework
    context (event loop already running).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        if timeout:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        return asyncio.run(coro)
    # Event loop already running (Jupyter, async framework)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        if timeout:
            return pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=timeout)).result(timeout=timeout)
        return pool.submit(asyncio.run, coro).result()


def sync_api(async_fn: Callable[..., Any]) -> Callable[..., Any]:
    """Create a sync wrapper from an async function.

    The sync function inherits the async function's signature, docstring,
    and type hints. The name has the leading 'a' stripped (abdp -> bdp).
    """

    @functools.wraps(async_fn)
    def wrapper(*args, **kwargs):
        return _run_sync(async_fn(*args, **kwargs))

    name = async_fn.__name__
    if name.startswith("a") and not name.startswith("async"):
        sync_name = name[1:]
        wrapper.__name__ = sync_name
        if "." in wrapper.__qualname__:
            wrapper.__qualname__ = wrapper.__qualname__.rsplit(".", 1)[0] + "." + sync_name
        else:
            wrapper.__qualname__ = sync_name

    return wrapper


async def arequest(
    request: Any,
    process_func: Callable[..., Any],
    service: str | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    """The async foundation for all Bloomberg I/O.

    Every Bloomberg request/response cycle in xbbg flows through this function.
    Sends a request with a per-request EventQueue and polls for events
    using non-blocking tryNextEvent() + await asyncio.sleep().

    Args:
        request: Bloomberg API request to send.
        process_func: Function to process response messages (e.g., process_ref, process_hist).
        service: Service name for logging.
        **kwargs: Additional options forwarded to session retrieval.

    Returns:
        List of dicts from processed response events.
    """
    import time

    event_queue = blpapi.EventQueue()
    correlation_id = blpapi.CorrelationId()

    # Get session (async-safe - wraps blocking start/openService in to_thread)
    sess = await _session_manager.aget_session(port=kwargs.get("port", _PORT_), **kwargs)

    try:
        if logger.isEnabledFor(logging.DEBUG):
            if service:
                logger.debug("Sending Bloomberg API request (service: %s)", service)
            else:
                logger.debug("Sending Bloomberg API request")
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)
    except blpapi.InvalidStateException as e:
        logger.exception("Error sending Bloomberg request: %s", e)
        # Remove invalid session and retry
        port = kwargs.get("port", _PORT_)
        server_host = kwargs.get("server_host") or kwargs.get("server", "localhost")
        _session_manager.remove_session(port=port, server_host=server_host)
        sess = await _session_manager.aget_session(port=kwargs.get("port", _PORT_), **kwargs)
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)

    # Async event polling
    responses = [blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE]
    slow_warn_seconds = kwargs.pop("slow_warn_seconds", 15.0)
    start_time = time.time()
    warned = False
    results = []

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Starting async Bloomberg event processing")

    while True:
        ev = event_queue.tryNextEvent()
        if ev is None:
            await asyncio.sleep(0.001)  # 1ms polling interval
            # Check for slow request warning
            elapsed = time.time() - start_time
            if not warned and elapsed > slow_warn_seconds:
                logger.warning(
                    "Bloomberg request taking %.1f seconds (still waiting for response)...",
                    elapsed,
                )
                warned = True
            continue

        if ev.eventType() in responses:
            for msg in ev:
                results.extend(process_func(msg=msg, **kwargs))
            if ev.eventType() == blpapi.Event.RESPONSE:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Received final RESPONSE event")
                break
        elif ev.eventType() == blpapi.Event.TIMEOUT:
            continue
        else:
            # SESSION_TERMINATED or other events
            for msg in ev:
                if getattr(msg, "messageType", lambda: None)() == blpapi.Name("SessionTerminated"):
                    logger.warning("Session terminated during async event processing")
                    return results

    return results


def request(
    request: Any,
    process_func: Callable[..., Any],
    service: str | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    """Synchronous Bloomberg request. Wraps arequest().

    Args:
        request: Bloomberg API request to send.
        process_func: Function to process response messages.
        service: Service name for logging.
        **kwargs: Additional options.

    Returns:
        List of dicts from processed response events.
    """
    return _run_sync(arequest(request, process_func, service=service, **kwargs))
