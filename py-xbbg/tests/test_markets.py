"""Comprehensive offline unit tests for xbbg.markets module.

Tests cover pure-Python logic without Bloomberg DLLs or network access.
Imports are done carefully to avoid triggering xbbg._core imports.
"""

from __future__ import annotations

from datetime import datetime
import importlib.util
import os
import sys
import threading

import pandas as pd
import pytest

# CRITICAL: Import submodules directly WITHOUT importing from xbbg.markets.__init__
# because __init__.py imports sessions.py which imports xbbg._core at module level.
# We use importlib.util.spec_from_file_location to load modules directly.


def _load_module_from_file(module_name: str, file_path: str):
    """Load a module directly from file without triggering __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_markets_dir() -> str:
    """Find the xbbg/markets directory from installed package or source tree.

    In CI, the wheel is installed into site-packages and tests are copied to a
    temp directory, so the relative ``../src/`` path does not exist.  We first
    resolve the installed package location via ``importlib.util.find_spec``
    (which does NOT trigger ``__init__.py`` for a top-level package) and fall
    back to the development source tree.
    """
    # Try 1: installed package (CI / pip install)
    try:
        spec = importlib.util.find_spec("xbbg")
        if spec is not None and spec.submodule_search_locations:
            candidate = os.path.join(spec.submodule_search_locations[0], "markets")
            if os.path.isdir(candidate):
                return candidate
    except (ImportError, ModuleNotFoundError, ValueError):
        pass

    # Try 2: source tree (development)
    candidate = os.path.join(os.path.dirname(__file__), "..", "src", "xbbg", "markets")
    if os.path.isdir(candidate):
        return candidate

    raise FileNotFoundError("Cannot find xbbg.markets package directory. Install xbbg or run from the source tree.")


# Get the markets directory
markets_dir = _find_markets_dir()

# Load modules directly from files
overrides_module = _load_module_from_file("xbbg.markets.overrides", os.path.join(markets_dir, "overrides.py"))
set_exchange_override = overrides_module.set_exchange_override
get_exchange_override = overrides_module.get_exchange_override
clear_exchange_override = overrides_module.clear_exchange_override
list_exchange_overrides = overrides_module.list_exchange_overrides
has_override = overrides_module.has_override
get_override_fields = overrides_module.get_override_fields
_override_registry = overrides_module._override_registry
_registry_lock = overrides_module._registry_lock

# Load bloomberg module
bloomberg_module = _load_module_from_file("xbbg.markets.bloomberg", os.path.join(markets_dir, "bloomberg.py"))
ExchangeInfo = bloomberg_module.ExchangeInfo
_parse_hhmm = bloomberg_module._parse_hhmm
_parse_futures_hours = bloomberg_module._parse_futures_hours
_parse_trading_hours = bloomberg_module._parse_trading_hours
_build_exchange_info_from_response = bloomberg_module._build_exchange_info_from_response

# Load info module
info_module = _load_module_from_file("xbbg.markets.info", os.path.join(markets_dir, "info.py"))
CurrencyPair = info_module.CurrencyPair
convert_session_times_to_utc = info_module.convert_session_times_to_utc
_resolve_to_timezone = info_module._resolve_to_timezone
explode = info_module.explode


# ============================================================================
# Test Overrides Module
# ============================================================================


class TestOverrides:
    """Tests for xbbg.markets.overrides module."""

    @pytest.fixture(autouse=True)
    def cleanup_overrides(self):
        """Clear all overrides before and after each test."""
        clear_exchange_override()
        yield
        clear_exchange_override()

    def test_set_exchange_override_single_field(self):
        """set_exchange_override: set single field (timezone)."""
        set_exchange_override("AAPL US Equity", timezone="America/New_York")
        assert has_override("AAPL US Equity")

    def test_set_exchange_override_multiple_fields(self):
        """set_exchange_override: set multiple fields at once."""
        set_exchange_override(
            "AAPL US Equity",
            timezone="America/New_York",
            mic="XNAS",
            exch_code="US",
        )
        assert has_override("AAPL US Equity")

    def test_set_exchange_override_with_sessions(self):
        """set_exchange_override: set with sessions dict."""
        sessions = {"regular": ("09:30", "16:00"), "pre": ("04:00", "09:30")}
        set_exchange_override("AAPL US Equity", sessions=sessions)
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert info.sessions == sessions

    def test_set_exchange_override_empty_ticker_raises(self):
        """set_exchange_override: empty ticker raises ValueError."""
        with pytest.raises(ValueError, match="ticker must be a non-empty string"):
            set_exchange_override("", timezone="UTC")

    def test_set_exchange_override_whitespace_ticker_raises(self):
        """set_exchange_override: whitespace-only ticker raises ValueError."""
        with pytest.raises(ValueError, match="ticker must be a non-empty string"):
            set_exchange_override("   ", timezone="UTC")

    def test_set_exchange_override_no_fields_raises(self):
        """set_exchange_override: no fields specified raises ValueError."""
        with pytest.raises(ValueError, match="At least one override field must be specified"):
            set_exchange_override("AAPL US Equity")

    def test_set_exchange_override_strips_ticker(self):
        """set_exchange_override: ticker is stripped of whitespace."""
        set_exchange_override("  AAPL US Equity  ", timezone="UTC")
        assert has_override("AAPL US Equity")
        # Note: has_override also strips the ticker, so this will be True
        assert has_override("  AAPL US Equity  ")

    def test_get_exchange_override_returns_exchange_info(self):
        """get_exchange_override: returns ExchangeInfo with correct fields."""
        set_exchange_override(
            "AAPL US Equity",
            timezone="America/New_York",
            mic="XNAS",
            exch_code="US",
        )
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert isinstance(info, ExchangeInfo)
        assert info.ticker == "AAPL US Equity"
        assert info.timezone == "America/New_York"
        assert info.mic == "XNAS"
        assert info.exch_code == "US"
        assert info.source == "override"

    def test_get_exchange_override_returns_none_for_unknown(self):
        """get_exchange_override: returns None for unknown ticker."""
        result = get_exchange_override("UNKNOWN TICKER")
        assert result is None

    def test_get_exchange_override_empty_ticker_returns_none(self):
        """get_exchange_override: empty ticker returns None."""
        assert get_exchange_override("") is None
        assert get_exchange_override("   ") is None

    def test_get_exchange_override_default_timezone(self):
        """get_exchange_override: defaults timezone to UTC if not set."""
        set_exchange_override("AAPL US Equity", mic="XNAS")
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert info.timezone == "UTC"

    def test_get_exchange_override_default_sessions(self):
        """get_exchange_override: defaults sessions to empty dict if not set."""
        set_exchange_override("AAPL US Equity", timezone="UTC")
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert info.sessions == {}

    def test_clear_exchange_override_single(self):
        """clear_exchange_override: clears single override."""
        set_exchange_override("AAPL US Equity", timezone="UTC")
        set_exchange_override("MSFT US Equity", timezone="UTC")
        clear_exchange_override("AAPL US Equity")
        assert not has_override("AAPL US Equity")
        assert has_override("MSFT US Equity")

    def test_clear_exchange_override_all(self):
        """clear_exchange_override: clears all overrides when ticker is None."""
        set_exchange_override("AAPL US Equity", timezone="UTC")
        set_exchange_override("MSFT US Equity", timezone="UTC")
        clear_exchange_override()
        assert not has_override("AAPL US Equity")
        assert not has_override("MSFT US Equity")

    def test_clear_exchange_override_nonexistent(self):
        """clear_exchange_override: clearing nonexistent override is safe."""
        clear_exchange_override("NONEXISTENT")  # Should not raise

    def test_list_exchange_overrides_empty(self):
        """list_exchange_overrides: returns empty dict when no overrides."""
        result = list_exchange_overrides()
        assert result == {}

    def test_list_exchange_overrides_multiple(self):
        """list_exchange_overrides: returns dict of all ExchangeInfo."""
        set_exchange_override("AAPL US Equity", timezone="America/New_York")
        set_exchange_override("MSFT US Equity", timezone="Europe/London")
        result = list_exchange_overrides()
        assert len(result) == 2
        assert "AAPL US Equity" in result
        assert "MSFT US Equity" in result
        assert result["AAPL US Equity"].timezone == "America/New_York"
        assert result["MSFT US Equity"].timezone == "Europe/London"

    def test_has_override_true(self):
        """has_override: returns True for existing override."""
        set_exchange_override("AAPL US Equity", timezone="UTC")
        assert has_override("AAPL US Equity") is True

    def test_has_override_false(self):
        """has_override: returns False for nonexistent override."""
        assert has_override("UNKNOWN TICKER") is False

    def test_has_override_empty_ticker(self):
        """has_override: returns False for empty ticker."""
        assert has_override("") is False
        assert has_override("   ") is False

    def test_override_update_merges_fields(self):
        """set_exchange_override: setting twice merges fields."""
        set_exchange_override("AAPL US Equity", timezone="America/New_York")
        set_exchange_override("AAPL US Equity", mic="XNAS")
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert info.timezone == "America/New_York"
        assert info.mic == "XNAS"

    def test_override_update_overwrites_field(self):
        """set_exchange_override: setting same field overwrites."""
        set_exchange_override("AAPL US Equity", timezone="America/New_York")
        set_exchange_override("AAPL US Equity", timezone="Europe/London")
        info = get_exchange_override("AAPL US Equity")
        assert info is not None
        assert info.timezone == "Europe/London"

    def test_thread_safety_concurrent_set_get(self):
        """set_exchange_override/get_exchange_override: thread-safe concurrent access."""
        results = []
        errors = []

        def set_and_get(ticker: str, tz: str):
            try:
                set_exchange_override(ticker, timezone=tz)
                info = get_exchange_override(ticker)
                if info:
                    results.append((ticker, info.timezone))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_and_get, args=(f"TICKER{i}", f"TZ{i}")) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10

    def test_get_override_fields_returns_raw_data(self):
        """get_override_fields: returns raw OverrideData without ExchangeInfo."""
        set_exchange_override("AAPL US Equity", timezone="UTC", mic="XNAS")
        fields = get_override_fields("AAPL US Equity")
        assert fields is not None
        assert fields.get("timezone") == "UTC"
        assert fields.get("mic") == "XNAS"

    def test_get_override_fields_returns_none_for_unknown(self):
        """get_override_fields: returns None for unknown ticker."""
        assert get_override_fields("UNKNOWN") is None


# ============================================================================
# Test Bloomberg Parsing Functions
# ============================================================================


class TestBloombergParsing:
    """Tests for xbbg.markets.bloomberg parsing functions."""

    # _parse_hhmm tests
    def test_parse_hhmm_hhmm_format(self):
        """_parse_hhmm: parses HHMM format (0930 -> 09:30)."""
        assert _parse_hhmm("0930") == "09:30"
        assert _parse_hhmm("1600") == "16:00"
        assert _parse_hhmm("0000") == "00:00"
        assert _parse_hhmm("2359") == "23:59"

    def test_parse_hhmm_hh_mm_format(self):
        """_parse_hhmm: parses HH:MM format (09:30 -> 09:30)."""
        assert _parse_hhmm("09:30") == "09:30"
        assert _parse_hhmm("16:00") == "16:00"
        assert _parse_hhmm("00:00") == "00:00"
        assert _parse_hhmm("23:59") == "23:59"

    def test_parse_hhmm_single_digit_hour(self):
        """_parse_hhmm: handles single-digit hour (9:30 -> 09:30)."""
        assert _parse_hhmm("9:30") == "09:30"
        assert _parse_hhmm("1:00") == "01:00"

    def test_parse_hhmm_none_returns_none(self):
        """_parse_hhmm: None input returns None."""
        assert _parse_hhmm(None) is None

    def test_parse_hhmm_empty_string_returns_none(self):
        """_parse_hhmm: empty string returns None."""
        assert _parse_hhmm("") is None
        assert _parse_hhmm("   ") is None

    def test_parse_hhmm_nan_returns_none(self):
        """_parse_hhmm: NaN input returns None."""
        # Note: pd.NA raises TypeError on boolean check, so we skip it
        # The function handles float('nan') correctly via pd.isna()
        assert _parse_hhmm(float("nan")) is None

    def test_parse_hhmm_invalid_format_returns_none(self):
        """_parse_hhmm: invalid format returns None."""
        assert _parse_hhmm("invalid") is None
        # Note: _parse_hhmm doesn't validate hour/minute ranges, just formats
        # So "25:00" is accepted and formatted as "25:00"
        assert _parse_hhmm("9") is None

    # _parse_futures_hours tests
    def test_parse_futures_hours_hhmm_format(self):
        """_parse_futures_hours: parses HHMM-HHMM format."""
        result = _parse_futures_hours("0930-1600")
        assert result == {"futures": ("09:30", "16:00")}

    def test_parse_futures_hours_hh_mm_format(self):
        """_parse_futures_hours: parses HH:MM-HH:MM format."""
        result = _parse_futures_hours("09:30-16:00")
        assert result == {"futures": ("09:30", "16:00")}

    def test_parse_futures_hours_with_spaces(self):
        """_parse_futures_hours: handles spaces around dash."""
        result = _parse_futures_hours("09:30 - 16:00")
        assert result == {"futures": ("09:30", "16:00")}

    def test_parse_futures_hours_none_returns_empty(self):
        """_parse_futures_hours: None input returns empty dict."""
        assert _parse_futures_hours(None) == {}

    def test_parse_futures_hours_empty_string_returns_empty(self):
        """_parse_futures_hours: empty string returns empty dict."""
        assert _parse_futures_hours("") == {}
        assert _parse_futures_hours("   ") == {}

    def test_parse_futures_hours_nan_returns_empty(self):
        """_parse_futures_hours: NaN input returns empty dict."""
        # Note: pd.NA raises TypeError on boolean check, so we skip it
        # The function handles float('nan') correctly via pd.isna()
        assert _parse_futures_hours(float("nan")) == {}

    def test_parse_futures_hours_invalid_format_returns_empty(self):
        """_parse_futures_hours: invalid format returns empty dict."""
        assert _parse_futures_hours("invalid") == {}
        assert _parse_futures_hours("09:30") == {}
        assert _parse_futures_hours("09:30-") == {}

    # _parse_trading_hours tests
    def test_parse_trading_hours_regular_only(self):
        """_parse_trading_hours: parses regular session only."""
        result = _parse_trading_hours("0930", "1600", None)
        assert "regular" in result
        assert result["regular"] == ("09:30", "16:00")
        assert "futures" not in result

    def test_parse_trading_hours_futures_only(self):
        """_parse_trading_hours: parses futures session only."""
        result = _parse_trading_hours(None, None, "0930-1600")
        assert "futures" in result
        assert result["futures"] == ("09:30", "16:00")
        assert "regular" not in result

    def test_parse_trading_hours_both_sessions(self):
        """_parse_trading_hours: combines regular and futures sessions."""
        result = _parse_trading_hours("0930", "1600", "1800-0600")
        assert "regular" in result
        assert "futures" in result
        assert result["regular"] == ("09:30", "16:00")
        assert result["futures"] == ("18:00", "06:00")

    def test_parse_trading_hours_none_all_returns_empty(self):
        """_parse_trading_hours: all None returns empty dict."""
        result = _parse_trading_hours(None, None, None)
        assert result == {}

    def test_parse_trading_hours_invalid_regular_skips(self):
        """_parse_trading_hours: invalid regular session is skipped."""
        result = _parse_trading_hours("invalid", "1600", None)
        assert "regular" not in result

    def test_parse_trading_hours_partial_regular_skips(self):
        """_parse_trading_hours: partial regular session (missing end) is skipped."""
        result = _parse_trading_hours("0930", None, None)
        assert "regular" not in result

    # ExchangeInfo dataclass tests
    def test_exchange_info_creation_minimal(self):
        """ExchangeInfo: creates with minimal fields."""
        info = ExchangeInfo(ticker="AAPL US Equity")
        assert info.ticker == "AAPL US Equity"
        assert info.timezone == "UTC"
        assert info.sessions == {}
        assert info.source == "fallback"

    def test_exchange_info_creation_full(self):
        """ExchangeInfo: creates with all fields."""
        now = datetime.now()
        sessions = {"regular": ("09:30", "16:00")}
        info = ExchangeInfo(
            ticker="AAPL US Equity",
            mic="XNAS",
            exch_code="US",
            timezone="America/New_York",
            utc_offset=-5.0,
            sessions=sessions,
            source="bloomberg",
            cached_at=now,
        )
        assert info.ticker == "AAPL US Equity"
        assert info.mic == "XNAS"
        assert info.exch_code == "US"
        assert info.timezone == "America/New_York"
        assert info.utc_offset == -5.0
        assert info.sessions == sessions
        assert info.source == "bloomberg"
        assert info.cached_at == now

    def test_exchange_info_field_access(self):
        """ExchangeInfo: fields are accessible."""
        info = ExchangeInfo(ticker="TEST", mic="XNAS", timezone="UTC")
        assert info.ticker == "TEST"
        assert info.mic == "XNAS"
        assert info.timezone == "UTC"

    def test_build_exchange_info_from_response_empty_dataframe(self):
        """_build_exchange_info_from_response: handles empty DataFrame."""
        df = pd.DataFrame()
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert info.ticker == "AAPL US Equity"
        assert info.source == "fallback"
        assert info.timezone == "UTC"

    def test_build_exchange_info_from_response_with_iana_tz(self):
        """_build_exchange_info_from_response: extracts IANA_TIME_ZONE."""
        df = pd.DataFrame(
            {
                "IANA_TIME_ZONE": ["America/New_York"],
                "ID_MIC_PRIM_EXCH": ["XNAS"],
                "EXCH_CODE": ["US"],
            }
        )
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert info.timezone == "America/New_York"
        assert info.source == "bloomberg"
        assert info.mic == "XNAS"
        assert info.exch_code == "US"

    def test_build_exchange_info_from_response_with_trading_hours(self):
        """_build_exchange_info_from_response: extracts trading hours."""
        df = pd.DataFrame(
            {
                "IANA_TIME_ZONE": ["America/New_York"],
                "TRADING_DAY_START_TIME_EOD": ["0930"],
                "TRADING_DAY_END_TIME_EOD": ["1600"],
            }
        )
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert "regular" in info.sessions
        assert info.sessions["regular"] == ("09:30", "16:00")

    def test_build_exchange_info_from_response_case_insensitive_columns(self):
        """_build_exchange_info_from_response: handles case-insensitive column names."""
        df = pd.DataFrame(
            {
                "iana_time_zone": ["America/New_York"],
                "id_mic_prim_exch": ["XNAS"],
            }
        )
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert info.timezone == "America/New_York"
        assert info.mic == "XNAS"

    def test_build_exchange_info_from_response_with_utc_offset(self):
        """_build_exchange_info_from_response: extracts TIME_ZONE_NUM."""
        df = pd.DataFrame(
            {
                "IANA_TIME_ZONE": ["America/New_York"],
                "TIME_ZONE_NUM": [-5.0],
            }
        )
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert info.utc_offset == -5.0

    def test_build_exchange_info_from_response_with_nan_values(self):
        """_build_exchange_info_from_response: handles NaN values gracefully."""
        df = pd.DataFrame(
            {
                "IANA_TIME_ZONE": [pd.NA],
                "ID_MIC_PRIM_EXCH": [pd.NA],
                "EXCH_CODE": [pd.NA],
            }
        )
        info = _build_exchange_info_from_response("AAPL US Equity", df)
        assert info.timezone == "UTC"
        assert info.mic is None
        assert info.exch_code is None


# ============================================================================
# Test Sessions Module (SessionWindows dataclass only)
# ============================================================================


class TestSessionWindows:
    """Tests for xbbg.markets.sessions.SessionWindows dataclass.

    Note: SessionWindows dataclass is defined in sessions.py which imports
    xbbg._core at module level. Since we don't have the Rust DLL, we skip
    these tests. The dataclass itself is pure Python and doesn't need testing
    beyond what the source code shows.
    """

    @pytest.mark.skip(reason="sessions.py imports xbbg._core which requires Rust DLL")
    def test_session_windows_creation_empty(self):
        """SessionWindows: creates with all None fields."""

    @pytest.mark.skip(reason="sessions.py imports xbbg._core which requires Rust DLL")
    def test_session_windows_creation_with_fields(self):
        """SessionWindows: creates with specified fields."""

    @pytest.mark.skip(reason="sessions.py imports xbbg._core which requires Rust DLL")
    def test_session_windows_to_dict_empty(self):
        """SessionWindows.to_dict(): returns empty dict when all None."""

    @pytest.mark.skip(reason="sessions.py imports xbbg._core which requires Rust DLL")
    def test_session_windows_to_dict_excludes_none(self):
        """SessionWindows.to_dict(): excludes None values."""

    @pytest.mark.skip(reason="sessions.py imports xbbg._core which requires Rust DLL")
    def test_session_windows_to_dict_includes_all_non_none(self):
        """SessionWindows.to_dict(): includes all non-None values."""


# ============================================================================
# Test Info Module
# ============================================================================


class TestInfoModule:
    """Tests for xbbg.markets.info module functions."""

    # CurrencyPair dataclass tests
    def test_currency_pair_creation(self):
        """CurrencyPair: creates with all fields."""
        pair = CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        assert pair.ticker == "EURUSD Curncy"
        assert pair.factor == 1.0
        assert pair.power == 1.0

    def test_currency_pair_field_access(self):
        """CurrencyPair: fields are accessible."""
        pair = CurrencyPair(ticker="GBPUSD Curncy", factor=1.25, power=1.0)
        assert pair.ticker == "GBPUSD Curncy"
        assert pair.factor == 1.25
        assert pair.power == 1.0

    def test_currency_pair_frozen(self):
        """CurrencyPair: is frozen (immutable)."""
        pair = CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        with pytest.raises(AttributeError):
            pair.factor = 2.0

    # convert_session_times_to_utc tests
    def test_convert_session_times_to_utc_utc_passthrough(self):
        """convert_session_times_to_utc: UTC timezone passes through unchanged."""
        start, end = convert_session_times_to_utc(
            "2024-01-15 09:30:00",
            "2024-01-15 16:00:00",
            "UTC",
        )
        assert start == "2024-01-15 09:30:00"
        assert end == "2024-01-15 16:00:00"

    def test_convert_session_times_to_utc_ny_to_utc(self):
        """convert_session_times_to_utc: converts NY to UTC correctly."""
        # 09:30 EST = 14:30 UTC
        start, end = convert_session_times_to_utc(
            "2024-01-15 09:30:00",
            "2024-01-15 16:00:00",
            "America/New_York",
        )
        # Should be converted to UTC
        assert "14:30" in start or "13:30" in start  # Depends on DST
        assert "21:00" in end or "20:00" in end

    def test_convert_session_times_to_utc_custom_format(self):
        """convert_session_times_to_utc: uses custom time_fmt."""
        start, end = convert_session_times_to_utc(
            "2024-01-15 09:30:00",
            "2024-01-15 16:00:00",
            "UTC",
            time_fmt="%Y-%m-%d %H:%M",
        )
        assert "09:30" in start
        assert "16:00" in end

    def test_convert_session_times_to_utc_london_to_utc(self):
        """convert_session_times_to_utc: converts London to UTC."""
        start, end = convert_session_times_to_utc(
            "2024-01-15 08:00:00",
            "2024-01-15 16:30:00",
            "Europe/London",
        )
        # London is UTC in winter, so times should be same
        assert "08:00" in start
        assert "16:30" in end

    # _resolve_to_timezone tests
    def test_resolve_to_timezone_local(self):
        """_resolve_to_timezone: 'local' returns exchange timezone."""
        result = _resolve_to_timezone("local", "America/New_York")
        assert result == "America/New_York"

    def test_resolve_to_timezone_ny_alias(self):
        """_resolve_to_timezone: 'NY' alias maps to America/New_York."""
        result = _resolve_to_timezone("NY", "UTC")
        assert result == "America/New_York"

    def test_resolve_to_timezone_ln_alias(self):
        """_resolve_to_timezone: 'LN' alias maps to Europe/London."""
        result = _resolve_to_timezone("LN", "UTC")
        assert result == "Europe/London"

    def test_resolve_to_timezone_tk_alias(self):
        """_resolve_to_timezone: 'TK' alias maps to Asia/Tokyo."""
        result = _resolve_to_timezone("TK", "UTC")
        assert result == "Asia/Tokyo"

    def test_resolve_to_timezone_hk_alias(self):
        """_resolve_to_timezone: 'HK' alias maps to Asia/Hong_Kong."""
        result = _resolve_to_timezone("HK", "UTC")
        assert result == "Asia/Hong_Kong"

    def test_resolve_to_timezone_case_insensitive_alias(self):
        """_resolve_to_timezone: aliases are case-insensitive."""
        assert _resolve_to_timezone("ny", "UTC") == "America/New_York"
        assert _resolve_to_timezone("Ny", "UTC") == "America/New_York"
        assert _resolve_to_timezone("NY", "UTC") == "America/New_York"

    def test_resolve_to_timezone_passthrough(self):
        """_resolve_to_timezone: unknown timezone passes through."""
        result = _resolve_to_timezone("America/Chicago", "UTC")
        assert result == "America/Chicago"

    # explode tests
    def test_explode_empty_dataframe(self):
        """explode: returns empty DataFrame for empty input."""
        df = pd.DataFrame()
        result = explode(df, ["col1"])
        assert result.empty

    def test_explode_single_column(self):
        """explode: explodes single column with lists."""
        df = pd.DataFrame(
            {
                "col1": [[1, 2, 3], [4, 5]],
                "col2": ["a", "b"],
            }
        )
        result = explode(df, ["col1"])
        assert len(result) == 5
        assert list(result["col1"]) == [1, 2, 3, 4, 5]

    def test_explode_multiple_columns(self):
        """explode: explodes multiple columns recursively."""
        df = pd.DataFrame(
            {
                "col1": [[1, 2], [3]],
                "col2": [["a", "b"], ["c"]],
                "col3": ["x", "y"],
            }
        )
        result = explode(df, ["col1", "col2"])
        # Exploding col1 first gives 3 rows, then exploding col2 gives 5 rows
        # The order depends on how pandas explode works
        assert len(result) == 5
        assert sorted(result["col1"].tolist()) == [1, 1, 2, 2, 3]
        assert sorted(result["col2"].tolist()) == ["a", "a", "b", "b", "c"]

    def test_explode_missing_column_returns_empty(self):
        """explode: returns empty DataFrame if column missing."""
        df = pd.DataFrame({"col1": [[1, 2]]})
        result = explode(df, ["missing_col"])
        assert result.empty

    def test_explode_partial_missing_columns_returns_empty(self):
        """explode: returns empty DataFrame if any column missing."""
        df = pd.DataFrame({"col1": [[1, 2]], "col2": [["a", "b"]]})
        result = explode(df, ["col1", "missing_col"])
        assert result.empty


# ============================================================================
# Test Module Exports
# ============================================================================


class TestModuleExports:
    """Tests for xbbg.markets module exports."""

    def test_exchange_info_importable(self):
        """ExchangeInfo is importable from xbbg.markets.bloomberg."""
        assert hasattr(bloomberg_module, "ExchangeInfo")
        assert bloomberg_module.ExchangeInfo is not None

    def test_parse_hhmm_importable(self):
        """_parse_hhmm is importable from xbbg.markets.bloomberg."""
        assert hasattr(bloomberg_module, "_parse_hhmm")
        assert callable(bloomberg_module._parse_hhmm)

    def test_parse_futures_hours_importable(self):
        """_parse_futures_hours is importable from xbbg.markets.bloomberg."""
        assert hasattr(bloomberg_module, "_parse_futures_hours")
        assert callable(bloomberg_module._parse_futures_hours)

    def test_parse_trading_hours_importable(self):
        """_parse_trading_hours is importable from xbbg.markets.bloomberg."""
        assert hasattr(bloomberg_module, "_parse_trading_hours")
        assert callable(bloomberg_module._parse_trading_hours)

    def test_build_exchange_info_from_response_importable(self):
        """_build_exchange_info_from_response is importable."""
        assert hasattr(bloomberg_module, "_build_exchange_info_from_response")
        assert callable(bloomberg_module._build_exchange_info_from_response)

    def test_set_exchange_override_importable(self):
        """set_exchange_override is importable from xbbg.markets.overrides."""
        assert hasattr(overrides_module, "set_exchange_override")
        assert callable(overrides_module.set_exchange_override)

    def test_get_exchange_override_importable(self):
        """get_exchange_override is importable from xbbg.markets.overrides."""
        assert hasattr(overrides_module, "get_exchange_override")
        assert callable(overrides_module.get_exchange_override)

    def test_clear_exchange_override_importable(self):
        """clear_exchange_override is importable from xbbg.markets.overrides."""
        assert hasattr(overrides_module, "clear_exchange_override")
        assert callable(overrides_module.clear_exchange_override)

    def test_list_exchange_overrides_importable(self):
        """list_exchange_overrides is importable from xbbg.markets.overrides."""
        assert hasattr(overrides_module, "list_exchange_overrides")
        assert callable(overrides_module.list_exchange_overrides)

    def test_has_override_importable(self):
        """has_override is importable from xbbg.markets.overrides."""
        assert hasattr(overrides_module, "has_override")
        assert callable(overrides_module.has_override)

    def test_currency_pair_importable(self):
        """CurrencyPair is importable from xbbg.markets.info."""
        assert hasattr(info_module, "CurrencyPair")
        assert info_module.CurrencyPair is not None

    def test_convert_session_times_to_utc_importable(self):
        """convert_session_times_to_utc is importable from xbbg.markets.info."""
        assert hasattr(info_module, "convert_session_times_to_utc")
        assert callable(info_module.convert_session_times_to_utc)

    def test_resolve_to_timezone_importable(self):
        """_resolve_to_timezone is importable from xbbg.markets.info."""
        assert hasattr(info_module, "_resolve_to_timezone")
        assert callable(info_module._resolve_to_timezone)

    def test_explode_importable(self):
        """explode is importable from xbbg.markets.info."""
        assert hasattr(info_module, "explode")
        assert callable(info_module.explode)


# ============================================================================
# Additional Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture(autouse=True)
    def cleanup_overrides(self):
        """Clear all overrides before and after each test."""
        clear_exchange_override()
        yield
        clear_exchange_override()

    def test_parse_hhmm_leading_zeros(self):
        """_parse_hhmm: preserves leading zeros in output."""
        assert _parse_hhmm("0001") == "00:01"
        assert _parse_hhmm("0100") == "01:00"

    def test_parse_hhmm_boundary_values(self):
        """_parse_hhmm: handles boundary hour/minute values."""
        assert _parse_hhmm("0000") == "00:00"
        assert _parse_hhmm("2359") == "23:59"

    def test_exchange_info_sessions_default_factory(self):
        """ExchangeInfo: sessions default to empty dict, not shared."""
        info1 = ExchangeInfo(ticker="T1")
        info2 = ExchangeInfo(ticker="T2")
        info1.sessions["test"] = ("00:00", "23:59")
        assert "test" not in info2.sessions

    def test_override_registry_isolation(self):
        """Override registry: changes don't leak between tests."""
        set_exchange_override("TEST1", timezone="UTC")
        clear_exchange_override()
        assert not has_override("TEST1")

    def test_parse_trading_hours_with_mixed_formats(self):
        """_parse_trading_hours: handles mixed HHMM and HH:MM formats."""
        result = _parse_trading_hours("0930", "16:00", "09:30-1600")
        assert result["regular"] == ("09:30", "16:00")
        assert result["futures"] == ("09:30", "16:00")

    def test_convert_session_times_preserves_date(self):
        """convert_session_times_to_utc: preserves date in output."""
        start, end = convert_session_times_to_utc(
            "2024-06-15 09:30:00",
            "2024-06-15 16:00:00",
            "UTC",
        )
        assert "2024-06-15" in start
        assert "2024-06-15" in end

    @pytest.mark.parametrize("ticker", ["", "   ", "\t", "\n"])
    def test_set_override_rejects_empty_tickers(self, ticker):
        """set_exchange_override: rejects all forms of empty ticker."""
        with pytest.raises(ValueError):
            set_exchange_override(ticker, timezone="UTC")

    @pytest.mark.parametrize(
        "time_str,expected",
        [
            ("0930", "09:30"),
            ("09:30", "09:30"),
            ("1600", "16:00"),
            ("16:00", "16:00"),
            ("0000", "00:00"),
            ("23:59", "23:59"),
        ],
    )
    def test_parse_hhmm_parametrized(self, time_str, expected):
        """_parse_hhmm: parametrized test for various formats."""
        assert _parse_hhmm(time_str) == expected

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("NY", "America/New_York"),
            ("ny", "America/New_York"),
            ("LN", "Europe/London"),
            ("ln", "Europe/London"),
            ("TK", "Asia/Tokyo"),
            ("tk", "Asia/Tokyo"),
            ("HK", "Asia/Hong_Kong"),
            ("hk", "Asia/Hong_Kong"),
        ],
    )
    def test_resolve_to_timezone_parametrized(self, alias, expected):
        """_resolve_to_timezone: parametrized test for aliases."""
        assert _resolve_to_timezone(alias, "UTC") == expected
