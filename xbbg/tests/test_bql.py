import pandas as pd
import pytest

from xbbg import blp
from xbbg.core import process
from xbbg.core.infra import conn


@pytest.fixture
def fake_handle():
    return {"event_queue": object(), "correlation_id": object()}


@pytest.fixture(autouse=True)
def stub_bbg_service(monkeypatch):
    class _FakeParamElem:
        def appendElement(self):
            return self

        def setElement(self, *args, **kwargs):
            return None

    class _FakeRequest:
        def __init__(self):
            self._params = _FakeParamElem()

        def set(self, *args, **kwargs):
            return None

        def append(self, *args, **kwargs):
            return None

        def getElement(self, *args, **kwargs):
            return self._params

        def __str__(self):
            return "<FakeRequest>"

    class _FakeService:
        def createRequest(self, *args, **kwargs):
            return _FakeRequest()

    monkeypatch.setattr(conn, "bbg_service", lambda service, **kwargs: _FakeService())


def test_bql_returns_dataframe_from_rows(monkeypatch, fake_handle):
    # Arrange: stub send_request and rec_events to avoid real blpapi calls
    monkeypatch.setattr(conn, "send_request", lambda request, **kwargs: fake_handle)
    rows = [{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}]
    monkeypatch.setattr(process, "rec_events", lambda func, event_queue=None, **kwargs: rows)

    # Act
    df = blp.bql("get(foo, bar)")

    # Assert
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2"]
    assert df.shape == (2, 2)


def test_bql_empty_results_returns_empty_dataframe(monkeypatch, fake_handle):
    monkeypatch.setattr(conn, "send_request", lambda request, **kwargs: fake_handle)
    monkeypatch.setattr(process, "rec_events", lambda func, event_queue=None, **kwargs: [])

    df = blp.bql("get(foo)")

    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_bql_accepts_params(monkeypatch, fake_handle):
    monkeypatch.setattr(conn, "send_request", lambda request, **kwargs: fake_handle)
    monkeypatch.setattr(process, "rec_events", lambda func, event_queue=None, **kwargs: [{"x": 1}])

    df = blp.bql("get(foo)", params={"p": 1, "q": "abc"})

    assert not df.empty
    assert list(df.columns) == ["x"]
    assert df.iloc[0, 0] == 1


def test_iter_bql_json_rows_handles_duplicate_ids():
    """Test BQL JSON parser handles duplicate IDs (e.g., eco_calendar).

    This is the main fix for issue #150: BQL only returns one row when
    requesting multiple calendar events. The issue was that rows_by_id
    merged all rows with the same ID into one.
    """
    import json
    from unittest.mock import MagicMock

    import blpapi

    # Simulate eco_calendar response: same ID repeated for all values
    json_payload = json.dumps({
        "results": {
            "eco_calendar": {
                "idColumn": {"values": ["US Country", "US Country", "US Country"]},
                "valuesColumn": {"values": ["GDP", "CPI", "NFP"]},
                "secondaryColumns": [
                    {"name": "RELEASE_DATE", "values": ["2024-01-01", "2024-01-15", "2024-01-05"]}
                ]
            }
        }
    })

    mock_elem = MagicMock()
    mock_elem.datatype.return_value = blpapi.DataType.STRING
    mock_elem.getValue.return_value = json_payload

    mock_msg = MagicMock()
    mock_msg.messageType.return_value = "result"
    mock_msg.asElement.return_value = mock_elem

    rows = list(process._iter_bql_json_rows(mock_msg))

    # Should return 3 rows (one per value), not 1 merged row
    assert len(rows) == 3
    assert rows[0] == {"ID": "US Country", "eco_calendar": "GDP", "RELEASE_DATE": "2024-01-01"}
    assert rows[1] == {"ID": "US Country", "eco_calendar": "CPI", "RELEASE_DATE": "2024-01-15"}
    assert rows[2] == {"ID": "US Country", "eco_calendar": "NFP", "RELEASE_DATE": "2024-01-05"}


def test_iter_bql_json_rows_handles_rows_schema():
    """Test that BQL JSON parser handles rows schema as fallback."""
    import json
    from unittest.mock import MagicMock

    import blpapi

    json_payload = json.dumps({
        "results": {
            "data": {
                "rows": [
                    {"event_name": "GDP", "country": "US"},
                    {"event_name": "CPI", "country": "US"},
                ]
            }
        }
    })

    mock_elem = MagicMock()
    mock_elem.datatype.return_value = blpapi.DataType.STRING
    mock_elem.getValue.return_value = json_payload

    mock_msg = MagicMock()
    mock_msg.messageType.return_value = "result"
    mock_msg.asElement.return_value = mock_elem

    rows = list(process._iter_bql_json_rows(mock_msg))

    assert len(rows) == 2
    assert rows[0] == {"event_name": "GDP", "country": "US"}
    assert rows[1] == {"event_name": "CPI", "country": "US"}
