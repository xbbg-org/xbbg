"""Unit tests for timezone utility functions."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from xbbg.core.utils import timezone


class TestGetTz:
    """Test get_tz function."""

    def test_get_tz_none(self):
        """Test get_tz with None."""
        result = timezone.get_tz(None)
        assert result is not None  # Returns DEFAULT_TZ

    def test_get_tz_shortcut_ny(self):
        """Test get_tz with NY shortcut."""
        result = timezone.get_tz('NY')
        assert result == 'America/New_York'

    def test_get_tz_timezone_class(self):
        """Test get_tz with TimeZone class attribute."""
        result = timezone.get_tz(timezone.TimeZone.NY)
        assert result == 'America/New_York'

    def test_get_tz_all_shortcuts(self):
        """Test all timezone shortcuts."""
        shortcuts = {
            'NY': 'America/New_York',
            'AU': 'Australia/Sydney',
            'JP': 'Asia/Tokyo',
            'SK': 'Asia/Seoul',
            'HK': 'Asia/Hong_Kong',
            'SH': 'Asia/Shanghai',
            'TW': 'Asia/Taipei',
            'SG': 'Asia/Singapore',
            'IN': 'Asia/Calcutta',
            'DB': 'Asia/Dubai',
            'UK': 'Europe/London',
        }
        for shortcut, expected in shortcuts.items():
            result = timezone.get_tz(shortcut)
            assert result == expected

    @patch('xbbg.const.exch_info')
    def test_get_tz_from_ticker(self, mock_exch_info):
        """Test get_tz with ticker that resolves to exchange."""
        mock_exch_info.return_value = pd.Series({'tz': 'Australia/Sydney'}, index=['tz'])
        result = timezone.get_tz('BHP AU Equity')
        assert result == 'Australia/Sydney'

    @patch('xbbg.const.exch_info')
    def test_get_tz_ticker_no_exchange(self, mock_exch_info):
        """Test get_tz with ticker that has no exchange info."""
        mock_exch_info.return_value = pd.Series(dtype=object)
        result = timezone.get_tz('UNKNOWN Ticker')
        # Should return the string as-is if no exchange info
        assert result == 'UNKNOWN Ticker'

    def test_get_tz_direct_timezone_string(self):
        """Test get_tz with direct timezone string."""
        result = timezone.get_tz('Europe/London')
        assert result == 'Europe/London'


class TestTzConvert:
    """Test tz_convert function."""

    def test_tz_convert_with_tz_aware_timestamp(self):
        """Test converting timezone-aware timestamp."""
        dt = pd.Timestamp('2018-09-10 16:00', tz='Asia/Hong_Kong')
        result = timezone.tz_convert(dt, to_tz='NY')
        assert '2018-09-10' in result
        assert '-04:00' in result or '-05:00' in result  # EDT or EST

    def test_tz_convert_with_naive_timestamp(self):
        """Test converting timezone-naive timestamp."""
        dt = pd.Timestamp('2018-01-10 16:00')
        result = timezone.tz_convert(dt, to_tz='HK', from_tz='NY')
        assert '2018-01-11' in result  # Next day due to timezone difference
        assert '+08:00' in result

    def test_tz_convert_with_string(self):
        """Test converting string datetime."""
        result = timezone.tz_convert('2018-09-10 15:00', to_tz='NY', from_tz='JP')
        assert '2018-09-10' in result
        assert '-04:00' in result or '-05:00' in result

    def test_tz_convert_none_from_tz(self):
        """Test converting with None from_tz."""
        dt = pd.Timestamp('2018-09-10 16:00')
        result = timezone.tz_convert(dt, to_tz='NY', from_tz=None)
        # Should use DEFAULT_TZ
        assert isinstance(result, str)

    def test_tz_convert_same_timezone(self):
        """Test converting to same timezone."""
        dt = pd.Timestamp('2018-09-10 16:00', tz='America/New_York')
        result = timezone.tz_convert(dt, to_tz='NY')
        assert '2018-09-10' in result
        assert 'America/New_York' in result or '-04:00' in result or '-05:00' in result

    def test_tz_convert_shortcut_to_shortcut(self):
        """Test converting between shortcuts."""
        dt = pd.Timestamp('2018-09-10 16:00', tz='Asia/Tokyo')
        result = timezone.tz_convert(dt, to_tz='NY', from_tz='JP')
        assert isinstance(result, str)
        assert '2018-09-10' in result or '2018-09-09' in result  # Could be previous day

    def test_tz_convert_date_object(self):
        """Test converting date object."""
        from datetime import date
        dt = date(2018, 9, 10)
        result = timezone.tz_convert(dt, to_tz='NY', from_tz='UTC')
        assert isinstance(result, str)
        # Date conversion may shift to previous day due to timezone
        assert '2018-09-09' in result or '2018-09-10' in result


class TestTimeZone:
    """Test TimeZone class constants."""

    def test_timezone_constants(self):
        """Test all TimeZone constants are strings."""
        assert isinstance(timezone.TimeZone.NY, str)
        assert isinstance(timezone.TimeZone.AU, str)
        assert isinstance(timezone.TimeZone.JP, str)
        assert isinstance(timezone.TimeZone.SK, str)
        assert isinstance(timezone.TimeZone.HK, str)
        assert isinstance(timezone.TimeZone.SH, str)
        assert isinstance(timezone.TimeZone.TW, str)
        assert isinstance(timezone.TimeZone.SG, str)
        assert isinstance(timezone.TimeZone.IN, str)
        assert isinstance(timezone.TimeZone.DB, str)
        assert isinstance(timezone.TimeZone.UK, str)

