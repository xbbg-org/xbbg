"""Tests for validate_fields request plumbing."""

from __future__ import annotations

import pyarrow as pa
import pytest

from xbbg.services import Operation, RequestParams, Service


def test_request_params_to_dict_omits_validate_fields_when_none():
    """RequestParams.to_dict() should omit validate_fields when None."""
    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
    )

    result = params.to_dict()

    assert "validate_fields" not in result


def test_request_params_to_dict_includes_validate_fields_when_set():
    """RequestParams.to_dict() should include validate_fields when explicitly set."""
    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
        validate_fields=False,
    )

    result = params.to_dict()

    assert result["validate_fields"] is False


@pytest.mark.asyncio
async def test_arequest_passes_validate_fields_to_engine(monkeypatch):
    """arequest() should pass validate_fields through to engine.request()."""
    from xbbg import blp

    captured: dict[str, object] = {}

    class FakeEngine:
        async def request(self, params_dict):
            captured.update(params_dict)
            return pa.record_batch(
                [
                    pa.array(["IBM US Equity"]),
                    pa.array(["PX_LAST"]),
                    pa.array(["123.45"]),
                ],
                names=["ticker", "field", "value"],
            )

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())

    result = await blp.arequest(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
        validate_fields=True,
    )

    assert captured["validate_fields"] is True
    assert len(result) == 1


@pytest.mark.asyncio
async def test_abdp_forwards_validate_fields(monkeypatch):
    """abdp() should forward validate_fields to arequest()."""
    from xbbg import blp

    captured: dict[str, object] = {}

    class FakeEngine:
        async def resolve_field_types(self, field_list, field_types, default_type):
            return field_types or dict.fromkeys(field_list, default_type)

    async def fake_route_kwargs(_service, _operation, _kwargs):
        return [], []

    async def fake_arequest(*_args, **kwargs):
        captured.update(kwargs)
        return [{"ticker": "IBM US Equity", "field": "PX_LAST", "value": "123.45"}]

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(blp, "_aroute_kwargs", fake_route_kwargs)
    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = await blp.abdp("IBM US Equity", "PX_LAST", validate_fields=True)

    assert captured["validate_fields"] is True
    assert len(result) == 1


def test_bdp_forwards_validate_fields(monkeypatch):
    """bdp() sync wrapper should forward validate_fields to arequest()."""
    from xbbg import blp

    captured: dict[str, object] = {}

    class FakeEngine:
        async def resolve_field_types(self, field_list, field_types, default_type):
            return field_types or dict.fromkeys(field_list, default_type)

    async def fake_route_kwargs(_service, _operation, _kwargs):
        return [], []

    async def fake_arequest(*_args, **kwargs):
        captured.update(kwargs)
        return [{"ticker": "IBM US Equity", "field": "PX_LAST", "value": "123.45"}]

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(blp, "_aroute_kwargs", fake_route_kwargs)
    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = blp.bdp("IBM US Equity", "PX_LAST", validate_fields=True)

    assert captured["validate_fields"] is True
    assert len(result) == 1
