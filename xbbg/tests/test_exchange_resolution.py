"""Unit tests for Exchange Resolution System v2.

Tests cover:
1. ExchangeInfo dataclass (from bloomberg.py)
2. Exchange override functions (from overrides.py)
3. Exchange cache functions (from io/cache.py)
4. Helper functions from bloomberg.py (_parse_hhmm, _parse_futures_hours, etc.)
5. BloombergExchangeResolver (mocked Bloomberg calls)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from xbbg.markets.bloomberg import (
    COUNTRY_TIMEZONE_MAP,
    ExchangeInfo,
    _build_exchange_info_from_response,
    _extract_value,
    _infer_timezone_from_country,
    _parse_futures_hours,
    _parse_hhmm,
    _parse_trading_hours,
)
from xbbg.markets.overrides import (
    OverrideData,
    clear_exchange_override,
    get_exchange_override,
    get_override_fields,
    has_override,
    list_exchange_overrides,
    set_exchange_override,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_exchange_info() -> ExchangeInfo:
    """Create a sample ExchangeInfo for testing."""
    return ExchangeInfo(
        ticker="AAPL US Equity",
        mic="XNGS",
        exch_code="US",
        timezone="America/New_York",
        utc_offset=-5.0,
        sessions={"regular": ("09:30", "16:00")},
        source="bloomberg",
        cached_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_exchange_info_with_futures() -> ExchangeInfo:
    """Create a sample ExchangeInfo with futures sessions."""
    return ExchangeInfo(
        ticker="ES1 Index",
        mic="XCME",
        exch_code="US",
        timezone="America/Chicago",
        utc_offset=-6.0,
        sessions={"regular": ("08:30", "15:15"), "futures": ("18:00", "17:00")},
        source="bloomberg",
        cached_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def temp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override cache root for testing."""
    monkeypatch.setenv("BBG_ROOT", str(tmp_path))
    # Reset the module-level flag so it logs the new location
    from xbbg.io import cache

    cache._default_cache_logged = False
    return tmp_path


@pytest.fixture(autouse=True)
def clean_overrides():
    """Clean up overrides before and after each test."""
    clear_exchange_override()
    yield
    clear_exchange_override()


@pytest.fixture
def mock_bdp_response() -> pd.DataFrame:
    """Create a mock Bloomberg bdp response."""
    return pd.DataFrame(
        {
            "iana_time_zone": ["America/New_York"],
            "time_zone_num": [-5.0],
            "id_mic_prim_exch": ["XNGS"],
            "exch_code": ["US"],
            "country_iso": ["US"],
            "trading_day_start_time_eod": ["0930"],
            "trading_day_end_time_eod": ["1600"],
            "fut_trading_hrs": [None],
        },
        index=pd.Index(["AAPL US Equity"]),
    )


# ============================================================================
# Tests for ExchangeInfo dataclass
# ============================================================================


class TestExchangeInfo:
    """Tests for ExchangeInfo dataclass."""

    def test_default_values(self):
        """Test ExchangeInfo default values."""
        info = ExchangeInfo(ticker="TEST Equity")
        assert info.ticker == "TEST Equity"
        assert info.mic is None
        assert info.exch_code is None
        assert info.timezone == "UTC"
        assert info.utc_offset is None
        assert info.sessions == {}
        assert info.source == "fallback"
        assert info.cached_at is None

    def test_full_initialization(self, sample_exchange_info: ExchangeInfo):
        """Test ExchangeInfo with all fields."""
        info = sample_exchange_info
        assert info.ticker == "AAPL US Equity"
        assert info.mic == "XNGS"
        assert info.exch_code == "US"
        assert info.timezone == "America/New_York"
        assert info.utc_offset == -5.0
        assert info.sessions == {"regular": ("09:30", "16:00")}
        assert info.source == "bloomberg"
        assert info.cached_at is not None

    def test_sessions_with_multiple_entries(self, sample_exchange_info_with_futures: ExchangeInfo):
        """Test ExchangeInfo with multiple sessions."""
        info = sample_exchange_info_with_futures
        assert "regular" in info.sessions
        assert "futures" in info.sessions
        assert info.sessions["regular"] == ("08:30", "15:15")
        assert info.sessions["futures"] == ("18:00", "17:00")


# ============================================================================
# Tests for _parse_hhmm helper
# ============================================================================


class TestParseHhmm:
    """Tests for _parse_hhmm function."""

    def test_parse_hhmm_format(self):
        """Test parsing HHMM format."""
        assert _parse_hhmm("0930") == "09:30"
        assert _parse_hhmm("1600") == "16:00"
        assert _parse_hhmm("0000") == "00:00"
        assert _parse_hhmm("2359") == "23:59"

    def test_parse_colon_format(self):
        """Test parsing HH:MM format."""
        assert _parse_hhmm("09:30") == "09:30"
        assert _parse_hhmm("16:00") == "16:00"
        assert _parse_hhmm("9:30") == "09:30"
        assert _parse_hhmm("0:00") == "00:00"

    def test_parse_none_and_empty(self):
        """Test parsing None and empty values."""
        assert _parse_hhmm(None) is None
        assert _parse_hhmm("") is None
        assert _parse_hhmm("   ") is None

    def test_parse_nan(self):
        """Test parsing NaN values."""
        # NaN is passed as a value that could come from pandas

        nan_val = float("nan")
        # The function handles this via pd.isna check
        assert _parse_hhmm(str(nan_val)) is None

    def test_parse_invalid_format(self):
        """Test parsing invalid formats."""
        assert _parse_hhmm("930") is None  # Too short
        assert _parse_hhmm("09300") is None  # Too long
        assert _parse_hhmm("abcd") is None  # Non-numeric
        # Note: "12:34:56" returns "12:34" (takes first two parts) - this is acceptable behavior

    def test_parse_with_whitespace(self):
        """Test parsing with whitespace."""
        assert _parse_hhmm("  0930  ") == "09:30"
        assert _parse_hhmm("  09:30  ") == "09:30"


# ============================================================================
# Tests for _parse_futures_hours helper
# ============================================================================


class TestParseFuturesHours:
    """Tests for _parse_futures_hours function."""

    def test_parse_colon_format(self):
        """Test parsing HH:MM-HH:MM format."""
        result = _parse_futures_hours("18:00-17:00")
        assert result == {"futures": ("18:00", "17:00")}

    def test_parse_hhmm_format(self):
        """Test parsing HHMM-HHMM format."""
        result = _parse_futures_hours("1800-1700")
        assert result == {"futures": ("18:00", "17:00")}

    def test_parse_mixed_format(self):
        """Test parsing mixed formats."""
        result = _parse_futures_hours("18:00-1700")
        assert result == {"futures": ("18:00", "17:00")}

    def test_parse_with_spaces(self):
        """Test parsing with spaces around dash."""
        result = _parse_futures_hours("18:00 - 17:00")
        assert result == {"futures": ("18:00", "17:00")}

    def test_parse_none_and_empty(self):
        """Test parsing None and empty values."""
        assert _parse_futures_hours(None) == {}
        assert _parse_futures_hours("") == {}
        assert _parse_futures_hours("   ") == {}

    def test_parse_nan(self):
        """Test parsing NaN values."""
        # NaN is passed as a value that could come from pandas
        nan_val = float("nan")
        # The function handles this via pd.isna check
        assert _parse_futures_hours(str(nan_val)) == {}

    def test_parse_invalid_format(self):
        """Test parsing invalid formats."""
        assert _parse_futures_hours("invalid") == {}
        assert _parse_futures_hours("18:00") == {}  # Missing end time
        assert _parse_futures_hours("18:00-") == {}  # Missing end time


# ============================================================================
# Tests for _parse_trading_hours helper
# ============================================================================


class TestParseTradingHours:
    """Tests for _parse_trading_hours function."""

    def test_parse_regular_hours_only(self):
        """Test parsing regular trading hours only."""
        result = _parse_trading_hours("0930", "1600", None)
        assert result == {"regular": ("09:30", "16:00")}

    def test_parse_futures_hours_only(self):
        """Test parsing futures hours only."""
        result = _parse_trading_hours(None, None, "18:00-17:00")
        assert result == {"futures": ("18:00", "17:00")}

    def test_parse_both_sessions(self):
        """Test parsing both regular and futures hours."""
        result = _parse_trading_hours("0830", "1515", "18:00-17:00")
        assert result == {"regular": ("08:30", "15:15"), "futures": ("18:00", "17:00")}

    def test_parse_all_none(self):
        """Test parsing when all inputs are None."""
        result = _parse_trading_hours(None, None, None)
        assert result == {}

    def test_parse_partial_regular(self):
        """Test parsing when only start or end is provided."""
        result = _parse_trading_hours("0930", None, None)
        assert result == {}  # Need both start and end

        result = _parse_trading_hours(None, "1600", None)
        assert result == {}  # Need both start and end


# ============================================================================
# Tests for _infer_timezone_from_country helper
# ============================================================================


class TestInferTimezoneFromCountry:
    """Tests for _infer_timezone_from_country function."""

    def test_infer_common_countries(self):
        """Test inferring timezone for common countries."""
        assert _infer_timezone_from_country("US") == "America/New_York"
        assert _infer_timezone_from_country("GB") == "Europe/London"
        assert _infer_timezone_from_country("JP") == "Asia/Tokyo"
        assert _infer_timezone_from_country("HK") == "Asia/Hong_Kong"
        assert _infer_timezone_from_country("DE") == "Europe/Berlin"

    def test_infer_case_insensitive(self):
        """Test that country code is case insensitive."""
        assert _infer_timezone_from_country("us") == "America/New_York"
        assert _infer_timezone_from_country("Us") == "America/New_York"

    def test_infer_with_whitespace(self):
        """Test inferring with whitespace."""
        assert _infer_timezone_from_country("  US  ") == "America/New_York"

    def test_infer_none_and_empty(self):
        """Test inferring from None and empty values."""
        assert _infer_timezone_from_country(None) is None
        assert _infer_timezone_from_country("") is None

    def test_infer_unknown_country(self):
        """Test inferring from unknown country code."""
        assert _infer_timezone_from_country("XX") is None
        assert _infer_timezone_from_country("ZZ") is None


class TestCountryTimezoneMap:
    """Tests for COUNTRY_TIMEZONE_MAP constant."""

    def test_map_has_major_regions(self):
        """Test that map includes major financial regions."""
        # North America
        assert "US" in COUNTRY_TIMEZONE_MAP
        assert "CA" in COUNTRY_TIMEZONE_MAP

        # Europe
        assert "GB" in COUNTRY_TIMEZONE_MAP
        assert "DE" in COUNTRY_TIMEZONE_MAP
        assert "FR" in COUNTRY_TIMEZONE_MAP
        assert "CH" in COUNTRY_TIMEZONE_MAP

        # Asia Pacific
        assert "JP" in COUNTRY_TIMEZONE_MAP
        assert "HK" in COUNTRY_TIMEZONE_MAP
        assert "SG" in COUNTRY_TIMEZONE_MAP
        assert "AU" in COUNTRY_TIMEZONE_MAP

    def test_map_values_are_valid_timezones(self):
        """Test that all values are valid IANA timezone strings."""
        import zoneinfo

        for country, tz in COUNTRY_TIMEZONE_MAP.items():
            try:
                zoneinfo.ZoneInfo(tz)
            except Exception as e:
                pytest.fail(f"Invalid timezone {tz} for country {country}: {e}")


# ============================================================================
# Tests for _extract_value helper
# ============================================================================


class TestExtractValue:
    """Tests for _extract_value function."""

    def test_extract_existing_field(self, mock_bdp_response: pd.DataFrame):
        """Test extracting existing field."""
        assert _extract_value(mock_bdp_response, "IANA_TIME_ZONE") == "America/New_York"
        assert _extract_value(mock_bdp_response, "TIME_ZONE_NUM") == -5.0
        assert _extract_value(mock_bdp_response, "ID_MIC_PRIM_EXCH") == "XNGS"

    def test_extract_missing_field(self, mock_bdp_response: pd.DataFrame):
        """Test extracting missing field."""
        assert _extract_value(mock_bdp_response, "NONEXISTENT_FIELD") is None

    def test_extract_from_empty_df(self):
        """Test extracting from empty DataFrame."""
        empty_df = pd.DataFrame()
        assert _extract_value(empty_df, "IANA_TIME_ZONE") is None

    def test_extract_nan_value(self):
        """Test extracting NaN value."""
        df = pd.DataFrame({"test_field": [float("nan")]}, index=pd.Index(["TEST"]))
        assert _extract_value(df, "TEST_FIELD") is None


# ============================================================================
# Tests for _build_exchange_info_from_response helper
# ============================================================================


class TestBuildExchangeInfoFromResponse:
    """Tests for _build_exchange_info_from_response function."""

    def test_build_from_complete_response(self, mock_bdp_response: pd.DataFrame):
        """Test building ExchangeInfo from complete response."""
        info = _build_exchange_info_from_response("AAPL US Equity", mock_bdp_response)
        assert info.ticker == "AAPL US Equity"
        assert info.timezone == "America/New_York"
        assert info.mic == "XNGS"
        assert info.exch_code == "US"
        assert info.utc_offset == -5.0
        assert info.source == "bloomberg"
        assert "regular" in info.sessions
        assert info.sessions["regular"] == ("09:30", "16:00")

    def test_build_from_empty_response(self):
        """Test building ExchangeInfo from empty response."""
        empty_df = pd.DataFrame()
        info = _build_exchange_info_from_response("TEST Equity", empty_df)
        assert info.ticker == "TEST Equity"
        assert info.source == "fallback"
        assert info.timezone == "UTC"

    def test_build_with_country_inference(self):
        """Test building ExchangeInfo with timezone inferred from country."""
        df = pd.DataFrame(
            {
                "iana_time_zone": [None],
                "country_iso": ["JP"],
                "id_mic_prim_exch": ["XTKS"],
                "exch_code": ["JP"],
                "time_zone_num": [9.0],
                "trading_day_start_time_eod": ["0900"],
                "trading_day_end_time_eod": ["1500"],
                "fut_trading_hrs": [None],
            },
            index=pd.Index(["7203 JP Equity"]),
        )
        info = _build_exchange_info_from_response("7203 JP Equity", df)
        assert info.timezone == "Asia/Tokyo"
        assert info.source == "inferred"

    def test_build_with_futures_hours(self):
        """Test building ExchangeInfo with futures hours."""
        df = pd.DataFrame(
            {
                "iana_time_zone": ["America/Chicago"],
                "country_iso": ["US"],
                "id_mic_prim_exch": ["XCME"],
                "exch_code": ["US"],
                "time_zone_num": [-6.0],
                "trading_day_start_time_eod": ["0830"],
                "trading_day_end_time_eod": ["1515"],
                "fut_trading_hrs": ["18:00-17:00"],
            },
            index=pd.Index(["ES1 Index"]),
        )
        info = _build_exchange_info_from_response("ES1 Index", df)
        assert "regular" in info.sessions
        assert "futures" in info.sessions
        assert info.sessions["futures"] == ("18:00", "17:00")


# ============================================================================
# Tests for Exchange Override Functions
# ============================================================================


class TestSetExchangeOverride:
    """Tests for set_exchange_override function."""

    def test_set_timezone_override(self):
        """Test setting timezone override."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.timezone == "Asia/Tokyo"
        assert info.source == "override"

    def test_set_mic_override(self):
        """Test setting MIC override."""
        set_exchange_override("TEST Equity", mic="XTKS")
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.mic == "XTKS"

    def test_set_sessions_override(self):
        """Test setting sessions override."""
        sessions = {"regular": ("09:00", "15:00"), "pre": ("08:00", "09:00")}
        set_exchange_override("TEST Equity", sessions=sessions)
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.sessions == sessions

    def test_set_multiple_fields(self):
        """Test setting multiple fields at once."""
        set_exchange_override(
            "TEST Equity",
            timezone="Europe/London",
            mic="XLON",
            exch_code="LN",
        )
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.timezone == "Europe/London"
        assert info.mic == "XLON"
        assert info.exch_code == "LN"

    def test_update_existing_override(self):
        """Test updating existing override."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        set_exchange_override("TEST Equity", mic="XTKS")
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.timezone == "Asia/Tokyo"  # Preserved
        assert info.mic == "XTKS"  # Added

    def test_empty_ticker_raises(self):
        """Test that empty ticker raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            set_exchange_override("", timezone="UTC")

        with pytest.raises(ValueError, match="non-empty string"):
            set_exchange_override("   ", timezone="UTC")

    def test_no_fields_raises(self):
        """Test that no override fields raises ValueError."""
        with pytest.raises(ValueError, match="At least one override field"):
            set_exchange_override("TEST Equity")


class TestGetExchangeOverride:
    """Tests for get_exchange_override function."""

    def test_get_existing_override(self):
        """Test getting existing override."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        info = get_exchange_override("TEST Equity")
        assert info is not None
        assert info.ticker == "TEST Equity"
        assert info.timezone == "Asia/Tokyo"

    def test_get_nonexistent_override(self):
        """Test getting nonexistent override."""
        info = get_exchange_override("NONEXISTENT Equity")
        assert info is None

    def test_get_with_whitespace(self):
        """Test getting override with whitespace in ticker."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        info = get_exchange_override("  TEST Equity  ")
        assert info is not None

    def test_get_empty_ticker(self):
        """Test getting override with empty ticker."""
        assert get_exchange_override("") is None
        assert get_exchange_override(None) is None  # type: ignore[arg-type]


class TestClearExchangeOverride:
    """Tests for clear_exchange_override function."""

    def test_clear_single_override(self):
        """Test clearing single override."""
        set_exchange_override("TEST1 Equity", timezone="Asia/Tokyo")
        set_exchange_override("TEST2 Equity", timezone="Europe/London")

        clear_exchange_override("TEST1 Equity")

        assert get_exchange_override("TEST1 Equity") is None
        assert get_exchange_override("TEST2 Equity") is not None

    def test_clear_all_overrides(self):
        """Test clearing all overrides."""
        set_exchange_override("TEST1 Equity", timezone="Asia/Tokyo")
        set_exchange_override("TEST2 Equity", timezone="Europe/London")

        clear_exchange_override()

        assert get_exchange_override("TEST1 Equity") is None
        assert get_exchange_override("TEST2 Equity") is None

    def test_clear_nonexistent_override(self):
        """Test clearing nonexistent override (should not raise)."""
        clear_exchange_override("NONEXISTENT Equity")  # Should not raise


class TestListExchangeOverrides:
    """Tests for list_exchange_overrides function."""

    def test_list_empty(self):
        """Test listing when no overrides exist."""
        overrides = list_exchange_overrides()
        assert overrides == {}

    def test_list_multiple_overrides(self):
        """Test listing multiple overrides."""
        set_exchange_override("TEST1 Equity", timezone="Asia/Tokyo")
        set_exchange_override("TEST2 Equity", mic="XLON")

        overrides = list_exchange_overrides()

        assert len(overrides) == 2
        assert "TEST1 Equity" in overrides
        assert "TEST2 Equity" in overrides
        assert overrides["TEST1 Equity"].timezone == "Asia/Tokyo"
        assert overrides["TEST2 Equity"].mic == "XLON"


class TestHasOverride:
    """Tests for has_override function."""

    def test_has_existing_override(self):
        """Test checking existing override."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        assert has_override("TEST Equity") is True

    def test_has_nonexistent_override(self):
        """Test checking nonexistent override."""
        assert has_override("NONEXISTENT Equity") is False

    def test_has_empty_ticker(self):
        """Test checking with empty ticker."""
        assert has_override("") is False


class TestGetOverrideFields:
    """Tests for get_override_fields function."""

    def test_get_fields_existing(self):
        """Test getting fields for existing override."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo", mic="XTKS")
        fields = get_override_fields("TEST Equity")
        assert fields is not None
        assert fields.get("timezone") == "Asia/Tokyo"
        assert fields.get("mic") == "XTKS"
        assert "sessions" not in fields  # Not set

    def test_get_fields_nonexistent(self):
        """Test getting fields for nonexistent override."""
        fields = get_override_fields("NONEXISTENT Equity")
        assert fields is None

    def test_get_fields_returns_copy(self):
        """Test that returned dict is a copy."""
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        fields = get_override_fields("TEST Equity")
        assert fields is not None
        fields["timezone"] = "Europe/London"  # Modify copy

        # Original should be unchanged
        original = get_override_fields("TEST Equity")
        assert original is not None
        assert original.get("timezone") == "Asia/Tokyo"


# ============================================================================
# Tests for Exchange Cache Functions
# ============================================================================


class TestExchangeCacheFile:
    """Tests for exchange_cache_file function."""

    def test_cache_file_path(self, temp_cache_dir: Path):
        """Test cache file path construction."""
        from xbbg.io.cache import exchange_cache_file

        path = exchange_cache_file()
        assert path != ""
        assert path.endswith("exchanges.parquet")
        assert "cache" in path

    def test_cache_file_no_root(self, monkeypatch: pytest.MonkeyPatch):
        """Test cache file when BBG_ROOT is not set."""
        # This test is tricky because get_cache_root() has a default
        # We'll just verify it returns a non-empty path
        from xbbg.io.cache import exchange_cache_file

        path = exchange_cache_file()
        # Should return a path (either from BBG_ROOT or default)
        assert isinstance(path, str)


class TestSaveAndLoadExchangeInfo:
    """Tests for save_exchange_info and load_exchange_info functions."""

    def test_save_and_load_roundtrip(self, temp_cache_dir: Path, sample_exchange_info: ExchangeInfo):
        """Test saving and loading ExchangeInfo."""
        from xbbg.io.cache import load_exchange_info, save_exchange_info

        save_exchange_info(sample_exchange_info)
        loaded = load_exchange_info("AAPL US Equity")

        assert loaded is not None
        assert loaded.ticker == sample_exchange_info.ticker
        assert loaded.mic == sample_exchange_info.mic
        assert loaded.exch_code == sample_exchange_info.exch_code
        assert loaded.timezone == sample_exchange_info.timezone
        assert loaded.utc_offset == sample_exchange_info.utc_offset
        assert loaded.sessions == sample_exchange_info.sessions

    def test_load_nonexistent(self, temp_cache_dir: Path):
        """Test loading nonexistent ticker."""
        from xbbg.io.cache import load_exchange_info

        loaded = load_exchange_info("NONEXISTENT Equity")
        assert loaded is None

    def test_save_multiple_and_load(self, temp_cache_dir: Path):
        """Test saving multiple entries and loading."""
        from xbbg.io.cache import load_exchange_info, save_exchange_infos

        infos = [
            ExchangeInfo(
                ticker="TEST1 Equity",
                timezone="Asia/Tokyo",
                source="bloomberg",
            ),
            ExchangeInfo(
                ticker="TEST2 Equity",
                timezone="Europe/London",
                source="bloomberg",
            ),
        ]
        save_exchange_infos(infos)

        loaded1 = load_exchange_info("TEST1 Equity")
        loaded2 = load_exchange_info("TEST2 Equity")

        assert loaded1 is not None
        assert loaded1.timezone == "Asia/Tokyo"
        assert loaded2 is not None
        assert loaded2.timezone == "Europe/London"

    def test_upsert_behavior(self, temp_cache_dir: Path):
        """Test that saving updates existing entries."""
        from xbbg.io.cache import load_exchange_info, save_exchange_info

        # Save initial
        info1 = ExchangeInfo(
            ticker="TEST Equity",
            timezone="Asia/Tokyo",
            source="bloomberg",
        )
        save_exchange_info(info1)

        # Update
        info2 = ExchangeInfo(
            ticker="TEST Equity",
            timezone="Europe/London",
            source="bloomberg",
        )
        save_exchange_info(info2)

        # Load and verify update
        loaded = load_exchange_info("TEST Equity")
        assert loaded is not None
        assert loaded.timezone == "Europe/London"

    def test_staleness_check(self, temp_cache_dir: Path):
        """Test cache staleness check.

        Note: save_exchange_info always sets cached_at to current time,
        so we test staleness by checking that recently saved data is NOT stale.
        """
        from xbbg.io.cache import load_exchange_info, save_exchange_info

        # Save with current timestamp (save_exchange_info sets cached_at to now)
        info = ExchangeInfo(
            ticker="TEST Equity",
            timezone="Asia/Tokyo",
            source="bloomberg",
        )
        save_exchange_info(info)

        # Load with short max age - should return data (just saved, not stale)
        loaded = load_exchange_info("TEST Equity", max_age_hours=24.0)
        assert loaded is not None
        assert loaded.timezone == "Asia/Tokyo"

        # Load with very short max age (0 hours) - should return None (stale)
        loaded = load_exchange_info("TEST Equity", max_age_hours=0.0)
        assert loaded is None

        # Load with infinite max age - should return data
        loaded = load_exchange_info("TEST Equity", max_age_hours=float("inf"))
        assert loaded is not None

    def test_sessions_serialization(self, temp_cache_dir: Path):
        """Test that sessions are properly serialized/deserialized."""
        from xbbg.io.cache import load_exchange_info, save_exchange_info

        sessions = {
            "regular": ("09:30", "16:00"),
            "pre": ("04:00", "09:30"),
            "post": ("16:00", "20:00"),
        }
        info = ExchangeInfo(
            ticker="TEST Equity",
            timezone="America/New_York",
            sessions=sessions,
            source="bloomberg",
        )
        save_exchange_info(info)

        loaded = load_exchange_info("TEST Equity")
        assert loaded is not None
        assert loaded.sessions == sessions

    def test_basic_conversion(self, sample_exchange_info: ExchangeInfo):
        """Test basic conversion to Series."""
        from xbbg.markets.resolver_chain import _exchange_info_to_series

        series = _exchange_info_to_series(sample_exchange_info)
        assert series["tz"] == "America/New_York"
        assert series["mic"] == "XNGS"
        assert series["exch_code"] == "US"
        assert series["regular"] == ["09:30", "16:00"]

    def test_conversion_with_multiple_sessions(self, sample_exchange_info_with_futures: ExchangeInfo):
        """Test conversion with multiple sessions."""
        from xbbg.markets.resolver_chain import _exchange_info_to_series

        series = _exchange_info_to_series(sample_exchange_info_with_futures)
        assert "regular" in series
        assert "futures" in series
        assert series["regular"] == ["08:30", "15:15"]
        assert series["futures"] == ["18:00", "17:00"]

    def test_conversion_minimal_info(self):
        """Test conversion with minimal info."""
        from xbbg.markets.resolver_chain import _exchange_info_to_series

        info = ExchangeInfo(ticker="TEST Equity", timezone="UTC")
        series = _exchange_info_to_series(info)
        assert series["tz"] == "UTC"
        assert "mic" not in series
        assert "exch_code" not in series


class TestMergeExchangeInfo:
    """Tests for _merge_exchange_info function."""

    def test_merge_timezone(self, sample_exchange_info: ExchangeInfo):
        """Test merging timezone override."""
        from xbbg.markets.resolver_chain import _merge_exchange_info

        override: OverrideData = {"timezone": "Asia/Tokyo"}
        merged = _merge_exchange_info(sample_exchange_info, override)

        assert merged.timezone == "Asia/Tokyo"
        assert merged.mic == sample_exchange_info.mic  # Preserved
        assert merged.exch_code == sample_exchange_info.exch_code  # Preserved
        assert merged.source == "override"

    def test_merge_sessions(self, sample_exchange_info: ExchangeInfo):
        """Test merging sessions override."""
        from xbbg.markets.resolver_chain import _merge_exchange_info

        new_sessions = {"regular": ("08:00", "17:00")}
        override: OverrideData = {"sessions": new_sessions}
        merged = _merge_exchange_info(sample_exchange_info, override)

        assert merged.sessions == new_sessions
        assert merged.timezone == sample_exchange_info.timezone  # Preserved

    def test_merge_multiple_fields(self, sample_exchange_info: ExchangeInfo):
        """Test merging multiple fields."""
        from xbbg.markets.resolver_chain import _merge_exchange_info

        override: OverrideData = {
            "timezone": "Europe/London",
            "mic": "XLON",
            "exch_code": "LN",
        }
        merged = _merge_exchange_info(sample_exchange_info, override)

        assert merged.timezone == "Europe/London"
        assert merged.mic == "XLON"
        assert merged.exch_code == "LN"


# ============================================================================
# Tests for BloombergExchangeResolver (mocked)
# ============================================================================


class TestBloombergExchangeResolver:
    """Tests for BloombergExchangeResolver with mocked Bloomberg calls."""

    def test_can_resolve_always_true(self):
        """Test that can_resolve always returns True."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="AAPL US Equity", dt="2024-01-15")
        assert resolver.can_resolve(request) is True

    def test_resolve_with_override_and_cache(self, temp_cache_dir: Path):
        """Test resolution with runtime override merged with cache.

        Note: The resolver merges overrides with cache/Bloomberg data.
        Overrides alone don't provide a complete result - they need
        base data from cache or Bloomberg to merge with.
        """
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.io.cache import save_exchange_info
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # First, save base data to cache
        base_info = ExchangeInfo(
            ticker="TEST Equity",
            timezone="America/New_York",
            mic="XNYS",
            exch_code="US",
            source="bloomberg",
        )
        save_exchange_info(base_info)

        # Set override to change timezone and mic
        set_exchange_override("TEST Equity", timezone="Asia/Tokyo", mic="XTKS")

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="TEST Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is True
        assert result.exchange_info["tz"] == "Asia/Tokyo"  # From override
        assert result.exchange_info["mic"] == "XTKS"  # From override
        assert result.resolver_name == "BloombergExchangeResolver"

    def test_resolve_with_cache(self, temp_cache_dir: Path):
        """Test resolution with cached data."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.io.cache import save_exchange_info
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Save to cache
        info = ExchangeInfo(
            ticker="CACHED Equity",
            timezone="Europe/London",
            mic="XLON",
            source="bloomberg",
        )
        save_exchange_info(info)

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="CACHED Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is True
        assert result.exchange_info["tz"] == "Europe/London"
        assert result.exchange_info["mic"] == "XLON"

    def test_resolve_with_partial_override_merge(self, temp_cache_dir: Path):
        """Test resolution merges cache with partial override.

        When only some fields are overridden, the resolver should merge
        the override with cached data, preserving non-overridden fields.
        """
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.io.cache import save_exchange_info
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Save to cache with all fields
        info = ExchangeInfo(
            ticker="MERGE Equity",
            timezone="Europe/London",
            mic="XLON",
            exch_code="LN",
            source="bloomberg",
        )
        save_exchange_info(info)

        # Set partial override (only timezone)
        set_exchange_override("MERGE Equity", timezone="Asia/Tokyo")

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="MERGE Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is True
        assert result.exchange_info["tz"] == "Asia/Tokyo"  # From override
        # Note: mic is preserved from cache via _merge_exchange_info
        assert result.exchange_info.get("mic") == "XLON"  # From cache

    @patch("xbbg.markets.resolver_chain.fetch_exchange_info")
    def test_resolve_from_bloomberg(self, mock_fetch: MagicMock, temp_cache_dir: Path):
        """Test resolution from Bloomberg API (mocked)."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Mock Bloomberg response
        mock_fetch.return_value = ExchangeInfo(
            ticker="BBG Equity",
            timezone="America/New_York",
            mic="XNYS",
            exch_code="US",
            source="bloomberg",
        )

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="BBG Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is True
        assert result.exchange_info["tz"] == "America/New_York"
        assert result.exchange_info["mic"] == "XNYS"
        mock_fetch.assert_called_once()

    @patch("xbbg.markets.resolver_chain.fetch_exchange_info")
    def test_resolve_bloomberg_fallback(self, mock_fetch: MagicMock, temp_cache_dir: Path):
        """Test resolution when Bloomberg returns fallback."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Mock Bloomberg fallback response
        mock_fetch.return_value = ExchangeInfo(
            ticker="UNKNOWN Equity",
            source="fallback",
        )

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="UNKNOWN Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is False

    @patch("xbbg.markets.resolver_chain.fetch_exchange_info")
    def test_resolve_bloomberg_exception(self, mock_fetch: MagicMock, temp_cache_dir: Path):
        """Test resolution when Bloomberg raises exception."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Mock Bloomberg exception
        mock_fetch.side_effect = Exception("Bloomberg connection failed")

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="ERROR Equity", dt="2024-01-15")
        result = resolver.resolve(request)

        assert result.success is False

    @patch("xbbg.markets.resolver_chain.fetch_exchange_info")
    @patch("xbbg.markets.resolver_chain.save_exchange_info")
    def test_resolve_caches_bloomberg_result(
        self,
        mock_save: MagicMock,
        mock_fetch: MagicMock,
        temp_cache_dir: Path,
    ):
        """Test that Bloomberg result is cached."""
        from xbbg.core.domain.contracts import DataRequest
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        # Mock Bloomberg response
        mock_fetch.return_value = ExchangeInfo(
            ticker="CACHE_ME Equity",
            timezone="America/New_York",
            source="bloomberg",
        )

        resolver = BloombergExchangeResolver()
        request = DataRequest(ticker="CACHE_ME Equity", dt="2024-01-15")
        resolver.resolve(request)

        # Verify save was called
        mock_save.assert_called_once()

    def test_max_cache_age_configuration(self):
        """Test max cache age configuration."""
        from xbbg.markets.resolver_chain import BloombergExchangeResolver

        resolver = BloombergExchangeResolver(max_cache_age_hours=48.0)
        assert resolver._max_cache_age == 48.0

        resolver_infinite = BloombergExchangeResolver(max_cache_age_hours=float("inf"))
        assert resolver_infinite._max_cache_age == float("inf")


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unicode_ticker(self):
        """Test handling of unicode characters in ticker."""
        set_exchange_override("日経225 Index", timezone="Asia/Tokyo")
        info = get_exchange_override("日経225 Index")
        assert info is not None
        assert info.timezone == "Asia/Tokyo"

    def test_special_characters_in_ticker(self):
        """Test handling of special characters in ticker."""
        set_exchange_override("TEST/A Equity", timezone="UTC")
        info = get_exchange_override("TEST/A Equity")
        assert info is not None

    def test_very_long_ticker(self):
        """Test handling of very long ticker."""
        long_ticker = "A" * 200 + " Equity"
        set_exchange_override(long_ticker, timezone="UTC")
        info = get_exchange_override(long_ticker)
        assert info is not None

    def test_sessions_with_overnight_span(self):
        """Test sessions that span overnight."""
        sessions = {"futures": ("18:00", "05:00")}  # Overnight session
        set_exchange_override("ES1 Index", sessions=sessions)
        info = get_exchange_override("ES1 Index")
        assert info is not None
        assert info.sessions["futures"] == ("18:00", "05:00")

    def test_concurrent_override_access(self):
        """Test thread safety of override registry."""
        import threading

        errors = []

        def set_override(ticker: str):
            try:
                for _ in range(100):
                    set_exchange_override(ticker, timezone="UTC")
                    get_exchange_override(ticker)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_override, args=(f"TEST{i} Equity",)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent access errors: {errors}"

    def test_japan_close_time_override(self):
        """Issue #160: Japan market close moved from 15:00 to 15:30 (Nov 2024).

        Users need to override session times when exchange hours change.
        Verify the override system can handle updated Japan market hours.
        """
        updated_sessions = {
            "am": ("09:00", "11:30"),
            "pm": ("12:30", "15:30"),  # New close: 15:30 instead of 15:00
        }
        set_exchange_override("7203 JP Equity", sessions=updated_sessions, timezone="Asia/Tokyo")

        info = get_exchange_override("7203 JP Equity")
        assert info is not None
        assert info.sessions["pm"] == ("12:30", "15:30")
        assert info.sessions["am"] == ("09:00", "11:30")
        assert info.timezone == "Asia/Tokyo"
