"""Filesystem helpers for paths, folders, and file discovery.

Functions include existence checks, absolute path resolution, folder
creation, file/folder listing with filters, and utility getters.
"""

import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

DATE_FMT = r"\d{4}-(0?[1-9]|1[012])-(0?[1-9]|[12][0-9]|3[01])"


def exists(path) -> bool:
    """Check path or file exists."""
    if not path:
        return False
    return Path(path).exists()


def abspath(cur_file, parent=0) -> str:
    """Absolute path.

    Args:
        cur_file: __file__ or file or path str
        parent: level of parent to look for

    Returns:
        str: Absolute path in POSIX style.
    """
    p = Path(cur_file)
    cur_path = p.parent if p.is_file() else p
    if parent == 0:
        return cur_path.as_posix()
    return abspath(cur_file=cur_path.parent, parent=parent - 1)


def create_folder(path_name: str, is_file=False):
    """Make folder as well as all parent folders if not exists.

    Args:
        path_name: full path name
        is_file: whether input is name of file
    """
    p = Path(path_name).parent if is_file else Path(path_name)
    if not p.exists():
        logger.debug("Creating directory: %s", p)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create directory %s: %s", p, e)
        raise


def all_files(path_name, keyword="", ext="", full_path=True, has_date=False, date_fmt=DATE_FMT) -> list[str]:
    """Search all files with criteria.

    Returned list will be sorted by last modified.

    Args:
        path_name: full path name
        keyword: keyword to search
        ext: file extensions, split by ','
        full_path: whether return full path (default True)
        has_date: whether has date in file name (default False)
        date_fmt: date format to check for has_date parameter

    Returns:
        list: All file names with criteria fulfilled.
    """
    p = Path(path_name)
    if not p.is_dir():
        return []

    keyword = f"*{keyword}*" if keyword else "*"
    keyword += f".{ext}" if ext else ".*"
    r = re.compile(f".*{date_fmt}.*")
    return [
        f.as_posix() if full_path else f.name
        for f in p.glob(keyword)
        if f.is_file() and (f.name[0] != "~") and ((not has_date) or r.match(f.name))
    ]
