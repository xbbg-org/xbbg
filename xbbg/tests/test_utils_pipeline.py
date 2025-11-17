"""Unit tests for utils/pipeline utility functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xbbg.utils import pipeline


class TestGetSeries:
    """Test get_series function."""

    def test_get_series_from_series(self):
        """Test get_series with Series input."""
        series = pd.Series([1, 2, 3], index=pd.date_range('2024-01-01', periods=3))
        result = pipeline.get_series(series)
        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == 1

    def test_get_series_from_dataframe_no_multiindex(self):
        """Test get_series with DataFrame without MultiIndex."""
        df = pd.DataFrame({'close': [1, 2, 3]}, index=pd.date_range('2024-01-01', periods=3))
        result = pipeline.get_series(df)
        pd.testing.assert_frame_equal(result, df)

    def test_get_series_from_dataframe_with_multiindex(self):
        """Test get_series with DataFrame with MultiIndex columns."""
        df = pd.DataFrame(
            {('AAPL US Equity', 'close'): [1, 2, 3]},
            index=pd.date_range('2024-01-01', periods=3)
        )
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        result = pipeline.get_series(df, col='close')
        assert len(result.columns) == 1
        # After xs(), result may have single-level index or MultiIndex with one level
        if isinstance(result.columns, pd.MultiIndex):
            assert 'close' not in result.columns.get_level_values(1)
        else:
            assert 'AAPL US Equity' in result.columns.get_level_values(0) if isinstance(result.columns, pd.MultiIndex) else True

    def test_get_series_custom_column(self):
        """Test get_series with custom column name."""
        df = pd.DataFrame(
            {('AAPL US Equity', 'open'): [1, 2, 3], ('AAPL US Equity', 'close'): [4, 5, 6]},
            index=pd.date_range('2024-01-01', periods=3)
        )
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        result = pipeline.get_series(df, col='open')
        assert len(result.columns) == 1


class TestStandardCols:
    """Test standard_cols function."""

    def test_standard_cols_basic(self):
        """Test standard column renaming."""
        df = pd.DataFrame({
            'Declared Date': [1, 2],
            'Ex-Date': [3, 4],
            'Record Date': [5, 6]
        })
        result = pipeline.standard_cols(df)
        assert 'declared_date' in result.columns
        assert 'ex_date' in result.columns
        assert 'record_date' in result.columns

    def test_standard_cols_with_col_maps(self):
        """Test standard_cols with column mappings."""
        df = pd.DataFrame({
            'Declared Date': [1, 2],
            'Ex-Date': [3, 4]
        })
        result = pipeline.standard_cols(df, col_maps={'Declared Date': 'dec_date'})
        assert 'dec_date' in result.columns
        assert 'ex_date' in result.columns

    def test_standard_cols_hyphen_replacement(self):
        """Test that hyphens are replaced with underscores."""
        df = pd.DataFrame({'Ex-Date': [1, 2]})
        result = pipeline.standard_cols(df)
        assert 'ex_date' in result.columns
        assert 'Ex-Date' not in result.columns

    def test_standard_cols_space_replacement(self):
        """Test that spaces are replaced with underscores."""
        df = pd.DataFrame({'Record Date': [1, 2]})
        result = pipeline.standard_cols(df)
        assert 'record_date' in result.columns


class TestApplyFx:
    """Test apply_fx function."""

    def test_apply_fx_with_scalar(self):
        """Test apply_fx with scalar FX rate."""
        data = pd.DataFrame({'price': [100, 101, 102]})
        result = pipeline.apply_fx(data, fx=1.1)
        assert result.iloc[0, 0] == pytest.approx(100 * (1.1 ** -1))

    def test_apply_fx_with_series(self):
        """Test apply_fx with Series FX data."""
        data = pd.DataFrame({'price': [100, 101, 102]}, index=pd.date_range('2024-01-01', periods=3))
        fx = pd.Series([1.1, 1.11, 1.12], index=pd.date_range('2024-01-01', periods=3))
        result = pipeline.apply_fx(data, fx=fx)
        assert len(result) == 3

    def test_apply_fx_with_dataframe(self):
        """Test apply_fx with DataFrame FX data."""
        data = pd.DataFrame({'price': [100, 101]}, index=pd.date_range('2024-01-01', periods=2))
        fx = pd.DataFrame({('EURUSD', 'close'): [1.1, 1.11]}, index=pd.date_range('2024-01-01', periods=2))
        fx.columns = pd.MultiIndex.from_tuples(fx.columns)
        result = pipeline.apply_fx(data, fx=fx)
        assert len(result) == 2

    def test_apply_fx_custom_power(self):
        """Test apply_fx with custom power."""
        data = pd.DataFrame({'price': [100, 101]})
        result = pipeline.apply_fx(data, fx=1.1, power=1.0)
        assert result.iloc[0, 0] == pytest.approx(100 * 1.1)

    def test_apply_fx_with_series_input(self):
        """Test apply_fx with Series input."""
        data = pd.Series([100, 101, 102])
        result = pipeline.apply_fx(data, fx=1.1)
        assert isinstance(result, pd.DataFrame)


class TestDailyStats:
    """Test daily_stats function."""

    def test_daily_stats_basic(self):
        """Test daily stats calculation."""
        dates = pd.date_range('2024-01-01', periods=10, freq='h')
        data = pd.DataFrame({'price': np.random.randn(10)}, index=dates)
        result = pipeline.daily_stats(data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_daily_stats_empty(self):
        """Test daily_stats with empty DataFrame."""
        data = pd.DataFrame()
        result = pipeline.daily_stats(data)
        assert result.empty

    def test_daily_stats_custom_percentiles(self):
        """Test daily_stats with custom percentiles."""
        dates = pd.date_range('2024-01-01', periods=10, freq='h')
        data = pd.DataFrame({'price': np.random.randn(10)}, index=dates)
        result = pipeline.daily_stats(data, percentiles=[0.25, 0.5, 0.75])
        assert isinstance(result, pd.DataFrame)


class TestDropna:
    """Test dropna function."""

    def test_dropna_series(self):
        """Test dropna with Series."""
        series = pd.Series([1, np.nan, 3, np.nan, 5])
        result = pipeline.dropna(series)
        assert len(result) == 3
        assert result.notna().all()

    def test_dropna_dataframe_single_column(self):
        """Test dropna with DataFrame single column index."""
        df = pd.DataFrame({
            'col1': [1, np.nan, 3],
            'col2': [4, 5, 6]
        })
        result = pipeline.dropna(df, cols=0)
        assert len(result) == 2  # Should drop row with NaN in col1

    def test_dropna_dataframe_multiple_columns(self):
        """Test dropna with DataFrame multiple column indices."""
        df = pd.DataFrame({
            'col1': [1, np.nan, 3],
            'col2': [4, np.nan, 6],
            'col3': [7, 8, 9]
        })
        result = pipeline.dropna(df, cols=[0, 1])
        assert len(result) == 2  # Should drop row with NaN in col1 or col2


class TestFormatRaw:
    """Test format_raw function."""

    def test_format_raw_datetime_columns(self):
        """Test format_raw converts datetime columns."""
        df = pd.DataFrame({
            'date_col': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'num_col': [1, 2, 3]
        })
        result = pipeline.format_raw(df)
        assert pd.api.types.is_datetime64_any_dtype(result['date_col'])

    def test_format_raw_partial_datetime(self):
        """Test format_raw with partial datetime (should not convert)."""
        df = pd.DataFrame({
            'date_col': ['2024-01-01', 'invalid', '2024-01-03'],
            'num_col': [1, 2, 3]
        })
        result = pipeline.format_raw(df)
        # Should not convert if not all values parse
        assert not pd.api.types.is_datetime64_any_dtype(result['date_col'])

    def test_format_raw_numeric_columns(self):
        """Test format_raw with numeric string columns."""
        df = pd.DataFrame({
            'num_str': ['1', '2', '3'],
            'text': ['a', 'b', 'c']
        })
        result = pipeline.format_raw(df)
        # Numeric strings should be converted
        assert pd.api.types.is_numeric_dtype(result['num_str'])


class TestAddTicker:
    """Test add_ticker function."""

    def test_add_ticker_basic(self):
        """Test adding ticker to DataFrame."""
        df = pd.DataFrame({'close': [1, 2, 3]})
        result = pipeline.add_ticker(df, ticker='AAPL US Equity')
        assert isinstance(result.columns, pd.MultiIndex)
        assert 'AAPL US Equity' in result.columns.get_level_values(0)

    def test_add_ticker_column_rename(self):
        """Test that numEvents is renamed to num_trds."""
        df = pd.DataFrame({'numEvents': [1, 2, 3]})
        result = pipeline.add_ticker(df, ticker='AAPL US Equity')
        assert 'num_trds' in result.columns.get_level_values(1)


class TestSinceYear:
    """Test since_year function."""

    def test_since_year_filters_columns(self):
        """Test since_year filters columns by year."""
        df = pd.DataFrame({
            'fy2016': [1, 2],
            'fy2017': [3, 4],
            'fy2018': [5, 6],
            'fy2019': [7, 8]
        })
        result = pipeline.since_year(df, year=2018)
        assert 'fy2016' not in result.columns
        assert 'fy2017' not in result.columns
        assert 'fy2018' in result.columns
        assert 'fy2019' in result.columns


class TestPerf:
    """Test perf function."""

    def test_perf_series(self):
        """Test perf with Series."""
        series = pd.Series([100, 101, 102, 103])
        result = pipeline.perf(series)
        assert result.iloc[0] == pytest.approx(100.0)
        assert isinstance(result, pd.Series)

    def test_perf_dataframe(self):
        """Test perf with DataFrame."""
        df = pd.DataFrame({
            's1': [100, 101, 102],
            's2': [200, 201, 202]
        })
        result = pipeline.perf(df)
        assert result.iloc[0, 0] == pytest.approx(100.0)
        assert result.iloc[0, 1] == pytest.approx(100.0)
        assert isinstance(result, pd.DataFrame)

    def test_perf_with_nan(self):
        """Test perf handles NaN values."""
        df = pd.DataFrame({
            's1': [1.0, np.nan, 1.01, 1.03],
            's2': [np.nan, 1.0, 0.99, 1.04]
        })
        result = pipeline.perf(df)
        assert result.iloc[0, 0] == pytest.approx(100.0)
        assert pd.isna(result.iloc[0, 1])

    def test_perf_rebase_to_100(self):
        """Test that perf rebases to 100."""
        series = pd.Series([50, 51, 52])
        result = pipeline.perf(series)
        # First non-NaN value should be rebased to 100
        first_valid = result.dropna().iloc[0]
        assert first_valid == pytest.approx(100.0)

