"""Tests for RawRequest request plumbing."""

from __future__ import annotations

import pyarrow as pa
import pytest

from xbbg.services import ExtractorHint, Operation, RequestParams, Service


def test_request_params_to_dict_includes_request_operation_for_raw_request():
    """RequestParams.to_dict() should include request_operation for RawRequest."""
    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.RAW_REQUEST,
        request_operation=Operation.REFERENCE_DATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
    )

    result = params.to_dict()

    assert result["operation"] == Operation.RAW_REQUEST.value
    assert result["request_operation"] == Operation.REFERENCE_DATA.value


def test_request_params_validate_requires_request_operation_for_raw_request():
    """RequestParams.validate() should reject RawRequest without request_operation."""
    from xbbg.exceptions import BlpValidationError

    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.RAW_REQUEST,
    )

    with pytest.raises(BlpValidationError, match="request_operation is required for RawRequest"):
        params.validate()


@pytest.mark.asyncio
async def test_arequest_passes_request_operation_to_engine(monkeypatch):
    """arequest() should forward request_operation to engine.request()."""
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
        operation=Operation.RAW_REQUEST,
        request_operation=Operation.REFERENCE_DATA,
        extractor=ExtractorHint.REFDATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
    )

    assert captured["operation"] == Operation.RAW_REQUEST.value
    assert captured["request_operation"] == Operation.REFERENCE_DATA.value
    assert len(result) == 1


def test_request_sync_forwards_request_operation(monkeypatch):
    """request() sync wrapper should forward request_operation to arequest()."""
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

    result = blp.request(
        service=Service.REFDATA,
        operation=Operation.RAW_REQUEST,
        request_operation=Operation.REFERENCE_DATA,
        extractor=ExtractorHint.REFDATA,
        securities=["IBM US Equity"],
        fields=["PX_LAST"],
    )

    assert captured["request_operation"] == Operation.REFERENCE_DATA.value
    assert len(result) == 1
