from __future__ import annotations

import asyncio
import logging

import pyarrow as pa
import pytest

import xbbg
from xbbg import blp
from xbbg.services import Operation, Service


class DummyConfig:
    def __init__(self, **kwargs):
        self.host = "localhost"
        self.port = 8194
        self.request_pool_size = 2
        self.subscription_pool_size = 1
        self.validation_mode = "disabled"
        self.subscription_flush_threshold = 1
        self.max_event_queue_size = 10_000
        self.command_queue_size = 256
        self.subscription_stream_capacity = 256
        self.overflow_policy = "drop_newest"
        self.warmup_services = ["//blp/refdata", "//blp/apiflds"]
        self.field_cache_path = None
        self.auth_method = None
        self.app_name = None
        self.dir_property = None
        self.user_id = None
        self.ip_address = None
        self.token = None
        self.num_start_attempts = 3
        self.auto_restart_on_disconnection = True
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture(autouse=True)
def reset_blp_state():
    old_config = blp._config
    old_engine = blp._engine
    old_middleware = blp.get_middleware()
    blp.clear_middleware()
    blp._config = None
    blp._engine = None
    try:
        yield
    finally:
        blp.clear_middleware()
        blp.set_middleware(old_middleware)
        blp._config = old_config
        blp._engine = old_engine


def _sample_batch() -> pa.RecordBatch:
    return pa.record_batch(
        [
            pa.array(["IBM US Equity"]),
            pa.array(["PX_LAST"]),
            pa.array(["123.45"]),
        ],
        names=["ticker", "field", "value"],
    )


def test_arequest_runs_sync_and_async_middleware_in_order(monkeypatch):
    events: list[tuple[str, object]] = []
    contexts: list[blp.RequestContext] = []

    class FakeEngine:
        async def request(self, params_dict):
            events.append(("engine", params_dict["operation"]))
            return _sample_batch()

    async def outer(context: blp.RequestContext, call_next):
        events.append(("outer_pre", context.params.operation))
        context.metadata["trace"] = "outer"
        contexts.append(context)
        result = await call_next(context)
        events.append(("outer_post", context.batch.num_rows if context.batch else 0))
        return result

    def inner(context: blp.RequestContext, call_next):
        events.append(("inner_pre", context.metadata["trace"]))
        return call_next(context)

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    blp.add_middleware(outer)
    blp.add_middleware(inner)

    result = asyncio.run(
        blp.arequest(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=["IBM US Equity"],
            fields=["PX_LAST"],
        )
    )

    assert len(result) == 1
    assert events == [
        ("outer_pre", Operation.REFERENCE_DATA),
        ("inner_pre", "outer"),
        ("engine", Operation.REFERENCE_DATA.value),
        ("outer_post", 1),
    ]
    assert contexts[0].elapsed_ms is not None
    assert contexts[0].frame is result


def test_arequest_middleware_can_short_circuit(monkeypatch):
    called = False
    cached_result = [{"ticker": "IBM US Equity", "field": "PX_LAST", "value": "123.45"}]

    class FakeEngine:
        async def request(self, params_dict):
            nonlocal called
            called = True
            return _sample_batch()

    async def cache_middleware(context: blp.RequestContext, _call_next):
        context.metadata["cache_hit"] = True
        context.frame = cached_result
        return cached_result

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())
    blp.add_middleware(cache_middleware)

    result = asyncio.run(
        blp.arequest(
            service=Service.REFDATA,
            operation=Operation.REFERENCE_DATA,
            securities=["IBM US Equity"],
            fields=["PX_LAST"],
        )
    )

    assert result is cached_result
    assert called is False


def test_connect_normalizes_legacy_auth_kwargs(monkeypatch):
    sentinel = object()
    shutdown_calls: list[bool] = []
    blp._config = DummyConfig()
    monkeypatch.setattr(blp, "shutdown", lambda: shutdown_calls.append(True))
    monkeypatch.setattr(blp, "_get_engine", lambda: sentinel)

    result = blp.connect(
        max_attempt=5,
        auto_restart=False,
        auth_method="manual",
        app_name="my-app",
        user_id="123456",
        ip_address="10.0.0.1",
        server_host="bpipe-host",
        server_port=8195,
    )

    assert result is sentinel
    assert shutdown_calls == [True]
    assert isinstance(blp._config, DummyConfig)
    assert blp._config.host == "bpipe-host"
    assert blp._config.port == 8195
    assert blp._config.auth_method == "manual"
    assert blp._config.app_name == "my-app"
    assert blp._config.user_id == "123456"
    assert blp._config.ip_address == "10.0.0.1"
    assert blp._config.num_start_attempts == 5
    assert blp._config.auto_restart_on_disconnection is False


def test_connect_rejects_unsupported_session_inputs():
    with pytest.raises(NotImplementedError, match="sess"):
        blp.connect(sess=object())


def test_disconnect_resets_engine(monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(blp, "reset", lambda: calls.append(True))

    blp.disconnect()

    assert calls == [True]


def test_public_exports_include_connect_and_middleware_helpers():
    assert "connect" in xbbg.__all__
    assert "disconnect" in xbbg.__all__
    assert "add_middleware" in xbbg.__all__
    assert "RequestContext" in xbbg.__all__
    assert callable(xbbg.connect)
    assert callable(xbbg.add_middleware)


def test_arequest_preserves_centralized_request_logging(monkeypatch, caplog):
    class FakeEngine:
        async def request(self, params_dict):
            return _sample_batch()

    monkeypatch.setattr(blp, "_get_engine", lambda: FakeEngine())

    with caplog.at_level(logging.INFO, logger="xbbg.blp"):
        asyncio.run(
            blp.arequest(
                service=Service.REFDATA,
                operation=Operation.REFERENCE_DATA,
                securities=["IBM US Equity"],
                fields=["PX_LAST"],
            )
        )

    messages = [record.message for record in caplog.records]
    assert any("bloomberg" in message and "ReferenceDataRequest" in message for message in messages)
