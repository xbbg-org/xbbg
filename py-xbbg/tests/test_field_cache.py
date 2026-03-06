from __future__ import annotations

import xbbg.field_cache as field_cache_module


class FakeEngine:
    def field_cache_stats(self) -> dict[str, int | str]:
        return {
            "entry_count": 7,
            "cache_path": "C:/tmp/xbbg/field_cache.json",
        }


def test_get_field_cache_stats_export(monkeypatch):
    """The package root should export field cache stats with cache_path."""
    from xbbg import get_field_cache_stats

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    assert get_field_cache_stats() == {
        "entry_count": 7,
        "cache_path": "C:/tmp/xbbg/field_cache.json",
    }


def test_field_type_cache_exposes_cache_path(monkeypatch):
    """FieldTypeCache should surface the resolved cache path."""
    from xbbg import FieldTypeCache

    monkeypatch.setattr(field_cache_module, "_get_engine", lambda: FakeEngine())

    cache = FieldTypeCache()

    assert cache.stats == {
        "entry_count": 7,
        "cache_path": "C:/tmp/xbbg/field_cache.json",
    }
    assert cache.cache_path == "C:/tmp/xbbg/field_cache.json"
