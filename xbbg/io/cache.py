"""Cache utilities for Bloomberg data (paths, adapters, lookup).

Provides path resolution, cache adapters, and cache lookup utilities
for Bloomberg intraday bar data and reference data (BDP/BDS).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pandas as pd

from xbbg import const
from xbbg.core.config import overrides
from xbbg.core.domain import contracts
from xbbg.core.utils import utils
from xbbg.io import files

if TYPE_CHECKING:
    pass

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


def bar_file(ticker: str, dt, typ="TRADE") -> str:
    """Data file location for Bloomberg historical data.

    Args:
        ticker: ticker name
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]

    Returns:
        str: File location (uses default cache location if BBG_ROOT not set).
    """
    data_path_str = get_cache_root()
    if not data_path_str:
        return ""
    data_path = Path(data_path_str)
    asset = ticker.split()[-1]
    proper_ticker = ticker.replace("/", "_")
    cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
    return (data_path / asset / proper_ticker / typ / f"{cur_dt}.parq").as_posix()


def multi_day_bar_files(
    ticker: str,
    start_datetime: str | pd.Timestamp,
    end_datetime: str | pd.Timestamp,
    typ: str = "TRADE",
) -> list[tuple[str, str]]:
    """Get list of (date_str, file_path) tuples for a multi-day range.

    Args:
        ticker: Ticker name
        start_datetime: Start of range
        end_datetime: End of range
        typ: Event type

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

    return [(dt.strftime("%Y-%m-%d"), bar_file(ticker=ticker, dt=dt, typ=typ)) for dt in dates]


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


def save_intraday(data: pd.DataFrame, ticker: str, dt, typ="TRADE", **kwargs):
    """Check whether data is done for the day and save.

    Args:
        data: data
        ticker: ticker
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        **kwargs: Additional options forwarded to timing/logging helpers.
    """
    cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
    info = f"{ticker} / {cur_dt} / {typ}"
    data_file = bar_file(ticker=ticker, dt=dt, typ=typ)
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
    data.to_parquet(data_file)


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

        data_file = bar_file(ticker=request.ticker, dt=request.dt, typ=request.event_type)
        if not data_file:
            # BBG_ROOT not set - debug message logged in save() method if needed
            return None
        if not files.exists(data_file):
            return None

        try:
            from xbbg.utils import pipeline

            res = (
                pd.read_parquet(data_file)
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
                df = pd.read_parquet(path)
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
        data: pd.DataFrame,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> None:
        """Save bar data to cache."""
        if data.empty:
            logger.warning("No data to save for %s / %s", request.ticker, request.to_date_string())
            return

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
            data: DataFrame with DatetimeIndex containing multiple days.
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

        # Group by date and save each day
        grouped = raw_data.groupby(raw_data.index.date)
        saved_count = 0

        for date, day_data in grouped:
            if day_data.empty:
                continue

            # Use existing save_intraday which handles market timing checks
            save_intraday(
                data=day_data,
                ticker=request.ticker,
                dt=date,
                typ=request.event_type,
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
# Cache Lookup
# ============================================================================
