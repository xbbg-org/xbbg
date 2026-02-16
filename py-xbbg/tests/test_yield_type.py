"""Tests for YieldType enum.

Ported from main branch xbbg/tests/test_yas.py (TestYieldTypeEnum class).
Tests the YieldType IntEnum used in fixed income YAS analysis.
"""

from __future__ import annotations

from enum import IntEnum

import pytest

from xbbg.ext.fixed_income import YieldType


class TestYieldTypeEnum:
    """Tests for YieldType enum values and behavior."""

    def test_yield_type_is_int_enum(self):
        """YieldType should be an IntEnum."""
        assert issubclass(YieldType, IntEnum)

    def test_yield_type_members_are_ints(self):
        """Each YieldType member should be usable as an int."""
        for member in YieldType:
            assert isinstance(member, int)

    def test_ytm_value(self):
        """YTM (Yield to Maturity) should be 1."""
        assert YieldType.YTM == 1
        assert int(YieldType.YTM) == 1

    def test_ytc_value(self):
        """YTC (Yield to Call) should be 2."""
        assert YieldType.YTC == 2
        assert int(YieldType.YTC) == 2

    def test_ytr_value(self):
        """YTR (Yield to Refunding) should be 3."""
        assert YieldType.YTR == 3

    def test_ytp_value(self):
        """YTP (Yield to Next Put) should be 4."""
        assert YieldType.YTP == 4

    def test_ytw_value(self):
        """YTW (Yield to Worst) should be 5."""
        assert YieldType.YTW == 5

    def test_ytwr_value(self):
        """YTWR (Yield to Worst Refunding) should be 6."""
        assert YieldType.YTWR == 6

    def test_eytw_value(self):
        """EYTW (Euro Yield to Worst) should be 7."""
        assert YieldType.EYTW == 7

    def test_eytwr_value(self):
        """EYTWR (Euro Yield to Worst Refunding) should be 8."""
        assert YieldType.EYTWR == 8

    def test_ytal_value(self):
        """YTAL (Yield to Average Life) should be 9."""
        assert YieldType.YTAL == 9

    def test_total_member_count(self):
        """YieldType should have exactly 9 members."""
        assert len(YieldType) == 9

    def test_comparison_with_integers(self):
        """YieldType members should be directly comparable with ints."""
        assert YieldType.YTM == 1
        assert YieldType.YTM < YieldType.YTC
        assert YieldType.YTAL > YieldType.YTM
        assert YieldType.YTW >= 5
        assert YieldType.YTW <= 5

    def test_comparison_between_members(self):
        """YieldType members should be orderable."""
        assert YieldType.YTM < YieldType.YTC
        assert YieldType.YTC < YieldType.YTR
        assert YieldType.YTR < YieldType.YTP
        assert YieldType.YTP < YieldType.YTW
        assert YieldType.YTW < YieldType.YTWR
        assert YieldType.YTWR < YieldType.EYTW
        assert YieldType.EYTW < YieldType.EYTWR
        assert YieldType.EYTWR < YieldType.YTAL

    def test_yield_type_lookup_by_value(self):
        """YieldType should support lookup by integer value."""
        assert YieldType(1) == YieldType.YTM
        assert YieldType(5) == YieldType.YTW
        assert YieldType(9) == YieldType.YTAL

    def test_yield_type_invalid_value_raises(self):
        """YieldType should raise ValueError for invalid values."""
        with pytest.raises(ValueError):
            YieldType(0)
        with pytest.raises(ValueError):
            YieldType(10)

    def test_yield_type_lookup_by_name(self):
        """YieldType should support lookup by name string."""
        assert YieldType["YTM"] == YieldType.YTM
        assert YieldType["YTAL"] == YieldType.YTAL

    def test_yield_type_name_attribute(self):
        """YieldType members should have correct name attributes."""
        assert YieldType.YTM.name == "YTM"
        assert YieldType.YTAL.name == "YTAL"

    def test_yield_type_can_be_used_in_arithmetic(self):
        """YieldType members should support arithmetic as ints."""
        assert YieldType.YTM + 1 == YieldType.YTC
        assert YieldType.YTAL - YieldType.YTM == 8
