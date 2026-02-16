"""Tests for convert_ccy edge cases.

Ported from main branch xbbg/tests/test_helpers.py (TestAdjustCcy class).
Adapted for the current branch where convert_ccy lives in xbbg.ext.currency
and uses narwhals DataFrames rather than pandas.

These tests cover the non-Bloomberg-dependent edge cases:
- Empty DataFrame handling
- "local" currency (no conversion)
- Case insensitive "LOCAL" currency
"""

from __future__ import annotations

import narwhals.stable.v1 as nw
import pandas as pd
import pytest

from xbbg.ext.currency import aconvert_ccy, convert_ccy


class TestConvertCcyEmptyData:
    """Test convert_ccy with empty DataFrames."""

    def test_empty_dataframe_returns_empty(self):
        """convert_ccy with empty DataFrame should return empty."""
        pdf = pd.DataFrame()
        result = convert_ccy(pdf, ccy="USD")
        # Result should be convertible back and be empty
        result_nw = nw.from_native(result)
        assert len(result_nw) == 0

    def test_empty_dataframe_with_columns_returns_empty(self):
        """convert_ccy with empty DataFrame that has column schema should return empty."""
        pdf = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": pd.Series([], dtype=float)})
        result = convert_ccy(pdf, ccy="USD")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 0


class TestConvertCcyLocalCurrency:
    """Test convert_ccy with 'local' currency (no conversion)."""

    def test_local_currency_returns_unchanged(self):
        """convert_ccy with ccy='local' should return data unchanged."""
        pdf = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "value": [100.0, 101.0, 102.0],
            }
        )
        result = convert_ccy(pdf, ccy="local")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 3

    def test_local_currency_case_insensitive(self):
        """convert_ccy with ccy='LOCAL' (uppercase) should also return unchanged."""
        pdf = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "value": [100.0, 101.0],
            }
        )
        result = convert_ccy(pdf, ccy="LOCAL")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 2

    def test_local_currency_mixed_case(self):
        """convert_ccy with ccy='Local' (mixed case) should also return unchanged."""
        pdf = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "value": [100.0],
            }
        )
        result = convert_ccy(pdf, ccy="Local")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 1


class TestConvertCcyNoValueColumns:
    """Test convert_ccy when there are no value columns to convert."""

    def test_only_metadata_columns_returns_unchanged(self):
        """DataFrame with only date/ticker/field columns should be returned as-is."""
        pdf = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "ticker": ["AAPL US Equity"],
                "field": ["PX_LAST"],
            }
        )
        result = convert_ccy(pdf, ccy="USD")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 1


class TestAsyncConvertCcy:
    """Test async aconvert_ccy edge cases."""

    @pytest.mark.asyncio
    async def test_async_empty_dataframe(self):
        """aconvert_ccy with empty DataFrame should return empty."""
        pdf = pd.DataFrame()
        result = await aconvert_ccy(pdf, ccy="USD")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 0

    @pytest.mark.asyncio
    async def test_async_local_currency(self):
        """aconvert_ccy with ccy='local' should return unchanged."""
        pdf = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "value": [100.0],
            }
        )
        result = await aconvert_ccy(pdf, ccy="local")
        result_nw = nw.from_native(result)
        assert len(result_nw) == 1
