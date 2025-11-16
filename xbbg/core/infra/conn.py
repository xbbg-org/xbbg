"""Connection helpers for Bloomberg blpapi sessions and services.

Provides utilities to create and reuse `blpapi.Session` objects, open
services, and send requests with sensible defaults.
"""

import os
from pathlib import Path
import sys

try:
    ver = sys.version_info
    if f'{ver.major}.{ver.minor}' == '3.8':
        dll_path = os.environ.get('BBG_DLL', 'C:/blp/DAPI')
        if Path(dll_path).exists():
            with os.add_dll_directory(dll_path):
                import blpapi  # type: ignore[reportMissingImports]
        else:
            raise ImportError(
                'Please add BBG_DLL to your PATH variable'
            )
    else:
        import blpapi  # type: ignore[reportMissingImports]
except (ImportError, AttributeError):
    import pytest  # type: ignore[reportMissingImports]
    blpapi = pytest.importorskip('blpapi')

import logging

logger = logging.getLogger(__name__)

_CON_SYM_ = '_xcon_'
_PORT_ = 8194


def connect(max_attempt=3, auto_restart=True, **kwargs) -> blpapi.Session:
    """Connect to Bloomberg using alternative auth options.

    If a session object is passed via ``sess``, ``max_attempt`` and
    ``auto_restart`` are ignored.

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
    """
    if isinstance(kwargs.get('sess'), blpapi.Session):
        return bbg_session(sess=kwargs['sess'])

    sess_opts = blpapi.SessionOptions()
    sess_opts.setNumStartAttempts(numStartAttempts=max_attempt)
    sess_opts.setAutoRestartOnDisconnection(autoRestart=auto_restart)

    if isinstance(kwargs.get('auth_method'), str):
        auth_method = kwargs['auth_method']
        auth = None

        if auth_method == 'user':
            user = blpapi.AuthUser.createWithLogonName()
            auth = blpapi.AuthOptions.createWithUser(user=user)
        elif auth_method == 'app':
            auth = blpapi.AuthOptions.createWithApp(appName=kwargs['app_name'])
        elif auth_method == 'userapp':
            user = blpapi.AuthUser.createWithLogonName()
            auth = blpapi.AuthOptions.createWithUserAndApp(user=user, appName=kwargs['app_name'])
        elif auth_method == 'dir':
            user = blpapi.AuthUser.createWithActiveDirectoryProperty(propertyName=kwargs['dir_property'])
            auth = blpapi.AuthOptions.createWithUser(user=user)
        elif auth_method == 'manual':
            user = blpapi.AuthUser.createWithManualOptions(userId=kwargs['user_id'], ipAddress=kwargs['ip_address'])
            auth = blpapi.AuthOptions.createWithUserAndApp(user=user, appName=kwargs['app_name'])
        else:
            raise ValueError(
                'Received invalid value for auth_method. '
                'auth_method must be one of followings: user, app, userapp, dir, manual'
            )

        sess_opts.setSessionIdentityOptions(authOptions=auth)

    if isinstance(kwargs.get('server_host'), str):
        sess_opts.setServerHost(serverHost=kwargs['server_host'])

    if isinstance(kwargs.get('server_port'), int):
        sess_opts.setServerPort(serverPort=kwargs['server_port'])

    if isinstance(kwargs.get('tls_options'), blpapi.TlsOptions):
        sess_opts.setTlsOptions(tlsOptions=kwargs['tls_options'])

    return bbg_session(sess=blpapi.Session(sess_opts))


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
        if blpapi_logging and not hasattr(connect_bbg, '_blpapi_logging_registered'):
            blpapi_logging.register_blpapi_logging_callback()
            connect_bbg._blpapi_logging_registered = True  # type: ignore[attr-defined]
    except ImportError:
        pass

    if isinstance(kwargs.get('sess'), blpapi.Session):
        session = kwargs['sess']
        logger.debug('Reusing existing Bloomberg session: %s', session)
    else:
        sess_opts = blpapi.SessionOptions()
        server_host = kwargs.get('server') or kwargs.get('server_host', 'localhost')
        sess_opts.setServerHost(server_host)
        sess_opts.setServerPort(kwargs.get('port', _PORT_))
        session = blpapi.Session(sess_opts)

    server_host = kwargs.get('server') or kwargs.get('server_host', 'localhost')
    port = kwargs.get('port', _PORT_)
    logger.debug('Establishing connection to Bloomberg Terminal (%s:%d)', server_host, port)
    if session.start():
        logger.debug('Successfully connected to Bloomberg Terminal')
        return session
    logger.error('Failed to start Bloomberg session - check Terminal is running and %s:%d is accessible', server_host, port)
    raise ConnectionError('Cannot connect to Bloomberg')


def bbg_session(**kwargs) -> blpapi.Session:
    """Bloomberg session - initiate if not given.

    Args:
        **kwargs:
            port: port number (default 8194)
            server: server hostname or IP address (default 'localhost')
            server_host: alternative name for server parameter
            restart: whether to restart session

    Returns:
        Bloomberg session instance
    """
    port = kwargs.get('port', _PORT_)
    con_sym = f'{_CON_SYM_}//{port}'

    if (con_sym in globals()) and (getattr(globals()[con_sym], '_Session__handle', None) is None):
        del globals()[con_sym]

    if con_sym not in globals():
        globals()[con_sym] = connect_bbg(**kwargs)

    return globals()[con_sym]


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
    logger = logging.getLogger(__name__)

    port = kwargs.get('port', _PORT_)
    serv_sym = f'{_CON_SYM_}/{port}{service}'

    # Use parameterized strings (avoid f-string overhead when logging disabled)
    log_info = 'Initiating service %s ...' % service
    if (serv_sym in globals()) and (getattr(globals()[serv_sym], '_Service__handle', None) is None):
        log_info = 'Restarting service %s ...' % service
        del globals()[serv_sym]

    if serv_sym not in globals():
        logger.debug('Bloomberg service operation: %s', log_info)
        bbg_session(**kwargs).openService(service)
        globals()[serv_sym] = bbg_session(**kwargs).getService(service)

    return globals()[serv_sym]


def event_types() -> dict:
    """Bloomberg event types."""
    return {
        getattr(blpapi.Event, ev_typ): ev_typ
        for ev_typ in dir(blpapi.Event) if ev_typ.isupper()
    }


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
    event_queue = kwargs.get('event_queue') or blpapi.EventQueue()
    correlation_id = kwargs.get('correlation_id') or blpapi.CorrelationId()

    sess = bbg_session(**kwargs)
    try:
        # Only log request details if DEBUG enabled (avoid overhead)
        if logger.isEnabledFor(logging.DEBUG):
            # Service name is passed explicitly since Request objects don't have service() method
            service_name = kwargs.get('service')
            if service_name:
                logger.debug('Sending Bloomberg API request (service: %s)', service_name)
            else:
                logger.debug('Sending Bloomberg API request')
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('Bloomberg API request sent successfully')
    except blpapi.InvalidStateException as e:
        # Log exception with stack trace (important error, rare)
        logger.exception('Error sending Bloomberg request: %s', e)

        # Delete existing connection and send again
        port = kwargs.get('port', _PORT_)
        con_sym = f'{_CON_SYM_}//{port}'
        if con_sym in globals(): del globals()[con_sym]

        sess = bbg_session(**kwargs)
        sess.sendRequest(request=request, eventQueue=event_queue, correlationId=correlation_id)

    return {"event_queue": event_queue, "correlation_id": correlation_id}
