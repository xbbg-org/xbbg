"""Bloomberg API exception hierarchy.

All xbbg exceptions inherit from BlpError, allowing users to catch all
Bloomberg-related errors with a single except clause.

This module provides forward-compatible exception classes that will be
used in xbbg v1.0. Using these exceptions now helps prepare for the
upcoming release.

Example:
    try:
        df = xbbg.bdp(['INVALID'], ['PX_LAST'])
    except BlpRequestError as e:
        print(f"Request failed: {e}")
    except BlpError as e:
        print(f"Bloomberg error: {e}")
"""

from __future__ import annotations


class BlpError(Exception):
    """Base exception for all Bloomberg API errors."""


class BlpSessionError(BlpError):
    """Session lifecycle errors (start, connect, service open)."""


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


class BlpFieldError(BlpRequestError):
    """Invalid or inaccessible field."""


class BlpValidationError(BlpError):
    """Request validation errors.

    Raised when request parameters fail validation against Bloomberg schemas.
    Includes helpful suggestions for typos and invalid enum values.

    Attributes:
        message: Human-readable error description.
        element: The element name that caused the error (if available).
        suggestion: Suggested correction for typos (if available).
        valid_values: List of valid values for enum fields (if available).

    Example:
        try:
            df = xbbg.bdp('AAPL US Equity', 'PX_LAST', periodictySelection='DAILY')
        except BlpValidationError as e:
            if e.suggestion:
                print(f"Did you mean '{e.suggestion}'?")
    """

    def __init__(
        self,
        message: str,
        *,
        element: str | None = None,
        suggestion: str | None = None,
        valid_values: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.element = element
        self.suggestion = suggestion
        self.valid_values = valid_values

    @classmethod
    def from_error_message(cls, message: str) -> BlpValidationError:
        """Parse a validation error message.

        Extracts element name and suggestion from formatted error messages.
        """
        # Try to extract suggestion from "(did you mean 'xxx'?)" pattern
        suggestion = None
        if "(did you mean '" in message:
            start = message.find("(did you mean '") + len("(did you mean '")
            end = message.find("'?)", start)
            if end > start:
                suggestion = message[start:end]

        # Try to extract element name from "Unknown element 'xxx'" pattern
        element = None
        if "Unknown element '" in message:
            start = message.find("Unknown element '") + len("Unknown element '")
            end = message.find("'", start)
            if end > start:
                element = message[start:end]
        elif "Invalid enum value" in message and "for '" in message:
            start = message.find("for '") + len("for '")
            end = message.find("'", start)
            if end > start:
                element = message[start:end]

        return cls(message, element=element, suggestion=suggestion)


class BlpTimeoutError(BlpError):
    """Request timeout."""


class BlpInternalError(BlpError):
    """Internal errors (should not happen in normal operation).

    If you encounter this error, please report it as a bug.
    """
