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


class TestTickModeWarning:
    """Verify warning when tick_mode=True conflicts with flush_threshold."""

    def test_tick_mode_flush_threshold_warning(self):
        """tick_mode=True with flush_threshold>1 emits UserWarning before engine call."""
        from xbbg.blp import asubscribe

        with pytest.warns(UserWarning, match="tick_mode"):
            with pytest.raises(Exception):
                # Warning is emitted before engine call; engine call fails without Bloomberg
                asyncio.run(
                    asubscribe(
                        ["AAPL US Equity"],
                        ["LAST_PRICE"],
                        tick_mode=True,
                        flush_threshold=50,
                    )
                )


class TestSubscriptionStats:
    """Verify Subscription class has a stats property."""

    def test_subscription_stats_property_exists(self):
        """Subscription.stats is a property descriptor."""
        from xbbg.blp import Subscription

        assert hasattr(Subscription, "stats")
        assert isinstance(inspect.getattr_static(Subscription, "stats"), property)


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
        ]
        for param_name in new_params:
            assert param_name in params, f"{param_name} missing from signature"
            assert params[param_name].default is not inspect.Parameter.empty, f"{param_name} should have a default"
