"""Tests for _convert_backend() function.

Ported from main branch xbbg/tests/test_convert.py (TestConvertBackend* classes).
Adapted for the current branch where _convert_backend lives in xbbg.blp
and supports 7 backends (NARWHALS, NARWHALS_LAZY, PANDAS, POLARS,
POLARS_LAZY, PYARROW, DUCKDB).

NOTE: _convert_backend is a private function. These tests are
implementation-focused to ensure backend conversion works correctly
across all supported output formats.
"""

from __future__ import annotations

from unittest import TestCase

import narwhals.stable.v1 as nw
import pandas as pd
import pytest

from xbbg.blp import Backend, _convert_backend, set_backend

_CASE = TestCase()


class TestConvertBackendNarwhals:
    """Test _convert_backend() for narwhals backend (passthrough)."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity", "MSFT US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "px_last": [150.0, 380.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_narwhals_returns_narwhals(self):
        """Converting to NARWHALS should return a narwhals DataFrame."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        _CASE.assertIsInstance(result, nw.DataFrame)

    def test_convert_narwhals_preserves_data(self):
        """Converting to NARWHALS should preserve all data."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        _CASE.assertEqual(len(result), 2)
        _CASE.assertIn("ticker", result.columns)
        _CASE.assertIn("px_last", result.columns)

    def test_convert_none_backend_returns_default(self):
        """Passing None as backend should return the default narwhals DataFrame."""
        nw_frame = self._create_test_nw_frame()
        set_backend(None)
        result = _convert_backend(nw_frame, None)

        _CASE.assertIsInstance(result, nw.DataFrame)
        _CASE.assertEqual(result.columns, ["ticker", "date", "px_last"])
        _CASE.assertEqual(len(result), 2)
        _CASE.assertEqual(result["ticker"].to_list()[0], "AAPL US Equity")
        _CASE.assertEqual(result["px_last"].to_list()[1], 380.0)


class TestConvertBackendPandas:
    """Test _convert_backend() for pandas backend."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity", "MSFT US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "px_last": [150.0, 380.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_pandas_returns_pd_dataframe(self):
        """Converting to PANDAS should return a pandas DataFrame."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        _CASE.assertIsInstance(result, pd.DataFrame)

    def test_convert_pandas_preserves_columns(self):
        """Converting to PANDAS should preserve column names."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        _CASE.assertIn("ticker", result.columns)
        _CASE.assertIn("date", result.columns)
        _CASE.assertIn("px_last", result.columns)

    def test_convert_pandas_preserves_row_count(self):
        """Converting to PANDAS should preserve row count."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        _CASE.assertEqual(len(result), 2)

    def test_convert_pandas_from_string_backend(self):
        """Converting with string 'pandas' should work like Backend.PANDAS."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, "pandas")
        _CASE.assertIsInstance(result, pd.DataFrame)

    def test_convert_pandas_already_pandas(self):
        """Converting an already-pandas DataFrame should return it as-is."""
        pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = _convert_backend(pdf, Backend.PANDAS)
        _CASE.assertIsInstance(result, pd.DataFrame)
        _CASE.assertEqual(len(result), 2)


class TestConvertBackendPolars:
    """Test _convert_backend() for polars backends.

    NOTE: _convert_backend assumes polars-backed narwhals frames for POLARS/POLARS_LAZY
    conversion (calls .to_native() which returns polars, then .lazy()). We must create
    narwhals frames from polars, not pandas, for these tests.
    """

    def _create_test_nw_frame(self):
        """Create a polars-backed narwhals DataFrame."""
        pl = pytest.importorskip("polars")
        plf = pl.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(plf)

    def test_convert_polars_returns_polars_df(self):
        """Converting to POLARS should return a polars DataFrame."""
        pl = pytest.importorskip("polars")
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.POLARS)
        _CASE.assertIsInstance(result, pl.DataFrame)

    def test_convert_polars_lazy_returns_lazyframe(self):
        """Converting to POLARS_LAZY should return a polars LazyFrame."""
        pl = pytest.importorskip("polars")
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.POLARS_LAZY)
        _CASE.assertIsInstance(result, pl.LazyFrame)


class TestConvertBackendPyArrow:
    """Test _convert_backend() for pyarrow backend.

    NOTE: _convert_backend's PYARROW path calls .to_native().to_arrow() which
    requires a polars-backed narwhals frame. When backed by pandas, it falls back
    to pa.Table.from_pandas(). We test both paths.
    """

    def _create_polars_backed_nw_frame(self):
        """Create a polars-backed narwhals DataFrame for .to_arrow() path."""
        pl = pytest.importorskip("polars")
        plf = pl.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(plf)

    def _create_pandas_backed_nw_frame(self):
        """Create a pandas-backed narwhals DataFrame for from_pandas fallback path."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_pyarrow_from_polars_returns_arrow_table(self):
        """Converting polars-backed narwhals to PYARROW should return a pyarrow Table."""
        import pyarrow as pa

        nw_frame = self._create_polars_backed_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        _CASE.assertIsInstance(result, pa.Table)

    def test_convert_pyarrow_from_pandas_returns_arrow_table(self):
        """Converting pandas-backed narwhals to PYARROW should fallback to from_pandas."""
        import pyarrow as pa

        nw_frame = self._create_pandas_backed_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        _CASE.assertIsInstance(result, pa.Table)

    def test_convert_pyarrow_preserves_columns(self):
        """Converting to PYARROW should preserve column names."""
        nw_frame = self._create_polars_backed_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        _CASE.assertIn("ticker", result.column_names)
        _CASE.assertIn("px_last", result.column_names)


class TestConvertBackendDuckDB:
    """Test _convert_backend() for duckdb backend."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_duckdb(self):
        """Converting to DUCKDB should return a collectable duckdb lazy frame."""
        pytest.importorskip("duckdb")
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.DUCKDB)
        collected = result.collect()

        _CASE.assertIsInstance(result, nw.LazyFrame)
        _CASE.assertEqual(collected.columns, ["ticker", "px_last"])
        _CASE.assertEqual(len(collected), 1)
        _CASE.assertEqual(collected["ticker"].to_list()[0], "AAPL US Equity")
        _CASE.assertEqual(collected["px_last"].to_list()[0], 150.0)


class TestConvertBackendNarwhalsLazy:
    """Test _convert_backend() for narwhals lazy backend."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_narwhals_lazy(self):
        """Converting to NARWHALS_LAZY should return a collectable lazy frame."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS_LAZY)
        collected = result.collect()

        _CASE.assertIsInstance(result, nw.LazyFrame)
        _CASE.assertEqual(collected.columns, ["ticker", "px_last"])
        _CASE.assertEqual(len(collected), 1)
        _CASE.assertEqual(collected["ticker"].to_list()[0], "AAPL US Equity")
        _CASE.assertEqual(collected["px_last"].to_list()[0], 150.0)


class TestConvertBackendInvalid:
    """Test _convert_backend() with invalid backends."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame({"a": [1]})
        return nw.from_native(pdf)

    def test_invalid_string_backend_raises(self):
        """Invalid string backend should raise ValueError."""
        nw_frame = self._create_test_nw_frame()
        with pytest.raises(ValueError):
            _convert_backend(nw_frame, "invalid_backend")


class TestConvertBackendEmptyFrame:
    """Test _convert_backend() with empty DataFrames."""

    def _create_empty_nw_frame(self):
        """Create an empty narwhals DataFrame."""
        pdf = pd.DataFrame({"ticker": pd.Series([], dtype=str), "px_last": pd.Series([], dtype=float)})
        return nw.from_native(pdf)

    def test_convert_empty_to_pandas(self):
        """Converting empty frame to pandas should work."""
        nw_frame = self._create_empty_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        _CASE.assertIsInstance(result, pd.DataFrame)
        _CASE.assertEqual(len(result), 0)

    def test_convert_empty_to_narwhals(self):
        """Converting empty frame to narwhals should work."""
        nw_frame = self._create_empty_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        _CASE.assertIsInstance(result, nw.DataFrame)
        _CASE.assertEqual(len(result), 0)


class TestConvertBackendNativeInput:
    """Regression tests for issue #287.

    ``_convert_backend`` must accept raw native frames (not only narwhals
    wrappers). Before the fix, feeding an already-native polars frame
    caused ``AttributeError: 'DataFrame' object has no attribute 'to_native'``
    because the polars branch assumed a narwhals wrapper.
    """

    def test_native_polars_to_polars(self):
        pl = pytest.importorskip("polars")
        plf = pl.DataFrame({"ticker": ["IBM"], "px_last": [150.0]})
        result = _convert_backend(plf, Backend.POLARS)
        _CASE.assertIsInstance(result, pl.DataFrame)
        _CASE.assertEqual(result["px_last"][0], 150.0)

    def test_native_polars_to_pandas(self):
        pl = pytest.importorskip("polars")
        plf = pl.DataFrame({"ticker": ["IBM"], "px_last": [150.0]})
        result = _convert_backend(plf, Backend.PANDAS)
        _CASE.assertIsInstance(result, pd.DataFrame)
        _CASE.assertEqual(result["px_last"].iloc[0], 150.0)

    def test_native_pandas_to_polars(self):
        pl = pytest.importorskip("polars")
        pdf = pd.DataFrame({"ticker": ["IBM"], "px_last": [150.0]})
        result = _convert_backend(pdf, Backend.POLARS)
        _CASE.assertIsInstance(result, pl.DataFrame)
        _CASE.assertEqual(result["px_last"][0], 150.0)

    def test_native_polars_to_pyarrow(self):
        pl = pytest.importorskip("polars")
        import pyarrow as pa

        plf = pl.DataFrame({"ticker": ["IBM"], "px_last": [150.0]})
        result = _convert_backend(plf, Backend.PYARROW)
        _CASE.assertIsInstance(result, pa.Table)

    def test_double_conversion_is_safe(self):
        """The pre-fix bug: _execute_generated_endpoint called _convert_backend
        twice when a non-pandas global backend was set, causing the second
        call to receive an already-native frame. Verify this now no-ops.
        """
        pl = pytest.importorskip("polars")
        nw_frame = nw.from_native(pl.DataFrame({"a": [1, 2]}))
        first = _convert_backend(nw_frame, Backend.POLARS)
        second = _convert_backend(first, Backend.POLARS)
        _CASE.assertIsInstance(second, pl.DataFrame)
        _CASE.assertEqual(len(second), 2)
