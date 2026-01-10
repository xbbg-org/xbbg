"""Unit tests for constants and configuration mappings.

Tests all constant definitions in xbbg/const.py including:
- Futures month codes mapping
- CurrencyPair dataclass
- ValidSessions list
- ASSET_INFO mapping
- DVD_TPYES mapping
- DVD_COLS mapping
- LIVE_INFO, LIVE_CHG, LIVE_VOL, LIVE_RATIO sets
- PKG_PATH validation
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from xbbg import const


class TestFuturesMonthCodes:
    """Test Futures month codes mapping."""

    def test_futures_has_all_12_months(self):
        """Test that Futures dict contains all 12 months."""
        expected_months = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        assert len(const.Futures) == 12
        for month in expected_months:
            assert month in const.Futures

    def test_futures_month_codes_are_correct(self):
        """Test that each month maps to the correct Bloomberg code."""
        expected = {
            "Jan": "F",
            "Feb": "G",
            "Mar": "H",
            "Apr": "J",
            "May": "K",
            "Jun": "M",
            "Jul": "N",
            "Aug": "Q",
            "Sep": "U",
            "Oct": "V",
            "Nov": "X",
            "Dec": "Z",
        }
        assert const.Futures == expected

    def test_futures_codes_are_unique(self):
        """Test that all futures codes are unique."""
        codes = list(const.Futures.values())
        assert len(codes) == len(set(codes))

    def test_futures_codes_are_single_letters(self):
        """Test that all futures codes are single uppercase letters."""
        for code in const.Futures.values():
            assert len(code) == 1
            assert code.isupper()


class TestCurrencyPair:
    """Test CurrencyPair dataclass."""

    def test_currency_pair_creation(self):
        """Test creating a CurrencyPair instance."""
        pair = const.CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        assert pair.ticker == "EURUSD Curncy"
        assert pair.factor == 1.0
        assert pair.power == 1.0

    def test_currency_pair_is_frozen(self):
        """Test that CurrencyPair is immutable (frozen)."""
        pair = const.CurrencyPair(ticker="GBPUSD Curncy", factor=1.0, power=1.0)
        with pytest.raises(FrozenInstanceError):
            pair.ticker = "USDJPY Curncy"

    def test_currency_pair_with_different_values(self):
        """Test CurrencyPair with non-default factor and power."""
        pair = const.CurrencyPair(ticker="USDJPY Curncy", factor=100.0, power=-1.0)
        assert pair.factor == 100.0
        assert pair.power == -1.0

    def test_currency_pair_equality(self):
        """Test CurrencyPair equality comparison."""
        pair1 = const.CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        pair2 = const.CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        assert pair1 == pair2

    def test_currency_pair_inequality(self):
        """Test CurrencyPair inequality comparison."""
        pair1 = const.CurrencyPair(ticker="EURUSD Curncy", factor=1.0, power=1.0)
        pair2 = const.CurrencyPair(ticker="GBPUSD Curncy", factor=1.0, power=1.0)
        assert pair1 != pair2


class TestValidSessions:
    """Test ValidSessions list."""

    def test_valid_sessions_contains_expected_sessions(self):
        """Test that ValidSessions contains all expected session names."""
        expected = ["allday", "day", "am", "pm", "night", "pre", "post"]
        assert const.ValidSessions == expected

    def test_valid_sessions_is_list(self):
        """Test that ValidSessions is a list."""
        assert isinstance(const.ValidSessions, list)

    def test_valid_sessions_has_seven_entries(self):
        """Test that ValidSessions has exactly 7 entries."""
        assert len(const.ValidSessions) == 7


class TestAssetInfo:
    """Test ASSET_INFO mapping."""

    def test_asset_info_has_expected_keys(self):
        """Test that ASSET_INFO contains expected asset types."""
        expected_keys = ["Index", "Comdty", "Curncy", "Equity"]
        for key in expected_keys:
            assert key in const.ASSET_INFO

    def test_asset_info_index_config(self):
        """Test Index asset configuration."""
        assert const.ASSET_INFO["Index"] == ["tickers"]

    def test_asset_info_comdty_config(self):
        """Test Comdty asset configuration."""
        assert const.ASSET_INFO["Comdty"] == ["tickers", "key_month"]

    def test_asset_info_curncy_config(self):
        """Test Curncy asset configuration."""
        assert const.ASSET_INFO["Curncy"] == ["tickers"]

    def test_asset_info_equity_config(self):
        """Test Equity asset configuration."""
        assert const.ASSET_INFO["Equity"] == ["exch_codes"]

    def test_asset_info_values_are_lists(self):
        """Test that all ASSET_INFO values are lists."""
        for value in const.ASSET_INFO.values():
            assert isinstance(value, list)


class TestDvdTypes:
    """Test DVD_TPYES mapping."""

    def test_dvd_types_has_expected_keys(self):
        """Test that DVD_TPYES contains expected dividend type keys."""
        expected_keys = [
            "all",
            "dvd",
            "split",
            "gross",
            "adjust",
            "adj_fund",
            "with_amt",
            "dvd_amt",
            "gross_amt",
            "projected",
        ]
        for key in expected_keys:
            assert key in const.DVD_TPYES

    def test_dvd_types_all_mapping(self):
        """Test 'all' dividend type mapping."""
        assert const.DVD_TPYES["all"] == "DVD_Hist_All"

    def test_dvd_types_dvd_mapping(self):
        """Test 'dvd' dividend type mapping."""
        assert const.DVD_TPYES["dvd"] == "DVD_Hist"

    def test_dvd_types_split_mapping(self):
        """Test 'split' dividend type mapping."""
        assert const.DVD_TPYES["split"] == "Eqy_DVD_Hist_Splits"

    def test_dvd_types_projected_mapping(self):
        """Test 'projected' dividend type mapping."""
        assert const.DVD_TPYES["projected"] == "BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann"

    def test_dvd_types_values_are_strings(self):
        """Test that all DVD_TPYES values are strings."""
        for value in const.DVD_TPYES.values():
            assert isinstance(value, str)


class TestDvdCols:
    """Test DVD_COLS mapping."""

    def test_dvd_cols_has_expected_keys(self):
        """Test that DVD_COLS contains expected column name keys."""
        expected_keys = [
            "Declared Date",
            "Ex-Date",
            "Record Date",
            "Payable Date",
            "Dividend Amount",
            "Dividend Frequency",
            "Dividend Type",
            "Amount Status",
            "Adjustment Date",
            "Adjustment Factor",
            "Adjustment Factor Operator Type",
            "Adjustment Factor Flag",
            "Amount Per Share",
            "Projected/Confirmed",
        ]
        for key in expected_keys:
            assert key in const.DVD_COLS

    def test_dvd_cols_date_mappings(self):
        """Test date column mappings."""
        assert const.DVD_COLS["Declared Date"] == "dec_date"
        assert const.DVD_COLS["Ex-Date"] == "ex_date"
        assert const.DVD_COLS["Record Date"] == "rec_date"
        assert const.DVD_COLS["Payable Date"] == "pay_date"

    def test_dvd_cols_amount_mapping(self):
        """Test dividend amount column mapping."""
        assert const.DVD_COLS["Dividend Amount"] == "dvd_amt"

    def test_dvd_cols_values_are_snake_case(self):
        """Test that all DVD_COLS values are snake_case strings."""
        for value in const.DVD_COLS.values():
            assert isinstance(value, str)
            # Check it's lowercase with underscores (snake_case)
            assert value == value.lower()


class TestLiveInfo:
    """Test LIVE_INFO set."""

    def test_live_info_is_set(self):
        """Test that LIVE_INFO is a set."""
        assert isinstance(const.LIVE_INFO, set)

    def test_live_info_contains_last_price(self):
        """Test that LIVE_INFO contains LAST_PRICE field."""
        assert "LAST_PRICE" in const.LIVE_INFO

    def test_live_info_contains_bid_ask(self):
        """Test that LIVE_INFO contains BID and ASK fields."""
        assert "BID" in const.LIVE_INFO
        assert "ASK" in const.LIVE_INFO

    def test_live_info_contains_volume(self):
        """Test that LIVE_INFO contains VOLUME field."""
        assert "VOLUME" in const.LIVE_INFO

    def test_live_info_contains_event_type(self):
        """Test that LIVE_INFO contains event type fields."""
        assert "MKTDATA_EVENT_TYPE" in const.LIVE_INFO
        assert "MKTDATA_EVENT_SUBTYPE" in const.LIVE_INFO

    def test_live_info_all_uppercase(self):
        """Test that all LIVE_INFO fields are uppercase."""
        for field in const.LIVE_INFO:
            assert field == field.upper()


class TestLiveChg:
    """Test LIVE_CHG set."""

    def test_live_chg_is_set(self):
        """Test that LIVE_CHG is a set."""
        assert isinstance(const.LIVE_CHG, set)

    def test_live_chg_contains_1d_change(self):
        """Test that LIVE_CHG contains 1-day change field."""
        assert "RT_PX_CHG_PCT_1D" in const.LIVE_CHG

    def test_live_chg_contains_ytd_change(self):
        """Test that LIVE_CHG contains YTD change field."""
        assert "CHG_PCT_YTD_RT" in const.LIVE_CHG

    def test_live_chg_contains_realtime_changes(self):
        """Test that LIVE_CHG contains realtime change fields."""
        assert "REALTIME_15_SEC_PRICE_PCT_CHG" in const.LIVE_CHG
        assert "REALTIME_ONE_MIN_PRICE_PCT_CHG" in const.LIVE_CHG


class TestLiveVol:
    """Test LIVE_VOL set."""

    def test_live_vol_is_set(self):
        """Test that LIVE_VOL is a set."""
        assert isinstance(const.LIVE_VOL, set)

    def test_live_vol_contains_volume_interval(self):
        """Test that LIVE_VOL contains volume interval field."""
        assert "REALTIME_VOLUME_5_DAY_INTERVAL" in const.LIVE_VOL

    def test_live_vol_contains_delta_avat_fields(self):
        """Test that LIVE_VOL contains DELTA_AVAT fields."""
        assert "DELTA_AVAT_1_DAY_INTERVAL" in const.LIVE_VOL
        assert "DELTA_AVAT_5_DAY_INTERVAL" in const.LIVE_VOL

    def test_live_vol_contains_delta_atat_fields(self):
        """Test that LIVE_VOL contains DELTA_ATAT fields."""
        assert "DELTA_ATAT_1_DAY_INTERVAL" in const.LIVE_VOL
        assert "DELTA_ATAT_5_DAY_INTERVAL" in const.LIVE_VOL


class TestLiveRatio:
    """Test LIVE_RATIO set."""

    def test_live_ratio_is_set(self):
        """Test that LIVE_RATIO is a set."""
        assert isinstance(const.LIVE_RATIO, set)

    def test_live_ratio_contains_pe_ratio(self):
        """Test that LIVE_RATIO contains P/E ratio field."""
        assert "PRICE_EARNINGS_RATIO_RT" in const.LIVE_RATIO

    def test_live_ratio_contains_pb_ratio(self):
        """Test that LIVE_RATIO contains P/B ratio field."""
        assert "PRICE_TO_BOOK_RATIO_RT" in const.LIVE_RATIO

    def test_live_ratio_contains_ps_ratio(self):
        """Test that LIVE_RATIO contains P/S ratio field."""
        assert "PRICE_TO_SALES_RATIO_RT" in const.LIVE_RATIO

    def test_live_ratio_has_five_fields(self):
        """Test that LIVE_RATIO has exactly 5 fields."""
        assert len(const.LIVE_RATIO) == 5


class TestPkgPath:
    """Test PKG_PATH constant."""

    def test_pkg_path_is_string(self):
        """Test that PKG_PATH is a string."""
        assert isinstance(const.PKG_PATH, str)

    def test_pkg_path_exists(self):
        """Test that PKG_PATH points to an existing directory."""
        assert Path(const.PKG_PATH).exists()

    def test_pkg_path_is_directory(self):
        """Test that PKG_PATH is a directory."""
        assert Path(const.PKG_PATH).is_dir()

    def test_pkg_path_contains_const_module(self):
        """Test that PKG_PATH contains the const.py module."""
        const_file = Path(const.PKG_PATH) / "const.py"
        assert const_file.exists()


class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_exports_exist(self):
        """Test that all items in __all__ are accessible."""
        for name in const.__all__:
            assert hasattr(const, name), f"{name} in __all__ but not accessible"

    def test_futures_in_exports(self):
        """Test that Futures is in exports."""
        assert "Futures" in const.__all__

    def test_currency_pair_in_exports(self):
        """Test that CurrencyPair is in exports."""
        assert "CurrencyPair" in const.__all__

    def test_valid_sessions_in_exports(self):
        """Test that ValidSessions is in exports."""
        assert "ValidSessions" in const.__all__

    def test_live_sets_in_exports(self):
        """Test that LIVE_* sets are in exports."""
        assert "LIVE_INFO" in const.__all__
        assert "LIVE_CHG" in const.__all__
        assert "LIVE_VOL" in const.__all__
        assert "LIVE_RATIO" in const.__all__
