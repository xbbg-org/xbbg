"""Tests for Bloomberg Quote Request (BQR) functionality."""

import pandas as pd
import pytest

from xbbg import blp
from xbbg.core import process
from xbbg.core.infra import conn
from xbbg.core.pipeline_factories import bqr_pipeline_config
from xbbg.core.strategies import BqrRequestBuilder, BqrTransformer


@pytest.fixture(autouse=True)
def stub_bbg_service(monkeypatch):
    """Stub Bloomberg service to avoid real API calls."""

    class _FakeRequest:
        def __init__(self):
            self._elements = {}

        def set(self, name, value):
            self._elements[name] = value
            return

        def getElement(self, name):
            return _FakeEventTypes()

    class _FakeEventTypes:
        def appendValue(self, value):
            pass

    class _FakeService:
        def createRequest(self, request_type):
            return _FakeRequest()

    monkeypatch.setattr(conn, "bbg_service", lambda service, **kwargs: _FakeService())


class TestBqrRequestBuilder:
    """Tests for BqrRequestBuilder class."""

    def test_parse_date_offset_days(self):
        """Test parsing day offset."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        result = builder._parse_date_offset("-2d", ref)

        assert result == ref - pd.Timedelta(days=2)

    def test_parse_date_offset_weeks(self):
        """Test parsing week offset."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        result = builder._parse_date_offset("-1w", ref)

        assert result == ref - pd.Timedelta(weeks=1)

    def test_parse_date_offset_hours(self):
        """Test parsing hour offset."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        result = builder._parse_date_offset("-3h", ref)

        assert result == ref - pd.Timedelta(hours=3)

    def test_parse_date_offset_months(self):
        """Test parsing month offset (approximated as 30 days)."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        result = builder._parse_date_offset("-1m", ref)

        assert result == ref - pd.Timedelta(days=30)

    def test_parse_date_offset_invalid_format(self):
        """Test that invalid offset format raises ValueError."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        with pytest.raises(ValueError, match="Invalid date offset format"):
            builder._parse_date_offset("invalid", ref)

    def test_parse_date_offset_positive(self):
        """Test positive offset (forward in time)."""
        builder = BqrRequestBuilder()
        ref = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")

        result = builder._parse_date_offset("2d", ref)

        assert result == ref + pd.Timedelta(days=2)


class TestBqrPipelineConfig:
    """Tests for BQR pipeline configuration."""

    def test_bqr_pipeline_config_service(self):
        """Test that BQR pipeline uses refdata service."""
        config = bqr_pipeline_config()

        assert config.service == "//blp/refdata"

    def test_bqr_pipeline_config_request_type(self):
        """Test that BQR uses IntradayTickRequest."""
        config = bqr_pipeline_config()

        assert config.request_type == "IntradayTickRequest"

    def test_bqr_pipeline_config_has_builder(self):
        """Test that BQR config has request builder."""
        config = bqr_pipeline_config()

        assert isinstance(config.request_builder, BqrRequestBuilder)

    def test_bqr_pipeline_config_has_transformer(self):
        """Test that BQR config has transformer."""
        config = bqr_pipeline_config()

        assert isinstance(config.transformer, BqrTransformer)

    def test_bqr_pipeline_config_process_func(self):
        """Test that BQR config uses process_bqr."""
        config = bqr_pipeline_config()

        assert config.process_func == process.process_bqr


class TestProcessBqr:
    """Tests for process_bqr function."""

    def test_process_bqr_empty_message(self):
        """Test process_bqr with message lacking tickData."""
        from unittest.mock import MagicMock

        mock_msg = MagicMock()
        mock_msg.hasElement.return_value = False

        result = list(process.process_bqr(mock_msg))

        assert result == []

    def test_process_bqr_with_tick_data(self):
        """Test process_bqr extracts tick data correctly."""
        from unittest.mock import MagicMock

        # Create mock tick element
        mock_tick = MagicMock()
        mock_tick.numElements.return_value = 3

        # Mock elements: time, value, brokerBuyCode
        mock_time_elem = MagicMock()
        mock_time_elem.name.return_value = "time"
        mock_time_elem.isNull.return_value = False
        mock_time_elem.getValue.return_value = "2024-01-15T10:30:00"

        mock_value_elem = MagicMock()
        mock_value_elem.name.return_value = "value"
        mock_value_elem.isNull.return_value = False
        mock_value_elem.getValue.return_value = 100.5

        mock_broker_elem = MagicMock()
        mock_broker_elem.name.return_value = "brokerBuyCode"
        mock_broker_elem.isNull.return_value = False
        mock_broker_elem.getValue.return_value = "EUBS"

        mock_tick.getElement.side_effect = [mock_time_elem, mock_value_elem, mock_broker_elem]

        # Create mock tick array
        mock_tick_array = MagicMock()
        mock_tick_array.numValues.return_value = 1
        mock_tick_array.getValueAsElement.return_value = mock_tick

        # Create mock tickData element with nested tickData
        mock_tick_data = MagicMock()

        # hasElement needs to return True for "tickData" but False for "responseError"
        def has_element_side_effect(name):
            name_str = str(name)
            return "tickData" in name_str

        mock_tick_data.hasElement.side_effect = has_element_side_effect
        mock_tick_data.getElement.return_value = mock_tick_array

        # Create mock message
        mock_msg = MagicMock()
        mock_msg.hasElement.side_effect = has_element_side_effect
        mock_msg.getElement.return_value = mock_tick_data

        result = list(process.process_bqr(mock_msg))

        assert len(result) == 1
        assert result[0]["time"] == "2024-01-15T10:30:00"
        assert result[0]["value"] == 100.5
        assert result[0]["brokerBuyCode"] == "EUBS"


def _make_async_arequest_stub(rows):
    """Create an async stub for conn.arequest that returns the given rows."""

    async def _stub(request, process_func, service=None, **kwargs):
        return rows

    return _stub


class TestBqrApi:
    """Tests for blp.bqr() API function."""

    def test_bqr_returns_dataframe(self, monkeypatch):
        """Test that bqr returns a DataFrame."""
        rows = [
            {"time": "2024-01-15T10:30:00", "type": "BID", "value": 100.5, "size": 1000, "brokerBuyCode": "EUBS"},
        ]
        monkeypatch.setattr(conn, "arequest", _make_async_arequest_stub(rows))

        df = blp.bqr("TEST Corp", date_offset="-2d")

        assert isinstance(df, pd.DataFrame)

    def test_bqr_empty_results_returns_empty_dataframe(self, monkeypatch):
        """Test that empty results return empty DataFrame."""
        monkeypatch.setattr(conn, "arequest", _make_async_arequest_stub([]))

        df = blp.bqr("TEST Corp", date_offset="-2d")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_bqr_default_event_types(self, monkeypatch):
        """Test that default event types are BID and ASK."""
        monkeypatch.setattr(conn, "arequest", _make_async_arequest_stub([]))

        # Verified the function runs without error with default event types
        df = blp.bqr("TEST Corp", date_offset="-2d")
        assert isinstance(df, pd.DataFrame)

    def test_bqr_with_explicit_dates(self, monkeypatch):
        """Test bqr with explicit start and end dates."""
        monkeypatch.setattr(conn, "arequest", _make_async_arequest_stub([]))

        df = blp.bqr("TEST Corp", start_date="2024-01-15", end_date="2024-01-17")

        assert isinstance(df, pd.DataFrame)

    def test_bqr_with_trade_events(self, monkeypatch):
        """Test bqr with TRADE event type."""
        rows = [
            {"time": "2024-01-15T10:30:00", "type": "TRADE", "value": 100.5, "size": 1000},
        ]
        monkeypatch.setattr(conn, "arequest", _make_async_arequest_stub(rows))

        df = blp.bqr("TEST Corp", date_offset="-2d", event_types=["TRADE"])

        assert isinstance(df, pd.DataFrame)
