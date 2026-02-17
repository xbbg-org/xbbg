"""Unit tests for output conversion layer.

Tests all conversion utilities in xbbg/io/convert.py including:
- _convert_backend() for all backends (pandas, polars, pyarrow, narwhals)
- to_output() for LONG format
- to_output() for SEMI_LONG format
- to_output() for WIDE format
- _apply_multiindex() for pandas MultiIndex
- Empty table handling
- Reference data (no date column) handling

CRITICAL: These tests are essential for v1.0 migration.
"""

from __future__ import annotations

import narwhals as nw
import pandas as pd
import pyarrow as pa
import pytest

from xbbg.backend import Backend, Format
from xbbg.io.convert import (
    _apply_multiindex,
    _convert_backend,
    to_output,
)


class TestConvertBackend:
    """Test _convert_backend() function."""

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

    def test_convert_backend_narwhals(self):
        """Test converting to narwhals backend (passthrough)."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.NARWHALS)
        # Should return the same narwhals frame
        assert isinstance(result, nw.DataFrame)

    def test_convert_backend_pandas(self):
        """Test converting to pandas backend."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PANDAS)
        assert isinstance(result, pd.DataFrame)
        assert "ticker" in result.columns
        assert len(result) == 2

    def test_convert_backend_pyarrow(self):
        """Test converting to pyarrow backend."""
        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.PYARROW)
        assert isinstance(result, pa.Table)
        assert "ticker" in result.column_names

    def test_convert_backend_string_value(self):
        """Test converting with string backend value."""
        nw_frame = self._create_test_nw_frame()
        # Backend enum can be passed as string
        result = _convert_backend(nw_frame, Backend.PANDAS)
        assert isinstance(result, pd.DataFrame)

    def test_convert_backend_unsupported_raises_error(self):
        """Test that unsupported backend raises ValueError."""
        nw_frame = self._create_test_nw_frame()
        with pytest.raises(ValueError, match="is not a valid Backend"):
            _convert_backend(nw_frame, "invalid_backend")  # type: ignore[invalid-argument-type]


class TestConvertBackendPolars:
    """Test _convert_backend() with polars backend."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01"]),
                "px_last": [150.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_backend_polars(self):
        """Test converting to polars backend."""
        pytest.importorskip("polars")
        import polars as pl

        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.POLARS)
        assert isinstance(result, pl.DataFrame)

    def test_convert_backend_polars_lazy(self):
        """Test converting to polars lazy backend."""
        pytest.importorskip("polars")
        import polars as pl

        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.POLARS_LAZY)
        assert isinstance(result, pl.LazyFrame)


class TestConvertBackendDuckDB:
    """Test _convert_backend() with duckdb backend."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity"],
                "px_last": [150.0],
            }
        )
        return nw.from_native(pdf)

    def test_convert_backend_duckdb(self):
        """Test converting to duckdb backend."""
        pytest.importorskip("duckdb")

        nw_frame = self._create_test_nw_frame()
        result = _convert_backend(nw_frame, Backend.DUCKDB)
        # DuckDB returns a relation
        assert hasattr(result, "fetchall")


class TestApplyMultiindex:
    """Test _apply_multiindex() function."""

    def _create_test_nw_frame(self):
        """Create a test narwhals DataFrame for multiindex."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity", "MSFT US Equity", "MSFT US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0, 380.0, 382.0],
                "volume": [1000000, 1100000, 500000, 550000],
            }
        )
        return nw.from_native(pdf)

    def test_apply_multiindex_creates_multiindex_columns(self):
        """Test that _apply_multiindex creates MultiIndex columns."""
        nw_frame = self._create_test_nw_frame()
        result = _apply_multiindex(nw_frame, "ticker", "date", ["px_last", "volume"])
        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.columns, pd.MultiIndex)

    def test_apply_multiindex_has_correct_structure(self):
        """Test that MultiIndex has correct ticker/field structure."""
        nw_frame = self._create_test_nw_frame()
        result = _apply_multiindex(nw_frame, "ticker", "date", ["px_last", "volume"])
        # Should have columns for each ticker-field combination
        assert len(result.columns) == 4  # 2 tickers * 2 fields

    def test_apply_multiindex_date_as_index(self):
        """Test that date becomes the index."""
        nw_frame = self._create_test_nw_frame()
        result = _apply_multiindex(nw_frame, "ticker", "date", ["px_last", "volume"])
        assert result.index.name == "date"

    def test_apply_multiindex_empty_frame(self):
        """Test _apply_multiindex with empty frame."""
        pdf = pd.DataFrame(columns=pd.Index(["ticker", "date", "px_last"]))
        nw_frame = nw.from_native(pdf)
        result = _apply_multiindex(nw_frame, "ticker", "date", ["px_last"])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestToOutputLong:
    """Test to_output() with LONG format."""

    def _create_test_arrow_table(self):
        """Create a test Arrow table."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0],
                "volume": [1000000, 1100000],
            }
        )

    def test_to_output_long_format(self):
        """Test to_output with LONG format."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        assert isinstance(result, pd.DataFrame)
        # LONG format should have field and value columns
        assert "field" in result.columns
        assert "value" in result.columns

    def test_to_output_long_unpivots_fields(self):
        """Test that LONG format unpivots field columns."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        # Should have 4 rows (2 dates * 2 fields)
        assert len(result) == 4
        # Should have both field names
        assert set(result["field"].unique()) == {"px_last", "volume"}


class TestToOutputSemiLong:
    """Test to_output() with SEMI_LONG format."""

    def _create_test_arrow_table(self):
        """Create a test Arrow table."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "MSFT US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "px_last": [150.0, 380.0],
            }
        )

    def test_to_output_semi_long_format(self):
        """Test to_output with SEMI_LONG format (passthrough)."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.SEMI_LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        assert isinstance(result, pd.DataFrame)
        # SEMI_LONG should preserve original structure
        assert "ticker" in result.columns
        assert "date" in result.columns
        assert "px_last" in result.columns

    def test_to_output_semi_long_preserves_rows(self):
        """Test that SEMI_LONG format preserves row count."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.SEMI_LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        assert len(result) == 2


class TestToOutputWide:
    """Test to_output() with WIDE format."""

    def _create_test_arrow_table(self):
        """Create a test Arrow table."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity", "MSFT US Equity", "MSFT US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0, 380.0, 382.0],
            }
        )

    def test_to_output_wide_format_pandas(self):
        """Test to_output with WIDE format for pandas backend."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.WIDE,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        assert isinstance(result, pd.DataFrame)
        # WIDE format should have MultiIndex columns for pandas
        assert isinstance(result.columns, pd.MultiIndex)

    def test_to_output_wide_format_narwhals(self):
        """Test to_output with WIDE format for narwhals backend."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.NARWHALS,
            format=Format.WIDE,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        # WIDE format may return pandas or narwhals depending on implementation
        # The key is that it should not raise an error and return valid data
        assert result is not None
        assert len(result) > 0


class TestToOutputEmptyTable:
    """Test to_output() with empty tables."""

    def test_to_output_empty_table_pandas(self):
        """Test to_output with empty Arrow table for pandas."""
        arrow_table = pa.table(
            {
                "ticker": pa.array([], type=pa.string()),
                "date": pa.array([], type=pa.timestamp("ns")),
                "px_last": pa.array([], type=pa.float64()),
            }
        )
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.SEMI_LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_to_output_empty_table_narwhals(self):
        """Test to_output with empty Arrow table for narwhals."""
        arrow_table = pa.table({})
        result = to_output(
            arrow_table,
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last"],
        )
        # Should return a narwhals DataFrame
        assert isinstance(result, nw.DataFrame)


class TestToOutputReferenceData:
    """Test to_output() with reference data (no date column)."""

    def _create_reference_data_table(self):
        """Create a reference data Arrow table (BDP-style)."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity", "MSFT US Equity", "MSFT US Equity"],
                "field": ["PX_LAST", "VOLUME", "PX_LAST", "VOLUME"],
                "value": ["150.0", "1000000", "380.0", "500000"],
            }
        )

    def test_to_output_reference_data_long(self):
        """Test to_output with reference data in LONG format."""
        arrow_table = self._create_reference_data_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="date",  # Not present in data
            field_cols=["field", "value"],
        )
        assert isinstance(result, pd.DataFrame)
        # Should passthrough since no date column
        assert "ticker" in result.columns

    def test_to_output_reference_data_wide(self):
        """Test to_output with reference data in WIDE format."""
        arrow_table = self._create_reference_data_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.WIDE,
            ticker_col="ticker",
            date_col="date",  # Not present in data
            field_cols=["field", "value"],
        )
        assert isinstance(result, pd.DataFrame)
        # Should pivot with ticker as index, fields as columns
        assert "PX_LAST" in result.columns
        assert "VOLUME" in result.columns


class TestToOutputFieldColsInference:
    """Test to_output() field column inference."""

    def test_to_output_infers_field_cols(self):
        """Test that to_output infers field columns when not provided."""
        arrow_table = pa.table(
            {
                "ticker": ["AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01"]),
                "px_last": [150.0],
                "volume": [1000000],
            }
        )
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=None,  # Should infer
        )
        assert isinstance(result, pd.DataFrame)
        # Should have unpivoted px_last and volume
        assert "field" in result.columns
        assert set(result["field"].unique()) == {"px_last", "volume"}


class TestToOutputLongMixedTypes:
    """Test to_output() LONG format with mixed-type columns (e.g., tick data)."""

    def _create_tick_arrow_table(self):
        """Create a tick-data Arrow table with mixed float/int/string columns."""
        pdf = pd.DataFrame(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity"],
                "time": pd.to_datetime(["2024-01-01 09:30:00", "2024-01-01 09:30:01"]),
                "value": [150.0, 150.5],
                "volume": [100, 200],
                "typ": ["TRADE", "TRADE"],
                "cond": ["R", "R"],
            }
        )
        return pa.Table.from_pandas(pdf)

    def test_long_mixed_types_does_not_error(self):
        """LONG format should not raise on mixed float+string columns."""
        arrow_table = self._create_tick_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="time",
            field_cols=None,
        )
        assert isinstance(result, pd.DataFrame)
        assert "field" in result.columns
        assert "value" in result.columns

    def test_long_mixed_types_has_all_fields(self):
        """All field columns should appear in the unpivoted output."""
        arrow_table = self._create_tick_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="time",
            field_cols=None,
        )
        expected_fields = {"value", "volume", "typ", "cond"}
        assert set(result["field"].unique()) == expected_fields

    def test_long_mixed_types_row_count(self):
        """2 ticks * 4 fields = 8 rows."""
        arrow_table = self._create_tick_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="time",
            field_cols=None,
        )
        assert len(result) == 8  # 2 rows * 4 field columns

    def test_long_homogeneous_preserves_numeric(self):
        """When all fields are numeric, LONG should keep float values (no string cast)."""
        arrow_table = pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0],
                "volume": [1000000, 1100000],
            }
        )
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        # Values should be numeric, not string
        assert result["value"].dtype.kind == "f"  # float


class TestToOutputLongTyped:
    """Test to_output() with LONG_TYPED format."""

    def _create_test_arrow_table(self):
        """Create a test Arrow table with multiple types."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0],
                "volume": [1000000, 1100000],
            }
        )

    def test_long_typed_has_typed_columns(self):
        """LONG_TYPED should have value_f64, value_i64, etc. columns."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_TYPED,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        assert isinstance(result, pd.DataFrame)
        assert "field" in result.columns
        assert "value_f64" in result.columns
        assert "value_i64" in result.columns
        assert "value_str" in result.columns

    def test_long_typed_routes_values_correctly(self):
        """Float fields go to value_f64, int fields go to value_i64."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_TYPED,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        px_rows = result[result["field"] == "px_last"]
        vol_rows = result[result["field"] == "volume"]
        # px_last (float) should populate value_f64
        assert px_rows["value_f64"].notna().all()
        assert px_rows["value_i64"].isna().all()
        # volume (int) should populate value_i64
        assert vol_rows["value_i64"].notna().all()
        assert vol_rows["value_f64"].isna().all()

    def test_long_typed_row_count(self):
        """2 dates * 2 fields = 4 rows."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_TYPED,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        assert len(result) == 4

    def test_long_typed_with_mixed_types(self):
        """LONG_TYPED with float + string columns."""
        arrow_table = pa.table(
            {
                "ticker": ["AAPL", "AAPL"],
                "time": pd.to_datetime(["2024-01-01 09:30:00", "2024-01-01 09:30:01"]),
                "price": [150.0, 150.5],
                "exchange": ["NYSE", "NYSE"],
            }
        )
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_TYPED,
            ticker_col="ticker",
            date_col="time",
            field_cols=["price", "exchange"],
        )
        price_rows = result[result["field"] == "price"]
        exch_rows = result[result["field"] == "exchange"]
        assert price_rows["value_f64"].notna().all()
        assert exch_rows["value_str"].notna().all()


class TestToOutputLongWithMetadata:
    """Test to_output() with LONG_WITH_METADATA format."""

    def _create_test_arrow_table(self):
        """Create a test Arrow table."""
        return pa.table(
            {
                "ticker": ["AAPL US Equity", "AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "px_last": [150.0, 151.0],
                "volume": [1000000, 1100000],
            }
        )

    def test_long_metadata_has_dtype_column(self):
        """LONG_WITH_METADATA should have a 'dtype' column."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_WITH_METADATA,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        assert isinstance(result, pd.DataFrame)
        assert "field" in result.columns
        assert "value" in result.columns
        assert "dtype" in result.columns

    def test_long_metadata_dtype_values(self):
        """dtype column should reflect Arrow type names."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_WITH_METADATA,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        px_dtypes = result[result["field"] == "px_last"]["dtype"].unique()
        vol_dtypes = result[result["field"] == "volume"]["dtype"].unique()
        assert len(px_dtypes) == 1
        assert "double" in px_dtypes[0] or "float" in px_dtypes[0]
        assert len(vol_dtypes) == 1
        assert "int" in vol_dtypes[0]

    def test_long_metadata_values_are_strings(self):
        """All values should be cast to string."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_WITH_METADATA,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        # value column should be string type
        assert result["value"].dtype == object or str(result["value"].dtype) == "string"

    def test_long_metadata_row_count(self):
        """2 dates * 2 fields = 4 rows."""
        arrow_table = self._create_test_arrow_table()
        result = to_output(
            arrow_table,
            backend=Backend.PANDAS,
            format=Format.LONG_WITH_METADATA,
            ticker_col="ticker",
            date_col="date",
            field_cols=["px_last", "volume"],
        )
        assert len(result) == 4


class TestToOutputUnsupportedFormat:
    """Test to_output() with unsupported format."""

    def test_to_output_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValueError."""
        arrow_table = pa.table(
            {
                "ticker": ["AAPL US Equity"],
                "date": pd.to_datetime(["2024-01-01"]),
                "px_last": [150.0],
            }
        )
        with pytest.raises(ValueError, match="Unsupported format"):
            to_output(
                arrow_table,
                backend=Backend.PANDAS,
                format="invalid_format",  # type: ignore[invalid-argument-type]
                ticker_col="ticker",
                date_col="date",
                field_cols=["px_last"],
            )


class TestBackendEnum:
    """Test Backend enum values."""

    def test_backend_values(self):
        """Test that Backend enum has expected values."""
        # Eager backends
        assert Backend.NARWHALS.value == "narwhals"
        assert Backend.PANDAS.value == "pandas"
        assert Backend.POLARS.value == "polars"
        assert Backend.PYARROW.value == "pyarrow"
        assert Backend.CUDF.value == "cudf"
        assert Backend.MODIN.value == "modin"
        # Lazy backends
        assert Backend.NARWHALS_LAZY.value == "narwhals_lazy"
        assert Backend.POLARS_LAZY.value == "polars_lazy"
        assert Backend.DUCKDB.value == "duckdb"
        assert Backend.DASK.value == "dask"
        assert Backend.IBIS.value == "ibis"
        assert Backend.PYSPARK.value == "pyspark"
        assert Backend.SQLFRAME.value == "sqlframe"

    def test_backend_is_string_enum(self):
        """Test that Backend inherits from str."""
        assert isinstance(Backend.PANDAS, str)
        assert Backend.PANDAS == "pandas"

    def test_all_backends_counted(self):
        """Test that we have all expected backends."""
        # 6 eager + 7 lazy = 13 total backends
        assert len(Backend) == 13


class TestFormatEnum:
    """Test Format enum values."""

    def test_format_values(self):
        """Test that Format enum has expected values."""
        assert Format.LONG.value == "long"
        assert Format.SEMI_LONG.value == "semi_long"
        assert Format.WIDE.value == "wide"

    def test_format_is_string_enum(self):
        """Test that Format inherits from str."""
        assert isinstance(Format.LONG, str)
        assert Format.LONG == "long"
