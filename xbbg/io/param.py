"""Parameter/config file helpers for xbbg.

Utilities to locate config YAMLs, load them with caching, and convert
numeric time formats into ``HH:MM`` strings.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
from ruamel.yaml import YAML

from xbbg.io import files

PKG_PATH = files.abspath(__file__, 1)

_yaml = YAML(typ='safe')
_yaml.allow_duplicate_keys = False


def config_files(cat: str) -> list:
    """Category files.

    Args:
        cat: category

    Returns:
        list: Files that exist for the given category.
    """
    paths = [
        Path(PKG_PATH),
        Path(os.environ.get('BBG_ROOT', '')),
    ]
    return [
        str(p / 'markets' / 'config' / f'{cat}.yml')
        for p in paths
        if p.as_posix() and files.exists(str(p / 'markets' / 'config' / f'{cat}.yml'))
    ]


def load_config(cat: str) -> pd.DataFrame:
    """Load market info that can apply ``pd.Series`` directly.

    Args:
        cat: category name

    Returns:
        pd.DataFrame: Concatenated configuration.
    """
    cfg_files = config_files(cat=cat)
    if not cfg_files:
        return pd.DataFrame()
    cache_cfg = str(Path(PKG_PATH) / 'markets' / 'cached' / f'{cat}_cfg.parq')
    last_mod = max(map(files.modified_time, cfg_files), default=0)
    if files.exists(cache_cfg) and files.modified_time(cache_cfg) > last_mod:
        return pd.read_parquet(cache_cfg)

    if not cfg_files:
        return pd.DataFrame()
    config = (
        pd.concat([
            load_yaml(cf).apply(pd.Series)
            for cf in cfg_files
        ], sort=False)
    )
    if config.empty:
        return pd.DataFrame()
    files.create_folder(cache_cfg, is_file=True)
    config.to_parquet(cache_cfg)
    return config


def load_yaml(yaml_file: str) -> pd.Series:
    """Load YAML from cache.

    Args:
        yaml_file: YAML file name

    Returns:
        pd.Series: Parsed YAML content.
    """
    # Convert to Path for cross-platform compatibility
    yaml_path = Path(yaml_file)
    cache_file = str(
        yaml_path.parent.parent / 'cached' / yaml_path.with_suffix('.parq').name
    )
    cur_mod = files.modified_time(yaml_file)
    if files.exists(cache_file) and files.modified_time(cache_file) > cur_mod:
        # Load from parquet: Series was saved as DataFrame with 'value' column
        df = pd.read_parquet(cache_file)
        # Restore Series with original index
        return pd.Series(df['value'].values, index=df.index, name=df['value'].name)

    with open(yaml_file) as fp:
        data = pd.Series(_yaml.load(fp))
        files.create_folder(cache_file, is_file=True)
        # Convert Series to DataFrame for parquet storage
        # Store index as column and values as 'value' column
        df = pd.DataFrame({'value': data.values}, index=data.index)
        df.to_parquet(cache_file)
        return data


def to_hours(num_ts: str | list | int | float | np.integer | np.floating) -> str | list:
    """Convert YAML input to hours.

    Args:
        num_ts: list of number in YMAL file, e.g., 900, 1700, etc.

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
    if isinstance(num_ts, str): return num_ts
    # Handle numpy scalar types (int64, int32, float64, etc.)
    if isinstance(num_ts, (int, float, np.integer, np.floating)):
        num_val = float(num_ts)
        return f'{int(num_val / 100):02d}:{int(num_val % 100):02d}'
    # Handle list-like types (list, tuple, array, etc.)
    if hasattr(num_ts, '__iter__') and not isinstance(num_ts, (str, bytes)):
        return [to_hours(num) for num in num_ts]
    # Fallback: treat as scalar (convert to float first)
    num_val = float(num_ts)
    return f'{int(num_val / 100):02d}:{int(num_val % 100):02d}'
