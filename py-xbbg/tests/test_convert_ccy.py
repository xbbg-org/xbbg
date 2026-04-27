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

from unittest import TestCase

import narwhals.stable.v1 as nw
import pandas as pd
import pytest

from xbbg.ext.currency import aconvert_ccy, convert_ccy, ext_build_fx_pair, ext_same_currency

_CASE = TestCase()


def test_fx_helpers_match_native_contract():
    _CASE.assertTrue(ext_same_currency("GBP", "GBp"))
    _CASE.assertFalse(ext_same_currency("GBP", "USD"))
    _CASE.assertEqual(ext_build_fx_pair("GBP", "USD"), ("USDGBP Curncy", 1.0, "GBP", "USD"))
    _CASE.assertEqual(ext_build_fx_pair("GBp", "USD"), ("USDGBP Curncy", 100.0, "GBP", "USD"))


class TestConvertCcyEmptyData:
    """Test convert_ccy with empty DataFrames."""

    def test_empty_dataframe_returns_empty(self):
        """convert_ccy with empty DataFrame should return empty."""
        pdf = pd.DataFrame()
        result = convert_ccy(pdf, ccy="USD")
        # Result should be convertible back and be empty
        result_nw = nw.from_native(result)
        _CASE.assertEqual(len(result_nw), 0)

    def test_empty_dataframe_with_columns_returns_empty(self):
        """convert_ccy with empty DataFrame that has column schema should return empty."""
        pdf = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": pd.Series([], dtype=float)})
        result = convert_ccy(pdf, ccy="USD")
        result_nw = nw.from_native(result)
        _CASE.assertEqual(len(result_nw), 0)


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
        _CASE.assertEqual(len(result_nw), 3)

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
        _CASE.assertEqual(len(result_nw), 2)

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
        _CASE.assertEqual(len(result_nw), 1)


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
        _CASE.assertEqual(len(result_nw), 1)


class TestAsyncConvertCcy:
    """Test async aconvert_ccy edge cases."""

    @pytest.mark.asyncio
    async def test_async_empty_dataframe(self):
        """aconvert_ccy with empty DataFrame should return empty."""
        pdf = pd.DataFrame()
        result = await aconvert_ccy(pdf, ccy="USD")
        result_nw = nw.from_native(result)
        _CASE.assertEqual(len(result_nw), 0)

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
        _CASE.assertEqual(len(result_nw), 1)


@pytest.mark.asyncio
async def test_async_convert_ccy_warns_for_malformed_fx_rows(monkeypatch, caplog):
    """Malformed FX responses are aggregated while valid rows still convert."""
    import logging

    import xbbg

    async def fake_abdp(*, tickers, flds, **kwargs):
        return pd.DataFrame(
            {
                "ticker": ["ABC LN Equity"],
                "field": ["crncy"],
                "value": ["GBP"],
            }
        )

    async def fake_abdh(*, tickers, flds, start_date, end_date, **kwargs):
        return pd.DataFrame(
            {
                "ticker": ["USDGBP Curncy", "USDGBP Curncy", "USDGBP Curncy"],
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "field": ["PX_LAST", "PX_LAST", "PX_LAST"],
                "value": ["2", "bad", "0"],
            }
        )

    monkeypatch.setattr(xbbg, "abdp", fake_abdp, raising=False)
    monkeypatch.setattr(xbbg, "abdh", fake_abdh, raising=False)

    pdf = pd.DataFrame(
        {
            "ticker": ["ABC LN Equity", "ABC LN Equity", "ABC LN Equity"],
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "field": ["PX_LAST", "PX_LAST", "PX_LAST"],
            "value": ["10", "20", "30"],
        }
    )

    with caplog.at_level(logging.WARNING, logger="xbbg.ext.currency"):
        result = await aconvert_ccy(pdf, ccy="USD")

    result_nw = nw.from_native(result)
    _CASE.assertEqual(result_nw["value"].to_list(), ["5.0", "20", "30"])
    _CASE.assertIn("malformed_fx_rows=1", caplog.text)
    _CASE.assertIn("zero_fx_rows=1", caplog.text)
    _CASE.assertIn("unconverted_rows=2", caplog.text)


@pytest.mark.asyncio
async def test_async_convert_ccy_ignores_non_numeric_source_without_warning(monkeypatch, caplog):
    """Non-numeric source values remain best-effort and silent."""
    import logging

    import xbbg

    async def fake_abdp(*, tickers, flds, **kwargs):
        return pd.DataFrame({"ticker": ["ABC LN Equity"], "field": ["crncy"], "value": ["GBP"]})

    async def fake_abdh(*, tickers, flds, start_date, end_date, **kwargs):
        return pd.DataFrame(
            {
                "ticker": ["USDGBP Curncy"],
                "date": ["2024-01-01"],
                "field": ["PX_LAST"],
                "value": ["2"],
            }
        )

    monkeypatch.setattr(xbbg, "abdp", fake_abdp, raising=False)
    monkeypatch.setattr(xbbg, "abdh", fake_abdh, raising=False)

    pdf = pd.DataFrame(
        {
            "ticker": ["ABC LN Equity"],
            "date": ["2024-01-01"],
            "field": ["PX_LAST"],
            "value": ["N/A"],
        }
    )

    with caplog.at_level(logging.WARNING, logger="xbbg.ext.currency"):
        result = await aconvert_ccy(pdf, ccy="USD")

    _CASE.assertEqual(nw.from_native(result)["value"].to_list(), ["N/A"])
    _CASE.assertEqual(caplog.text, "")
