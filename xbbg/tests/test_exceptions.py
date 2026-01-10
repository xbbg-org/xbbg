"""Unit tests for Bloomberg API exception hierarchy.

Tests all custom exception classes in xbbg/exceptions.py including:
- BlpError base class
- BlpSessionError
- BlpRequestError with attributes
- BlpSecurityError
- BlpFieldError
- BlpValidationError with from_error_message() parsing
- BlpTimeoutError
- BlpInternalError
"""

from __future__ import annotations

import pytest

from xbbg.exceptions import (
    BlpError,
    BlpFieldError,
    BlpInternalError,
    BlpRequestError,
    BlpSecurityError,
    BlpSessionError,
    BlpTimeoutError,
    BlpValidationError,
)


class TestBlpError:
    """Test BlpError base exception class."""

    def test_blp_error_is_exception(self):
        """Test that BlpError inherits from Exception."""
        assert issubclass(BlpError, Exception)

    def test_blp_error_can_be_raised(self):
        """Test that BlpError can be raised and caught."""
        with pytest.raises(BlpError):
            raise BlpError("Test error")

    def test_blp_error_message(self):
        """Test that BlpError stores the message correctly."""
        error = BlpError("Test message")
        assert str(error) == "Test message"

    def test_blp_error_catches_all_subclasses(self):
        """Test that catching BlpError catches all subclasses."""
        subclasses = [
            BlpSessionError,
            BlpRequestError,
            BlpSecurityError,
            BlpFieldError,
            BlpValidationError,
            BlpTimeoutError,
            BlpInternalError,
        ]
        for subclass in subclasses:
            with pytest.raises(BlpError):
                raise subclass("Test")


class TestBlpSessionError:
    """Test BlpSessionError exception class."""

    def test_blp_session_error_inherits_from_blp_error(self):
        """Test that BlpSessionError inherits from BlpError."""
        assert issubclass(BlpSessionError, BlpError)

    def test_blp_session_error_can_be_raised(self):
        """Test that BlpSessionError can be raised and caught."""
        with pytest.raises(BlpSessionError):
            raise BlpSessionError("Session failed to start")

    def test_blp_session_error_message(self):
        """Test that BlpSessionError stores the message correctly."""
        error = BlpSessionError("Connection refused")
        assert str(error) == "Connection refused"


class TestBlpRequestError:
    """Test BlpRequestError exception class with attributes."""

    def test_blp_request_error_inherits_from_blp_error(self):
        """Test that BlpRequestError inherits from BlpError."""
        assert issubclass(BlpRequestError, BlpError)

    def test_blp_request_error_basic(self):
        """Test BlpRequestError with just a message."""
        error = BlpRequestError("Request failed")
        assert str(error) == "Request failed"
        assert error.service is None
        assert error.operation is None
        assert error.request_id is None
        assert error.code is None

    def test_blp_request_error_with_all_attributes(self):
        """Test BlpRequestError with all optional attributes."""
        error = BlpRequestError(
            "Request failed",
            service="//blp/refdata",
            operation="ReferenceDataRequest",
            request_id="req-123",
            code=500,
        )
        assert str(error) == "Request failed"
        assert error.service == "//blp/refdata"
        assert error.operation == "ReferenceDataRequest"
        assert error.request_id == "req-123"
        assert error.code == 500

    def test_blp_request_error_with_partial_attributes(self):
        """Test BlpRequestError with some optional attributes."""
        error = BlpRequestError(
            "Request failed",
            service="//blp/refdata",
            code=404,
        )
        assert error.service == "//blp/refdata"
        assert error.operation is None
        assert error.request_id is None
        assert error.code == 404


class TestBlpSecurityError:
    """Test BlpSecurityError exception class."""

    def test_blp_security_error_inherits_from_blp_request_error(self):
        """Test that BlpSecurityError inherits from BlpRequestError."""
        assert issubclass(BlpSecurityError, BlpRequestError)

    def test_blp_security_error_inherits_from_blp_error(self):
        """Test that BlpSecurityError also inherits from BlpError."""
        assert issubclass(BlpSecurityError, BlpError)

    def test_blp_security_error_with_attributes(self):
        """Test BlpSecurityError with request attributes."""
        error = BlpSecurityError(
            "Invalid security: INVALID US Equity",
            service="//blp/refdata",
            operation="ReferenceDataRequest",
        )
        assert "Invalid security" in str(error)
        assert error.service == "//blp/refdata"


class TestBlpFieldError:
    """Test BlpFieldError exception class."""

    def test_blp_field_error_inherits_from_blp_request_error(self):
        """Test that BlpFieldError inherits from BlpRequestError."""
        assert issubclass(BlpFieldError, BlpRequestError)

    def test_blp_field_error_inherits_from_blp_error(self):
        """Test that BlpFieldError also inherits from BlpError."""
        assert issubclass(BlpFieldError, BlpError)

    def test_blp_field_error_with_attributes(self):
        """Test BlpFieldError with request attributes."""
        error = BlpFieldError(
            "Invalid field: INVALID_FIELD",
            service="//blp/refdata",
            code=100,
        )
        assert "Invalid field" in str(error)
        assert error.code == 100


class TestBlpValidationError:
    """Test BlpValidationError exception class."""

    def test_blp_validation_error_inherits_from_blp_error(self):
        """Test that BlpValidationError inherits from BlpError."""
        assert issubclass(BlpValidationError, BlpError)

    def test_blp_validation_error_basic(self):
        """Test BlpValidationError with just a message."""
        error = BlpValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert error.element is None
        assert error.suggestion is None
        assert error.valid_values is None

    def test_blp_validation_error_with_all_attributes(self):
        """Test BlpValidationError with all optional attributes."""
        error = BlpValidationError(
            "Invalid enum value",
            element="periodicitySelection",
            suggestion="DAILY",
            valid_values=["DAILY", "WEEKLY", "MONTHLY"],
        )
        assert error.element == "periodicitySelection"
        assert error.suggestion == "DAILY"
        assert error.valid_values == ["DAILY", "WEEKLY", "MONTHLY"]

    def test_from_error_message_with_suggestion(self):
        """Test from_error_message() extracts suggestion from message."""
        message = "Unknown element 'periodictySelection' (did you mean 'periodicitySelection'?)"
        error = BlpValidationError.from_error_message(message)
        assert error.suggestion == "periodicitySelection"
        assert error.element == "periodictySelection"

    def test_from_error_message_with_element_only(self):
        """Test from_error_message() extracts element without suggestion."""
        message = "Unknown element 'invalidField'"
        error = BlpValidationError.from_error_message(message)
        assert error.element == "invalidField"
        assert error.suggestion is None

    def test_from_error_message_with_invalid_enum(self):
        """Test from_error_message() extracts element from invalid enum message."""
        message = "Invalid enum value 'DAYLY' for 'periodicitySelection'"
        error = BlpValidationError.from_error_message(message)
        assert error.element == "periodicitySelection"
        assert error.suggestion is None

    def test_from_error_message_no_pattern_match(self):
        """Test from_error_message() with message that doesn't match patterns."""
        message = "Some other validation error"
        error = BlpValidationError.from_error_message(message)
        assert str(error) == message
        assert error.element is None
        assert error.suggestion is None

    def test_from_error_message_preserves_full_message(self):
        """Test from_error_message() preserves the full original message."""
        message = "Unknown element 'foo' (did you mean 'bar'?)"
        error = BlpValidationError.from_error_message(message)
        assert str(error) == message


class TestBlpTimeoutError:
    """Test BlpTimeoutError exception class."""

    def test_blp_timeout_error_inherits_from_blp_error(self):
        """Test that BlpTimeoutError inherits from BlpError."""
        assert issubclass(BlpTimeoutError, BlpError)

    def test_blp_timeout_error_can_be_raised(self):
        """Test that BlpTimeoutError can be raised and caught."""
        with pytest.raises(BlpTimeoutError):
            raise BlpTimeoutError("Request timed out after 30 seconds")


class TestBlpInternalError:
    """Test BlpInternalError exception class."""

    def test_blp_internal_error_inherits_from_blp_error(self):
        """Test that BlpInternalError inherits from BlpError."""
        assert issubclass(BlpInternalError, BlpError)

    def test_blp_internal_error_can_be_raised(self):
        """Test that BlpInternalError can be raised and caught."""
        with pytest.raises(BlpInternalError):
            raise BlpInternalError("Unexpected internal state")


class TestExceptionHierarchy:
    """Test the complete exception hierarchy."""

    def test_all_exceptions_inherit_from_blp_error(self):
        """Test that all custom exceptions inherit from BlpError."""
        exceptions = [
            BlpSessionError,
            BlpRequestError,
            BlpSecurityError,
            BlpFieldError,
            BlpValidationError,
            BlpTimeoutError,
            BlpInternalError,
        ]
        for exc in exceptions:
            assert issubclass(exc, BlpError), f"{exc.__name__} should inherit from BlpError"

    def test_security_and_field_errors_inherit_from_request_error(self):
        """Test that BlpSecurityError and BlpFieldError inherit from BlpRequestError."""
        assert issubclass(BlpSecurityError, BlpRequestError)
        assert issubclass(BlpFieldError, BlpRequestError)

    def test_exception_chain_catching(self):
        """Test that exception hierarchy allows proper catching."""
        # BlpSecurityError should be caught by BlpRequestError
        try:
            raise BlpSecurityError("Invalid security")
        except BlpRequestError as e:
            assert "Invalid security" in str(e)

        # BlpRequestError should be caught by BlpError
        try:
            raise BlpRequestError("Request failed")
        except BlpError as e:
            assert "Request failed" in str(e)

    def test_specific_exception_not_caught_by_sibling(self):
        """Test that sibling exceptions don't catch each other."""
        with pytest.raises(BlpSessionError):
            try:
                raise BlpSessionError("Session error")
            except BlpRequestError:
                pytest.fail("BlpSessionError should not be caught by BlpRequestError")
