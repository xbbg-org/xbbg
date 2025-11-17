"""Helpers to track and persist retries (trials) for missing data.

Utilities include reading existing logs, normalizing trial metadata,
counting and updating attempt counters, and writing per-query log files.
"""

from collections.abc import Iterator
import os
from pathlib import Path

from xbbg.core.config.overrides import BBG_ROOT
from xbbg.core.utils import utils
from xbbg.io import db, files

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


def root_path() -> Path:
    """Root data path of Bloomberg."""
    return Path(os.environ.get(BBG_ROOT, ''))


def all_trials() -> Iterator[dict]:
    """Yield all missing logs.

    Yields:
        dict: Trial metadata records for backfilling the database.
    """
    data_path = root_path()
    if data_path.as_posix():
        for sub1 in files.all_folders(str(data_path / 'Logs' / 'bdib')):
            for sub2 in files.all_folders(sub1, has_date=True):
                for sub3 in files.all_folders(sub2):
                    cnt = len(files.all_files(sub3, ext='log'))
                    if cnt:
                        yield {
                            'func': 'bdib',
                            'ticker': Path(sub1).name,
                            'dt': Path(sub2).name,
                            'typ': Path(sub3).name,
                            'cnt': cnt,
                        }


def trail_info(**kwargs) -> dict:
    """Convert trial info to a normalized format for the database.

    Returns:
        dict: Normalized key/value pairs for storage.
    """
    kwargs['func'] = kwargs.pop('func', 'unknown')
    if 'ticker' in kwargs:
        kwargs['ticker'] = kwargs['ticker'].replace('/', '_')
    for dt in ['dt', 'start_dt', 'end_dt', 'start_date', 'end_date']:
        if dt not in kwargs: continue
        kwargs[dt] = utils.fmt_dt(kwargs[dt])
    return kwargs


def missing_info(**kwargs) -> str:
    """Full information path fragment for a missing query."""
    func = kwargs.pop('func', 'unknown')
    if 'ticker' in kwargs: kwargs['ticker'] = kwargs['ticker'].replace('/', '_')
    for dt in ['dt', 'start_dt', 'end_dt', 'start_date', 'end_date']:
        if dt not in kwargs: continue
        kwargs[dt] = utils.fmt_dt(kwargs[dt])
    info = utils.to_str(kwargs, fmt='{value}', sep='/')[1:-1]
    return f'{func}/{info}'  # Path fragment, not a file path


def num_trials(**kwargs) -> int:
    """Check number of trials for missing values.

    Returns:
        int: Number of trials already tried.
    """
    data_path = root_path()
    if not data_path.as_posix(): return 0

    db_file = str(data_path / 'Logs' / 'xbbg.db')
    files.create_folder(db_file, is_file=True)
    with db.SQLite(db_file) as con:
        con.execute(TRIALS_TABLE)
        num = con.execute(db.select(
            table='trials',
            **trail_info(**kwargs),
        )).fetchall()
        if not num: return 0
        return num[0][-1]


def update_trials(**kwargs):
    """Update number of trials for missing values."""
    data_path = root_path()
    if not data_path.as_posix(): return

    if 'cnt' not in kwargs:
        kwargs['cnt'] = num_trials(**kwargs) + 1

    db_file = str(data_path / 'Logs' / 'xbbg.db')
    files.create_folder(db_file, is_file=True)
    with db.SQLite(db_file) as con:
        con.execute(TRIALS_TABLE)
        con.execute(db.replace_into(
            table='trials',
            **trail_info(**kwargs),
        ))


def current_missing(**kwargs) -> int:
    """Check number of trials for missing values.

    Returns:
        int: Number of trials already tried.
    """
    data_path = root_path()
    if not data_path.as_posix(): return 0
    return len(files.all_files(str(data_path / 'Logs' / missing_info(**kwargs))))


def update_missing(**kwargs):
    """Update number of trials for missing values."""
    data_path = root_path()
    if not data_path.as_posix(): return
    if len(kwargs) == 0: return

    log_path = data_path / 'Logs' / missing_info(**kwargs)

    cnt = len(files.all_files(str(log_path))) + 1
    files.create_folder(str(log_path))
    (log_path / f'{cnt}.log').touch()
