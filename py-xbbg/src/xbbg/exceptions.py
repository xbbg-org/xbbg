"""Bloomberg API exceptions.

Canonical exception classes are defined by the Rust extension module
(`xbbg._core`) and re-exported here for a stable Python import path.

Python-only exceptions should be additive and inherit from the Rust base.
"""

from __future__ import annotations

from . import _core

# Canonical Rust exceptions (single source of truth)
BlpError = _core.BlpError
BlpSessionError = _core.BlpSessionError
BlpRequestError = _core.BlpRequestError
BlpSecurityError = _core.BlpSecurityError
BlpFieldError = _core.BlpFieldError
BlpValidationError = _core.BlpValidationError
BlpTimeoutError = _core.BlpTimeoutError
BlpInternalError = _core.BlpInternalError


def _init_request_error(
    self,
    message: str,
    *,
    service: str | None = None,
    operation: str | None = None,
    request_id: str | None = None,
    code: int | None = None,
) -> None:
    """Back-compat init for request-derived errors with context attributes."""
    Exception.__init__(self, message)
    self.service = service
    self.operation = operation
    self.request_id = request_id
    self.code = code


def _init_validation_error(
    self,
    message: str,
    *,
    element: str | None = None,
    suggestion: str | None = None,
    valid_values: list[str] | None = None,
) -> None:
    """Back-compat init for validation errors with parsed metadata."""
    Exception.__init__(self, message)
    self.element = element
    self.suggestion = suggestion
    self.valid_values = valid_values


# Back-compat constructor behavior expected by tests and existing callers.
BlpRequestError.__init__ = _init_request_error  # type: ignore[invalid-assignment]
BlpSecurityError.__init__ = _init_request_error  # type: ignore[invalid-assignment]
BlpFieldError.__init__ = _init_request_error  # type: ignore[invalid-assignment]
BlpValidationError.__init__ = _init_validation_error  # type: ignore[invalid-assignment]


class BlpBPipeError(BlpError):
    """B-PIPE license required for this operation.

    Raised when attempting to use features that require Bloomberg B-PIPE
    license but only a standard Terminal connection is available.

    B-PIPE features include:
        - Level 2 market depth data (depth/adepth)
        - Option and futures chains (chains/achains)
    """


def _parse_validation_error(message: str) -> tuple[str | None, str | None]:
    """Extract (element, suggestion) from Rust validation error text."""
    suggestion = None
    if "(did you mean '" in message:
        start = message.find("(did you mean '") + len("(did you mean '")
        end = message.find("'?)", start)
        if end > start:
            suggestion = message[start:end]

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

    return element, suggestion


def _from_rust_error(cls, message: str):
    """Back-compat helper for constructing BlpValidationError from text."""
    element, suggestion = _parse_validation_error(message)
    err = cls(message)
    if element is not None:
        err.element = element
    if suggestion is not None:
        err.suggestion = suggestion
    return err


# Preserve legacy helper on the canonical Rust class.
BlpValidationError.from_rust_error = classmethod(_from_rust_error)  # type: ignore[unresolved-attribute]


__all__ = [
    "BlpError",
    "BlpSessionError",
    "BlpRequestError",
    "BlpSecurityError",
    "BlpFieldError",
    "BlpValidationError",
    "BlpTimeoutError",
    "BlpInternalError",
    "BlpBPipeError",
]
