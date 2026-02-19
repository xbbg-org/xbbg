"""Tests for Backend enum.

Ported from main branch xbbg/tests/test_backend_availability.py (TestBackendEnum class).
Adapted for the current branch which has 7 backends (not 13).

The current branch Backend enum in xbbg.blp supports:
    NARWHALS, NARWHALS_LAZY, PANDAS, POLARS, POLARS_LAZY, PYARROW, DUCKDB
"""

from __future__ import annotations

import pytest

from xbbg.blp import Backend


class TestBackendEnum:
    """Tests for Backend enum values and behavior."""

    def test_backend_is_string_enum(self):
        """Backend should inherit from str."""
        assert isinstance(Backend.PANDAS, str)
        assert isinstance(Backend.NARWHALS, str)

    def test_backend_string_comparison(self):
        """Backend members should compare equal to their string values."""
        assert Backend.PANDAS == "pandas"
        assert Backend.NARWHALS == "narwhals"
        assert Backend.POLARS == "polars"

    def test_backend_narwhals_value(self):
        """NARWHALS backend value should be 'narwhals'."""
        assert Backend.NARWHALS.value == "narwhals"

    def test_backend_narwhals_lazy_value(self):
        """NARWHALS_LAZY backend value should be 'narwhals_lazy'."""
        assert Backend.NARWHALS_LAZY.value == "narwhals_lazy"

    def test_backend_pandas_value(self):
        """PANDAS backend value should be 'pandas'."""
        assert Backend.PANDAS.value == "pandas"

    def test_backend_polars_value(self):
        """POLARS backend value should be 'polars'."""
        assert Backend.POLARS.value == "polars"

    def test_backend_polars_lazy_value(self):
        """POLARS_LAZY backend value should be 'polars_lazy'."""
        assert Backend.POLARS_LAZY.value == "polars_lazy"

    def test_backend_pyarrow_value(self):
        """PYARROW backend value should be 'pyarrow'."""
        assert Backend.PYARROW.value == "pyarrow"

    def test_backend_duckdb_value(self):
        """DUCKDB backend value should be 'duckdb'."""
        assert Backend.DUCKDB.value == "duckdb"

    def test_total_backend_count(self):
        """Backend should have exactly 7 members."""
        assert len(Backend) == 7

    def test_all_expected_backends_exist(self):
        """All expected backend names should be present."""
        expected = {"NARWHALS", "NARWHALS_LAZY", "PANDAS", "POLARS", "POLARS_LAZY", "PYARROW", "DUCKDB"}
        actual = {b.name for b in Backend}
        assert actual == expected

    def test_backend_lookup_by_value(self):
        """Backend should support lookup by string value."""
        assert Backend("pandas") == Backend.PANDAS
        assert Backend("narwhals") == Backend.NARWHALS
        assert Backend("duckdb") == Backend.DUCKDB

    def test_backend_invalid_value_raises(self):
        """Backend should raise ValueError for invalid string values."""
        with pytest.raises(ValueError):
            Backend("invalid_backend")

    def test_backend_name_attribute(self):
        """Backend members should have correct name attributes."""
        assert Backend.PANDAS.name == "PANDAS"
        assert Backend.NARWHALS.name == "NARWHALS"
        assert Backend.DUCKDB.name == "DUCKDB"

    def test_backend_lazy_variants(self):
        """Lazy backend variants should have '_lazy' suffix in value."""
        lazy_backends = [Backend.NARWHALS_LAZY, Backend.POLARS_LAZY]
        for backend in lazy_backends:
            assert "_lazy" in backend.value

    def test_backend_eager_variants(self):
        """Eager backends should not have '_lazy' suffix."""
        eager_backends = [Backend.NARWHALS, Backend.PANDAS, Backend.POLARS, Backend.PYARROW, Backend.DUCKDB]
        for backend in eager_backends:
            # DuckDB is technically lazy but doesn't have _lazy suffix
            if backend != Backend.DUCKDB:
                assert "_lazy" not in backend.value
