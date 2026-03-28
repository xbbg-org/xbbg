"""Tests for streaming API enhancements (Tasks 3-12).

These tests verify:
1. New parameter signatures on asubscribe, astream, stream, subscribe
2. Validation logic for config params (flush_threshold, stream_capacity, overflow_policy)
3. Warning behavior for tick_mode + flush_threshold conflicts
4. Subscription.stats property exists
5. Backward compatibility (all new params have defaults)

All tests run offline — no Bloomberg connection required.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest


class TestAsubscribeSignature:
    """Verify asubscribe() has all new streaming params with correct defaults."""

    def test_asubscribe_signature(self):
        """All new params exist with correct defaults."""
        from xbbg.blp import asubscribe

        sig = inspect.signature(asubscribe)
        params = sig.parameters

        assert "service" in params
        assert params["service"].default is None

        assert "options" in params
        assert params["options"].default is None

        assert "tick_mode" in params
        assert params["tick_mode"].default is False

        assert "flush_threshold" in params
        assert params["flush_threshold"].default is None

        assert "stream_capacity" in params
        assert params["stream_capacity"].default is None

        assert "overflow_policy" in params
        assert params["overflow_policy"].default is None

        assert "recovery_policy" in params
        assert params["recovery_policy"].default is None

        assert "all_fields" in params
        assert params["all_fields"].default is False


class TestAstreamSignature:
    """Verify astream() has callback and config params."""

    def test_astream_signature(self):
        """callback param exists with default None; config params present."""
        from xbbg.blp import astream

        sig = inspect.signature(astream)
        params = sig.parameters

        assert "callback" in params
        assert params["callback"].default is None

        assert "flush_threshold" in params
        assert params["flush_threshold"].default is None

        assert "stream_capacity" in params
        assert params["stream_capacity"].default is None

        assert "overflow_policy" in params
        assert params["overflow_policy"].default is None

        assert "all_fields" in params
        assert params["all_fields"].default is False


class TestStreamSignature:
    """Verify stream() also has the new params."""

    def test_stream_signature(self):
        """stream() has callback, flush_threshold, stream_capacity, overflow_policy."""
        from xbbg.blp import stream

        sig = inspect.signature(stream)
        params = sig.parameters

        assert "callback" in params
        assert params["callback"].default is None

        assert "flush_threshold" in params
        assert params["flush_threshold"].default is None

        assert "stream_capacity" in params
        assert params["stream_capacity"].default is None

        assert "overflow_policy" in params
        assert params["overflow_policy"].default is None

        assert "all_fields" in params
        assert params["all_fields"].default is False


class TestStreamingServiceHelpersSignature:
    """avwap / amktbar / adepth / achains forward all_fields."""

    def test_all_fields_kwarg_defaults(self):
        from xbbg.blp import achains, adepth, amktbar, avwap

        for fn in (avwap, amktbar, adepth, achains):
            sig = inspect.signature(fn)
            assert "all_fields" in sig.parameters
            assert sig.parameters["all_fields"].default is False


class TestConfigValidation:
    """Verify ValueError raised for invalid config params.

    Validation happens BEFORE the engine call, so these work offline.
    """

    def test_config_validation_flush_threshold(self):
        """flush_threshold=0 raises ValueError."""
        from xbbg.blp import asubscribe

        with pytest.raises(ValueError, match="flush_threshold"):
            asyncio.run(asubscribe(["AAPL US Equity"], ["LAST_PRICE"], flush_threshold=0))

    def test_config_validation_stream_capacity(self):
        """stream_capacity=0 raises ValueError."""
        from xbbg.blp import asubscribe

        with pytest.raises(ValueError, match="stream_capacity"):
            asyncio.run(asubscribe(["AAPL US Equity"], ["LAST_PRICE"], stream_capacity=0))

    def test_config_validation_overflow_policy(self):
        """Invalid overflow_policy raises ValueError."""
        from xbbg.blp import asubscribe

        with pytest.raises(ValueError, match="overflow_policy"):
            asyncio.run(
                asubscribe(
                    ["AAPL US Equity"],
                    ["LAST_PRICE"],
                    overflow_policy="invalid_policy",
                )
            )


    def test_config_validation_recovery_policy(self):
        """Invalid recovery_policy raises ValueError."""
        from xbbg.blp import asubscribe

        with pytest.raises(ValueError, match="recovery_policy"):
            asyncio.run(asubscribe(["AAPL US Equity"], ["LAST_PRICE"], recovery_policy="invalid"))


class TestTickModeWarning:
    """Verify warning when tick_mode=True conflicts with flush_threshold."""

    def test_tick_mode_flush_threshold_warning(self):
        """tick_mode=True with flush_threshold>1 emits UserWarning before engine call."""
        from xbbg.blp import asubscribe

        captured: dict[str, object] = {}

        class FakePySubscription:
            tickers = ["AAPL US Equity"]
            failed_tickers = []
            failures = []
            topic_states = [("AAPL US Equity", "pending", 1)]
            session_status = {
                "state": "up",
                "last_change_us": 1,
                "disconnect_count": 0,
                "reconnect_count": 0,
                "recovery_policy": "none",
                "recovery_attempt_count": 0,
                "recovery_success_count": 0,
                "last_recovery_attempt_us": None,
                "last_recovery_success_us": None,
                "last_recovery_error": None,
            }
            admin_status = {
                "slow_consumer_warning_active": False,
                "slow_consumer_warning_count": 0,
                "slow_consumer_cleared_count": 0,
                "data_loss_count": 0,
                "last_warning_us": None,
                "last_cleared_us": None,
                "last_data_loss_us": None,
            }
            service_status = []
            events = []
            fields = ["LAST_PRICE"]
            is_active = True
            all_failed = False
            stats = {
                "messages_received": 0,
                "dropped_batches": 0,
                "batches_sent": 0,
                "slow_consumer": False,
                "data_loss_events": 0,
                "last_message_us": 0,
                "last_data_loss_us": 0,
                "effective_overflow_policy": "drop_newest",
            }

        class FakeEngine:
            async def subscribe_with_options(self, service, tickers, fields, options, **kwargs):
                captured.update(
                    {
                        "service": service,
                        "tickers": tickers,
                        "fields": fields,
                        "options": options,
                        **kwargs,
                    }
                )
                return FakePySubscription()

        import xbbg.blp as blp_module

        original_get_engine = blp_module._get_engine
        blp_module._get_engine = lambda: FakeEngine()

        try:
            with pytest.warns(UserWarning, match="tick_mode"):
                sub = asyncio.run(
                    asubscribe(
                        ["AAPL US Equity"],
                        ["LAST_PRICE"],
                        tick_mode=True,
                        flush_threshold=50,
                    )
                )
        finally:
            blp_module._get_engine = original_get_engine

        assert sub._tick_mode is True
        assert captured["flush_threshold"] == 1

    def test_recovery_policy_is_forwarded(self):
        from xbbg.blp import asubscribe

        captured: dict[str, object] = {}

        class FakePySubscription:
            tickers = ["AAPL US Equity"]
            failed_tickers = []
            failures = []
            topic_states = [("AAPL US Equity", "pending", 1)]
            session_status = {
                "state": "up",
                "last_change_us": 1,
                "disconnect_count": 0,
                "reconnect_count": 0,
                "recovery_policy": "resubscribe",
                "recovery_attempt_count": 0,
                "recovery_success_count": 0,
                "last_recovery_attempt_us": None,
                "last_recovery_success_us": None,
                "last_recovery_error": None,
            }
            admin_status = {
                "slow_consumer_warning_active": False,
                "slow_consumer_warning_count": 0,
                "slow_consumer_cleared_count": 0,
                "data_loss_count": 0,
                "last_warning_us": None,
                "last_cleared_us": None,
                "last_data_loss_us": None,
            }
            service_status = []
            events = []
            fields = ["LAST_PRICE"]
            is_active = True
            all_failed = False
            stats = {
                "messages_received": 0,
                "dropped_batches": 0,
                "batches_sent": 0,
                "slow_consumer": False,
                "data_loss_events": 0,
                "last_message_us": 0,
                "last_data_loss_us": 0,
                "effective_overflow_policy": "drop_newest",
            }

        class FakeEngine:
            async def subscribe_with_options(self, service, tickers, fields, options, **kwargs):
                captured.update(kwargs)
                return FakePySubscription()

        import xbbg.blp as blp_module

        original_get_engine = blp_module._get_engine
        blp_module._get_engine = lambda: FakeEngine()

        try:
            sub = asyncio.run(asubscribe(["AAPL US Equity"], ["LAST_PRICE"], recovery_policy="resubscribe"))
        finally:
            blp_module._get_engine = original_get_engine

        assert captured["recovery_policy"] == "resubscribe"
        assert sub.session_status["recovery_policy"] == "resubscribe"


class TestSubscriptionStats:
    """Verify Subscription class has a stats property."""

    def test_subscription_stats_property_exists(self):
        """Subscription.stats is a property descriptor."""
        from xbbg.blp import Subscription

        assert hasattr(Subscription, "stats")
        assert isinstance(inspect.getattr_static(Subscription, "stats"), property)


class TestSubscriptionFailureMetadata:
    """Verify Subscription exposes non-fatal failure metadata."""

    def test_failure_properties_exist(self):
        from xbbg.blp import Subscription

        assert isinstance(inspect.getattr_static(Subscription, "failed_tickers"), property)
        assert isinstance(inspect.getattr_static(Subscription, "failures"), property)
        assert isinstance(inspect.getattr_static(Subscription, "status"), property)
        assert isinstance(inspect.getattr_static(Subscription, "events"), property)
        assert isinstance(inspect.getattr_static(Subscription, "topic_states"), property)

    def test_failure_properties_proxy_underlying_subscription(self):
        from xbbg.blp import Subscription

        class FakePySubscription:
            tickers = ["SPY US Equity"]
            failed_tickers = ["/isin/BMG8192H1557"]
            failures = [
                (
                    "/isin/BMG8192H1557",
                    "Security is not valid for subscription [EX336]",
                    "failure",
                )
            ]
            topic_states = [
                ("SPY US Equity", "streaming", 123),
                ("/isin/BMG8192H1557", "failed", 456),
            ]
            session_status = {
                "state": "up",
                "last_change_us": 789,
                "disconnect_count": 1,
                "reconnect_count": 1,
                "recovery_policy": "resubscribe",
                "recovery_attempt_count": 2,
                "recovery_success_count": 1,
                "last_recovery_attempt_us": 13,
                "last_recovery_success_us": 14,
                "last_recovery_error": "temporary failure",
            }
            admin_status = {
                "slow_consumer_warning_active": True,
                "slow_consumer_warning_count": 2,
                "slow_consumer_cleared_count": 1,
                "data_loss_count": 3,
                "last_warning_us": 10,
                "last_cleared_us": 11,
                "last_data_loss_us": 12,
            }
            service_status = [("//blp/mktdata", True, 99)]
            events = [
                (1, "session", "info", "SessionConnectionUp", None, "worker=0 active_subscriptions=1"),
                (
                    2,
                    "subscription",
                    "warning",
                    "SubscriptionFailure",
                    "/isin/BMG8192H1557",
                    "Security is not valid for subscription [EX336]",
                ),
            ]
            fields = ["LAST_PRICE"]
            is_active = True
            all_failed = False
            stats = {
                "messages_received": 0,
                "dropped_batches": 0,
                "batches_sent": 0,
                "slow_consumer": False,
                "data_loss_events": 3,
                "last_message_us": 100,
                "last_data_loss_us": 12,
                "effective_overflow_policy": "drop_newest",
            }

        sub = Subscription(FakePySubscription(), raw=True, backend=None)

        assert sub.tickers == ["SPY US Equity"]
        assert sub.failed_tickers == ["/isin/BMG8192H1557"]
        assert sub.failures == [
            {
                "ticker": "/isin/BMG8192H1557",
                "reason": "Security is not valid for subscription [EX336]",
                "kind": "failure",
            }
        ]
        assert sub.topic_states["SPY US Equity"]["state"] == "streaming"
        assert sub.session_status["state"] == "up"
        assert sub.session_status["recovery_policy"] == "resubscribe"
        assert sub.admin_status["data_loss_count"] == 3
        assert sub.service_status["//blp/mktdata"]["up"] is True
        assert sub.events[1]["message_type"] == "SubscriptionFailure"
        assert sub.status["session"]["reconnect_count"] == 1


class TestBackwardCompatibility:
    """Verify all new params are optional (backward compat)."""

    def test_backward_compat_signature(self):
        """asubscribe can be called with just tickers and fields — all new params have defaults."""
        from xbbg.blp import asubscribe

        sig = inspect.signature(asubscribe)
        params = sig.parameters

        assert "tickers" in params
        assert "fields" in params

        # Every new param must have a default (i.e. is optional)
        new_params = [
            "service",
            "options",
            "tick_mode",
            "flush_threshold",
            "stream_capacity",
            "overflow_policy",
            "recovery_policy",
        ]
        for param_name in new_params:
            assert param_name in params, f"{param_name} missing from signature"
            assert params[param_name].default is not inspect.Parameter.empty, f"{param_name} should have a default"
