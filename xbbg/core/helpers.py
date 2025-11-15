"""Common helper functions to reduce code duplication across modules."""

from __future__ import annotations

from typing import TypeVar

import pandas as pd

T = TypeVar('T', str, list[str])


def normalize_tickers(tickers: str | list[str]) -> list[str]:
    """Normalize tickers to a list.

    Args:
        tickers: Single ticker string or list of tickers.

    Returns:
        list[str]: List of tickers (always a list).
    """
    return [tickers] if isinstance(tickers, str) else tickers


def normalize_flds(flds: str | list[str] | None) -> list[str]:
    """Normalize fields to a list.

    Args:
        flds: Single field string, list of fields, or None.

    Returns:
        list[str]: List of fields (always a list).
    """
    if flds is None:
        return []
    return [flds] if isinstance(flds, str) else flds


def check_empty_result(res: pd.DataFrame, required_cols: list[str] | None = None) -> bool:
    """Check if result DataFrame is empty or missing required columns.

    Args:
        res: Result DataFrame to check.
        required_cols: List of required column names. If None, no column check.

    Returns:
        bool: True if empty or missing required columns, False otherwise.
    """
    if res.empty:
        return True
    if required_cols:
        return any(col not in res for col in required_cols)
    return False

