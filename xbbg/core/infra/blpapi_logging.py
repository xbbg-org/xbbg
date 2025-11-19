"""Bloomberg API (blpapi) logging integration.

This module provides integration with blpapi's internal logging system
and adds structured logging for Bloomberg events and messages.
"""

from collections.abc import Callable
from contextlib import suppress
import logging

from xbbg.core.infra.blpapi_wrapper import blpapi, is_available

logger = logging.getLogger(__name__)

# Map blpapi severity levels to Python logging levels
_BLPAPI_TO_PYTHON_LOG_LEVEL = {}
if is_available():
    _BLPAPI_TO_PYTHON_LOG_LEVEL = {
        blpapi.Logger.SEVERITY_OFF: logging.NOTSET,
        blpapi.Logger.SEVERITY_FATAL: logging.CRITICAL,
        blpapi.Logger.SEVERITY_ERROR: logging.ERROR,
        blpapi.Logger.SEVERITY_WARN: logging.WARNING,
        blpapi.Logger.SEVERITY_INFO: logging.INFO,
        blpapi.Logger.SEVERITY_DEBUG: logging.DEBUG,
        blpapi.Logger.SEVERITY_TRACE: logging.DEBUG,
    }


def register_blpapi_logging_callback(
    threshold_severity: int | None = None,
    use_python_logger: bool = True,
) -> Callable | None:
    """Register a callback to receive blpapi's internal log messages.

    This integrates blpapi's native logging with Python's logging system.
    Must be called before creating any Bloomberg sessions.

    Args:
        threshold_severity: Minimum blpapi severity level to log.
            Defaults to SEVERITY_INFO. Use blpapi.Logger.SEVERITY_* constants.
        use_python_logger: If True, routes blpapi logs to Python's logging system.
            If False, returns the callback function without registering it.

    Returns:
        The registered callback function, or None if blpapi is not available.

    Examples:
        >>> from xbbg.core.infra import blpapi_logging
        >>> # Register before creating sessions
        >>> cb = blpapi_logging.register_blpapi_logging_callback()
        >>> # Returns callback function or None if blpapi not available
        >>> cb is None or callable(cb)
        True
    """
    if not is_available():
        logger.warning('blpapi not available; cannot register logging callback')
        return None

    if threshold_severity is None:
        # Default to WARNING to keep logging quiet by default
        # Users can lower this if they want more verbose blpapi logs
        threshold_severity = blpapi.Logger.SEVERITY_WARN

    def blpapi_log_callback(
        thread_id: int,
        severity: int,
        timestamp,
        category: str,
        message: str,
    ) -> None:
        """Callback function that receives blpapi log messages."""
        if not use_python_logger:
            return

        # Map blpapi severity to Python logging level
        python_level = _BLPAPI_TO_PYTHON_LOG_LEVEL.get(
            severity, logging.INFO
        )

        # Create a logger with the blpapi category as the name
        # Use parameterized string formatting for performance
        blpapi_logger = logging.getLogger('blpapi.%s' % category)

        # Only log if the level is enabled (avoid overhead)
        if blpapi_logger.isEnabledFor(python_level):
            blpapi_logger.log(
                python_level,
                '[thread=%d] %s',
                thread_id,
                message,
            )

    try:
        blpapi.Logger.registerCallback(
            blpapi_log_callback,
            thresholdSeverity=threshold_severity,
        )
        logger.debug(
            'Registered blpapi logging callback (threshold severity: %d)',
            threshold_severity,
        )
        return blpapi_log_callback
    except Exception as e:
        logger.warning('Failed to register blpapi logging callback: %s', e)
        return None


def log_event_info(event, context: str = '') -> None:
    """Log information about a Bloomberg event.

    Performance-optimized: expensive operations are guarded by isEnabledFor checks.

    Args:
        event: blpapi.Event object.
        context: Optional context string (e.g., function name, operation).
    """
    if not is_available():
        return

    # Early return if DEBUG logging is disabled
    if not logger.isEnabledFor(logging.DEBUG):
        return

    try:
        event_type = event.eventType()
        event_type_name = _get_event_type_name(event_type)

        # Do NOT iterate the event here – that would consume messages and break callers.
        # Just log the event type and optional context.
        if context:
            logger.debug(
                'Bloomberg event received: type=%s (%d) [%s]',
                event_type_name,
                event_type,
                context,
            )
        else:
            logger.debug(
                'Bloomberg event received: type=%s (%d)',
                event_type_name,
                event_type,
            )

        # Log additional details only for important event types (avoid redundant logs)
        if event_type == blpapi.Event.RESPONSE:
            logger.debug('Response event received (final)')
        elif event_type == blpapi.Event.SESSION_STATUS:
            logger.info('Bloomberg session status event received')
        elif event_type == blpapi.Event.SUBSCRIPTION_STATUS:
            logger.debug('Subscription status event received')

    except Exception:  # noqa: BLE001
        # Don't log exceptions here - avoid recursive logging issues.
        # Silently ignore exceptions in logging code to prevent recursion.
        # Returning early avoids the "try/except/pass" pattern flagged by some linters
        # while keeping the same behavior.
        return


# Separate logger for verbose message-level logging (opt-in)
_message_logger = logging.getLogger(__name__ + '.messages')


def log_message_info(msg, context: str = '') -> None:
    """Log information about a Bloomberg message.

    Performance-optimized: uses opt-in logger for per-message details.
    Error messages are always logged (they're important and rare).

    Args:
        msg: blpapi.Message object.
        context: Optional context string (e.g., function name, operation).
    """
    if not is_available():
        return

    # Always check for errors (important, rare, should be logged)
    with suppress(Exception):  # noqa: BLE001
        if msg.hasElement('responseError'):
            error_elem = msg.getElement('responseError')
            if error_elem.hasElement('category'):
                category = error_elem.getElementAsString('category')
                message = error_elem.getElementAsString('message') if error_elem.hasElement('message') else ''
                logger.warning(
                    'Bloomberg API error: category=%s, message=%s',
                    category,
                    message,
                )

    # Per-message details only if verbose logging is enabled (opt-in)
    if not _message_logger.isEnabledFor(logging.DEBUG):
        return

    try:
        msg_type = str(msg.messageType())
        topic = None
        correlation_ids = None

        # Only do expensive operations if verbose logging is enabled
        if hasattr(msg, 'topicName'):
            with suppress(Exception):
                topic = msg.topicName()

        if hasattr(msg, 'correlationIds'):
            with suppress(Exception):
                cids = msg.correlationIds()
                if cids:
                    # Only build list if we're actually logging
                    correlation_ids = [str(cid.value()) for cid in cids]

        # Use parameterized logging
        if topic and correlation_ids:
            _message_logger.debug(
                'Bloomberg message: type=%s, topic=%s, correlation_ids=%s%s',
                msg_type,
                topic,
                correlation_ids,
                ' [%s]' % context if context else '',
            )
        elif topic:
            _message_logger.debug(
                'Bloomberg message: type=%s, topic=%s%s',
                msg_type,
                topic,
                ' [%s]' % context if context else '',
            )
        elif correlation_ids:
            _message_logger.debug(
                'Bloomberg message: type=%s, correlation_ids=%s%s',
                msg_type,
                correlation_ids,
                ' [%s]' % context if context else '',
            )
        else:
            _message_logger.debug(
                'Bloomberg message: type=%s%s',
                msg_type,
                ' [%s]' % context if context else '',
            )

    except Exception:  # noqa: BLE001
        # Don't log exceptions here - avoid recursive logging issues
        # Silently ignore exceptions in logging code to prevent recursion
        pass  # noqa: S110


def _get_event_type_name(event_type: int) -> str:
    """Get human-readable name for event type."""
    if not is_available():
        return f'UNKNOWN({event_type})'

    event_type_map = {
        blpapi.Event.SESSION_STATUS: 'SESSION_STATUS',
        blpapi.Event.SUBSCRIPTION_STATUS: 'SUBSCRIPTION_STATUS',
        blpapi.Event.SUBSCRIPTION_DATA: 'SUBSCRIPTION_DATA',
        blpapi.Event.RESPONSE: 'RESPONSE',
        blpapi.Event.PARTIAL_RESPONSE: 'PARTIAL_RESPONSE',
        blpapi.Event.REQUEST_STATUS: 'REQUEST_STATUS',
        blpapi.Event.TIMEOUT: 'TIMEOUT',
        blpapi.Event.AUTHORIZATION_STATUS: 'AUTHORIZATION_STATUS',
        blpapi.Event.RESOLUTION_STATUS: 'RESOLUTION_STATUS',
        blpapi.Event.TOPIC_STATUS: 'TOPIC_STATUS',
        blpapi.Event.TOKEN_STATUS: 'TOKEN_STATUS',
        blpapi.Event.SERVICE_STATUS: 'SERVICE_STATUS',
    }

    return event_type_map.get(event_type, f'UNKNOWN({event_type})')

