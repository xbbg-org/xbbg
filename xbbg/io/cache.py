"""Cache utilities for Bloomberg data (paths, adapters, lookup).

Provides path resolution, cache adapters, and cache lookup utilities
for Bloomberg intraday bar data and reference data (BDP/BDS).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from xbbg import const
from xbbg.core.config import overrides
from xbbg.core.domain import contracts
from xbbg.core.utils import utils
from xbbg.io import files
from xbbg.io.convert import is_empty, to_pandas

if TYPE_CHECKING:
    from xbbg.markets.bloomberg import ExchangeInfo

logger = logging.getLogger(__name__)

# Module-level flag to log default cache location only once
_default_cache_logged = False


# ============================================================================
# Path Resolution
# ============================================================================


def get_cache_root() -> str:
    """Get the cache root directory path.

    Returns BBG_ROOT if set, otherwise returns a platform-specific default cache location.
    Logs an INFO message once when default location is first used.

    Returns:
        str: Cache root directory path, or empty string if no cache location available.
    """
    global _default_cache_logged

    # Check if BBG_ROOT is explicitly set
    bbg_root = os.environ.get(overrides.BBG_ROOT, "")
    if bbg_root:
        return bbg_root

    # Use platform-specific default cache location
    try:
        home = Path.home()
    except RuntimeError:
        # Fallback if home directory cannot be determined
        # Use current directory as last resort
        home = Path.cwd()

    if sys.platform == "win32":
        # Windows: Use APPDATA if available, otherwise use user home
        appdata = os.environ.get("APPDATA", "")
        default_cache = Path(appdata) / "xbbg" if appdata else home / ".xbbg"
    else:
        # Linux/Mac: Use .cache directory if it exists, otherwise use .xbbg in home
        cache_dir = home / ".cache"
        default_cache = cache_dir / "xbbg" if cache_dir.exists() else home / ".xbbg"

    # Log once when default is first used
    if not _default_cache_logged:
        logger.info(
            "BBG_ROOT not set. Using default cache location: %s. "
            "Set BBG_ROOT environment variable to use a custom location.",
            default_cache,
        )
        _default_cache_logged = True

    return str(default_cache)


def bar_file(
    ticker: str,
    dt,
    typ: str = "TRADE",
    interval: int = 1,
    interval_has_seconds: bool = False,
) -> str:
    """Data file location for Bloomberg historical data.

    Args:
        ticker: ticker name
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        interval: bar interval (in minutes by default, or seconds if interval_has_seconds=True)
        interval_has_seconds: if True, interval is in seconds

    Returns:
        str: File location (uses default cache location if BBG_ROOT not set).

    Note:
        Cache path includes interval to avoid mixing data from different intervals.
        Format: {BBG_ROOT}/{asset}/{ticker}/{typ}/{interval_str}/{date}.parq
        where interval_str is e.g., "1m" for 1-minute bars or "10s" for 10-second bars.
    """
    data_path_str = get_cache_root()
    if not data_path_str:
        return ""
    data_path = Path(data_path_str)
    asset = ticker.split()[-1]
    proper_ticker = ticker.replace("/", "_")
    cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
    # Include interval in path to avoid cache collisions between different intervals
    interval_str = f"{interval}s" if interval_has_seconds else f"{interval}m"
    return (data_path / asset / proper_ticker / typ / interval_str / f"{cur_dt}.parq").as_posix()


def multi_day_bar_files(
    ticker: str,
    start_datetime: str | pd.Timestamp,
    end_datetime: str | pd.Timestamp,
    typ: str = "TRADE",
    interval: int = 1,
    interval_has_seconds: bool = False,
) -> list[tuple[str, str]]:
    """Get list of (date_str, file_path) tuples for a multi-day range.

    Args:
        ticker: Ticker name
        start_datetime: Start of range
        end_datetime: End of range
        typ: Event type
        interval: bar interval (in minutes by default, or seconds if interval_has_seconds=True)
        interval_has_seconds: if True, interval is in seconds

    Returns:
        List of (date_str, file_path) tuples for each day in range.
        Returns empty list if cache root is not available.
    """
    data_path_str = get_cache_root()
    if not data_path_str:
        return []

    start_dt = pd.Timestamp(start_datetime).normalize()
    end_dt = pd.Timestamp(end_datetime).normalize()

    dates = pd.date_range(start=start_dt, end=end_dt, freq="D")

    return [
        (
            dt.strftime("%Y-%m-%d"),
            bar_file(
                ticker=ticker,
                dt=dt,
                typ=typ,
                interval=interval,
                interval_has_seconds=interval_has_seconds,
            ),
        )
        for dt in dates
    ]


def ref_file(ticker: str, fld: str, has_date=False, cache=False, ext="parq", **kwargs) -> str:
    """Data file location for Bloomberg reference data.

    Args:
        ticker: ticker name
        fld: field
        has_date: whether add current date to data file
        cache: if has_date is True, whether to load file from latest cached
        ext: file extension
        **kwargs: other overrides passed to ref function

    Returns:
        str: File location or empty string if not cached.
    """
    if not cache:
        return ""
    data_path_str = get_cache_root()
    if not data_path_str:
        return ""
    data_path = Path(data_path_str)

    proper_ticker = ticker.replace("/", "_")
    cache_days = kwargs.pop("cache_days", 10)
    root = data_path / ticker.split()[-1] / proper_ticker / fld

    ref_kw = {k: v for k, v in kwargs.items() if k not in overrides.PRSV_COLS}
    info = utils.to_str(ref_kw)[1:-1].replace("|", "_") if len(ref_kw) > 0 else "ovrd=None"

    if has_date:
        cache_file = (root / f"asof=[cur_date], {info}.{ext}").as_posix()
        cur_dt = utils.cur_time()
        start_dt = pd.date_range(end=cur_dt, freq=f"{cache_days}D", periods=2)[0]
        for dt in pd.date_range(start=start_dt, end=cur_dt, normalize=True)[1:][::-1]:
            cur_file = cache_file.replace("[cur_date]", dt.strftime("%Y-%m-%d"))
            if files.exists(cur_file):
                return cur_file
        return cache_file.replace("[cur_date]", str(cur_dt))

    return (root / f"{info}.{ext}").as_posix()


def save_intraday(
    data: pd.DataFrame,
    ticker: str,
    dt,
    typ: str = "TRADE",
    interval: int = 1,
    interval_has_seconds: bool = False,
    **kwargs,
):
    """Check whether data is done for the day and save.

    Args:
        data: data
        ticker: ticker
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        interval: bar interval (in minutes by default, or seconds if interval_has_seconds=True)
        interval_has_seconds: if True, interval is in seconds
        **kwargs: Additional options forwarded to timing/logging helpers.
    """
    cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
    interval_str = f"{interval}s" if interval_has_seconds else f"{interval}m"
    info = f"{ticker} / {cur_dt} / {typ} / {interval_str}"
    data_file = bar_file(
        ticker=ticker,
        dt=dt,
        typ=typ,
        interval=interval,
        interval_has_seconds=interval_has_seconds,
    )
    if not data_file:
        return

    if data.empty:
        logger.warning("No data to save for %s (empty DataFrame)", info)
        return

    exch = const.exch_info(ticker=ticker, **kwargs)
    if exch.empty:
        return

    end_time = pd.Timestamp(const.market_timing(ticker=ticker, dt=dt, timing="FINISHED", **kwargs)).tz_localize(exch.tz)
    now = pd.Timestamp("now", tz=exch.tz) - pd.Timedelta("1h")

    if end_time > now:
        logger.debug(
            "Skipping save: market close time %s is less than 1 hour ago (%s), data may be incomplete", end_time, now
        )
        return

    if logger.isEnabledFor(logging.INFO):
        logger.info("Saving intraday data to cache: %s (%d rows)", data_file, len(data))
    else:
        logger.info("Saving intraday data to cache: %s", data_file)
    files.create_folder(data_file, is_file=True)
    # Use PyArrow for parquet I/O (backend-agnostic)
    table = pa.Table.from_pandas(data)
    pq.write_table(table, data_file)


# ============================================================================
# Cache Adapters
# ============================================================================


class BarCacheAdapter:
    """Cache adapter for intraday bar data (parquet-based)."""

    def load(
        self,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> pd.DataFrame | None:
        """Load cached bar data if available."""
        # Handle multi-day requests
        if request.is_multi_day():
            return self._load_multi_day(request)

        # Single-day request: require valid session window
        if not session_window.is_valid():
            return None

        data_file = bar_file(
            ticker=request.ticker,
            dt=request.dt,
            typ=request.event_type,
            interval=request.interval,
            interval_has_seconds=request.interval_has_seconds,
        )
        if not data_file:
            # BBG_ROOT not set - debug message logged in save() method if needed
            return None
        if not files.exists(data_file):
            return None

        try:
            from xbbg.utils import pipeline

            # Use PyArrow for parquet I/O, then convert to pandas for pipeline
            table = pq.read_table(data_file)
            res = (
                table.to_pandas()
                .pipe(pipeline.add_ticker, ticker=request.ticker)
                .loc[session_window.start_time : session_window.end_time]
            )

            if not res.empty:
                logger.debug("Loading cached Bloomberg intraday data from: %s", data_file)
                return res
        except Exception as e:
            logger.debug("Cache load failed: %s", e)

        return None

    def _load_multi_day(
        self,
        request: contracts.DataRequest,
    ) -> pd.DataFrame | None:
        """Load multi-day data from individual day caches.

        Returns concatenated DataFrame only if ALL days are cached.
        Returns None if any day is missing (triggers full Bloomberg fetch).

        Args:
            request: Data request with start_datetime and end_datetime.

        Returns:
            Concatenated DataFrame if all days cached, None otherwise.
        """
        from xbbg.utils import pipeline

        day_files = multi_day_bar_files(
            ticker=request.ticker,
            start_datetime=request.start_datetime,
            end_datetime=request.end_datetime,
            typ=request.event_type,
            interval=request.interval,
            interval_has_seconds=request.interval_has_seconds,
        )

        if not day_files:
            return None

        # Check if all files exist first (fail fast)
        missing_days = [dt for dt, path in day_files if not files.exists(path)]
        if missing_days:
            logger.debug(
                "Multi-day cache miss: %d of %d days missing for %s (first missing: %s)",
                len(missing_days),
                len(day_files),
                request.ticker,
                missing_days[:3],
            )
            return None

        # All files exist - load and concatenate
        dfs = []
        for _dt_str, path in day_files:
            try:
                # Use PyArrow for parquet I/O
                table = pq.read_table(path)
                df = table.to_pandas()
                dfs.append(df)
            except Exception as e:
                logger.debug("Failed to load cache file %s: %s", path, e)
                return None  # Fail entire load if any file is corrupt

        if not dfs:
            return None

        result = pd.concat(dfs, axis=0).sort_index().pipe(pipeline.add_ticker, ticker=request.ticker)

        # Filter to exact datetime range requested
        start_ts = pd.Timestamp(request.start_datetime)
        end_ts = pd.Timestamp(request.end_datetime)

        # Handle timezone: localize filter timestamps to match index timezone
        if result.index.tz is not None:
            start_ts = (
                start_ts.tz_localize(result.index.tz) if start_ts.tz is None else start_ts.tz_convert(result.index.tz)
            )
            end_ts = end_ts.tz_localize(result.index.tz) if end_ts.tz is None else end_ts.tz_convert(result.index.tz)

        result = result.loc[start_ts:end_ts]

        if not result.empty:
            logger.debug(
                "Multi-day cache hit: loaded %d rows from %d cached days for %s",
                len(result),
                len(day_files),
                request.ticker,
            )
            return result

        return None

    def save(
        self,
        data,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> None:
        """Save bar data to cache."""
        if is_empty(data):
            logger.warning("No data to save for %s / %s", request.ticker, request.to_date_string())
            return

        # Convert to pandas for cache storage (cache always uses parquet via pandas)
        data = to_pandas(data)

        # Handle multi-day requests: split and save each day separately
        if request.is_multi_day():
            self._save_multi_day(data, request)
            return

        # Get cache root (uses default if BBG_ROOT not set)
        data_path_str = get_cache_root()
        if not data_path_str:
            return

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        save_intraday(
            data=data[request.ticker] if request.ticker in data.columns else data,
            ticker=request.ticker,
            dt=request.dt,
            typ=request.event_type,
            interval=request.interval,
            interval_has_seconds=request.interval_has_seconds,
            **ctx_kwargs,
        )

    def _save_multi_day(
        self,
        data: pd.DataFrame,
        request: contracts.DataRequest,
    ) -> None:
        """Save multi-day data as individual day files.

        Splits the DataFrame by date and saves each day separately,
        allowing future single-day or multi-day requests to reuse the cache.

        Args:
            data: DataFrame with DatetimeIndex or "time" column containing multiple days.
            request: Original data request.
        """
        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Get the raw data (remove ticker level if MultiIndex columns)
        if (
            isinstance(data.columns, pd.MultiIndex) and request.ticker in data.columns.get_level_values(0)
        ) or request.ticker in data.columns:
            raw_data = data[request.ticker]
        else:
            raw_data = data

        # Handle long format data with RangeIndex and "time" column
        if isinstance(raw_data.index, pd.RangeIndex) and "time" in raw_data.columns:
            # Convert "time" column to datetime and extract date
            time_col = pd.to_datetime(raw_data["time"])
            date_col = time_col.dt.date

            # Group by date
            saved_count = 0
            for date in date_col.unique():
                day_mask = date_col == date
                day_data = raw_data[day_mask].copy()

                if is_empty(day_data):
                    continue

                # Convert to format expected by save_intraday (DatetimeIndex)
                day_data_indexed = day_data.set_index(pd.DatetimeIndex(pd.to_datetime(day_data["time"])))
                day_data_indexed = day_data_indexed.drop(columns=["time", "ticker"], errors="ignore")

                save_intraday(
                    data=day_data_indexed,
                    ticker=request.ticker,
                    dt=date,
                    typ=request.event_type,
                    interval=request.interval,
                    interval_has_seconds=request.interval_has_seconds,
                    **ctx_kwargs,
                )
                saved_count += 1
        else:
            # Standard format with DatetimeIndex
            grouped = raw_data.groupby(raw_data.index.date)  # type: ignore[union-attr]
            saved_count = 0

            for date, day_data in grouped:
                if is_empty(day_data):
                    continue

                # Use existing save_intraday which handles market timing checks
                save_intraday(
                    data=day_data,
                    ticker=request.ticker,
                    dt=date,
                    typ=request.event_type,
                    interval=request.interval,
                    interval_has_seconds=request.interval_has_seconds,
                    **ctx_kwargs,
                )
                saved_count += 1

        if saved_count > 0:
            logger.debug(
                "Saved multi-day data: %d days cached for %s",
                saved_count,
                request.ticker,
            )


class TickCacheAdapter:
    """Cache adapter for tick data (future implementation)."""

    def load(
        self,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> pd.DataFrame | None:
        """Load cached tick data (not implemented yet)."""
        return None

    def save(
        self,
        data: pd.DataFrame,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> None:
        """Save tick data (not implemented yet)."""
        ...


# ============================================================================
# Exchange Metadata Cache
# ============================================================================


def exchange_cache_file() -> str:
    """Return path to exchange metadata cache file.

    Returns:
        str: Path to exchanges.parquet file, or empty string if cache root unavailable.
    """
    root = get_cache_root()
    if not root:
        return ""
    return str(Path(root) / "cache" / "exchanges.parquet")


def save_exchange_info(info: ExchangeInfo) -> None:
    """Save single ExchangeInfo to cache (upsert by ticker).

    Args:
        info: ExchangeInfo dataclass to save.
    """
    save_exchange_infos([info])


def save_exchange_infos(infos: list[ExchangeInfo]) -> None:
    """Bulk save multiple ExchangeInfo entries.

    Performs upsert: existing entries with matching tickers are replaced,
    new entries are appended.

    Args:
        infos: List of ExchangeInfo dataclasses to save.
    """
    if not infos:
        return

    cache_file = exchange_cache_file()
    if not cache_file:
        logger.debug("Cache root not available, skipping exchange info save")
        return

    # Set cached_at timestamp for all entries
    now = datetime.now(timezone.utc)

    # Convert ExchangeInfo list to records
    new_records = []
    for info in infos:
        new_records.append(
            {
                "ticker": info.ticker,
                "mic": info.mic,
                "exch_code": info.exch_code,
                "timezone": info.timezone,
                "utc_offset": info.utc_offset,
                "sessions": json.dumps(info.sessions),
                "source": info.source,
                "cached_at": now,
            }
        )

    new_df = pd.DataFrame(new_records)
    new_tickers = set(new_df["ticker"].tolist())

    # Load existing cache and merge
    if files.exists(cache_file):
        try:
            existing_table = pq.read_table(cache_file)
            existing_df = existing_table.to_pandas()
            # Remove entries that will be replaced
            existing_df = existing_df[~existing_df["ticker"].isin(new_tickers)]
            # Concatenate
            merged_df = pd.concat([existing_df, new_df], ignore_index=True)
        except Exception as e:
            logger.warning("Failed to read existing exchange cache, overwriting: %s", e)
            merged_df = new_df
    else:
        merged_df = new_df

    # Ensure directory exists
    files.create_folder(cache_file, is_file=True)

    # Write to parquet
    table = pa.Table.from_pandas(merged_df, preserve_index=False)
    pq.write_table(table, cache_file)
    logger.debug("Saved %d exchange info entries to cache: %s", len(infos), cache_file)


def load_exchange_info(ticker: str, max_age_hours: float = 24.0) -> ExchangeInfo | None:
    """Load cached ExchangeInfo if exists and not stale.

    Args:
        ticker: Ticker symbol to look up.
        max_age_hours: Maximum age in hours before cache is considered stale.
            Use float('inf') to ignore staleness.

    Returns:
        ExchangeInfo if found and not stale, None otherwise.
    """
    from xbbg.markets.bloomberg import ExchangeInfo

    cache_file = exchange_cache_file()
    if not cache_file or not files.exists(cache_file):
        return None

    try:
        table = pq.read_table(cache_file)
        df = table.to_pandas()
    except Exception as e:
        logger.warning("Failed to read exchange cache: %s", e)
        return None

    if df.empty:
        return None

    # Filter by ticker
    matches = df[df["ticker"] == ticker]
    if matches.empty:
        return None

    row = matches.iloc[0]

    # Check staleness
    cached_at = row.get("cached_at")
    if cached_at is not None and max_age_hours != float("inf"):
        if pd.isna(cached_at):
            return None
        # Handle timezone-aware and naive timestamps
        if hasattr(cached_at, "tzinfo") and cached_at.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            cached_at = pd.Timestamp(cached_at).to_pydatetime()
            now = datetime.now(timezone.utc)
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age_hours = (now - cached_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            logger.debug("Exchange cache stale for %s (%.1f hours old)", ticker, age_hours)
            return None

    # Deserialize sessions from JSON
    sessions_str = row.get("sessions", "{}")
    try:
        sessions = json.loads(sessions_str) if sessions_str else {}
    except (json.JSONDecodeError, TypeError):
        sessions = {}

    # Convert sessions values to tuples
    sessions_dict: dict[str, tuple[str, str]] = {}
    for k, v in sessions.items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            sessions_dict[k] = (str(v[0]), str(v[1]))

    return ExchangeInfo(
        ticker=row["ticker"],
        mic=row.get("mic") if pd.notna(row.get("mic")) else None,
        exch_code=row.get("exch_code") if pd.notna(row.get("exch_code")) else None,
        timezone=row.get("timezone", "UTC"),
        utc_offset=float(row["utc_offset"]) if pd.notna(row.get("utc_offset")) else None,
        sessions=sessions_dict,
        source=row.get("source", "cache"),
        cached_at=_parse_cached_at(cached_at),
    )


def _parse_cached_at(cached_at: object) -> datetime | None:
    """Parse cached_at value to datetime, handling NaT and None."""
    if cached_at is None:
        return None
    try:
        if pd.isna(cached_at):  # type: ignore[arg-type]
            return None
        ts = pd.Timestamp(cached_at)  # type: ignore[arg-type]
        if pd.isna(ts):
            return None
        result = ts.to_pydatetime()
        # to_pydatetime can return NaT for NaT input
        if pd.isna(result):  # type: ignore[arg-type]
            return None
        return result  # type: ignore[return-value]
    except Exception:
        return None


def load_all_exchange_infos() -> dict[str, ExchangeInfo]:
    """Load all cached exchange infos as dict keyed by ticker.

    Returns:
        Dict mapping ticker to ExchangeInfo. Empty dict if cache unavailable.
    """
    from xbbg.markets.bloomberg import ExchangeInfo

    cache_file = exchange_cache_file()
    if not cache_file or not files.exists(cache_file):
        return {}

    try:
        table = pq.read_table(cache_file)
        df = table.to_pandas()
    except Exception as e:
        logger.warning("Failed to read exchange cache: %s", e)
        return {}

    if df.empty:
        return {}

    result: dict[str, ExchangeInfo] = {}
    for _, row in df.iterrows():
        ticker = row["ticker"]

        # Deserialize sessions from JSON
        sessions_str = row.get("sessions", "{}")
        try:
            sessions = json.loads(sessions_str) if sessions_str else {}
        except (json.JSONDecodeError, TypeError):
            sessions = {}

        # Convert sessions values to tuples
        sessions_dict: dict[str, tuple[str, str]] = {}
        for k, v in sessions.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                sessions_dict[k] = (str(v[0]), str(v[1]))

        cached_at = row.get("cached_at")
        result[ticker] = ExchangeInfo(
            ticker=ticker,
            mic=row.get("mic") if pd.notna(row.get("mic")) else None,
            exch_code=row.get("exch_code") if pd.notna(row.get("exch_code")) else None,
            timezone=row.get("timezone", "UTC"),
            utc_offset=float(row["utc_offset"]) if pd.notna(row.get("utc_offset")) else None,
            sessions=sessions_dict,
            source=row.get("source", "cache"),
            cached_at=_parse_cached_at(cached_at),
        )

    return result


def invalidate_exchange_cache(ticker: str | None = None) -> None:
    """Invalidate cache for ticker, or entire cache if ticker is None.

    Args:
        ticker: Ticker to invalidate. If None, invalidates entire cache.
    """
    cache_file = exchange_cache_file()
    if not cache_file:
        return

    if not files.exists(cache_file):
        return

    if ticker is None:
        # Delete entire cache file
        try:
            Path(cache_file).unlink()
            logger.info("Invalidated entire exchange cache: %s", cache_file)
        except Exception as e:
            logger.warning("Failed to delete exchange cache: %s", e)
        return

    # Remove specific ticker from cache
    try:
        table = pq.read_table(cache_file)
        df = table.to_pandas()
    except Exception as e:
        logger.warning("Failed to read exchange cache for invalidation: %s", e)
        return

    if df.empty:
        return

    original_len = len(df)
    df = df[df["ticker"] != ticker]

    if len(df) == original_len:
        logger.debug("Ticker %s not found in exchange cache", ticker)
        return

    if df.empty:
        # No entries left, delete file
        try:
            Path(cache_file).unlink()
            logger.info("Removed last entry, deleted exchange cache: %s", cache_file)
        except Exception as e:
            logger.warning("Failed to delete exchange cache: %s", e)
        return

    # Write updated cache
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, cache_file)
    logger.info("Invalidated exchange cache for ticker: %s", ticker)


# ============================================================================
# Cache Lookup
# ============================================================================
