import os

import pandas as pd

from xbbg.api import intraday
from xbbg.core.infra import conn
from xbbg.io import param


def test_bdib_uses_cached_parquet_when_available(monkeypatch):
    """bdib should load from cached intraday parquet and avoid live Bloomberg calls."""
    data_root = os.path.join(param.PKG_PATH, "tests", "data")
    monkeypatch.setenv("BBG_ROOT", data_root)

    def _fail(*args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("send_request should not be called when cache file exists")

    monkeypatch.setattr(conn, "send_request", _fail)

    df = intraday.bdib(
        ticker="AAPL US Equity",
        dt="2018-11-02",
        session="allday",
        typ="TRADE",
        cache=True,
        reload=False,
    )

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    # bdib returns MultiIndex columns with ticker as first level
    assert "AAPL US Equity" in df.columns.get_level_values(0)
