"""Tests for offline xbbg.blp behavior.

These tests verify selected Python API behavior without requiring a Bloomberg connection.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from pathlib import Path
import threading
from unittest import TestCase

import pytest

_CASE = TestCase()


class TestNotebookSyncBridge:
    """Tests for sync wrappers called from running event loops."""

    def test_generic_async_context_still_raises(self, monkeypatch):
        """Non-notebook async callers should be directed to the async API."""
        from xbbg import blp

        async def fake_request():
            return "ok"

        wrapper = blp._build_sync_wrapper("bdp", fake_request, allow_notebook_bridge=True)
        monkeypatch.setattr(blp, "_is_notebook_context", lambda: False)

        async def call_wrapper():
            wrapper()

        with pytest.raises(RuntimeError, match="await abdp"):
            asyncio.run(call_wrapper())

    def test_notebook_context_uses_background_loop_and_preserves_contextvars(self, monkeypatch):
        """Notebook callers should block on a background loop without losing context."""
        from xbbg import blp

        scoped_value = contextvars.ContextVar("scoped_value", default="missing")

        async def fake_request():
            return scoped_value.get(), threading.current_thread().name

        wrapper = blp._build_sync_wrapper("bdp", fake_request, allow_notebook_bridge=True)
        monkeypatch.setattr(blp, "_is_notebook_context", lambda: True)
        token = scoped_value.set("active-engine")

        async def call_wrapper():
            return wrapper()

        try:
            value, thread_name = asyncio.run(call_wrapper())
        finally:
            scoped_value.reset(token)
            blp._stop_notebook_sync_loop()

        _CASE.assertEqual(value, "active-engine")
        _CASE.assertEqual(thread_name, "xbbg-notebook-sync-bridge")

    def test_notebook_context_propagates_async_exceptions(self, monkeypatch):
        """Async failures should surface unchanged to the sync caller."""
        from xbbg import blp

        class ExpectedError(Exception):
            pass

        async def fake_request():
            raise ExpectedError("boom")

        wrapper = blp._build_sync_wrapper("bdh", fake_request, allow_notebook_bridge=True)
        monkeypatch.setattr(blp, "_is_notebook_context", lambda: True)

        async def call_wrapper():
            wrapper()

        try:
            with pytest.raises(ExpectedError, match="boom"):
                asyncio.run(call_wrapper())
        finally:
            blp._stop_notebook_sync_loop()

    def test_public_bridge_scope_is_one_shot_only(self, monkeypatch):
        """Installed public wrappers should bridge one-shot APIs, not streams."""
        from xbbg import blp

        def fake_bridge(async_func, args, kwargs):
            return async_func.__name__, args, kwargs

        monkeypatch.setattr(blp, "_is_notebook_context", lambda: True)
        monkeypatch.setattr(blp, "_run_in_notebook_sync_bridge", fake_bridge)

        async def call_bdp():
            return blp.bdp("AAPL US Equity", "PX_LAST")

        async def call_request():
            return blp.request(service="//blp/refdata", operation="ReferenceDataRequest")

        async def call_subscribe():
            blp.subscribe(["AAPL US Equity"], ["LAST_PRICE"])

        bdp_name, bdp_args, _ = asyncio.run(call_bdp())
        request_name, _, request_kwargs = asyncio.run(call_request())

        _CASE.assertEqual(bdp_name, "abdp")
        _CASE.assertEqual(bdp_args, ("AAPL US Equity", "PX_LAST"))
        _CASE.assertEqual(request_name, "arequest")
        _CASE.assertEqual(request_kwargs["service"], "//blp/refdata")
        with pytest.raises(RuntimeError, match="await asubscribe"):
            asyncio.run(call_subscribe())


class TestExtSyncify:
    """Tests for xbbg.ext sync wrappers sharing the core async boundary."""

    def test_sync_context_runs_helper(self):
        from xbbg.ext._utils import _syncify

        async def afake_ext(value):
            return f"ok:{value}"

        wrapper = _syncify(afake_ext)

        _CASE.assertEqual(wrapper("value"), "ok:value")
        _CASE.assertEqual(wrapper.__name__, "fake_ext")

    def test_generic_async_context_rejects_before_creating_coroutine(self):
        from xbbg.ext._utils import _syncify

        created = False

        def afake_ext():
            nonlocal created
            created = True

            async def inner():
                return "ok"

            return inner()

        wrapper = _syncify(afake_ext)

        async def call_wrapper():
            wrapper()

        with pytest.raises(RuntimeError, match="await afake_ext"):
            asyncio.run(call_wrapper())

        _CASE.assertFalse(created)

    def test_notebook_context_uses_core_bridge(self, monkeypatch):
        from xbbg import blp
        from xbbg.ext._utils import _syncify

        async def afake_ext(*args, **kwargs):
            return args, kwargs

        wrapper = _syncify(afake_ext)

        def fake_bridge(async_func, args, kwargs):
            return async_func.__name__, args, kwargs

        monkeypatch.setattr(blp, "_is_notebook_context", lambda: True)
        monkeypatch.setattr(blp, "_run_in_notebook_sync_bridge", fake_bridge)

        async def call_wrapper():
            return wrapper("abc", flag=True)

        name, args, kwargs = asyncio.run(call_wrapper())

        _CASE.assertEqual(name, "afake_ext")
        _CASE.assertEqual(args, ("abc",))
        _CASE.assertEqual(kwargs, {"flag": True})


class TestBdtick:
    """Tests for bdtick (tick data) function."""

    def test_bdtick_sync_signature_matches_async(self):
        """bdtick exposes the generated sync signature for IDE/runtime help."""
        import xbbg
        from xbbg import blp

        sync_sig = inspect.signature(blp.bdtick)
        async_sig = inspect.signature(blp.abdtick)

        _CASE.assertEqual(sync_sig, async_sig)
        _CASE.assertEqual(inspect.signature(xbbg.bdtick), async_sig)
        _CASE.assertIn("request_tz", sync_sig.parameters)
        _CASE.assertIn("output_tz", sync_sig.parameters)
        _CASE.assertIn("event_types", sync_sig.parameters)

    def test_top_level_stub_reexports_bdtick(self):
        """Generated top-level stub preserves IDE help for xbbg.bdtick."""
        import xbbg

        stub = Path(xbbg.__file__).with_name("__init__.pyi")
        text = stub.read_text()

        _CASE.assertIn("bdtick as bdtick", text)
        _CASE.assertIn('"bdtick"', text)
        _CASE.assertNotIn("__all__ = []", text)
