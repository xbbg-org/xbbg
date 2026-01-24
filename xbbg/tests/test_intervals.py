"""Unit tests for trading session interval utilities.

Tests all interval utilities in xbbg/core/config/intervals.py including:
- Session dataclass
- SessNA constant
- get_interval() function for various session types
- shift_time() function
- Intervals class methods (market_open, market_close, market_normal, market_exact)
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from xbbg.core.config.intervals import (
    Intervals,
    Session,
    SessNA,
    get_interval,
    shift_time,
)


class TestSession:
    """Test Session dataclass."""

    def test_session_creation(self):
        """Test creating a Session instance."""
        session = Session(start_time="09:00", end_time="16:00")
        assert session.start_time == "09:00"
        assert session.end_time == "16:00"

    def test_session_is_frozen(self):
        """Test that Session is immutable (frozen)."""
        session = Session(start_time="09:00", end_time="16:00")
        with pytest.raises(AttributeError):
            session.start_time = "10:00"

    def test_session_with_none_values(self):
        """Test Session with None values."""
        session = Session(start_time=None, end_time=None)
        assert session.start_time is None
        assert session.end_time is None

    def test_session_equality(self):
        """Test Session equality comparison."""
        session1 = Session(start_time="09:00", end_time="16:00")
        session2 = Session(start_time="09:00", end_time="16:00")
        assert session1 == session2

    def test_session_inequality(self):
        """Test Session inequality comparison."""
        session1 = Session(start_time="09:00", end_time="16:00")
        session2 = Session(start_time="09:30", end_time="16:00")
        assert session1 != session2


class TestSessNA:
    """Test SessNA constant."""

    def test_sess_na_is_session(self):
        """Test that SessNA is a Session instance."""
        assert isinstance(SessNA, Session)

    def test_sess_na_has_none_values(self):
        """Test that SessNA has None for both times."""
        assert SessNA.start_time is None
        assert SessNA.end_time is None

    def test_sess_na_equality(self):
        """Test SessNA equality with equivalent Session."""
        assert SessNA == Session(None, None)


class TestShiftTime:
    """Test shift_time() function."""

    def test_shift_time_positive_minutes(self):
        """Test shifting time forward by positive minutes."""
        result = shift_time("09:00", 30)
        assert result == "09:30"

    def test_shift_time_negative_minutes(self):
        """Test shifting time backward by negative minutes."""
        result = shift_time("16:00", -30)
        assert result == "15:30"

    def test_shift_time_zero_minutes(self):
        """Test shifting time by zero minutes."""
        result = shift_time("12:00", 0)
        assert result == "12:00"

    def test_shift_time_crosses_hour(self):
        """Test shifting time that crosses an hour boundary."""
        result = shift_time("09:45", 30)
        assert result == "10:15"

    def test_shift_time_large_shift(self):
        """Test shifting time by more than an hour."""
        result = shift_time("09:00", 90)
        assert result == "10:30"

    def test_shift_time_format(self):
        """Test that shift_time returns HH:MM format."""
        result = shift_time("09:00", 5)
        assert len(result) == 5
        assert result[2] == ":"


class TestIntervalsClass:
    """Test Intervals class."""

    def _create_mock_exch_info(self, sessions):
        """Create a mock exchange info Series."""
        return pd.Series(sessions)

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_intervals_initialization(self, mock_exch_info):
        """Test Intervals class initialization."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:00", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        assert intervals.ticker == "AAPL US Equity"
        mock_exch_info.assert_called_once()

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_open(self, mock_exch_info):
        """Test market_open() method."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_open("day", 30)
        assert result.start_time == "09:30"
        assert result.end_time == "10:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_open_session_not_found(self, mock_exch_info):
        """Test market_open() returns SessNA when session not found."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_open("night", 30)
        assert result is SessNA

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_close(self, mock_exch_info):
        """Test market_close() method."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_close("day", 30)
        assert result.end_time == "16:00"
        # Start time should be 30 mins before close + 1 min offset
        assert result.start_time == "15:31"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_close_session_not_found(self, mock_exch_info):
        """Test market_close() returns SessNA when session not found."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_close("night", 30)
        assert result is SessNA

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_normal(self, mock_exch_info):
        """Test market_normal() method."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_normal("day", 30, 20)
        # Start: 09:30 + 30 + 1 = 10:01
        # End: 16:00 - 20 = 15:40
        assert result.start_time == "10:01"
        assert result.end_time == "15:40"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_normal_session_not_found(self, mock_exch_info):
        """Test market_normal() returns SessNA when session not found."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_normal("night", 30, 20)
        assert result is SessNA

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_normal_invalid_range(self, mock_exch_info):
        """Test market_normal() returns SessNA when range is invalid."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        # Request too much time from both ends
        result = intervals.market_normal("day", 300, 300)
        assert result is SessNA

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_exact(self, mock_exch_info):
        """Test market_exact() method."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "allday": ["04:00", "20:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="ES1 Index")
        # Use times within session bounds (04:00 to 20:00)
        result = intervals.market_exact("allday", "0900", "1500")
        # Should return the exact times within session bounds
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.start_time == "09:00"
        assert result.end_time == "15:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_market_exact_session_not_found(self, mock_exch_info):
        """Test market_exact() returns SessNA when session not found."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        intervals = Intervals(ticker="AAPL US Equity")
        result = intervals.market_exact("night", "2130", "2230")
        assert result is SessNA


class TestGetInterval:
    """Test get_interval() function."""

    def _create_mock_exch_info(self, sessions):
        """Create a mock exchange info Series."""
        return pd.Series(sessions)

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_basic_session(self, mock_exch_info):
        """Test get_interval() with basic session name."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        result = get_interval("AAPL US Equity", "day")
        assert result.start_time == "09:30"
        assert result.end_time == "16:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_allday_session(self, mock_exch_info):
        """Test get_interval() with allday session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "allday": ["04:00", "20:00"],
                "tz": "America/New_York",
            }
        )
        result = get_interval("AAPL US Equity", "allday")
        assert result.start_time == "04:00"
        assert result.end_time == "20:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_compound_open(self, mock_exch_info):
        """Test get_interval() with compound open session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        result = get_interval("AAPL US Equity", "day_open_30")
        assert result.start_time == "09:30"
        assert result.end_time == "10:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_compound_close(self, mock_exch_info):
        """Test get_interval() with compound close session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        result = get_interval("AAPL US Equity", "day_close_20")
        assert result.end_time == "16:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_compound_normal(self, mock_exch_info):
        """Test get_interval() with compound normal session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        result = get_interval("AAPL US Equity", "day_normal_30_20")
        assert result.start_time == "10:01"
        assert result.end_time == "15:40"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_session_not_found_raises_error(self, mock_exch_info):
        """Test get_interval() raises ValueError for unknown bare session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        # Bare session names (without underscore) should raise ValueError
        with pytest.raises(ValueError, match="is not defined"):
            get_interval("AAPL US Equity", "night")

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_compound_base_not_found_returns_sessna(self, mock_exch_info):
        """Test get_interval() returns SessNA for compound with missing base."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        # 'night' base session doesn't exist
        result = get_interval("AAPL US Equity", "night_open_30")
        assert result is SessNA

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_invalid_session_type_raises_error(self, mock_exch_info):
        """Test get_interval() raises ValueError for invalid session type."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        with pytest.raises(ValueError, match="not supported"):
            get_interval("AAPL US Equity", "day_invalid_30")


class TestGetIntervalEdgeCases:
    """Test edge cases for get_interval() function."""

    def _create_mock_exch_info(self, sessions):
        """Create a mock exchange info Series."""
        return pd.Series(sessions)

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_am_session(self, mock_exch_info):
        """Test get_interval() with AM session (Asian markets)."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "am": ["09:00", "12:00"],
                "pm": ["13:00", "15:00"],
                "tz": "Asia/Tokyo",
            }
        )
        result = get_interval("7974 JP Equity", "am")
        assert result.start_time == "09:00"
        assert result.end_time == "12:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_pm_session(self, mock_exch_info):
        """Test get_interval() with PM session (Asian markets)."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "am": ["09:00", "12:00"],
                "pm": ["13:00", "15:00"],
                "tz": "Asia/Tokyo",
            }
        )
        result = get_interval("7974 JP Equity", "pm")
        assert result.start_time == "13:00"
        assert result.end_time == "15:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_am_open(self, mock_exch_info):
        """Test get_interval() with AM open session."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "am": ["09:30", "12:00"],
                "tz": "Asia/Hong_Kong",
            }
        )
        result = get_interval("700 HK Equity", "am_open_30")
        assert result.start_time == "09:30"
        assert result.end_time == "10:00"

    @patch("xbbg.core.config.intervals.const.exch_info")
    def test_get_interval_with_kwargs(self, mock_exch_info):
        """Test get_interval() passes kwargs to exch_info."""
        mock_exch_info.return_value = self._create_mock_exch_info(
            {
                "day": ["09:30", "16:00"],
                "tz": "America/New_York",
            }
        )
        get_interval("ES1 Index", "day", ref="ES1 Index")
        # Verify kwargs were passed
        mock_exch_info.assert_called_with(ticker="ES1 Index", ref="ES1 Index")


class TestStandardSessions:
    """Test _get_standard_sessions() function."""

    def test_standard_sessions_is_set(self):
        """Test that STANDARD_SESSIONS is a set."""
        from xbbg.core.config.intervals import STANDARD_SESSIONS

        assert isinstance(STANDARD_SESSIONS, set)

    def test_standard_sessions_contains_expected_values(self):
        """Test that STANDARD_SESSIONS contains the expected session names."""
        from xbbg.core.config.intervals import STANDARD_SESSIONS

        expected = {"allday", "day", "am", "pm", "pre", "post", "night"}
        assert expected == STANDARD_SESSIONS
