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

import narwhals.stable.v1 as nw
import pandas as pd
import pytest

from xbbg.blp import Backend, _convert_backend


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
        assert isinstance(result, nw.DataFrame)

    def test_convert_narwhals_preserves_data(self):
        """Converting to NARWHALS should preserve all data."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        assert len(result) == 2
        assert "ticker" in result.columns
        assert "px_last" in result.columns

    def test_convert_none_backend_returns_default(self):
        """Passing None as backend should return default backend result."""
        nw_frame = self._create_test_nw_frame()
        # Should not raise
        result = _convert_backend(nw_frame, None)
        assert result is not None


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
        assert isinstance(result, pd.DataFrame)

    def test_convert_pandas_preserves_columns(self):
        """Converting to PANDAS should preserve column names."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        assert "ticker" in result.columns
        assert "date" in result.columns
        assert "px_last" in result.columns

    def test_convert_pandas_preserves_row_count(self):
        """Converting to PANDAS should preserve row count."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        assert len(result) == 2

    def test_convert_pandas_from_string_backend(self):
        """Converting with string 'pandas' should work like Backend.PANDAS."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, "pandas")
        assert isinstance(result, pd.DataFrame)

    def test_convert_pandas_already_pandas(self):
        """Converting an already-pandas DataFrame should return it as-is."""
        pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = _convert_backend(pdf, Backend.PANDAS)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2


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
        assert isinstance(result, pl.DataFrame)

    def test_convert_polars_lazy_returns_lazyframe(self):
        """Converting to POLARS_LAZY should return a polars LazyFrame."""
        pl = pytest.importorskip("polars")
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.POLARS_LAZY)
        assert isinstance(result, pl.LazyFrame)


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
        assert isinstance(result, pa.Table)

    def test_convert_pyarrow_from_pandas_returns_arrow_table(self):
        """Converting pandas-backed narwhals to PYARROW should fallback to from_pandas."""
        import pyarrow as pa

        nw_frame = self._create_pandas_backed_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        assert isinstance(result, pa.Table)

    def test_convert_pyarrow_preserves_columns(self):
        """Converting to PYARROW should preserve column names."""
        nw_frame = self._create_polars_backed_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        assert "ticker" in result.column_names
        assert "px_last" in result.column_names


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
        """Converting to DUCKDB should return a lazy result."""
        pytest.importorskip("duckdb")
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.DUCKDB)
        # DuckDB conversion returns a narwhals lazy frame backed by duckdb
        assert result is not None


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
        """Converting to NARWHALS_LAZY should return a lazy frame."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS_LAZY)
        assert result is not None


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
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_convert_empty_to_narwhals(self):
        """Converting empty frame to narwhals should work."""
        nw_frame = self._create_empty_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        assert isinstance(result, nw.DataFrame)
        assert len(result) == 0
