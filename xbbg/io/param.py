"""Parameter/config file helpers for xbbg.

This module provides utilities for time formatting and configuration paths.

Note: YAML configuration loading utilities (load_config, load_yaml, config_files)
are deprecated since YAML configuration files have been removed in favor of
Bloomberg API calls. Use Bloomberg API directly for market metadata:
- Exchange info: bdp(ticker, ['EXCH_CODE', 'IANA_TIME_ZONE', 'TRADING_DAY_START_TIME_EOD', ...])
- Futures cycles: bdp(ticker, 'FUT_GEN_MONTH')
- Currency pairs: bdp(ticker, ['INVERSE_QUOTED', 'BASE_CRNCY'])
"""

import numpy as np
import pandas as pd

from xbbg.io import files

# Package path - used for locating test data and other resources
PKG_PATH = files.abspath(__file__, 1)


def config_files(cat: str) -> list:
    """Category files.

    .. deprecated::
        YAML configuration files have been removed. This function is deprecated
        and will be removed in a future version.

    Args:
        cat: category

    Returns:
        list: Empty list. YAML config files no longer exist.
    """
    import warnings

    warnings.warn(
        "config_files() is deprecated. YAML configuration files have been removed. "
        "Use Bloomberg API directly for market metadata.",
        DeprecationWarning,
        stacklevel=2,
    )
    return []


def load_config(cat: str) -> pd.DataFrame:
    """Load market info that can apply ``pd.Series`` directly.

    .. deprecated::
        YAML configuration files have been removed. This function is deprecated
        and will be removed in a future version. Use Bloomberg API directly.

    Args:
        cat: category name

    Returns:
        pd.DataFrame: Empty DataFrame. YAML config files no longer exist.
    """
    import warnings

    warnings.warn(
        "load_config() is deprecated. YAML configuration files have been removed. "
        "Use Bloomberg API directly for market metadata (e.g., bdp with EXCH_CODE, "
        "IANA_TIME_ZONE, FUT_GEN_MONTH fields).",
        DeprecationWarning,
        stacklevel=2,
    )
    return pd.DataFrame()


def load_yaml(yaml_file: str) -> pd.Series:
    """Load YAML from cache.

    .. deprecated::
        YAML configuration files have been removed. This function is deprecated
        and will be removed in a future version.

    Args:
        yaml_file: YAML file name

    Returns:
        pd.Series: Empty Series. YAML config files no longer exist.
    """
    import warnings

    warnings.warn(
        "load_yaml() is deprecated. YAML configuration files have been removed. "
        "Use Bloomberg API directly for market metadata.",
        DeprecationWarning,
        stacklevel=2,
    )
    return pd.Series(dtype=object)


def to_hours(num_ts: str | list | int | float | np.integer | np.floating) -> str | list:
    """Convert numeric time to hours format (HH:MM).

    Args:
        num_ts: Numeric time value or list of values. Examples:
            - 900 → "09:00"
            - 1700 → "17:00"
            - [900, 1700] → ["09:00", "17:00"]
            - "XYZ" → "XYZ" (strings returned as-is)

    Returns:
        str | list: Time formatted as ``HH:MM`` or list of times.

    Examples:
        >>> to_hours([900, 1700])
        ['09:00', '17:00']
        >>> to_hours(901)
        '09:01'
        >>> to_hours('XYZ')
        'XYZ'
    """
    if isinstance(num_ts, str):
        return num_ts
    # Handle numpy scalar types (int64, int32, float64, etc.)
    if isinstance(num_ts, (int, float, np.integer, np.floating)):
        num_val = float(num_ts)
        return f"{int(num_val / 100):02d}:{int(num_val % 100):02d}"
    # Handle list-like types (list, tuple, array, etc.)
    if hasattr(num_ts, "__iter__") and not isinstance(num_ts, (str, bytes)):
        return [to_hours(num) for num in num_ts]  # type: ignore[arg-type]
    # Fallback: treat as scalar (convert to float first)
    num_val = float(num_ts)  # type: ignore[arg-type]
    return f"{int(num_val / 100):02d}:{int(num_val % 100):02d}"
