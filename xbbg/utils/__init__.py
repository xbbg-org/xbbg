"""Utility functions for data processing pipelines.

This package provides data processing utilities for working with Bloomberg data:
- pipeline: DataFrame processing functions (standard_cols, apply_fx, perf, etc.)

All functions are designed to work with pandas DataFrames and can be used
with the `.pipe()` method for method chaining.
"""

from __future__ import annotations

from xbbg.utils.pipeline import (
    add_ticker,
    apply_fx,
    daily_stats,
    dropna,
    format_raw,
    get_series,
    perf,
    since_year,
    standard_cols,
)

__all__ = [
    "add_ticker",
    "apply_fx",
    "daily_stats",
    "dropna",
    "format_raw",
    "get_series",
    "perf",
    "since_year",
    "standard_cols",
]
