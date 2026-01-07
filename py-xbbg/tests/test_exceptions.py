"""Tests for the xbbg exception hierarchy.

These tests verify that:
1. Python exceptions are properly defined
2. Rust _core exceptions are exposed and can be caught
3. Exception hierarchy allows catching by base class
"""

from __future__ import annotations

import pytest


class TestPythonExceptionHierarchy:
    """Tests for the Python-defined exception classes."""

    def test_blp_error_is_base_exception(self):
        """BlpError should be the base class for all xbbg exceptions."""
        from xbbg.exceptions import BlpError

        assert issubclass(BlpError, Exception)

    def test_blp_session_error_inherits_from_blp_error(self):
        """BlpSessionError should inherit from BlpError."""
        from xbbg.exceptions import BlpError, BlpSessionError

        assert issubclass(BlpSessionError, BlpError)

    def test_blp_request_error_inherits_from_blp_error(self):
        """BlpRequestError should inherit from BlpError."""
        from xbbg.exceptions import BlpError, BlpRequestError

        assert issubclass(BlpRequestError, BlpError)

    def test_blp_security_error_inherits_from_blp_request_error(self):
        """BlpSecurityError should inherit from BlpRequestError."""
        from xbbg.exceptions import BlpRequestError, BlpSecurityError

        assert issubclass(BlpSecurityError, BlpRequestError)

    def test_blp_field_error_inherits_from_blp_request_error(self):
        """BlpFieldError should inherit from BlpRequestError."""
        from xbbg.exceptions import BlpFieldError, BlpRequestError

        assert issubclass(BlpFieldError, BlpRequestError)

    def test_blp_validation_error_inherits_from_blp_error(self):
        """BlpValidationError should inherit from BlpError."""
        from xbbg.exceptions import BlpError, BlpValidationError

        assert issubclass(BlpValidationError, BlpError)

    def test_blp_timeout_error_inherits_from_blp_error(self):
        """BlpTimeoutError should inherit from BlpError."""
        from xbbg.exceptions import BlpError, BlpTimeoutError

        assert issubclass(BlpTimeoutError, BlpError)

    def test_blp_internal_error_inherits_from_blp_error(self):
        """BlpInternalError should inherit from BlpError."""
        from xbbg.exceptions import BlpError, BlpInternalError

        assert issubclass(BlpInternalError, BlpError)

    def test_blp_request_error_has_context_attributes(self):
        """BlpRequestError should have service/operation/request_id/code attributes."""
        from xbbg.exceptions import BlpRequestError

        err = BlpRequestError(
            "test error",
            service="//blp/refdata",
            operation="ReferenceDataRequest",
            request_id="req-123",
            code=42,
        )

        assert str(err) == "test error"
        assert err.service == "//blp/refdata"
        assert err.operation == "ReferenceDataRequest"
        assert err.request_id == "req-123"
        assert err.code == 42

    def test_catching_by_base_class(self):
        """Should be able to catch any xbbg exception with BlpError."""
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

        exceptions = [
            BlpSessionError("session error"),
            BlpRequestError("request error"),
            BlpSecurityError("security error"),
            BlpFieldError("field error"),
            BlpValidationError("validation error"),
            BlpTimeoutError("timeout error"),
            BlpInternalError("internal error"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except BlpError as e:
                # Should catch all of them
                assert str(e) in str(exc)
            else:
                pytest.fail(f"Failed to catch {type(exc).__name__} with BlpError")


class TestRustCoreExceptions:
    """Tests for the Rust _core exception classes exposed to Python."""

    def test_core_exceptions_exist(self):
        """Rust _core module should expose exception classes."""
        import xbbg

        # Access _core through xbbg to trigger DLL path setup
        _core = xbbg._core

        # These exception classes should be exposed by the Rust module
        assert hasattr(_core, "BlpError")
        assert hasattr(_core, "BlpSessionError")
        assert hasattr(_core, "BlpRequestError")
        assert hasattr(_core, "BlpSecurityError")
        assert hasattr(_core, "BlpFieldError")
        assert hasattr(_core, "BlpValidationError")
        assert hasattr(_core, "BlpTimeoutError")
        assert hasattr(_core, "BlpInternalError")

    def test_core_exceptions_are_exception_types(self):
        """Rust _core exceptions should be exception types."""
        import xbbg

        _core = xbbg._core

        # All should be exception classes (types that inherit from BaseException)
        assert isinstance(_core.BlpError, type)
        assert issubclass(_core.BlpError, BaseException)
        assert issubclass(_core.BlpSessionError, BaseException)
        assert issubclass(_core.BlpRequestError, BaseException)
        assert issubclass(_core.BlpValidationError, BaseException)
        assert issubclass(_core.BlpTimeoutError, BaseException)
        assert issubclass(_core.BlpInternalError, BaseException)

    def test_core_session_error_inherits_from_blp_error(self):
        """Rust BlpSessionError should inherit from BlpError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpSessionError, _core.BlpError)

    def test_core_request_error_inherits_from_blp_error(self):
        """Rust BlpRequestError should inherit from BlpError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpRequestError, _core.BlpError)

    def test_core_validation_error_inherits_from_blp_error(self):
        """Rust BlpValidationError should inherit from BlpError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpValidationError, _core.BlpError)

    def test_core_timeout_error_inherits_from_blp_error(self):
        """Rust BlpTimeoutError should inherit from BlpError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpTimeoutError, _core.BlpError)

    def test_core_internal_error_inherits_from_blp_error(self):
        """Rust BlpInternalError should inherit from BlpError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpInternalError, _core.BlpError)

    def test_core_security_error_inherits_from_request_error(self):
        """Rust BlpSecurityError should inherit from BlpRequestError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpSecurityError, _core.BlpRequestError)

    def test_core_field_error_inherits_from_request_error(self):
        """Rust BlpFieldError should inherit from BlpRequestError."""
        import xbbg

        _core = xbbg._core

        assert issubclass(_core.BlpFieldError, _core.BlpRequestError)

    def test_core_exceptions_can_be_raised_and_caught(self):
        """Rust _core exceptions should be raisable and catchable."""
        import xbbg

        _core = xbbg._core

        # Test raising and catching each exception type
        with pytest.raises(_core.BlpSessionError):
            raise _core.BlpSessionError("test session error")

        with pytest.raises(_core.BlpRequestError):
            raise _core.BlpRequestError("test request error")

        with pytest.raises(_core.BlpValidationError):
            raise _core.BlpValidationError("test validation error")

        with pytest.raises(_core.BlpTimeoutError):
            raise _core.BlpTimeoutError("test timeout error")

        with pytest.raises(_core.BlpInternalError):
            raise _core.BlpInternalError("test internal error")

    def test_core_exceptions_catchable_by_base(self):
        """Rust _core exceptions should be catchable by their base class."""
        import xbbg

        _core = xbbg._core

        # BlpSessionError should be catchable by BlpError
        with pytest.raises(_core.BlpError):
            raise _core.BlpSessionError("session error")

        # BlpRequestError should be catchable by BlpError
        with pytest.raises(_core.BlpError):
            raise _core.BlpRequestError("request error")

        # BlpSecurityError should be catchable by BlpRequestError
        with pytest.raises(_core.BlpRequestError):
            raise _core.BlpSecurityError("security error")

        # BlpFieldError should be catchable by BlpRequestError
        with pytest.raises(_core.BlpRequestError):
            raise _core.BlpFieldError("field error")


class TestValidationErrorsFromPython:
    """Tests for validation errors raised from the Python layer."""

    def test_missing_securities_raises_validation_error(self):
        """RequestParams validation should raise BlpValidationError for missing securities."""
        from xbbg.exceptions import BlpValidationError
        from xbbg.services import Operation, RequestParams, Service

        params = RequestParams(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=None,  # Missing!
            fields=["PX_LAST"],
        )

        with pytest.raises(BlpValidationError, match="securities is required"):
            params.validate()

    def test_missing_fields_raises_validation_error(self):
        """RequestParams validation should raise BlpValidationError for missing fields."""
        from xbbg.exceptions import BlpValidationError
        from xbbg.services import Operation, RequestParams, Service

        params = RequestParams(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=["AAPL US Equity"],
            fields=None,  # Missing!
        )

        with pytest.raises(BlpValidationError, match="fields is required"):
            params.validate()

    def test_missing_dates_for_historical_raises_validation_error(self):
        """RequestParams validation should raise BlpValidationError for missing dates."""
        from xbbg.exceptions import BlpValidationError
        from xbbg.services import Operation, RequestParams, Service

        params = RequestParams(
            service=Service.REFDATA,
            operation=Operation.HISTORICAL_DATA,
            securities=["AAPL US Equity"],
            fields=["PX_LAST"],
            start_date=None,  # Missing!
            end_date="20241201",
        )

        with pytest.raises(BlpValidationError, match="start_date is required"):
            params.validate()

    def test_missing_security_for_intraday_raises_validation_error(self):
        """RequestParams validation should raise BlpValidationError for intraday requests."""
        from xbbg.exceptions import BlpValidationError
        from xbbg.services import Operation, RequestParams, Service

        params = RequestParams(
            service=Service.REFDATA,
            operation=Operation.INTRADAY_BAR,
            security=None,  # Missing! (intraday uses 'security' not 'securities')
            event_type="TRADE",
            interval=1,
            start_datetime="2024-12-01T09:30:00",
            end_datetime="2024-12-01T16:00:00",
        )

        with pytest.raises(BlpValidationError, match="security is required"):
            params.validate()
