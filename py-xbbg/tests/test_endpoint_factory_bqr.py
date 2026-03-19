from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from xbbg import blp
from xbbg.services import Operation, Service


class _FakeNwDf:
    def __init__(self, columns: list[str]):
        self._columns = columns

    def __len__(self):
        return 1

    def to_arrow(self):
        return pa.table({name: [None] for name in self._columns})


class _NoArrowFrame:
    def __len__(self):
        return 1


@pytest.mark.asyncio
async def test_abqr_generated_routes_intraday_tick_defaults(monkeypatch):
    captured: dict[str, Any] = {}
    fake_df = _NoArrowFrame()

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


def test_reshape_bqr_generic_uses_arrow_table_without_pandas():
    table = pa.table(
        {
            "path": [
                "tickData[0].time",
                "tickData[0].type",
                "tickData[0].value",
                "tickData[0].size",
                "tickData[0].brokerBuyCode",
                "tickData.eidData[0]",
            ],
            "value_str": [
                "2026-03-03T09:30:00",
                "BID",
                None,
                None,
                "ABCD",
                None,
            ],
            "value_num": [
                None,
                None,
                123.45,
                1000.0,
                None,
                None,
            ],
        }
    )

    result = blp._reshape_bqr_generic(table, "AAPL US Equity")
    rows = result.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL US Equity"
    assert rows[0]["time"] == "2026-03-03T09:30:00"
    assert rows[0]["type"] == "BID"
    assert rows[0]["value"] == 123.45
    assert rows[0]["size"] == 1000.0
    assert rows[0]["brokerBuyCode"] == "ABCD"
