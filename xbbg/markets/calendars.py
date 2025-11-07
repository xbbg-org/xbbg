"""Helpers to integrate pandas-market-calendars with Bloomberg exchange codes.

- Loads a user-editable JSON mapping (merged with built-in defaults)
- Resolves Bloomberg exch_code to a pandas_market_calendars key
- Caches resolved Bloomberg exch_codes in BBG_ROOT to avoid repeat lookups
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from xbbg.io import files, logs, overrides


PKG_ROOT = files.abspath(__file__, 1)
DEFAULT_MAP_FILE = f"{PKG_ROOT}/calendar_map.json"
USER_MAP_FILE = os.path.join(os.environ.get(overrides.BBG_ROOT, ''), 'markets', 'calendar_map.json')
CACHE_FILE = os.path.join(os.environ.get(overrides.BBG_ROOT, ''), 'markets', 'cached', 'bbg_exch_code_cache.json')


def _read_json(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        if files.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _deep_update(base: Dict[str, Any], upd: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_calendar_map() -> Dict[str, Any]:
    """Load built-in mapping merged with user overrides (if present)."""
    base = _read_json(DEFAULT_MAP_FILE)
    user = _read_json(USER_MAP_FILE)
    return _deep_update(base or {}, user or {})


def _load_cache() -> Dict[str, str]:
    return _read_json(CACHE_FILE)


def _save_cache(cache: Dict[str, str]) -> None:
    root = os.path.dirname(CACHE_FILE)
    if root:
        files.create_folder(root)
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except Exception:
        pass


def get_bbg_exch_code(ticker: str, **kwargs) -> str:
    """Fetch Bloomberg exchange code for a ticker, with simple JSON caching.

    Tries fields listed in calendar_map.json -> bbg_exch_code_fields.
    """
    logger = logs.get_logger(get_bbg_exch_code, **kwargs)
    cache = _load_cache()
    if ticker in cache:
        return cache[ticker]

    mapping = load_calendar_map()
    fields = mapping.get('bbg_exch_code_fields', [])
    if not fields:
        fields = ['PRIMARY_EXCHANGE_CODE', 'EXCH_CODE', 'EXCHANGE_CODE']

    try:
        from xbbg.blp import bdp  # lazy import
        info = bdp(ticker, fields, **kwargs)
        if not info.empty:
            for fld in fields:
                if fld in info.columns:
                    val = str(info.iloc[0][fld] or '').strip()
                    if val:
                        cache[ticker] = val
                        _save_cache(cache)
                        return val
    except Exception as e:
        logger.debug(f'bbg exch code fetch failed for {ticker}: {e}')

    cache[ticker] = ''
    _save_cache(cache)
    return ''


def resolve_calendar_key(ticker: str, exch_name: Optional[str] = None, **kwargs) -> str:
    """Resolve pandas_market_calendars key using BBG exch_code or fallback exchange name.

    - Prefer Bloomberg exch_code via bdp
    - Fallback to exch_name (like "EquityUS", "CME", etc.) using mapping
    """
    mapping = load_calendar_map()
    exch_code = get_bbg_exch_code(ticker, **kwargs)
    if exch_code:
        cal = mapping.get('exch_code_to_pmc', {}).get(exch_code, '')
        if cal:
            return cal

    if exch_name:
        return mapping.get('exch_name_to_pmc', {}).get(exch_name, '')

    return ''


def get_schedule_for_date(calendar_key: str, dt: str):
    """Return schedule row from pandas_market_calendars for a given date.

    Returns tuple (tz_name, market_open, market_close) or ('', None, None) on failure.
    """
    if not calendar_key:
        return '', None, None
    try:
        import pandas as pd
        import pandas_market_calendars as mcal

        cal = mcal.get_calendar(calendar_key)
        tz_name = getattr(cal.tz, 'zone', str(cal.tz))
        sched = cal.schedule(start_date=dt, end_date=dt)
        if sched.empty:
            return tz_name, None, None
        row = sched.iloc[0]
        # Normalize to naive "HH:MM" local to exchange tz
        m_open = pd.Timestamp(row['market_open']).tz_convert(tz_name).strftime('%H:%M')
        m_close = pd.Timestamp(row['market_close']).tz_convert(tz_name).strftime('%H:%M')
        return tz_name, m_open, m_close
    except Exception:
        return '', None, None


