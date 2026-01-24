"""Unit tests for parameter/config file utilities.

Note: The YAML configuration loading functions in param.py are deprecated
since YAML configuration files have been removed. However, to_hours() is
still used internally and is NOT deprecated.
"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from xbbg.io import param


class TestToHours:
    """Test time conversion utility function."""

    def test_to_hours_list(self):
        """Test converting list of numeric times."""
        result = param.to_hours([900, 1700])
        assert result == ["09:00", "17:00"]

    def test_to_hours_single_int(self):
        """Test converting single integer time."""
        result = param.to_hours(901)
        assert result == "09:01"

    def test_to_hours_single_float(self):
        """Test converting single float time."""
        result = param.to_hours(1700.0)
        assert result == "17:00"

    def test_to_hours_string(self):
        """Test converting string (should return as-is)."""
        result = param.to_hours("XYZ")
        assert result == "XYZ"

    def test_to_hours_midnight(self):
        """Test converting midnight time."""
        result = param.to_hours(0)
        assert result == "00:00"

    def test_to_hours_end_of_day(self):
        """Test converting end of day time."""
        result = param.to_hours(2359)
        assert result == "23:59"

    def test_to_hours_with_minutes(self):
        """Test converting time with minutes."""
        result = param.to_hours(930)
        assert result == "09:30"

    def test_to_hours_nested_list(self):
        """Test converting nested list."""
        result = param.to_hours([[900, 1700], [930, 1630]])
        assert result == [["09:00", "17:00"], ["09:30", "16:30"]]


class TestConfigFiles:
    """Test config file location utility (deprecated)."""

    def test_config_files_returns_empty_list(self):
        """Test that config_files returns an empty list (deprecated)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = param.config_files("test_cat")
        assert isinstance(result, list)
        assert result == []

    def test_config_files_deprecation_warning(self):
        """Test that config_files raises DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="config_files.*deprecated"):
            param.config_files("test_cat")


class TestLoadConfig:
    """Test config loading utility (deprecated)."""

    def test_load_config_returns_empty_dataframe(self):
        """Test that load_config returns an empty DataFrame (deprecated)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = param.load_config("test_cat")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_load_config_deprecation_warning(self):
        """Test that load_config raises DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="load_config.*deprecated"):
            param.load_config("test_cat")


class TestLoadYaml:
    """Test YAML loading utility (deprecated)."""

    def test_load_yaml_returns_empty_series(self):
        """Test that load_yaml returns an empty Series (deprecated)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = param.load_yaml("test.yml")
        assert isinstance(result, pd.Series)
        assert result.empty

    def test_load_yaml_deprecation_warning(self):
        """Test that load_yaml raises DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="load_yaml.*deprecated"):
            param.load_yaml("test.yml")
