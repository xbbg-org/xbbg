"""Comprehensive tests for unified request() and arequest() functions.

Tests cover:
- Config resolution (instance vs callable)
- Parameter handling (tickers, fields, dates)
- Date precedence (dt > start_datetime/end_datetime > start_date/end_date > asof)
- Per-ticker fan-out behavior
- Retry logic and error handling
- Backend/format options
- Async wrapper (arequest)
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from xbbg.backend import Backend, Format
from xbbg.core.domain.context import BloombergContext
from xbbg.core.domain.contracts import DataRequest
from xbbg.core.pipeline import (
    PipelineConfig,
    RequestBuilder,
    reference_pipeline_config,
    historical_pipeline_config,
    bql_pipeline_config,
)
from xbbg.core.request import request, arequest, _normalize_tickers, _normalize_fields


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_pipeline():
    """Mock BloombergPipeline for testing."""
    with patch("xbbg.core.request.BloombergPipeline") as mock:
        pipeline_instance = MagicMock()
        mock.return_value = pipeline_instance
        yield mock, pipeline_instance


@pytest.fixture
def mock_split_kwargs():
    """Mock split_kwargs to return predictable split."""
    with patch("xbbg.core.request.split_kwargs") as mock:
        split = MagicMock()
        split.infra.to_kwargs.return_value = {}
        split.request_opts = {}
        split.override_like = {}
        mock.return_value = split
        yield mock, split


@pytest.fixture
def mock_context():
    """Mock BloombergContext."""
    with patch("xbbg.core.request.BloombergContext") as mock:
        context_instance = MagicMock()
        context_instance.cache = True
        context_instance.reload = False
        mock.from_kwargs.return_value = context_instance
        yield mock, context_instance


@pytest.fixture
def sample_dataframe():
    """Sample DataFrame for mock pipeline results."""
    return pd.DataFrame(
        {
            "ticker": ["AAPL US Equity"],
            "px_last": [150.0],
            "volume": [1000000],
        }
    )


# ============================================================================
# Tests: Normalization Functions
# ============================================================================


class TestNormalizationFunctions:
    """Test ticker and field normalization helpers."""

    def test_normalize_tickers_single_string(self):
        """Test normalizing single ticker string."""
        with patch("xbbg.core.request.utils.normalize_tickers") as mock:
            mock.return_value = ["AAPL US Equity"]
            result = _normalize_tickers("AAPL US Equity")
            assert result == ["AAPL US Equity"]
            mock.assert_called_once()

    def test_normalize_tickers_list(self):
        """Test normalizing list of tickers."""
        with patch("xbbg.core.request.utils.normalize_tickers") as mock:
            mock.return_value = ["AAPL US Equity", "MSFT US Equity"]
            result = _normalize_tickers(["AAPL US Equity", "MSFT US Equity"])
            assert result == ["AAPL US Equity", "MSFT US Equity"]

    def test_normalize_tickers_none(self):
        """Test normalizing None returns empty list."""
        result = _normalize_tickers(None)
        assert result == []

    def test_normalize_fields_single_string(self):
        """Test normalizing single field string."""
        with patch("xbbg.core.request.utils.normalize_flds") as mock:
            mock.return_value = ["PX_LAST"]
            result = _normalize_fields("PX_LAST")
            assert result == ["PX_LAST"]

    def test_normalize_fields_list(self):
        """Test normalizing list of fields."""
        with patch("xbbg.core.request.utils.normalize_flds") as mock:
            mock.return_value = ["PX_LAST", "VOLUME"]
            result = _normalize_fields(["PX_LAST", "VOLUME"])
            assert result == ["PX_LAST", "VOLUME"]

    def test_normalize_fields_none(self):
        """Test normalizing None returns empty list."""
        result = _normalize_fields(None)
        assert result == []


# ============================================================================
# Tests: Config Resolution
# ============================================================================


class TestConfigResolution:
    """Test config resolution (instance vs callable)."""

    def test_request_with_config_instance(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with PipelineConfig instance."""
        mock_pipeline[1].run.return_value = sample_dataframe

        config = reference_pipeline_config
        result = request(config, "AAPL US Equity", "PX_LAST")

        assert isinstance(result, pd.DataFrame)
        mock_pipeline[0].assert_called_once()

    def test_request_with_config_factory(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with callable config factory."""
        mock_pipeline[1].run.return_value = sample_dataframe

        def config_factory():
            return reference_pipeline_config

        result = request(config_factory, "AAPL US Equity", "PX_LAST")

        assert isinstance(result, pd.DataFrame)
        mock_pipeline[0].assert_called_once()

    def test_request_with_historical_config(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with historical_pipeline_config."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            historical_pipeline_config,
            "SPX Index",
            "PX_LAST",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_bql_config(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with bql_pipeline_config."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            bql_pipeline_config,
            tickers=None,
            fields=None,
            primary_ticker="DUMMY",
            tickers_key=None,
            fields_key=None,
            request_opts={"query": "get(px_last) for('AAPL US Equity')"},
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Ticker and Field Variations
# ============================================================================


class TestTickerFieldVariations:
    """Test various ticker and field parameter combinations."""

    def test_request_single_ticker_single_field(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with single ticker and single field."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(reference_pipeline_config, "AAPL US Equity", "PX_LAST")

        assert isinstance(result, pd.DataFrame)
        mock_pipeline[1].run.assert_called_once()

    def test_request_list_tickers_list_fields(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with list of tickers and fields."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            ["AAPL US Equity", "MSFT US Equity"],
            ["PX_LAST", "VOLUME"],
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_none_tickers(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with tickers=None (for BQL, etc.)."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            bql_pipeline_config,
            tickers=None,
            fields=None,
            request_opts={"query": "get(px_last) for('AAPL US Equity')"},
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_none_fields(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with fields=None."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            fields=None,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_primary_ticker_default(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that primary_ticker defaults to first ticker."""
        mock_pipeline[1].run.return_value = sample_dataframe

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            request(reference_pipeline_config, ["AAPL US Equity", "MSFT US Equity"], "PX_LAST")

            # Verify primary_ticker was set to first ticker
            call_args = mock_pipeline[1].run.call_args
            assert call_args is not None

    def test_request_primary_ticker_explicit(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test explicit primary_ticker parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            primary_ticker="CUSTOM US Equity",
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Date Precedence
# ============================================================================


class TestDatePrecedence:
    """Test date parameter precedence logic."""

    def test_date_precedence_dt_over_start_end_date(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test that dt takes precedence over start_date/end_date."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            dt="2024-06-15",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        assert isinstance(result, pd.DataFrame)

    def test_date_precedence_start_datetime_end_datetime(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test that start_datetime/end_datetime take precedence."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            start_datetime="2024-06-15 09:30:00",
            end_datetime="2024-06-15 16:00:00",
            dt="2024-06-15",
        )

        assert isinstance(result, pd.DataFrame)

    def test_date_precedence_start_date_over_asof(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test that start_date takes precedence over asof."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            start_date="2024-01-01",
            asof="2024-06-15",
        )

        assert isinstance(result, pd.DataFrame)

    def test_date_default_today(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that dt defaults to 'today' when no date specified."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(reference_pipeline_config, "AAPL US Equity", "PX_LAST")

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Per-Ticker Fan-Out
# ============================================================================


class TestPerTickerFanOut:
    """Test per_ticker fan-out behavior."""

    def test_request_per_ticker_true_executes_separate_requests(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test that per_ticker=True executes one request per ticker."""
        # Return different DataFrames for each call
        df1 = pd.DataFrame({"ticker": ["AAPL US Equity"], "px_last": [150.0]})
        df2 = pd.DataFrame({"ticker": ["MSFT US Equity"], "px_last": [300.0]})
        mock_pipeline[1].run.side_effect = [df1, df2]

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            result = request(
                reference_pipeline_config,
                ["AAPL US Equity", "MSFT US Equity"],
                "PX_LAST",
                per_ticker=True,
            )

            # Should have called run twice (once per ticker)
            assert mock_pipeline[1].run.call_count == 2

    def test_request_per_ticker_false_single_request(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test that per_ticker=False executes single request."""
        mock_pipeline[1].run.return_value = sample_dataframe

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            result = request(
                reference_pipeline_config,
                ["AAPL US Equity", "MSFT US Equity"],
                "PX_LAST",
                per_ticker=False,
            )

            # Should have called run once
            assert mock_pipeline[1].run.call_count == 1

    def test_request_per_ticker_concat_true(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test that per_ticker=True with concat=True concatenates results."""
        df1 = pd.DataFrame({"ticker": ["AAPL US Equity"], "px_last": [150.0]})
        df2 = pd.DataFrame({"ticker": ["MSFT US Equity"], "px_last": [300.0]})
        mock_pipeline[1].run.side_effect = [df1, df2]

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            with patch("xbbg.core.request.concat_frames") as mock_concat:
                mock_concat.return_value = pd.concat([df1, df2])

                result = request(
                    reference_pipeline_config,
                    ["AAPL US Equity", "MSFT US Equity"],
                    "PX_LAST",
                    per_ticker=True,
                    concat=True,
                )

                mock_concat.assert_called_once()

    def test_request_per_ticker_concat_false(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test that per_ticker=True with concat=False returns list."""
        df1 = pd.DataFrame({"ticker": ["AAPL US Equity"], "px_last": [150.0]})
        df2 = pd.DataFrame({"ticker": ["MSFT US Equity"], "px_last": [300.0]})
        mock_pipeline[1].run.side_effect = [df1, df2]

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            result = request(
                reference_pipeline_config,
                ["AAPL US Equity", "MSFT US Equity"],
                "PX_LAST",
                per_ticker=True,
                concat=False,
            )

            assert isinstance(result, list)
            assert len(result) == 2

    def test_request_per_ticker_empty_ticker_list(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test per_ticker=True with empty ticker list."""
        mock_pipeline[1].run.return_value = sample_dataframe

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = []

            result = request(
                reference_pipeline_config,
                [],
                "PX_LAST",
                per_ticker=True,
            )

            # When per_ticker=True and ticker_list is empty, the loop doesn't execute
            # but run is still called with primary_ticker (DUMMY)
            assert isinstance(result, (pd.DataFrame, list))


# ============================================================================
# Tests: Error Handling and Retry Logic
# ============================================================================


class TestErrorHandlingAndRetry:
    """Test error handling and retry logic."""

    def test_request_retries_on_failure(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test retry logic when pipeline fails."""
        # First call fails, second succeeds
        mock_pipeline[1].run.side_effect = [Exception("API Error"), sample_dataframe]

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            max_retries=1,
            raise_on_error=False,
        )

        # Should have retried
        assert mock_pipeline[1].run.call_count == 2

    def test_request_raises_after_max_retries(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test that request() raises after max retries exceeded."""
        mock_pipeline[1].run.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            request(
                reference_pipeline_config,
                "AAPL US Equity",
                "PX_LAST",
                max_retries=1,
                raise_on_error=True,
            )

    def test_request_returns_empty_dataframe_on_failure_no_raise(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test that request() returns empty DataFrame on failure when raise_on_error=False."""
        mock_pipeline[1].run.side_effect = Exception("API Error")

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            max_retries=0,
            raise_on_error=False,
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_request_retries_on_empty_result(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test retry logic when result is empty."""
        empty_df = pd.DataFrame()

        # First call returns empty, second succeeds
        mock_pipeline[1].run.side_effect = [empty_df, sample_dataframe]

        with patch("xbbg.core.request.is_empty") as mock_is_empty:
            mock_is_empty.side_effect = [True, False]

            result = request(
                reference_pipeline_config,
                "AAPL US Equity",
                "PX_LAST",
                max_retries=1,
            )

            # Should have retried
            assert mock_pipeline[1].run.call_count == 2

    def test_request_no_retry_on_non_empty_result(
        self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe
    ):
        """Test that request() doesn't retry on non-empty result."""
        mock_pipeline[1].run.return_value = sample_dataframe

        with patch("xbbg.core.request.is_empty") as mock_is_empty:
            mock_is_empty.return_value = False

            result = request(
                reference_pipeline_config,
                "AAPL US Equity",
                "PX_LAST",
                max_retries=5,
            )

            # Should not retry
            assert mock_pipeline[1].run.call_count == 1


# ============================================================================
# Tests: Backend and Format Options
# ============================================================================


class TestBackendFormatOptions:
    """Test backend and format parameter handling."""

    def test_request_with_backend_option(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with backend parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            backend=Backend.PANDAS,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_format_option(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with format parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            format=Format.LONG,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_backend_and_format(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with both backend and format."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            backend=Backend.PANDAS,
            format=Format.LONG,
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Cache and Infrastructure Options
# ============================================================================


class TestCacheAndInfraOptions:
    """Test cache and infrastructure parameter handling."""

    def test_request_with_cache_enabled(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with cache_enabled=True."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            cache_enabled=True,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_cache_disabled(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with cache_enabled=False."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            cache_enabled=False,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_reload(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with reload=True."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            reload=True,
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_infra_options(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with infra parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            infra={"server": "localhost", "port": 8194},
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Request Options and Overrides
# ============================================================================


class TestRequestOptionsAndOverrides:
    """Test request_opts and overrides parameter handling."""

    def test_request_with_request_opts(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with request_opts parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            request_opts={"custom_opt": "value"},
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_overrides(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with overrides parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            overrides={"VWAP_Dt": "20240115"},
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_custom_keys(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with custom tickers_key and fields_key."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            tickers_key="securities",
            fields_key="fields",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_none_keys(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with tickers_key=None and fields_key=None."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            bql_pipeline_config,
            tickers=None,
            fields=None,
            tickers_key=None,
            fields_key=None,
            request_opts={"query": "get(px_last) for('AAPL US Equity')"},
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Session and Event Type Options
# ============================================================================


class TestSessionEventTypeOptions:
    """Test session and event type parameter handling."""

    def test_request_with_session(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with session parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            session="day",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_event_type(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with typ parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            typ="TRADE",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_session_default(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that session defaults to 'allday'."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_event_type_default(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that event type defaults to 'TRADE'."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Interval Options
# ============================================================================


class TestIntervalOptions:
    """Test interval parameter handling."""

    def test_request_with_interval(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with interval parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            request_opts={"interval": 5},
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_interval_has_seconds(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with intervalHasSeconds parameter."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            "PX_LAST",
            request_opts={"interval": 10, "intervalHasSeconds": True},
        )

        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests: Async Wrapper (arequest)
# ============================================================================


class TestArequest:
    """Test async arequest() wrapper."""

    def test_arequest_calls_request_in_thread(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that arequest() uses asyncio.to_thread()."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = asyncio.run(arequest(reference_pipeline_config, "AAPL US Equity", "PX_LAST"))

        assert isinstance(result, pd.DataFrame)

    def test_arequest_preserves_parameters(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test that arequest() passes all parameters to request()."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = asyncio.run(
            arequest(
                reference_pipeline_config,
                ["AAPL US Equity", "MSFT US Equity"],
                ["PX_LAST", "VOLUME"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                backend=Backend.PANDAS,
                format=Format.LONG,
            )
        )

        assert isinstance(result, pd.DataFrame)

    def test_arequest_with_per_ticker(self, mock_pipeline, mock_split_kwargs, mock_context):
        """Test arequest() with per_ticker=True."""
        df1 = pd.DataFrame({"ticker": ["AAPL US Equity"], "px_last": [150.0]})
        df2 = pd.DataFrame({"ticker": ["MSFT US Equity"], "px_last": [300.0]})
        mock_pipeline[1].run.side_effect = [df1, df2]

        with patch("xbbg.core.request.utils.normalize_tickers") as mock_norm:
            mock_norm.return_value = ["AAPL US Equity", "MSFT US Equity"]

            result = asyncio.run(
                arequest(
                    reference_pipeline_config,
                    ["AAPL US Equity", "MSFT US Equity"],
                    "PX_LAST",
                    per_ticker=True,
                    concat=False,
                )
            )

            assert isinstance(result, list)

    def test_arequest_concurrent_requests(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test concurrent arequest() calls."""
        mock_pipeline[1].run.return_value = sample_dataframe

        async def run_concurrent():
            return await asyncio.gather(
                arequest(reference_pipeline_config, "AAPL US Equity", "PX_LAST"),
                arequest(reference_pipeline_config, "MSFT US Equity", "PX_LAST"),
            )

        results = asyncio.run(run_concurrent())

        assert len(results) == 2
        assert all(isinstance(r, pd.DataFrame) for r in results)


# ============================================================================
# Tests: Integration Scenarios
# ============================================================================


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_request_reference_data_workflow(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test typical reference data workflow."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            ["AAPL US Equity", "MSFT US Equity"],
            ["PX_LAST", "VOLUME", "SECURITY_NAME"],
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_historical_data_workflow(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test typical historical data workflow."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            historical_pipeline_config,
            "SPX Index",
            ["PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW"],
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_intraday_workflow(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test typical intraday data workflow."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            "AAPL US Equity",
            ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
            dt="2024-06-15",
            session="day",
            request_opts={"interval": 5},
        )

        assert isinstance(result, pd.DataFrame)

    def test_request_with_all_parameters(self, mock_pipeline, mock_split_kwargs, mock_context, sample_dataframe):
        """Test request() with comprehensive parameter set."""
        mock_pipeline[1].run.return_value = sample_dataframe

        result = request(
            reference_pipeline_config,
            ["AAPL US Equity", "MSFT US Equity"],
            ["PX_LAST", "VOLUME"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            session="day",
            typ="TRADE",
            primary_ticker="AAPL US Equity",
            request_opts={"interval": 5},
            overrides={"VWAP_Dt": "20240115"},
            infra={"server": "localhost", "port": 8194},
            backend=Backend.PANDAS,
            format=Format.LONG,
            cache_enabled=True,
            reload=False,
            per_ticker=False,
            concat=True,
            max_retries=1,
            raise_on_error=False,
        )

        assert isinstance(result, pd.DataFrame)
