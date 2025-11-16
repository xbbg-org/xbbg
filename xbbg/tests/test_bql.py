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


