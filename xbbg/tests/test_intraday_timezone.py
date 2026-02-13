"""Tests for bdib timezone conversion (IntradayTransformer).

Bloomberg IntradayBarRequest returns timestamps in UTC.  The transformer
should convert them to the exchange local timezone by default, matching
the behaviour of bdtick() and xbbg v0.7.x bdib().

These are pure unit tests — they exercise IntradayTransformer.transform()
directly with synthetic Arrow tables, so no Bloomberg connection is needed.
"""

from __future__ import annotations

import pandas as pd
import pyarrow as pa

from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.core.strategies.intraday import IntradayTransformer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_bar_table(n: int = 3, base: str = "2024-01-15 14:30:00") -> pa.Table:
    """Create a synthetic Arrow table mimicking Bloomberg IntradayBarRequest output.

    Timestamps are in UTC (as Bloomberg returns them).
    """
    times = pd.date_range(base, periods=n, freq="1min", tz="UTC")
    return pa.table(
        {
            "time": times.to_pydatetime().tolist(),
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": [1000 * (i + 1) for i in range(n)],
            "numEvents": [10 * (i + 1) for i in range(n)],
        }
    )


def _exchange_info(tz: str = "America/New_York") -> pd.Series:
    """Create a minimal exchange info Series."""
    return pd.Series({"tz": tz, "allday": ["04:00", "20:00"]}, name="XNGS")


def _request(ticker: str = "AAPL US Equity", tz: str | None = None) -> DataRequest:
    return DataRequest(ticker=ticker, dt="2024-01-15", tz=tz)


def _session_window() -> SessionWindow:
    return SessionWindow(
        start_time="2024-01-15T09:30:00",
        end_time="2024-01-15T16:00:00",
        session_name="day",
        timezone="America/New_York",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIntradayTransformerTimezone:
    """Verify that IntradayTransformer converts UTC → target timezone."""

    def test_default_converts_to_exchange_tz(self):
        """With tz=None (default), timestamps should be in exchange local tz."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(tz=None),
            exchange_info=_exchange_info("America/New_York"),
            session_window=_session_window(),
        )

        # Convert back to pandas to inspect timezone
        df = result.to_pandas()
        time_col = df["time"]
        assert time_col.dt.tz is not None, "Timestamps should be timezone-aware"
        assert str(time_col.dt.tz) == "America/New_York", f"Expected America/New_York, got {time_col.dt.tz}"

    def test_explicit_utc_keeps_utc(self):
        """With tz='UTC', timestamps should stay in UTC."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(tz="UTC"),
            exchange_info=_exchange_info("America/New_York"),
            session_window=_session_window(),
        )

        df = result.to_pandas()
        time_col = df["time"]
        assert time_col.dt.tz is not None
        assert str(time_col.dt.tz) == "UTC"

    def test_explicit_tokyo_converts(self):
        """With tz='Asia/Tokyo', timestamps should be in Tokyo time."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(base="2024-01-15 01:00:00"),
            request=_request(tz="Asia/Tokyo"),
            exchange_info=_exchange_info("America/New_York"),
            session_window=_session_window(),
        )

        df = result.to_pandas()
        time_col = df["time"]
        assert str(time_col.dt.tz) == "Asia/Tokyo"
        # 01:00 UTC = 10:00 JST
        assert time_col.iloc[0].hour == 10

    def test_tokyo_exchange_default(self):
        """Japanese equity with no explicit tz should get Asia/Tokyo."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(base="2024-01-15 01:00:00"),
            request=_request(ticker="7974 JT Equity", tz=None),
            exchange_info=_exchange_info("Asia/Tokyo"),
            session_window=_session_window(),
        )

        df = result.to_pandas()
        time_col = df["time"]
        assert str(time_col.dt.tz) == "Asia/Tokyo"
        assert time_col.iloc[0].hour == 10  # 01:00 UTC = 10:00 JST

    def test_empty_exchange_info_no_conversion(self):
        """If exchange info is empty and no explicit tz, data stays as-is."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(tz=None),
            exchange_info=pd.Series(dtype=object),
            session_window=_session_window(),
        )

        df = result.to_pandas()
        time_col = df["time"]
        # No conversion applied — stays in UTC (tz-aware from Bloomberg)
        assert str(time_col.dt.tz) == "UTC"

    def test_empty_table_returns_empty(self):
        """Empty input should return empty output without errors."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=pa.table({}),
            request=_request(),
            exchange_info=_exchange_info(),
            session_window=_session_window(),
        )

        assert result.num_rows == 0

    def test_num_events_renamed(self):
        """numEvents column should be renamed to num_trds."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(),
            exchange_info=_exchange_info(),
            session_window=_session_window(),
        )

        assert "num_trds" in result.column_names
        assert "numEvents" not in result.column_names

    def test_ticker_column_added(self):
        """Output should have a ticker column."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(ticker="SPY US Equity"),
            exchange_info=_exchange_info(),
            session_window=_session_window(),
        )

        assert "ticker" in result.column_names
        assert result.column("ticker").to_pylist() == ["SPY US Equity"] * 3

    def test_column_order(self):
        """Columns should be: ticker, time, then other fields."""
        transformer = IntradayTransformer()
        result = transformer.transform(
            raw_data=_utc_bar_table(),
            request=_request(),
            exchange_info=_exchange_info(),
            session_window=_session_window(),
        )

        assert result.column_names[0] == "ticker"
        assert result.column_names[1] == "time"


class TestDataRequestTz:
    """Verify tz field on DataRequest."""

    def test_default_tz_is_none(self):
        """DataRequest.tz should default to None."""
        req = DataRequest(ticker="X", dt="2024-01-01")
        assert req.tz is None

    def test_explicit_tz(self):
        """DataRequest.tz can be set explicitly."""
        req = DataRequest(ticker="X", dt="2024-01-01", tz="UTC")
        assert req.tz == "UTC"

    def test_request_builder_tz(self):
        """RequestBuilder should propagate tz."""
        from xbbg.core.request_builder import RequestBuilder

        req = RequestBuilder.from_legacy_kwargs(
            ticker="AAPL US Equity",
            dt="2024-01-15",
            tz="Asia/Tokyo",
        )
        assert req.tz == "Asia/Tokyo"

    def test_request_builder_tz_none_default(self):
        """RequestBuilder should default tz to None."""
        from xbbg.core.request_builder import RequestBuilder

        req = RequestBuilder.from_legacy_kwargs(
            ticker="AAPL US Equity",
            dt="2024-01-15",
        )
        assert req.tz is None
