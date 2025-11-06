import pandas as pd
import pytest

from xbbg import blp
from xbbg.core import process, conn


@pytest.fixture
def fake_handle():
    return {"event_queue": object(), "correlation_id": object()}


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


