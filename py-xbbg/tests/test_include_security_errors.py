"""Tests for include_security_errors request plumbing."""

from __future__ import annotations

import pyarrow as pa
import pytest

from xbbg.services import Operation, RequestParams, Service


def test_request_params_to_dict_omits_include_security_errors_when_false():
    """RequestParams.to_dict() should omit the flag when False."""
    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
    )

    result = params.to_dict()

    assert "include_security_errors" not in result


def test_request_params_to_dict_includes_include_security_errors_when_true():
    """RequestParams.to_dict() should include the flag when True."""
    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
        include_security_errors=True,
    )

    result = params.to_dict()

    assert result["include_security_errors"] is True


@pytest.mark.asyncio
async def test_arequest_passes_include_security_errors_to_engine(monkeypatch):
    """arequest() should pass include_security_errors=True to engine.request()."""
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
        include_security_errors=True,
    )

    assert captured["include_security_errors"] is True
    assert len(result) == 1


@pytest.mark.asyncio
async def test_arequest_omits_include_security_errors_when_false(monkeypatch):
    """arequest() should not include include_security_errors when False."""
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
    )

    assert "include_security_errors" not in captured
    assert len(result) == 1


@pytest.mark.asyncio
async def test_abdp_forwards_include_security_errors(monkeypatch):
    """abdp() should forward include_security_errors to arequest()."""
    from xbbg import blp

    captured: dict[str, object] = {}

    class FakeEngine:
        async def resolve_field_types(self, field_list, field_types, default_type):
            return field_types or {field: default_type for field in field_list}

    async def fake_route_kwargs(_service, _operation, _kwargs):
        return [], []

    async def fake_arequest(*_args, **kwargs):
        captured.update(kwargs)
        return [{"ticker": "IBM US Equity", "field": "PX_LAST", "value": "123.45"}]

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(blp, "_aroute_kwargs", fake_route_kwargs)
    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = await blp.abdp("IBM US Equity", "PX_LAST", include_security_errors=True)

    assert captured["include_security_errors"] is True
    assert len(result) == 1


def test_bdp_forwards_include_security_errors(monkeypatch):
    """bdp() sync wrapper should forward include_security_errors to arequest()."""
    from xbbg import blp

    captured: dict[str, object] = {}

    class FakeEngine:
        async def resolve_field_types(self, field_list, field_types, default_type):
            return field_types or {field: default_type for field in field_list}

    async def fake_route_kwargs(_service, _operation, _kwargs):
        return [], []

    async def fake_arequest(*_args, **kwargs):
        captured.update(kwargs)
        return [{"ticker": "IBM US Equity", "field": "PX_LAST", "value": "123.45"}]

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(blp, "_aroute_kwargs", fake_route_kwargs)
    monkeypatch.setattr(blp, "arequest", fake_arequest)
    monkeypatch.setattr(blp, "_convert_backend", lambda df, _backend: df)

    result = blp.bdp("IBM US Equity", "PX_LAST", include_security_errors=True)

    assert captured["include_security_errors"] is True
    assert len(result) == 1
