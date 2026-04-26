"""Unit tests for the override-path date normalizer in ``blp.py`` (#317).

The override path receives ``**kwargs`` from BDP / BDH / BDS calls without
per-field type metadata, so it relies on value-based duck typing to convert
date-typed override values to Bloomberg's expected ``YYYYMMDD`` form.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

# These tests import the normalizer directly so they don't drag in the full
# request stack or the Rust binary. The module's only "side effect" at import
# time is the lazy ``_fmt_date`` import already covered by other tests.
pytest.importorskip("xbbg")

from xbbg.blp import _normalize_override_value


class _DuckTimestamp:
    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def to_pydatetime(self) -> datetime:
        return self._dt


class TestNormalizeOverrideValue:
    def test_date_object(self) -> None:
        assert _normalize_override_value(date(2023, 1, 17)) == "20230117"

    def test_datetime_naive(self) -> None:
        assert _normalize_override_value(datetime(2023, 1, 17, 10, 30)) == "20230117"

    def test_datetime_aware(self) -> None:
        dt = datetime(2023, 1, 17, 10, 30, tzinfo=timezone.utc)
        assert _normalize_override_value(dt) == "20230117"

    def test_iso_date_string_normalized(self) -> None:
        assert _normalize_override_value("2023-01-17") == "20230117"

    def test_bloomberg_native_string_unchanged(self) -> None:
        assert _normalize_override_value("20230117") == "20230117"

    def test_duck_typed_timestamp(self) -> None:
        ts = _DuckTimestamp(datetime(2023, 1, 17, 10, 30))
        assert _normalize_override_value(ts) == "20230117"

    def test_other_string_passes_through(self) -> None:
        assert _normalize_override_value("MID") == "MID"

    def test_us_format_string_passes_through(self) -> None:
        # Override path is intentionally tolerant of non-ISO strings; only the
        # canonical date forms are normalized. The dedicated typed parameters
        # reject ambiguous strings instead.
        assert _normalize_override_value("01/17/2023") == "01/17/2023"

    def test_int_passes_through(self) -> None:
        assert _normalize_override_value(5) == "5"

    def test_float_passes_through(self) -> None:
        assert _normalize_override_value(1.5) == "1.5"

    def test_bool_preserved(self) -> None:
        assert _normalize_override_value(True) == "True"
        assert _normalize_override_value(False) == "False"
