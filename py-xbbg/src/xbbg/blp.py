"""High-level Bloomberg data API: reference, historical, intraday.

This module provides the xbbg-compatible API using the Rust backend.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "bdp",
    "bds",
    "bdh",
    "bdib",
    "bdtick",
]

# Lazy-load the engine to avoid import errors when the Rust module isn't built
_engine = None


def _get_engine():
    """Get or create the shared engine instance."""
    global _engine
    if _engine is None:
        from . import _core

        _engine = _core.PyEngine()
    return _engine


def _normalize_tickers(tickers: str | Sequence[str]) -> list[str]:
    """Normalize ticker input to a list of strings."""
    if isinstance(tickers, str):
        return [tickers]
    return list(tickers)


def _normalize_fields(fields: str | Sequence[str] | None) -> list[str]:
    """Normalize field input to a list of strings."""
    if fields is None:
        return ["PX_LAST"]
    if isinstance(fields, str):
        return [fields]
    return list(fields)


def _extract_overrides(kwargs: dict) -> list[tuple[str, str]]:
    """Extract Bloomberg overrides from kwargs.

    Overrides can be passed as:
    - Individual kwargs (e.g., GICS_SECTOR_NAME='Energy')
    - An 'overrides' dict

    Returns list of (name, value) tuples.
    """
    overrides = []

    # Check for explicit overrides dict
    if "overrides" in kwargs:
        ovrd = kwargs.pop("overrides")
        if isinstance(ovrd, dict):
            overrides.extend((k, str(v)) for k, v in ovrd.items())
        elif isinstance(ovrd, list):
            overrides.extend((str(k), str(v)) for k, v in ovrd)

    # Known infrastructure keys to skip
    infra_keys = {
        "cache",
        "reload",
        "raw",
        "timeout",
        "host",
        "port",
        "log",
        "batch",
        "session",
        "interval",
        "typ",
        "adjust",
        "wide",
    }

    # Treat remaining kwargs as potential overrides
    for key in list(kwargs.keys()):
        if key not in infra_keys:
            val = kwargs.pop(key)
            overrides.append((key, str(val)))

    return overrides


def _arrow_to_pandas(table: pa.Table) -> pd.DataFrame:
    """Convert PyArrow table to pandas DataFrame."""
    return table.to_pandas()


def _fmt_date(dt: str | pd.Timestamp | None, fmt: str = "%Y%m%d") -> str:
    """Format date to string."""
    if dt is None:
        return pd.Timestamp.now().strftime(fmt)
    if isinstance(dt, str):
        if dt.lower() == "today":
            return pd.Timestamp.now().strftime(fmt)
        # Try to parse and reformat
        try:
            return pd.Timestamp(dt).strftime(fmt)
        except (ValueError, TypeError):
            return dt
    return dt.strftime(fmt)


def bdp(
    tickers: str | Sequence[str],
    flds: str | Sequence[str],
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg reference data (BDP).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        **kwargs: Bloomberg overrides and infrastructure options.
            wide: If True, return wide format with one column per field.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.

    Examples:
        >>> bdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
        >>> bdp(['AAPL US Equity', 'MSFT US Equity'], 'PX_LAST')
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)
    wide = kwargs.pop("wide", True)  # Default to wide format for bdp
    overrides = _extract_overrides(kwargs)

    table = engine.bdp(ticker_list, field_list, overrides, wide)
    df = _arrow_to_pandas(table)

    # Set ticker as index if wide format
    if wide and "ticker" in df.columns:
        df = df.set_index("ticker")

    return df


def bds(
    tickers: str | Sequence[str],
    flds: str,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg bulk data (BDS).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field name (bulk fields return multiple rows).
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        pd.DataFrame: Bulk data with multiple rows per ticker.

    Examples:
        >>> bds('AAPL US Equity', 'DVD_Hist_All')
        >>> bds('SPX Index', 'INDX_MEMBERS')
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    overrides = _extract_overrides(kwargs)

    # Process each ticker
    results = []
    for ticker in ticker_list:
        table = engine.bds(ticker, flds, overrides)
        df = _arrow_to_pandas(table)
        if not df.empty:
            df.insert(0, "ticker", ticker)
            results.append(df)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)


def bdh(
    tickers: str | Sequence[str],
    flds: str | Sequence[str] | None = None,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp = "today",
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg historical data (BDH).

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields. Defaults to ['PX_LAST'].
        start_date: Start date. Defaults to 8 weeks before end_date.
        end_date: End date. Defaults to 'today'.
        **kwargs: Additional overrides and infrastructure options.
            adjust: Adjustment type ('all', 'dvd', 'split', '-', None).

    Returns:
        pd.DataFrame: Historical data with dates as index.

    Examples:
        >>> bdh('AAPL US Equity', 'PX_LAST', start_date='2024-01-01')
        >>> bdh(['AAPL US Equity', 'MSFT US Equity'], ['PX_LAST', 'VOLUME'])
    """
    engine = _get_engine()
    ticker_list = _normalize_tickers(tickers)
    field_list = _normalize_fields(flds)

    # Handle dates
    e_dt = _fmt_date(end_date, "%Y%m%d")
    if start_date is None:
        s_dt = (pd.Timestamp(e_dt) - pd.Timedelta(weeks=8)).strftime("%Y%m%d")
    else:
        s_dt = _fmt_date(start_date, "%Y%m%d")

    # Extract options
    options = []
    adjust = kwargs.pop("adjust", None)
    if adjust:
        if adjust == "all":
            options.append(("adjustmentSplit", "true"))
            options.append(("adjustmentNormal", "true"))
            options.append(("adjustmentAbnormal", "true"))
        elif adjust == "dvd":
            options.append(("adjustmentNormal", "true"))
            options.append(("adjustmentAbnormal", "true"))
        elif adjust == "split":
            options.append(("adjustmentSplit", "true"))
        elif adjust == "-":
            pass  # No adjustments

    # Add any remaining overrides as options
    overrides = _extract_overrides(kwargs)
    options.extend(overrides)

    table = engine.bdh(ticker_list, field_list, s_dt, e_dt, options)
    df = _arrow_to_pandas(table)

    # Convert date column to datetime index
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

    # Pivot to multi-index columns if multiple tickers
    if "ticker" in df.columns and len(ticker_list) > 1:
        df = df.pivot_table(index=df.index, columns="ticker", values=field_list)

    return df


def bdib(
    ticker: str,
    dt: str | pd.Timestamp | None = None,
    session: str = "allday",
    typ: str = "TRADE",
    start_datetime: str | pd.Timestamp | None = None,
    end_datetime: str | pd.Timestamp | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg intraday bar data (BDIB).

    Args:
        ticker: Ticker name.
        dt: Date to download (for single-day requests).
        session: Trading session name. Ignored when start_datetime/end_datetime provided.
        typ: Event type (TRADE, BID, ASK, etc.).
        start_datetime: Explicit start datetime for multi-day requests.
        end_datetime: Explicit end datetime for multi-day requests.
        **kwargs:
            interval: Bar interval in minutes (default: 1).

    Returns:
        pd.DataFrame: Intraday bar data with time as index.

    Examples:
        >>> bdib('AAPL US Equity', dt='2024-12-01')
        >>> bdib('AAPL US Equity', start_datetime='2024-12-01 09:30',
        ...      end_datetime='2024-12-01 16:00', interval=5)
    """
    engine = _get_engine()
    interval = kwargs.pop("interval", 1)

    # Determine datetime range
    if start_datetime is not None and end_datetime is not None:
        s_dt = pd.Timestamp(start_datetime).isoformat()
        e_dt = pd.Timestamp(end_datetime).isoformat()
    elif dt is not None:
        # Single day request - use full day
        cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
        s_dt = f"{cur_dt}T00:00:00"
        e_dt = f"{cur_dt}T23:59:59"
    else:
        raise ValueError("Either dt or both start_datetime and end_datetime must be provided")

    table = engine.bdib(ticker, typ, interval, s_dt, e_dt)
    df = _arrow_to_pandas(table)

    # Convert timestamp to datetime index
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

    return df


def bdtick(
    ticker: str,
    start_datetime: str | pd.Timestamp,
    end_datetime: str | pd.Timestamp,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg tick data (BDTICK).

    Args:
        ticker: Ticker name.
        start_datetime: Start datetime.
        end_datetime: End datetime.
        **kwargs: Additional options.

    Returns:
        pd.DataFrame: Tick data with time as index.

    Examples:
        >>> bdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00')
    """
    engine = _get_engine()

    s_dt = pd.Timestamp(start_datetime).isoformat()
    e_dt = pd.Timestamp(end_datetime).isoformat()

    table = engine.bdtick(ticker, s_dt, e_dt)
    df = _arrow_to_pandas(table)

    # Convert timestamp to datetime index
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

    return df
