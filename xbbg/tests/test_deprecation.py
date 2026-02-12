"""Unit tests for deprecation warning infrastructure.

Tests all deprecation utilities in xbbg/deprecation.py including:
- XbbgFutureWarning class
- warn_once() function
- warn_defaults_changing() function
- warn_function_removed() function
- warn_function_renamed() function
- warn_function_moved() function
- warn_signature_changed() function
- warn_parameter_renamed() function
- deprecated_alias() wrapper
"""

from __future__ import annotations

import warnings

import pytest

from xbbg import deprecation
from xbbg.deprecation import (
    XbbgFutureWarning,
    deprecated_alias,
    warn_defaults_changing,
    warn_function_moved,
    warn_function_removed,
    warn_function_renamed,
    warn_once,
    warn_parameter_renamed,
    warn_signature_changed,
)


class TestXbbgFutureWarning:
    """Test XbbgFutureWarning class."""

    def test_xbbg_future_warning_is_future_warning_subclass(self):
        """Test that XbbgFutureWarning inherits from FutureWarning."""
        assert issubclass(XbbgFutureWarning, FutureWarning)

    def test_xbbg_future_warning_can_be_raised(self):
        """Test that XbbgFutureWarning can be raised."""
        with pytest.raises(XbbgFutureWarning):
            raise XbbgFutureWarning("Test warning")

    def test_xbbg_future_warning_caught_by_future_warning(self):
        """Test that XbbgFutureWarning is caught by FutureWarning handler."""
        with pytest.raises(FutureWarning):
            raise XbbgFutureWarning("Test warning")

    def test_xbbg_future_warning_message(self):
        """Test that XbbgFutureWarning stores message correctly."""
        warning = XbbgFutureWarning("Test message")
        assert str(warning) == "Test message"


class TestWarnOnce:
    """Test warn_once() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_once_issues_warning(self):
        """Test that warn_once issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="Test warning"):
            warn_once("test_key", "Test warning", stacklevel=2)

    def test_warn_once_only_warns_once_per_key(self):
        """Test that warn_once only warns once per key."""
        # First call should warn
        with pytest.warns(XbbgFutureWarning):
            warn_once("unique_key_1", "First warning", stacklevel=2)

        # Second call with same key should not warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_once("unique_key_1", "Second warning", stacklevel=2)
            # Filter for XbbgFutureWarning only
            xbbg_warnings = [x for x in w if issubclass(x.category, XbbgFutureWarning)]
            assert len(xbbg_warnings) == 0

    def test_warn_once_different_keys_warn_separately(self):
        """Test that different keys warn independently."""
        with pytest.warns(XbbgFutureWarning, match="Warning A"):
            warn_once("key_a", "Warning A", stacklevel=2)

        with pytest.warns(XbbgFutureWarning, match="Warning B"):
            warn_once("key_b", "Warning B", stacklevel=2)

    def test_warn_once_key_tracked_in_warned_set(self):
        """Test that warned keys are tracked in _warned set."""
        assert "tracked_key" not in deprecation._warned
        with pytest.warns(XbbgFutureWarning):
            warn_once("tracked_key", "Test", stacklevel=2)
        assert "tracked_key" in deprecation._warned


class TestWarnDefaultsChanging:
    """Test warn_defaults_changing() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_defaults_changing_issues_warning(self):
        """Test that warn_defaults_changing issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="defaults are changing"):
            warn_defaults_changing()

    def test_warn_defaults_changing_mentions_narwhals(self):
        """Test that warning mentions narwhals backend."""
        with pytest.warns(XbbgFutureWarning, match="narwhals"):
            warn_defaults_changing()

    def test_warn_defaults_changing_mentions_long_format(self):
        """Test that warning mentions long format."""
        with pytest.warns(XbbgFutureWarning, match="long"):
            warn_defaults_changing()


class TestWarnFunctionRemoved:
    """Test warn_function_removed() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_function_removed_without_replacement(self):
        """Test warning for removed function without replacement."""
        with pytest.warns(XbbgFutureWarning, match="removed in v1.0"):
            warn_function_removed("oldFunc")

    def test_warn_function_removed_with_replacement(self):
        """Test warning for removed function with replacement."""
        with pytest.warns(XbbgFutureWarning, match="Use newFunc instead"):
            warn_function_removed("oldFunc2", replacement="Use newFunc instead")

    def test_warn_function_removed_includes_function_name(self):
        """Test that warning includes the function name."""
        with pytest.warns(XbbgFutureWarning, match="myFunction"):
            warn_function_removed("myFunction")


class TestWarnFunctionRenamed:
    """Test warn_function_renamed() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_function_renamed_issues_warning(self):
        """Test that warn_function_renamed issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="renamed to"):
            warn_function_renamed("oldName", "newName")

    def test_warn_function_renamed_includes_both_names(self):
        """Test that warning includes both old and new names."""
        with pytest.warns(XbbgFutureWarning, match="oldFunc.*newFunc"):
            warn_function_renamed("oldFunc", "newFunc")


class TestWarnFunctionMoved:
    """Test warn_function_moved() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_function_moved_issues_warning(self):
        """Test that warn_function_moved issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="has moved to"):
            warn_function_moved("myFunc", "xbbg.ext.myFunc")

    def test_warn_function_moved_includes_new_location(self):
        """Test that warning includes the new location."""
        with pytest.warns(XbbgFutureWarning, match="xbbg.ext.dividend"):
            warn_function_moved("dividend", "xbbg.ext.dividend")


class TestWarnSignatureChanged:
    """Test warn_signature_changed() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_signature_changed_issues_warning(self):
        """Test that warn_signature_changed issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="signature changed"):
            warn_signature_changed("myFunc", "Parameter order changed")

    def test_warn_signature_changed_includes_details(self):
        """Test that warning includes the details."""
        with pytest.warns(XbbgFutureWarning, match="New parameter added"):
            warn_signature_changed("myFunc", "New parameter added")


class TestWarnParameterRenamed:
    """Test warn_parameter_renamed() function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_parameter_renamed_issues_warning(self):
        """Test that warn_parameter_renamed issues a warning."""
        with pytest.warns(XbbgFutureWarning, match="renamed to"):
            warn_parameter_renamed("myFunc", "old_param", "new_param")

    def test_warn_parameter_renamed_includes_all_names(self):
        """Test that warning includes function and parameter names."""
        with pytest.warns(XbbgFutureWarning, match="myFunc.*old_param.*new_param"):
            warn_parameter_renamed("myFunc", "old_param", "new_param")


class TestDeprecatedAlias:
    """Test deprecated_alias() wrapper function."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_deprecated_alias_calls_new_function(self):
        """Test that deprecated_alias calls the new function."""

        def new_func(x, y):
            return x + y

        def warning_func():
            warn_once("alias_test", "Function deprecated", stacklevel=3)

        alias = deprecated_alias("old_func", new_func, warning_func)

        with pytest.warns(XbbgFutureWarning):
            result = alias(1, 2)

        assert result == 3

    def test_deprecated_alias_passes_args_and_kwargs(self):
        """Test that deprecated_alias passes all arguments correctly."""

        def new_func(a, b, c=None):
            return (a, b, c)

        def warning_func():
            warn_once("alias_test_2", "Deprecated", stacklevel=3)

        alias = deprecated_alias("old_func", new_func, warning_func)

        with pytest.warns(XbbgFutureWarning):
            result = alias(1, 2, c=3)

        assert result == (1, 2, 3)

    def test_deprecated_alias_has_correct_name(self):
        """Test that deprecated_alias wrapper has the old function name."""

        def new_func():
            pass

        def warning_func():
            pass

        alias = deprecated_alias("legacy_function", new_func, warning_func)
        assert alias.__name__ == "legacy_function"  # type: ignore[unresolved-attribute]

    def test_deprecated_alias_has_deprecation_docstring(self):
        """Test that deprecated_alias wrapper has deprecation docstring."""

        def new_func():
            pass

        def warning_func():
            pass

        alias = deprecated_alias("old_func", new_func, warning_func)
        assert alias.__doc__ is not None
        assert "DEPRECATED" in alias.__doc__

    def test_deprecated_alias_issues_warning_on_call(self):
        """Test that deprecated_alias issues warning when called."""
        call_count = [0]

        def new_func():
            return "result"

        def warning_func():
            call_count[0] += 1
            warn_once("alias_warning_test", "Deprecated", stacklevel=3)

        alias = deprecated_alias("old_func", new_func, warning_func)

        with pytest.warns(XbbgFutureWarning):
            alias()

        assert call_count[0] == 1


class TestPredefinedWarnings:
    """Test pre-defined warning functions."""

    def setup_method(self):
        """Clear the warned set before each test."""
        deprecation._warned.clear()

    def test_warn_connect(self):
        """Test warn_connect() function."""
        with pytest.warns(XbbgFutureWarning, match="connect.*removed"):
            deprecation.warn_connect()

    def test_warn_disconnect(self):
        """Test warn_disconnect() function."""
        with pytest.warns(XbbgFutureWarning, match="disconnect.*removed"):
            deprecation.warn_disconnect()

    def test_warn_field_info(self):
        """Test warn_fieldInfo() function."""
        with pytest.warns(XbbgFutureWarning, match="fieldInfo.*renamed.*bfld"):
            deprecation.warn_fieldInfo()

    def test_warn_field_search(self):
        """Test warn_fieldSearch() function."""
        with pytest.warns(XbbgFutureWarning, match="fieldSearch.*merged.*bfld"):
            deprecation.warn_fieldSearch()

    def test_warn_get_portfolio(self):
        """Test warn_getPortfolio() function."""
        with pytest.warns(XbbgFutureWarning, match="getPortfolio.*renamed.*bport"):
            deprecation.warn_getPortfolio()

    def test_warn_dividend(self):
        """Test warn_dividend() function."""
        with pytest.warns(XbbgFutureWarning, match="dividend.*moved.*xbbg.ext"):
            deprecation.warn_dividend()

    def test_warn_earning(self):
        """Test warn_earning() function."""
        with pytest.warns(XbbgFutureWarning, match="earning.*moved.*xbbg.ext"):
            deprecation.warn_earning()

    def test_warn_turnover(self):
        """Test warn_turnover() function."""
        with pytest.warns(XbbgFutureWarning, match="turnover.*moved.*xbbg.ext"):
            deprecation.warn_turnover()

    def test_warn_adjust_ccy(self):
        """Test warn_adjust_ccy() function."""
        with pytest.warns(XbbgFutureWarning, match="adjust_ccy.*moved.*xbbg.ext"):
            deprecation.warn_adjust_ccy()

    def test_warn_fut_ticker(self):
        """Test warn_fut_ticker() function."""
        with pytest.warns(XbbgFutureWarning, match="fut_ticker.*moved.*xbbg.ext"):
            deprecation.warn_fut_ticker()

    def test_warn_active_futures(self):
        """Test warn_active_futures() function."""
        with pytest.warns(XbbgFutureWarning, match="active_futures.*moved.*xbbg.ext"):
            deprecation.warn_active_futures()

    def test_warn_cdx_ticker(self):
        """Test warn_cdx_ticker() function."""
        with pytest.warns(XbbgFutureWarning, match="cdx_ticker.*moved.*xbbg.ext"):
            deprecation.warn_cdx_ticker()

    def test_warn_active_cdx(self):
        """Test warn_active_cdx() function."""
        with pytest.warns(XbbgFutureWarning, match="active_cdx.*moved.*xbbg.ext"):
            deprecation.warn_active_cdx()

    def test_warn_etf_holdings(self):
        """Test warn_etf_holdings() function."""
        with pytest.warns(XbbgFutureWarning, match="etf_holdings.*moved.*xbbg.ext"):
            deprecation.warn_etf_holdings()

    def test_warn_beqs_typ_param(self):
        """Test warn_beqs_typ_param() function."""
        with pytest.warns(XbbgFutureWarning, match="beqs.*typ.*renamed.*screen_type"):
            deprecation.warn_beqs_typ_param()


class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_exports_exist(self):
        """Test that all items in __all__ are accessible."""
        for name in deprecation.__all__:
            assert hasattr(deprecation, name), f"{name} in __all__ but not accessible"

    def test_xbbg_future_warning_in_exports(self):
        """Test that XbbgFutureWarning is in exports."""
        assert "XbbgFutureWarning" in deprecation.__all__

    def test_warn_once_in_exports(self):
        """Test that warn_once is in exports."""
        assert "warn_once" in deprecation.__all__

    def test_deprecated_alias_in_exports(self):
        """Test that deprecated_alias is in exports."""
        assert "deprecated_alias" in deprecation.__all__
