"""Regression tests for _events_to_table (mixed-type Arrow conversion).

Bloomberg's process_* functions yield event dicts where the ``value`` column
is a true variant -- it can contain float, str, datetime, bool, and None in
the same list.  ``pa.Table.from_pandas()`` and ``pa.Table.from_pylist()``
both raise ``ArrowInvalid`` on such mixed-type columns.

``_events_to_table`` builds Arrow tables directly from event dicts, falling
back to ``pa.string()`` for columns whose types cannot be inferred uniformly.

Regression: https://github.com/alpha-xone/xbbg/issues/XXX
  bdp(['ES1 Index'], ['FUT_CONT_SIZE', 'FUT_VAL_PT']) raised ArrowInvalid
  because FUT_CONT_SIZE returns float (Double) while FUT_VAL_PT returns str
  (String), creating a mixed float+str ``value`` column.
"""

from __future__ import annotations

from datetime import date, datetime

import pyarrow as pa

from xbbg.core.pipeline_core import _events_to_table

# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


class TestEventsToTableBasic:
    """Core behavior: empty input, uniform types."""

    def test_empty_events_returns_none(self):
        assert _events_to_table([]) is None

    def test_single_event(self):
        events = [{"ticker": "X", "field": "PX_LAST", "value": 100.0}]
        table = _events_to_table(events)
        assert isinstance(table, pa.Table)
        assert table.num_rows == 1
        assert table.num_columns == 3

    def test_uniform_float_values(self):
        events = [
            {"ticker": "X", "field": "PX_LAST", "value": 100.0},
            {"ticker": "X", "field": "VOLUME", "value": 5000.0},
        ]
        table = _events_to_table(events)
        assert table.num_rows == 2
        # All-float value column should stay numeric (double)
        assert pa.types.is_floating(table.column("value").type)

    def test_uniform_string_values(self):
        events = [
            {"ticker": "X", "field": "NAME", "value": "Foo Corp"},
            {"ticker": "X", "field": "SECTOR", "value": "Tech"},
        ]
        table = _events_to_table(events)
        assert pa.types.is_string(table.column("value").type) or pa.types.is_large_string(table.column("value").type)


# ---------------------------------------------------------------------------
# The actual bug: mixed-type value column
# ---------------------------------------------------------------------------


class TestMixedTypeValueColumn:
    """Regression tests for the ArrowInvalid bug on mixed-type value columns."""

    def test_float_and_string_values(self):
        """The exact scenario that triggered the bug.

        FUT_CONT_SIZE=50.0 (float) + FUT_VAL_PT='50.00' (str).
        """
        events = [
            {"ticker": "ES1 Index", "field": "FUT_CONT_SIZE", "value": 50.0},
            {"ticker": "ES1 Index", "field": "FUT_VAL_PT", "value": "50.00"},
        ]
        table = _events_to_table(events)
        assert table is not None
        assert table.num_rows == 2
        # Mixed column falls back to string
        assert pa.types.is_string(table.column("value").type) or pa.types.is_large_string(table.column("value").type)
        # Values are preserved (as strings)
        values = table.column("value").to_pylist()
        assert "50.0" in values
        assert "50.00" in values

    def test_float_string_and_name(self):
        """Multi-ticker, multi-field: numeric + string-typed + text fields."""
        events = [
            {"ticker": "ES1 Index", "field": "FUT_CONT_SIZE", "value": 50.0},
            {"ticker": "ES1 Index", "field": "FUT_VAL_PT", "value": "50.00"},
            {"ticker": "ES1 Index", "field": "SECURITY_NAME", "value": "Generic 1st 'ES' Future"},
        ]
        table = _events_to_table(events)
        assert table is not None
        assert table.num_rows == 3

    def test_int_and_string_values(self):
        events = [
            {"ticker": "X", "field": "A", "value": 42},
            {"ticker": "X", "field": "B", "value": "hello"},
        ]
        table = _events_to_table(events)
        assert table is not None
        assert table.num_rows == 2

    def test_float_and_date_values(self):
        events = [
            {"ticker": "X", "field": "PX_LAST", "value": 100.0},
            {"ticker": "X", "field": "MATURITY", "value": date(2030, 1, 15)},
        ]
        table = _events_to_table(events)
        assert table is not None
        assert table.num_rows == 2

    def test_float_string_date_bool_mixed(self):
        """Kitchen sink: every type Bloomberg might return."""
        events = [
            {"ticker": "X", "field": "PRICE", "value": 99.5},
            {"ticker": "X", "field": "NAME", "value": "Acme"},
            {"ticker": "X", "field": "MATURITY", "value": date(2030, 6, 15)},
            {"ticker": "X", "field": "IS_CALLABLE", "value": True},
            {"ticker": "X", "field": "COUPON_DT", "value": datetime(2025, 3, 1, 12, 0)},
        ]
        table = _events_to_table(events)
        assert table is not None
        assert table.num_rows == 5


# ---------------------------------------------------------------------------
# Null / missing value handling
# ---------------------------------------------------------------------------


class TestNullHandling:
    """Ensure None and NaN are preserved as Arrow nulls, not stringified."""

    def test_none_in_uniform_column(self):
        events = [
            {"ticker": "X", "field": "A", "value": 1.0},
            {"ticker": "X", "field": "B", "value": None},
            {"ticker": "X", "field": "C", "value": 3.0},
        ]
        table = _events_to_table(events)
        assert table.column("value")[1].as_py() is None

    def test_none_in_mixed_column(self):
        events = [
            {"ticker": "X", "field": "A", "value": 1.0},
            {"ticker": "X", "field": "B", "value": None},
            {"ticker": "X", "field": "C", "value": "text"},
        ]
        table = _events_to_table(events)
        assert table.column("value")[1].as_py() is None

    def test_nan_in_uniform_float_column(self):
        events = [
            {"ticker": "X", "field": "A", "value": 1.0},
            {"ticker": "X", "field": "B", "value": float("nan")},
        ]
        table = _events_to_table(events)
        # NaN should be preserved as null in Arrow
        assert table.column("value")[1].as_py() is None


# ---------------------------------------------------------------------------
# Non-uniform dict keys (BDS array fields add extra columns)
# ---------------------------------------------------------------------------


class TestNonUniformKeys:
    """Events with different sets of keys (e.g. BDS array expansion)."""

    def test_extra_key_in_later_event(self):
        events = [
            {"ticker": "X", "field": "A", "value": 1.0},
            {"ticker": "X", "field": "B", "value": "hello", "extra": "col"},
        ]
        table = _events_to_table(events)
        assert table.num_columns == 4
        assert "extra" in table.column_names
        # First row has no "extra" -> should be null
        assert table.column("extra")[0].as_py() is None
        assert table.column("extra")[1].as_py() == "col"

    def test_column_order_preserves_first_event(self):
        events = [
            {"ticker": "X", "field": "Z"},
            {"ticker": "Y", "alpha": 1},
        ]
        table = _events_to_table(events)
        # Column order should follow insertion order from events
        assert table.column_names[0] == "ticker"
        assert table.column_names[1] == "field"


# ---------------------------------------------------------------------------
# Integration: BloombergPipeline._events_to_arrow delegates correctly
# ---------------------------------------------------------------------------


class TestPipelineEventsToArrow:
    """Verify the pipeline static method delegates to _events_to_table."""

    def test_events_to_arrow_returns_none_for_empty(self):
        from xbbg.core.pipeline_core import BloombergPipeline

        assert BloombergPipeline._events_to_arrow([]) is None

    def test_events_to_arrow_mixed_types(self):
        from xbbg.core.pipeline_core import BloombergPipeline

        events = [
            {"ticker": "ES1 Index", "field": "FUT_CONT_SIZE", "value": 50.0},
            {"ticker": "ES1 Index", "field": "FUT_VAL_PT", "value": "50.00"},
        ]
        table = BloombergPipeline._events_to_arrow(events)
        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
