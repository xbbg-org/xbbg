"""Unit tests for utility functions that don't require Bloomberg connections."""

from __future__ import annotations

import datetime
from unittest.mock import Mock, patch

import pandas as pd

from xbbg.core.utils import utils


class TestFlatten:
    """Test flatten utility function."""

    def test_flatten_string(self):
        """Test flattening a string."""
        assert utils.flatten('abc') == ['abc']

    def test_flatten_int(self):
        """Test flattening an integer."""
        assert utils.flatten(1) == [1]

    def test_flatten_float(self):
        """Test flattening a float."""
        assert utils.flatten(1.5) == [1.5]

    def test_flatten_nested_list(self):
        """Test flattening nested lists."""
        assert utils.flatten(['ab', 'cd', ['xy', 'zz']]) == ['ab', 'cd', 'xy', 'zz']

    def test_flatten_with_maps(self):
        """Test flattening with mapping."""
        result = utils.flatten(['ab', ['xy', 'zz']], maps={'xy': '0x'})
        assert result == ['ab', '0x', 'zz']

    def test_flatten_with_unique(self):
        """Test flattening with unique flag."""
        result = utils.flatten(['a', 'b', 'a', ['c', 'b']], unique=True)
        assert set(result) == {'a', 'b', 'c'}
        assert len(result) == 3

    def test_flatten_none(self):
        """Test flattening None."""
        assert utils.flatten(None) == []

    def test_flatten_tuple(self):
        """Test flattening tuples."""
        assert utils.flatten(('a', ('b', 'c'))) == ['a', 'b', 'c']

    def test_flatten_deeply_nested(self):
        """Test flattening deeply nested structures."""
        result = utils.flatten([1, [2, [3, [4, 5]]]])
        assert result == [1, 2, 3, 4, 5]


class TestFmtDt:
    """Test date formatting utility function."""

    def test_fmt_dt_string_date(self):
        """Test formatting string date."""
        assert utils.fmt_dt('2018-12-31') == '2018-12-31'

    def test_fmt_dt_string_month(self):
        """Test formatting string month (should default to first day)."""
        assert utils.fmt_dt('2018-12') == '2018-12-01'

    def test_fmt_dt_custom_format(self):
        """Test formatting with custom format."""
        assert utils.fmt_dt('2018-12-31', fmt='%Y%m%d') == '20181231'

    def test_fmt_dt_timestamp(self):
        """Test formatting pd.Timestamp."""
        ts = pd.Timestamp('2018-12-31')
        assert utils.fmt_dt(ts) == '2018-12-31'

    def test_fmt_dt_date_object(self):
        """Test formatting datetime.date object."""
        dt = datetime.date(2018, 12, 31)
        assert utils.fmt_dt(dt) == '2018-12-31'


class TestCurTime:
    """Test current time utility function."""

    @patch('pandas.Timestamp')
    def test_cur_time_date(self, mock_timestamp):
        """Test current time as date string."""
        mock_timestamp.return_value.strftime.return_value = '2024-01-15'
        mock_timestamp.return_value = Mock()
        mock_timestamp.return_value.strftime = Mock(return_value='2024-01-15')
        result = utils.cur_time(typ='date')
        assert result == '2024-01-15'

    @patch('pandas.Timestamp')
    def test_cur_time_time(self, mock_timestamp):
        """Test current time as time string."""
        mock_ts = Mock()
        mock_ts.strftime.return_value = '2024-01-15 10:30:00'
        mock_timestamp.return_value = mock_ts
        result = utils.cur_time(typ='time')
        assert result == '2024-01-15 10:30:00'

    @patch('pandas.Timestamp')
    def test_cur_time_time_path(self, mock_timestamp):
        """Test current time as path string."""
        mock_ts = Mock()
        mock_ts.strftime.return_value = '2024-01-15/10-30-00'
        mock_timestamp.return_value = mock_ts
        result = utils.cur_time(typ='time_path')
        assert result == '2024-01-15/10-30-00'

    def test_cur_time_raw(self):
        """Test current time as raw Timestamp."""
        result = utils.cur_time(typ='raw')
        assert isinstance(result, pd.Timestamp)

    @patch('pandas.Timestamp')
    def test_cur_time_empty_type(self, mock_timestamp):
        """Test current time with empty type (returns date)."""
        mock_ts = Mock()
        mock_ts.date.return_value = datetime.date(2024, 1, 15)
        mock_timestamp.return_value = mock_ts
        result = utils.cur_time(typ='')
        assert result == datetime.date(2024, 1, 15)

    @patch('pandas.Timestamp')
    def test_cur_time_with_timezone(self, mock_timestamp):
        """Test current time with timezone."""
        mock_ts = Mock()
        mock_timestamp.return_value = mock_ts
        utils.cur_time(typ='raw', tz='Europe/London')
        mock_timestamp.assert_called_with('now', tz='Europe/London')


class TestToStr:
    """Test dict to string conversion utility function."""

    def test_to_str_simple_dict(self):
        """Test converting simple dict to string."""
        test_dict = {'b': 1, 'a': 0, 'c': 2}
        result = utils.to_str(test_dict)
        assert 'b=1' in result
        assert 'a=0' in result
        assert 'c=2' in result

    def test_to_str_with_private_keys(self):
        """Test converting dict with private keys."""
        test_dict = {'b': 1, 'a': 0, '_d': 3}
        result = utils.to_str(test_dict)
        assert '_d=3' not in result
        assert 'b=1' in result

    def test_to_str_public_only_false(self):
        """Test converting dict with public_only=False."""
        test_dict = {'b': 1, '_d': 3}
        result = utils.to_str(test_dict, public_only=False)
        assert '_d=3' in result

    def test_to_str_custom_separator(self):
        """Test converting dict with custom separator."""
        test_dict = {'a': 1, 'b': 2}
        result = utils.to_str(test_dict, sep='|')
        assert '|' in result
        assert ',' not in result

    def test_to_str_custom_format(self):
        """Test converting dict with custom format."""
        test_dict = {'a': 1}
        result = utils.to_str(test_dict, fmt='{key}:{value}')
        assert 'a:1' in result

    def test_to_str_nested_dict(self):
        """Test converting nested dict."""
        test_dict = {'a': 1, 'nested': {'b': 2}}
        result = utils.to_str(test_dict)
        assert 'a=1' in result
        assert 'b=2' in result


class TestNormalizeTickers:
    """Test ticker normalization utility function."""

    def test_normalize_tickers_string(self):
        """Test normalizing single ticker string."""
        result = utils.normalize_tickers('AAPL US Equity')
        assert result == ['AAPL US Equity']

    def test_normalize_tickers_list(self):
        """Test normalizing ticker list."""
        tickers = ['AAPL US Equity', 'MSFT US Equity']
        result = utils.normalize_tickers(tickers)
        assert result == tickers


class TestNormalizeFlds:
    """Test field normalization utility function."""

    def test_normalize_flds_string(self):
        """Test normalizing single field string."""
        result = utils.normalize_flds('PX_LAST')
        assert result == ['PX_LAST']

    def test_normalize_flds_list(self):
        """Test normalizing field list."""
        flds = ['PX_LAST', 'VOLUME']
        result = utils.normalize_flds(flds)
        assert result == flds

    def test_normalize_flds_none(self):
        """Test normalizing None fields."""
        result = utils.normalize_flds(None)
        assert result == []


class TestCheckEmptyResult:
    """Test empty result checking utility function."""

    def test_check_empty_result_empty_dataframe(self):
        """Test checking empty DataFrame."""
        df = pd.DataFrame()
        assert utils.check_empty_result(df) is True

    def test_check_empty_result_non_empty(self):
        """Test checking non-empty DataFrame."""
        df = pd.DataFrame({'a': [1, 2]})
        assert utils.check_empty_result(df) is False

    def test_check_empty_result_missing_required_cols(self):
        """Test checking DataFrame missing required columns."""
        df = pd.DataFrame({'a': [1, 2]})
        assert utils.check_empty_result(df, required_cols=['b']) is True

    def test_check_empty_result_has_required_cols(self):
        """Test checking DataFrame with required columns."""
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        assert utils.check_empty_result(df, required_cols=['a', 'b']) is False

