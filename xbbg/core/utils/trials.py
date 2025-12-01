"""Helpers to track and persist retries (trials) for missing data.

Utilities for tracking retry attempts when Bloomberg data queries return empty results.
Uses SQLite database for efficient storage and retrieval of trial counts.
"""

from pathlib import Path
import sqlite3
import time

from xbbg.core.utils import utils
from xbbg.io import db, files
from xbbg.io.cache import get_cache_root

# Retry settings for SQLite database locking (common on Windows)
MAX_RETRIES = 3
RETRY_DELAY = 0.1  # seconds

TRIALS_TABLE = """
    CREATE TABLE IF NOT EXISTS trials (
        func varchar(20),
        ticker varchar(30),
        dt varchar(10),
        typ varchar(20),
        cnt int,
        PRIMARY KEY (func, ticker, dt, typ)
    )
"""


def _get_db_path() -> Path | None:
    """Get the path to the trials database file.

    Returns:
        Path to database file, or None if cache root is not available.
    """
    cache_root = get_cache_root()
    if not cache_root:
        return None
    data_path = Path(cache_root)
    # Store database directly in cache root, not in a subfolder
    return data_path / "xbbg_trials.db"


def _trial_info(**kwargs) -> dict:
    """Convert trial info to a normalized format for the database.

    Returns:
        dict: Normalized key/value pairs for storage.
    """
    kwargs["func"] = kwargs.pop("func", "unknown")
    if "ticker" in kwargs:
        kwargs["ticker"] = kwargs["ticker"].replace("/", "_")
    for dt in ["dt", "start_dt", "end_dt", "start_date", "end_date"]:
        if dt not in kwargs:
            continue
        kwargs[dt] = utils.fmt_dt(kwargs[dt])
    return kwargs


def num_trials(**kwargs) -> int:
    """Check number of trials for missing values.

    Args:
        **kwargs: Trial parameters (func, ticker, dt, typ, etc.)

    Returns:
        int: Number of trials already tried, or 0 if not found or cache unavailable.
    """
    db_file = _get_db_path()
    if db_file is None:
        return 0

    files.create_folder(str(db_file), is_file=True)

    for attempt in range(MAX_RETRIES):
        try:
            with db.SQLite(str(db_file)) as con:
                con.execute(TRIALS_TABLE)
                num = con.execute(
                    db.select(
                        table="trials",
                        **_trial_info(**kwargs),
                    )
                ).fetchall()
                if not num:
                    return 0
                return num[0][-1]
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
    return 0


def update_trials(**kwargs):
    """Update number of trials for missing values.

    Args:
        **kwargs: Trial parameters (func, ticker, dt, typ, cnt, etc.)
            If 'cnt' is not provided, it will be auto-incremented.
    """
    db_file = _get_db_path()
    if db_file is None:
        return

    if "cnt" not in kwargs:
        kwargs["cnt"] = num_trials(**kwargs) + 1

    files.create_folder(str(db_file), is_file=True)

    for attempt in range(MAX_RETRIES):
        try:
            with db.SQLite(str(db_file)) as con:
                con.execute(TRIALS_TABLE)
                con.execute(
                    db.replace_into(
                        table="trials",
                        **_trial_info(**kwargs),
                    )
                )
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
