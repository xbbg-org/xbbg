from __future__ import annotations

import asyncio
from unittest import TestCase
import warnings

import pytest

import xbbg.field_cache as field_cache_module

_CASE = TestCase()


class FakeEngine:
    def field_cache_stats(self) -> dict[str, int | str]:
        return {
            "entry_count": 7,
            "cache_path": "C:/tmp/xbbg/field_cache.json",
        }

    async def resolve_field_types(
        self,
        fields: list[str],
        overrides: dict[str, str] | None,
        default_type: str,
    ) -> dict[str, str]:
        resolved = dict.fromkeys(fields, default_type)
        if overrides:
            resolved.update(overrides)
        return resolved


def test_get_field_cache_stats_export(monkeypatch):
    """The package root should export field cache stats with cache_path."""
    from xbbg import get_field_cache_stats

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    _CASE.assertEqual(
        get_field_cache_stats(),
        {
            "entry_count": 7,
            "cache_path": "C:/tmp/xbbg/field_cache.json",
        },
    )


def test_field_type_cache_exposes_cache_path(monkeypatch):
    """FieldTypeCache should surface the resolved cache path."""
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    cache = FieldTypeCache()

    _CASE.assertEqual(
        cache.stats,
        {
            "entry_count": 7,
            "cache_path": "C:/tmp/xbbg/field_cache.json",
        },
    )
    _CASE.assertEqual(cache.cache_path, "C:/tmp/xbbg/field_cache.json")


def test_default_field_cache_calls_do_not_warn(monkeypatch):
    from xbbg import FieldTypeCache, resolve_field_types

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        cache = FieldTypeCache()
        _CASE.assertEqual(cache.resolve_types(["PX_LAST"]), {"PX_LAST": "string"})
        _CASE.assertEqual(resolve_field_types(["PX_LAST"]), {"PX_LAST": "string"})

    _CASE.assertEqual(recorded, [])


def test_query_api_false_warns_but_resolves(monkeypatch):
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    cache = FieldTypeCache()
    with pytest.warns(UserWarning, match="query_api=False") as warnings:
        result = cache.resolve_types(["PX_LAST"], {"PX_LAST": "float64"}, query_api=False)

    _CASE.assertEqual(result, {"PX_LAST": "float64"})
    _CASE.assertEqual(len(warnings), 1)


def test_async_query_api_false_warns_but_resolves(monkeypatch):
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    cache = FieldTypeCache()
    with pytest.warns(UserWarning, match="query_api=False") as warnings:
        result = asyncio.run(cache.aresolve_types(["NAME"], query_api=False))

    _CASE.assertEqual(result, {"NAME": "string"})
    _CASE.assertEqual(len(warnings), 1)


def test_module_async_query_api_false_warns_but_resolves(monkeypatch):
    from xbbg import aresolve_field_types

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    with pytest.warns(UserWarning, match="query_api=False") as warnings:
        result = asyncio.run(aresolve_field_types(["NAME"], query_api=False))

    _CASE.assertEqual(result, {"NAME": "string"})
    _CASE.assertEqual(len(warnings), 1)


def test_unknown_field_cache_kwargs_stay_quiet(monkeypatch):
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = FieldTypeCache().resolve_types(["PX_LAST"], ignored="compat")

    _CASE.assertEqual(result, {"PX_LAST": "string"})
    _CASE.assertEqual(recorded, [])


def test_cache_path_warns_but_stats_still_resolve(monkeypatch):
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    with pytest.warns(UserWarning, match="cache_path") as warnings:
        cache = FieldTypeCache(cache_path="ignored.json")

    _CASE.assertEqual(len(warnings), 1)
    _CASE.assertEqual(cache.cache_path, "C:/tmp/xbbg/field_cache.json")
