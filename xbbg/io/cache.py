"""Cache utilities for Bloomberg data (paths, adapters, lookup).

Provides path resolution, cache adapters, and cache lookup utilities
for Bloomberg intraday bar data and reference data (BDP/BDS).

Cache Structure:
    ~/.xbbg/
    ├── metadata.json                  # Root cache metadata
    ├── intraday/                      # Intraday bar data (bdib)
    │   └── {asset_class}/
    │       └── {ticker}/
    │           └── {event_type}/
    │               └── {interval}/    # e.g., "1m", "5m", "10s"
    │                   └── {date}.parq
    ├── tick/                          # Tick data (bdtick)
    │   └── {asset_class}/
    │       └── {ticker}/
    │           └── {date}.parq
    ├── reference/                     # Reference data (bdp/bds)
    │   └── {asset_class}/
    │       └── {ticker}/
    │           └── {field}/
    │               └── {overrides_hash}.parq
    └── technical/                     # Technical analysis schema
        └── studies.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import platform
import sys
from typing import TYPE_CHECKING, Any

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
    pass

logger = logging.getLogger(__name__)

# Current cache schema version - increment when structure changes
CACHE_SCHEMA_VERSION = 1

# Module-level flag to log default cache location only once
_default_cache_logged = False

# Module-level cache for metadata (avoid reading file repeatedly)
_metadata_cache: dict[str, Any] | None = None


# ============================================================================
# Path Resolution
# ============================================================================


def get_cache_root() -> str:
    """Get the cache root directory path.

    Returns BBG_ROOT if set, otherwise returns ~/.xbbg consistently across platforms.
    Logs an INFO message once when default location is first used.

    Returns:
        str: Cache root directory path, or empty string if no cache location available.
    """
    global _default_cache_logged

    # Check if BBG_ROOT is explicitly set
    bbg_root = os.environ.get(overrides.BBG_ROOT, "")
    if bbg_root:
        return bbg_root

    # Use consistent ~/.xbbg across all platforms
    try:
        home = Path.home()
    except RuntimeError:
        # Fallback if home directory cannot be determined
        home = Path.cwd()

    default_cache = home / ".xbbg"

    # Log once when default is first used
    if not _default_cache_logged:
        logger.info(
            "BBG_ROOT not set. Using default cache location: %s. "
            "Set BBG_ROOT environment variable to use a custom location.",
            default_cache,
        )
        _default_cache_logged = True

    return str(default_cache)


# ============================================================================
# Cache Metadata
# ============================================================================


def _get_xbbg_version() -> str:
    """Get current xbbg version."""
    try:
        from xbbg import __version__

        return __version__
    except Exception:
        return "unknown"


def _get_metadata_path() -> Path:
    """Get path to metadata.json file."""
    cache_root = get_cache_root()
    if not cache_root:
        return Path()
    return Path(cache_root) / "metadata.json"


def read_cache_metadata() -> dict[str, Any]:
    """Read cache metadata from metadata.json.

    Returns:
        dict: Metadata dictionary, or empty dict if file doesn't exist.
    """
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    metadata_path = _get_metadata_path()
    if not metadata_path or not metadata_path.exists():
        return {}

    try:
        with open(metadata_path, encoding="utf-8") as f:
            _metadata_cache = json.load(f)
            return _metadata_cache
    except Exception as e:
        logger.debug("Failed to read cache metadata: %s", e)
        return {}


def write_cache_metadata(metadata: dict[str, Any]) -> None:
    """Write cache metadata to metadata.json.

    Args:
        metadata: Metadata dictionary to write.
    """
    global _metadata_cache
    metadata_path = _get_metadata_path()
    if not metadata_path:
        return

    try:
        files.create_folder(str(metadata_path), is_file=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        _metadata_cache = metadata
    except Exception as e:
        logger.warning("Failed to write cache metadata: %s", e)


def ensure_cache_metadata() -> dict[str, Any]:
    """Ensure cache metadata exists, creating if necessary.

    Creates metadata.json with current schema version if it doesn't exist.
    Logs a warning if existing schema version differs from current.

    Returns:
        dict: Current metadata.
    """
    metadata = read_cache_metadata()

    if not metadata:
        # Create new metadata
        metadata = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "xbbg_version": _get_xbbg_version(),
            "python_version": platform.python_version(),
            "platform": sys.platform,
        }
        write_cache_metadata(metadata)
        logger.info("Created cache metadata at %s", _get_metadata_path())
    elif metadata.get("schema_version") != CACHE_SCHEMA_VERSION:
        existing_version = metadata.get("schema_version", "unknown")
        logger.warning(
            "Cache schema version mismatch: found %s, expected %s. Cache may need migration or clearing.",
            existing_version,
            CACHE_SCHEMA_VERSION,
        )

    return metadata


def get_cache_info() -> dict[str, Any]:
    """Get cache information including metadata and statistics.

    Returns:
        dict: Cache info with metadata, paths, and basic stats.
    """
    cache_root = get_cache_root()
    metadata = read_cache_metadata()

    info = {
        "cache_root": cache_root,
        "metadata": metadata,
        "exists": Path(cache_root).exists() if cache_root else False,
    }

    if info["exists"]:
        # Add directory sizes if cache exists
        root_path = Path(cache_root)
        info["directories"] = {}
        for subdir in ["intraday", "tick", "reference", "technical"]:
            subdir_path = root_path / subdir
            if subdir_path.exists():
                info["directories"][subdir] = True

    return info


# ============================================================================
# Parquet Metadata Helpers
# ============================================================================


def build_parquet_metadata(
    ticker: str,
    data_type: str,
    *,
    interval: int | None = None,
    interval_has_seconds: bool = False,
    event_type: str | None = None,
    field: str | None = None,
    overrides_dict: dict | None = None,
    timezone_str: str | None = None,
) -> dict[str, str]:
    """Build metadata dictionary for embedding in parquet files.

    Args:
        ticker: Bloomberg ticker.
        data_type: Type of data (intraday, tick, reference, historical).
        interval: Bar interval (for intraday data).
        interval_has_seconds: Whether interval is in seconds.
        event_type: Event type (TRADE, BID, ASK, etc.).
        field: Bloomberg field name (for reference data).
        overrides_dict: Override parameters used in request.
        timezone_str: Timezone of the data.

    Returns:
        dict: Metadata dictionary with 'xbbg.' prefix on all keys.
    """
    meta = {
        "xbbg.fetched_at": datetime.now(timezone.utc).isoformat(),
        "xbbg.ticker": ticker,
        "xbbg.data_type": data_type,
        "xbbg.version": _get_xbbg_version(),
    }

    if interval is not None:
        interval_str = f"{interval}s" if interval_has_seconds else f"{interval}m"
        meta["xbbg.interval"] = interval_str

    if event_type:
        meta["xbbg.event_type"] = event_type

    if field:
        meta["xbbg.field"] = field

    if overrides_dict:
        meta["xbbg.overrides"] = json.dumps(overrides_dict)

    if timezone_str:
        meta["xbbg.timezone"] = timezone_str

    return meta


def write_parquet_with_metadata(
    table: pa.Table,
    path: str,
    metadata: dict[str, str],
) -> None:
    """Write parquet file with custom metadata.

    Args:
        table: PyArrow table to write.
        path: Output file path.
        metadata: Custom metadata to embed.
    """
    # Merge with existing schema metadata
    existing_meta = table.schema.metadata or {}
    combined_meta = {**existing_meta, **{k.encode(): v.encode() for k, v in metadata.items()}}

    # Replace schema with updated metadata
    new_schema = table.schema.with_metadata(combined_meta)
    table = table.cast(new_schema)

    pq.write_table(table, path)


def read_parquet_metadata(path: str) -> dict[str, str]:
    """Read xbbg metadata from a parquet file.

    Args:
        path: Path to parquet file.

    Returns:
        dict: Metadata dictionary with xbbg.* keys (without prefix).
    """
    try:
        pf = pq.ParquetFile(path)
        schema_meta = pf.schema.to_arrow_schema().metadata or {}
        return {
            k.decode().replace("xbbg.", ""): v.decode()
            for k, v in schema_meta.items()
            if k.decode().startswith("xbbg.")
        }
    except Exception as e:
        logger.debug("Failed to read parquet metadata from %s: %s", path, e)
        return {}


# ============================================================================
# Override Hashing
# ============================================================================


def hash_overrides(overrides_dict: dict | None) -> str:
    """Create a short hash of override parameters for use in filenames.

    Args:
        overrides_dict: Dictionary of override parameters, or None.

    Returns:
        str: Short hash string (8 chars) or "default" if no overrides.
    """
    if not overrides_dict:
        return "default"

    # Sort keys for consistent hashing
    sorted_items = sorted(overrides_dict.items())
    content = json.dumps(sorted_items, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def bar_file(
    ticker: str,
    dt,
    typ: str = "TRADE",
    interval: int = 1,
    interval_has_seconds: bool = False,
) -> str:
    """Data file location for Bloomberg intraday bar data.

    Args:
        ticker: ticker name
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        interval: bar interval (in minutes by default, or seconds if interval_has_seconds=True)
        interval_has_seconds: if True, interval is in seconds

    Returns:
        str: File location (uses default cache location if BBG_ROOT not set).

    Note:
        Cache path structure:
        {cache_root}/intraday/{asset}/{ticker}/{typ}/{interval_str}/{date}.parq
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
    return (data_path / "intraday" / asset / proper_ticker / typ / interval_str / f"{cur_dt}.parq").as_posix()


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

    Note:
        Cache path structure:
        {cache_root}/reference/{asset}/{ticker}/{field}/{overrides_hash}.parq
    """
    if not cache:
        return ""
    data_path_str = get_cache_root()
    if not data_path_str:
        return ""
    data_path = Path(data_path_str)

    asset = ticker.split()[-1]
    proper_ticker = ticker.replace("/", "_")
    cache_days = kwargs.pop("cache_days", 10)
    root = data_path / "reference" / asset / proper_ticker / fld

    ref_kw = {k: v for k, v in kwargs.items() if k not in overrides.PRSV_COLS}
    override_hash = hash_overrides(ref_kw)

    if has_date:
        cache_file = (root / f"asof=[cur_date]_{override_hash}.{ext}").as_posix()
        cur_dt = utils.cur_time()
        start_dt = pd.date_range(end=cur_dt, freq=f"{cache_days}D", periods=2)[0]
        for dt in pd.date_range(start=start_dt, end=cur_dt, normalize=True)[1:][::-1]:
            cur_file = cache_file.replace("[cur_date]", dt.strftime("%Y-%m-%d"))
            if files.exists(cur_file):
                return cur_file
        return cache_file.replace("[cur_date]", str(cur_dt))

    return (root / f"{override_hash}.{ext}").as_posix()


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

    # Ensure cache metadata exists
    ensure_cache_metadata()

    files.create_folder(data_file, is_file=True)

    # Build parquet metadata
    tz_str = str(exch.tz) if exch.tz else None
    parquet_meta = build_parquet_metadata(
        ticker=ticker,
        data_type="intraday",
        interval=interval,
        interval_has_seconds=interval_has_seconds,
        event_type=typ,
        timezone_str=tz_str,
    )

    # Use PyArrow for parquet I/O with embedded metadata
    table = pa.Table.from_pandas(data)
    write_parquet_with_metadata(table, data_file, parquet_meta)


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
# Cache Lookup
# ============================================================================
