"""Bloomberg API exception hierarchy.

All xbbg exceptions inherit from BlpError, allowing users to catch all
Bloomberg-related errors with a single except clause.

Example:
    try:
        df = await xbbg.abdp(['INVALID'], ['PX_LAST'])
    except BlpRequestError as e:
        print(f"Request failed: {e}")
    except BlpError as e:
        print(f"Bloomberg error: {e}")
"""

from __future__ import annotations


class BlpError(Exception):
    """Base exception for all Bloomberg API errors."""

    pass


class BlpSessionError(BlpError):
    """Session lifecycle errors (start, connect, service open)."""

    pass


class BlpRequestError(BlpError):
    """Request-level errors from the Bloomberg API.

    Attributes:
        service: The Bloomberg service URI (e.g., "//blp/refdata").
        operation: The request operation name (e.g., "ReferenceDataRequest").
        request_id: Optional correlation ID for debugging.
        code: Optional Bloomberg error code.
    """

    def __init__(
        self,
        message: str,
        *,
        service: str | None = None,
        operation: str | None = None,
        request_id: str | None = None,
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.request_id = request_id
        self.code = code


class BlpSecurityError(BlpRequestError):
    """Invalid or inaccessible security identifier."""

    pass


class BlpFieldError(BlpRequestError):
    """Invalid or inaccessible field."""

    pass


class BlpValidationError(BlpError):
    """Parameter validation errors (raised before sending to Rust).

    These errors are caught early in the Python layer before any
    Bloomberg API calls are made.
    """

    pass


class BlpTimeoutError(BlpError):
    """Request timeout."""

    pass


class BlpInternalError(BlpError):
    """Internal errors (should not happen in normal operation).

    If you encounter this error, please report it as a bug.
    """

    pass
