from __future__ import annotations

from typing import Any

import pytest

from xbbg import blp
from xbbg.services import Operation, Service


class _FakePdf:
    def __init__(self, columns: list[str]):
        self.columns = columns


class _FakeNwDf:
    def __init__(self, columns: list[str]):
        self._columns = columns

    def __len__(self):
        return 1

    def to_pandas(self):
        return _FakePdf(self._columns)


@pytest.mark.asyncio
async def test_abqr_generated_routes_intraday_tick_defaults(monkeypatch):
    captured: dict[str, Any] = {}
    fake_df = _FakeNwDf(columns=[])

    async def fake_arequest(*, service, operation, backend, **kwargs):
        captured["service"] = service
        captured["operation"] = operation
        captured["backend"] = backend
        captured["kwargs"] = kwargs
        return fake_df

    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = await blp.abqr("IBM US Equity@MSG1", date_offset="-1d")

    assert captured["service"] == Service.REFDATA
    assert captured["operation"] == Operation.INTRADAY_TICK
    assert captured["backend"] is None

    kwargs = captured["kwargs"]
    assert kwargs["security"] == "IBM US Equity@MSG1"
    assert kwargs["event_types"] == ["BID", "ASK"]
    assert kwargs["elements"] is None
    assert "T" in kwargs["start_datetime"]
    assert "T" in kwargs["end_datetime"]
    assert result is fake_df


@pytest.mark.asyncio
async def test_abqr_generated_reshapes_generic_when_extras_requested(monkeypatch):
    captured: dict[str, Any] = {}
    reshape_calls: dict[str, Any] = {}
    reshaped = object()

    async def fake_arequest(*, service, operation, backend, **kwargs):
        captured["service"] = service
        captured["operation"] = operation
        captured["backend"] = backend
        captured["kwargs"] = kwargs
        return _FakeNwDf(columns=["path"])

    def fake_reshape(pdf, ticker):
        reshape_calls["pdf"] = pdf
        reshape_calls["ticker"] = ticker
        return reshaped

    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_reshape_bqr_generic", fake_reshape)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = await blp.abqr(
        "US037833FB15@MSG1 Corp",
        date_offset="-2d",
        include_broker_codes=True,
        include_spread_price=True,
    )

    assert captured["service"] == Service.REFDATA
    assert captured["operation"] == Operation.INTRADAY_TICK
    assert captured["backend"] is None

    kwargs = captured["kwargs"]
    assert kwargs["event_types"] == ["BID", "ASK"]
    assert kwargs["elements"] == [
        ("includeBrokerCodes", "true"),
        ("includeSpreadPrice", "true"),
    ]

    assert reshape_calls["ticker"] == "US037833FB15@MSG1 Corp"
    assert result is reshaped


@pytest.mark.asyncio
async def test_abqr_generated_uses_explicit_date_range_and_event_types(monkeypatch):
    captured: dict[str, Any] = {}
    fake_df = _FakeNwDf(columns=[])

    async def fake_arequest(*, service, operation, backend, **kwargs):
        captured["service"] = service
        captured["operation"] = operation
        captured["backend"] = backend
        captured["kwargs"] = kwargs
        return fake_df

    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = await blp.abqr(
        "XYZ 4.5 01/15/30@MSG1 Corp",
        start_date="2024-01-15",
        end_date="2024-01-17",
        event_types=["TRADE"],
    )

    assert captured["service"] == Service.REFDATA
    assert captured["operation"] == Operation.INTRADAY_TICK
    assert captured["backend"] is None

    kwargs = captured["kwargs"]
    assert kwargs["security"] == "XYZ 4.5 01/15/30@MSG1 Corp"
    assert kwargs["start_datetime"] == "2024-01-15T00:00:00"
    assert kwargs["end_datetime"] == "2024-01-17T23:59:59"
    assert kwargs["event_types"] == ["TRADE"]
    assert result is fake_df
