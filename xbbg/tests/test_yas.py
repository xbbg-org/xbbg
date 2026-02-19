"""Tests for Bloomberg YAS (Yield & Spread Analysis) API."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, patch

import pandas as pd

from xbbg.api.fixed_income import YieldType, yas
from xbbg.api.reference import reference as _ref_mod


class TestYieldTypeEnum:
    """Tests for YieldType enum."""

    def test_yield_type_ytm_value(self):
        """Test YTM enum value is 1."""
        assert YieldType.YTM == 1
        assert int(YieldType.YTM) == 1

    def test_yield_type_ytc_value(self):
        """Test YTC enum value is 2."""
        assert YieldType.YTC == 2
        assert int(YieldType.YTC) == 2

    def test_yield_type_is_int_enum(self):
        """Test YieldType is an IntEnum and can be used as int."""
        assert isinstance(YieldType.YTM, int)
        assert isinstance(YieldType.YTC, int)

    def test_yield_type_comparison(self):
        """Test YieldType can be compared with integers."""
        assert YieldType.YTM == 1
        assert YieldType.YTC == 2
        assert YieldType.YTM < YieldType.YTC


class TestYasOverrideMapping:
    """Tests for YAS override parameter mapping."""

    @patch.object(_ref_mod, "bdp")
    def test_yas_default_field(self, mock_bdp: MagicMock):
        """Test default field is YAS_BOND_YLD."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["flds"] == "YAS_BOND_YLD"

    @patch.object(_ref_mod, "bdp")
    def test_yas_custom_fields(self, mock_bdp: MagicMock):
        """Test custom fields are passed through."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", flds=["YAS_BOND_YLD", "YAS_MOD_DUR"])
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["flds"] == ["YAS_BOND_YLD", "YAS_MOD_DUR"]

    @patch.object(_ref_mod, "bdp")
    def test_yas_settle_dt_string(self, mock_bdp: MagicMock):
        """Test settle_dt string override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", settle_dt="20240115")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["SETTLE_DT"] == "20240115"

    @patch.object(_ref_mod, "bdp")
    def test_yas_settle_dt_timestamp(self, mock_bdp: MagicMock):
        """Test settle_dt Timestamp override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        settle_dt = cast(pd.Timestamp, pd.Timestamp("2024-01-15"))
        yas("US912810TD00 Govt", settle_dt=settle_dt)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["SETTLE_DT"] == "20240115"

    @patch.object(_ref_mod, "bdp")
    def test_yas_settle_dt_date_string_format(self, mock_bdp: MagicMock):
        """Test settle_dt with various date string formats."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", settle_dt="2024-01-15")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["SETTLE_DT"] == "20240115"

    @patch.object(_ref_mod, "bdp")
    def test_yas_yield_type_ytm(self, mock_bdp: MagicMock):
        """Test yield_type YTM override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", yield_type=YieldType.YTM)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_YLD_FLAG"] == 1

    @patch.object(_ref_mod, "bdp")
    def test_yas_yield_type_ytc(self, mock_bdp: MagicMock):
        """Test yield_type YTC override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", yield_type=YieldType.YTC)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_YLD_FLAG"] == 2

    @patch.object(_ref_mod, "bdp")
    def test_yas_yield_type_int(self, mock_bdp: MagicMock):
        """Test yield_type accepts raw integer."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", yield_type=1)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_YLD_FLAG"] == 1

    @patch.object(_ref_mod, "bdp")
    def test_yas_spread_override(self, mock_bdp: MagicMock):
        """Test spread override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", spread=75.5)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_YLD_SPREAD"] == 75.5

    @patch.object(_ref_mod, "bdp")
    def test_yas_yield_override(self, mock_bdp: MagicMock):
        """Test yield_ override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", yield_=4.5)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_BOND_YLD"] == 4.5

    @patch.object(_ref_mod, "bdp")
    def test_yas_price_override(self, mock_bdp: MagicMock):
        """Test price override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", price=98.5)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_BOND_PX"] == 98.5

    @patch.object(_ref_mod, "bdp")
    def test_yas_benchmark_override(self, mock_bdp: MagicMock):
        """Test benchmark override mapping."""
        mock_bdp.return_value = pd.DataFrame()
        yas("XYZ Corp", benchmark="US912810TD00 Govt")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["YAS_BNCHMRK_BOND"] == "US912810TD00 Govt"

    @patch.object(_ref_mod, "bdp")
    def test_yas_multiple_overrides(self, mock_bdp: MagicMock):
        """Test multiple overrides are combined correctly."""
        mock_bdp.return_value = pd.DataFrame()
        yas(
            "US912810TD00 Govt",
            settle_dt="20240115",
            yield_type=YieldType.YTM,
            price=98.5,
        )
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["SETTLE_DT"] == "20240115"
        assert call_kwargs[1]["YAS_YLD_FLAG"] == 1
        assert call_kwargs[1]["YAS_BOND_PX"] == 98.5

    @patch.object(_ref_mod, "bdp")
    def test_yas_kwargs_passthrough(self, mock_bdp: MagicMock):
        """Test additional kwargs are passed through."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", CUSTOM_OVERRIDE="value")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["CUSTOM_OVERRIDE"] == "value"

    @patch.object(_ref_mod, "bdp")
    def test_yas_kwargs_override_named_params(self, mock_bdp: MagicMock):
        """Test kwargs override named parameters (kwargs take precedence)."""
        mock_bdp.return_value = pd.DataFrame()
        # YAS_BOND_PX in kwargs should override price parameter
        yas("US912810TD00 Govt", price=98.5, YAS_BOND_PX=99.0)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        # kwargs value should win
        assert call_kwargs[1]["YAS_BOND_PX"] == 99.0

    @patch.object(_ref_mod, "bdp")
    def test_yas_no_overrides_when_none(self, mock_bdp: MagicMock):
        """Test no overrides added when parameters are None."""
        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt")
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        # Should not have any YAS override keys
        assert "SETTLE_DT" not in call_kwargs[1]
        assert "YAS_YLD_FLAG" not in call_kwargs[1]
        assert "YAS_YLD_SPREAD" not in call_kwargs[1]
        assert "YAS_BOND_YLD" not in call_kwargs[1]
        assert "YAS_BOND_PX" not in call_kwargs[1]
        assert "YAS_BNCHMRK_BOND" not in call_kwargs[1]


class TestYasBackendFormat:
    """Tests for backend and format parameter passthrough."""

    @patch.object(_ref_mod, "bdp")
    def test_yas_backend_passthrough(self, mock_bdp: MagicMock):
        """Test backend parameter is passed through."""
        from xbbg.backend import Backend

        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", backend=Backend.PANDAS)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["backend"] == Backend.PANDAS

    @patch.object(_ref_mod, "bdp")
    def test_yas_format_passthrough(self, mock_bdp: MagicMock):
        """Test format parameter is passed through."""
        from xbbg.backend import Format

        mock_bdp.return_value = pd.DataFrame()
        yas("US912810TD00 Govt", format=Format.LONG)
        mock_bdp.assert_called_once()
        call_kwargs = mock_bdp.call_args
        assert call_kwargs[1]["format"] == Format.LONG


class TestYasImports:
    """Tests for module imports."""

    def test_import_from_fixed_income(self):
        """Test importing from xbbg.api.fixed_income."""
        from xbbg.api.fixed_income import YieldType, yas

        assert callable(yas)
        assert YieldType.YTM == 1

    def test_import_from_blp(self):
        """Test importing from xbbg.blp (with deprecation warning)."""
        import warnings

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            from xbbg import blp

            # Access yas to trigger import
            yas_fn = getattr(blp, "yas", None)
            assert yas_fn is not None
            assert callable(yas_fn)
