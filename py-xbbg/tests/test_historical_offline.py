"""Offline tests for historical extension fallbacks."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from unittest import TestCase

import narwhals.stable.v1 as nw
import pandas as pd
import pytest

from xbbg.ext.historical import aturnover, ext_default_turnover_dates

_CASE = TestCase()


def test_default_turnover_dates_matches_native_invalid_date_fallbacks():
    _CASE.assertEqual(ext_default_turnover_dates("not-a-date", "2024-06-15"), ("2024-05-16", "2024-06-15"))

    start, end = ext_default_turnover_dates(None, "not-a-date")
    _CASE.assertEqual(end, (date.today() - timedelta(days=1)).isoformat())
    _CASE.assertEqual(start, (date.fromisoformat(end) - timedelta(days=30)).isoformat())


@pytest.mark.asyncio
async def test_aturnover_rejects_invalid_explicit_dates(monkeypatch):
    import xbbg

    async def unexpected_abdh(**_kwargs):
        raise AssertionError("invalid dates must fail before requesting Bloomberg data")

    monkeypatch.setattr(xbbg, "abdh", unexpected_abdh, raising=False)

    with pytest.raises(ValueError):
        await aturnover("ABC US Equity", start_date="not-a-date", end_date="2024-06-15")

    with pytest.raises(ValueError):
        await aturnover("ABC US Equity", start_date="2024-01-01", end_date="not-a-date")

@pytest.mark.asyncio
async def test_aturnover_warns_for_malformed_volume_fallback(monkeypatch, caplog):
    """Malformed present VWAP/volume values are aggregated without live Bloomberg."""
    import xbbg

    calls = []

    async def fake_abdh(*, tickers, flds, start_date, end_date, **kwargs):
        calls.append(flds)
        if flds == "Turnover":
            return pd.DataFrame(columns=["ticker", "date", "field", "value"])
        return pd.DataFrame(
            {
                "ticker": ["ABC US Equity", "ABC US Equity", "ABC US Equity", "ABC US Equity"],
                "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
                "field": ["eqy_weighted_avg_px", "volume", "eqy_weighted_avg_px", "volume"],
                "value": ["10", "bad", "3", "4"],
            }
        )

    monkeypatch.setattr(xbbg, "abdh", fake_abdh, raising=False)

    with caplog.at_level(logging.WARNING, logger="xbbg.ext.historical"):
        result = await aturnover(
            "ABC US Equity",
            start_date="2024-01-01",
            end_date="2024-01-02",
            ccy="local",
            factor=1.0,
        )

    result_nw = nw.from_native(result)
    _CASE.assertEqual(result_nw["value"].to_list(), ["12.0"])
    _CASE.assertIn("malformed_rows=1", caplog.text)
    _CASE.assertIn("ABC US Equity/2024-01-01", caplog.text)
    _CASE.assertEqual(calls, ["Turnover", ["eqy_weighted_avg_px", "volume"]])


@pytest.mark.asyncio
async def test_aturnover_does_not_warn_for_sparse_volume_fallback(monkeypatch, caplog):
    """Genuinely missing sparse VWAP/volume data stays silent."""
    import xbbg

    async def fake_abdh(*, tickers, flds, start_date, end_date, **kwargs):
        if flds == "Turnover":
            return pd.DataFrame(columns=["ticker", "date", "field", "value"])
        return pd.DataFrame(
            {
                "ticker": ["ABC US Equity", "ABC US Equity"],
                "date": ["2024-01-01", "2024-01-02"],
                "field": ["eqy_weighted_avg_px", "volume"],
                "value": ["10", "4"],
            }
        )

    monkeypatch.setattr(xbbg, "abdh", fake_abdh, raising=False)

    with caplog.at_level(logging.WARNING, logger="xbbg.ext.historical"):
        result = await aturnover(
            "ABC US Equity",
            start_date="2024-01-01",
            end_date="2024-01-02",
            ccy="local",
            factor=1.0,
        )

    _CASE.assertEqual(len(nw.from_native(result)), 0)
    _CASE.assertEqual(caplog.text, "")
