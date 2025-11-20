"""Optional exchange-time resolution via pandas-market-calendars.

This module lets users infer exchange sessions from Bloomberg `exch_code`
using a user-editable JSON mapping to pandas-market-calendars calendar ids.

Design:
- Only reads Bloomberg field 'exch_code'.
- Looks up calendar id in a JSON map: { "EXCH_CODE": "PMC_CALENDAR" }.
- Uses pandas_market_calendars to compute open/close for a given date.
- Caches ticker->exch_code and exch_code->calendar name locally to reduce hits.

User config locations (first existing wins):
- ${BBG_ROOT}/markets/pmc_map.json
- package fallback: xbbg/markets/pmc_map.json (optional)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from xbbg.io import files

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

PKG_PATH = files.abspath(__file__, 1)
_CACHE_FILE = str(Path(PKG_PATH) / 'markets' / 'cached' / 'pmc_cache.json')


def _get_map_paths() -> list[str]:
    """Get PMC map paths, using lazy import to avoid circular dependency."""
    from xbbg.io.cache import get_cache_root
    cache_root = get_cache_root()
    return [
        str(Path(cache_root) / 'markets' / 'pmc_map.json') if cache_root else '',
        str(Path(PKG_PATH) / 'markets' / 'pmc_map.json'),
    ]


def _get_package_map_path() -> str:
    """Get the package fallback map path."""
    return str(Path(PKG_PATH) / 'markets' / 'pmc_map.json')


@dataclass(frozen=True)
class PmcSession:
    """Represents a computed trading session window from PMC for a date."""
    tz: str
    start: str  # 'HH:MM'
    end: str    # 'HH:MM'


def _load_pmc_map(logger=None) -> dict:
    """Load exch_code -> PMC calendar mapping from JSON.

    Returns an empty dict if none is found.
    """
    # Use module-level logger if none provided
    if logger is None:
        logger = logging.getLogger(__name__)
    # Get map paths (lazy import handled in _get_map_paths)
    for path in _get_map_paths():
        if path and files.exists(path):
            try:
                with open(path, encoding='utf-8') as fp:
                    data = json.load(fp)
                if not isinstance(data, dict):
                    logger.warning('PMC mapping file at %s is not a valid JSON object, skipping', path)
                    continue
                return {str(k).upper(): str(v) for k, v in data.items()}
            except Exception as e:
                logger.error('Failed to read PMC mapping file from %s: %s', path, e)
    logger.warning('PMC mapping file (pmc_map.json) not found; pandas-market-calendars integration disabled')
    return {}


def _save_cache(cache: dict):
    """Save PMC cache dictionary to JSON file."""
    files.create_folder(_CACHE_FILE, is_file=True)
    try:
        with open(_CACHE_FILE, 'w', encoding='utf-8') as fp:
            json.dump(cache, fp, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error('Failed to save PMC cache to %s: %s', _CACHE_FILE, e)


def _load_cache() -> dict:
    """Load PMC cache dictionary from JSON file."""
    if files.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, encoding='utf-8') as fp:
                data = json.load(fp)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.debug('Failed to load PMC cache from %s: %s', _CACHE_FILE, e)
            return {}
    return {}


def _user_map_path() -> str:
    """Get user PMC map path, using lazy import to avoid circular dependency."""
    from xbbg.io.cache import get_cache_root
    root_str = get_cache_root()
    if not root_str:
        return ''
    root = Path(root_str)
    return str(root / 'markets' / 'pmc_map.json')


def _load_map_at(path: str) -> dict:
    try:
        if not path or not files.exists(path):
            return {}
        with open(path, encoding='utf-8') as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_map_at(path: str, data: dict) -> None:
    files.create_folder(path, is_file=True)
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)


def _normalize_exch_code(exch_code: str) -> str:
    code = (exch_code or '').upper().strip()
    code = ' '.join(code.split())  # collapse whitespace
    code = code.replace(' / ', '/').replace('  ', ' ')
    if code in {'NASDAQ NGS', 'NGS NASDAQ'}:
        code = 'NASDAQ/NGS'
    return code


def _validate_calendar_id(calendar: str) -> bool:
    try:
        import pandas_market_calendars as mcal  # type: ignore
        _ = mcal.get_calendar(calendar)
        return True
    except Exception:
        return False


def pmc_list_mappings(scope: str = 'effective') -> dict:
    """List mappings.

    scope: 'effective' (merged view), 'user' (BBG_ROOT), or 'package' (fallback).
    """
    user_path = _user_map_path()
    pkg_path = _get_package_map_path()
    if scope == 'user':
        return _load_map_at(user_path)
    if scope == 'package':
        return _load_map_at(pkg_path)
    # effective: merge user over package
    eff = _load_map_at(pkg_path)
    eff.update({k.upper(): v for k, v in _load_map_at(user_path).items()})
    return eff


def pmc_add_mapping(exch_code: str, calendar: str, scope: str = 'user') -> None:
    """Add or update a mapping (exch_code -> PMC calendar).

    - scope: 'user' writes to %BBG_ROOT%/markets/pmc_map.json; 'package' writes to package fallback.
    - Uppercases/normalizes exch_code key; preserves existing entries otherwise.
    - Validates calendar id; refuses to save invalid ids.
    - Clears local pmc cache so changes take effect immediately.
    """
    # Logger is module-level
    if not exch_code or not calendar:
        logger.error('Both exch_code and calendar parameters are required to add PMC mapping')
        return
    exch_code = _normalize_exch_code(exch_code)
    if not _validate_calendar_id(calendar):
        logger.error('Invalid pandas-market-calendars calendar ID: %s (validation failed)', calendar)
        return
    path = _user_map_path() if scope == 'user' else _get_package_map_path()
    if not path:
        logger.error('BBG_ROOT environment variable not set; cannot write user-scope PMC mapping')
        return
    data = _load_map_at(path)
    data[exch_code] = str(calendar)
    _save_map_at(path, data)
    # clear caches
    _save_cache({})
    logger.info('PMC mapping saved: %s -> %s (scope: %s)', exch_code.upper(), calendar, scope)


def pmc_remove_mapping(exch_code: str, scope: str = 'user') -> None:
    """Remove a mapping by exch_code from selected scope."""
    # Logger is module-level
    path = _user_map_path() if scope == 'user' else _get_package_map_path()
    data = _load_map_at(path)
    key = _normalize_exch_code(exch_code)
    if key in data:
        data.pop(key)
        _save_map_at(path, data)
        _save_cache({})
        logger.info('PMC mapping removed: %s from %s scope', key, scope)
    else:
        logger.warning('PMC mapping not found: %s in %s scope', key, scope)


def _get_exch_code(
    ticker: str,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Fetch Bloomberg exch_code for ticker (cached).

    Args:
        ticker: Ticker symbol.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Exchange code string.
    """
    # Logger is module-level
    from xbbg.core.domain.context import split_kwargs

    cache = _load_cache()
    tkey = f"exch_code::{ticker}"
    if tkey in cache:
        return cache[tkey]

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    # Convert context to kwargs for bdp call
    safe_kwargs = ctx.to_kwargs()

    try:
        # Import directly from API modules to avoid circular dependency
        from xbbg.api.reference import bdp  # lazy import
        df = bdp(tickers=ticker, flds=['exch_code'], **safe_kwargs)
    except Exception as e:
        logger.error('Failed to fetch exchange code from Bloomberg for ticker %s: %s', ticker, e)
        return ''

    code = ''
    try:
        val = df.iloc[0, 0] if not df.empty else ''
        code = str(val).upper() if isinstance(val, str) or pd.notna(val) else ''
    except Exception:
        code = ''

    if code:
        cache[tkey] = code
        _save_cache(cache)
    return code


def _get_calendar_name_from_exch_code(exch_code: str) -> str:
    mapping = _load_pmc_map()
    return mapping.get(exch_code.upper(), '') if exch_code else ''


def resolve_calendar_name(
    ticker: str,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Resolve pandas-market-calendars id for ticker via Bloomberg exch_code.

    Looks up exch_code in user JSON mapping.

    Args:
        ticker: Ticker symbol.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Calendar name string.
    """
    # Logger is module-level
    from xbbg.core.domain.context import split_kwargs

    cache = _load_cache()
    tkey = f"calendar::{ticker}"
    if tkey in cache:
        return cache[tkey]

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    exch_code = _get_exch_code(ticker, ctx=ctx)
    cal = _get_calendar_name_from_exch_code(exch_code)
    if not cal:
        logger.warning('No PMC calendar mapping found for exchange code %s (ticker: %s)', exch_code, ticker)
        return ''
    cache[tkey] = cal
    _save_cache(cache)
    return cal


def _to_hhmm(ts: pd.Timestamp) -> str:
    return ts.strftime('%H:%M')


def pmc_session_for_date(
    ticker: str,
    dt,
    session: str = 'day',
    include_extended: bool = False,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> PmcSession | None:
    """Compute session open/close using pandas-market-calendars.

    - session='day': market_open to market_close
    - session='allday': pre to post if available, else falls back to market times

    Args:
        ticker: Ticker symbol.
        dt: Date to compute session for.
        session: Session name ('day' or 'allday').
        include_extended: Whether to include extended hours.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        PmcSession or None if not available.
    """
    # Logger is module-level
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    cal_name = resolve_calendar_name(ticker, ctx=ctx)
    if not cal_name:
        return None

    try:
        import pandas_market_calendars as mcal  # type: ignore
    except Exception as e:
        logger.error('pandas-market-calendars package not available: %s (install with: pip install pandas-market-calendars)', e)
        return None

    cal = mcal.get_calendar(cal_name)
    # Build schedule for the single date; include extended columns if requested
    s_date = pd.Timestamp(dt).date()
    if include_extended or session == 'allday':
        sched = cal.schedule(start_date=s_date, end_date=s_date, start='pre', end='post')
        # Extended columns may be absent for some calendars; handle gracefully
        pre_col = 'pre' if 'pre' in sched.columns else 'market_open'
        post_col = 'post' if 'post' in sched.columns else 'market_close'
        tz_name = cal.tz.zone if hasattr(cal.tz, 'zone') else str(cal.tz)
        if sched.empty:
            return None
        return PmcSession(
            tz=tz_name,
            start=_to_hhmm(sched.iloc[0][pre_col].tz_convert(tz_name)),
            end=_to_hhmm(sched.iloc[0][post_col].tz_convert(tz_name)),
        )

    # Regular market times
    sched = cal.schedule(start_date=s_date, end_date=s_date)
    if sched.empty:
        return None
    tz_name = cal.tz.zone if hasattr(cal.tz, 'zone') else str(cal.tz)
    return PmcSession(
        tz=tz_name,
        start=_to_hhmm(sched.iloc[0]['market_open'].tz_convert(tz_name)),
        end=_to_hhmm(sched.iloc[0]['market_close'].tz_convert(tz_name)),
    )



def pmc_wizard(
    ticker: str,
    scope: str = 'user',
    ctx: BloombergContext | None = None,
    **kwargs,
) -> None:
    """Interactive wizard to add/update PMC mapping for a security's exch_code.

    Steps:
    1) Fetch Bloomberg exch_code for the given ticker.
    2) Display current effective mapping (if any) and available PMC calendars.
    3) Prompt for a calendar id and save to the chosen scope (default: user).

    Args:
        ticker: Ticker symbol.
        scope: Mapping scope ('user' or 'package').
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.
    """
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    exch_code = _resolve_exch_code_for_wizard(ticker=ticker, ctx=ctx)
    if not exch_code:
        return

    current = pmc_list_mappings(scope='effective').get(exch_code.upper(), '')
    avail = _load_available_calendars()

    print(f"Ticker: {ticker}")
    print(f"Resolved exch_code: {exch_code}")
    print(f"Current mapping (effective): {current or '<none>'}")

    calendar = _choose_calendar_interactively(
        ticker=ticker,
        exch_code=exch_code,
        current=current,
        available=avail,
    )
    if not calendar:
        logger.error('No calendar ID provided; cannot complete PMC mapping operation')
        return

    # Strictly validate calendar id before saving
    if not _validate_calendar_id(calendar):
        logger.error('Invalid PMC calendar ID: %s (validation failed); aborting save operation', calendar)
        return

    pmc_add_mapping(exch_code=exch_code, calendar=calendar, scope=scope)
    print(f"Saved mapping: {exch_code.upper()} -> {calendar} ({scope}).")


def _resolve_exch_code_for_wizard(ticker: str, ctx: BloombergContext) -> str | None:
    """Resolve exchange code for wizard, prompting user when necessary."""
    exch_code = _get_exch_code(ticker, ctx=ctx)
    if exch_code:
        return exch_code

    print(f"Could not resolve exch_code from Bloomberg for: {ticker}")
    hint = ' (hint: TRACE for US credit/OTC)' if ticker.endswith(' Corp') else ''
    typed = input(f"Enter exch_code manually{hint}: ").strip()
    if not typed:
        logger.error('No exchange code provided; cannot run PMC wizard for ticker %s', ticker)
        return None
    return _normalize_exch_code(typed)


def _load_available_calendars() -> list[str]:
    """Load available PMC calendar ids from pandas-market-calendars."""
    try:
        import pandas_market_calendars as mcal  # type: ignore

        return sorted(set(getattr(mcal, 'get_calendar_names', lambda: [])()))
    except Exception:  # noqa: BLE001
        return []


def _choose_calendar_interactively(
    ticker: str,
    exch_code: str,
    current: str | None,
    available: list[str],
) -> str | None:
    """Interactive flow to select or enter a PMC calendar id."""
    calendar = current or ''
    if available:
        suggestions = _suggest_calendars(exch_code, available, current)
        print(f"Select PMC calendar for exch_code={exch_code}")
        for i, c in enumerate(suggestions, 1):
            mark = "*" if current and c == current else ""
            print(f"  [{i}] {c} {mark}")
        print("  [0] Other (search)")
        raw = input("Enter number (default 1): ").strip()
        sel_idx = 1 if not raw else (int(raw) if raw.isdigit() else -1)
        if sel_idx == 0:
            # Simple search
            key = input("Enter keyword to search calendars: ").strip().lower()
            if key:
                matches = [c for c in available if key in c.lower()]
                if not matches:
                    print("No matches found.")
                else:
                    for j, m in enumerate(matches[:30], 1):
                        print(f"  [{j}] {m}")
                    pick = input("Enter number (or exact id): ").strip()
                    if pick.isdigit():
                        j = int(pick)
                        if 1 <= j <= min(30, len(matches)):
                            calendar = matches[j - 1]
                    elif pick in available:
                        calendar = pick
        elif 1 <= sel_idx <= len(suggestions):
            calendar = suggestions[sel_idx - 1]
        else:
            # fallback to default suggestion
            calendar = suggestions[0] if suggestions else current or ''
    else:
        prompt = f"Enter PMC calendar id for exch_code={exch_code}"
        if current:
            prompt += f" [default: {current}]"
        prompt += ": "
        user_val = input(prompt).strip()
        calendar = user_val or (current or '')
    return calendar or None

def _suggest_calendars(exch_code: str, avail: list[str], current: str | None) -> list[str]:
    code = (exch_code or '').upper()
    prefs: list[str] = []
    def add(*cals: str):
        for c in cals:
            if c in avail and c not in prefs:
                prefs.append(c)
    if any(tok in code for tok in ['NASDAQ']):
        add('NASDAQ')
    if any(tok in code for tok in ['NEW YORK', 'NYSE', 'OTC US', 'US']):
        add('NYSE')
    if 'CME' in code:
        add('CME_Equity', 'CME_Agriculture')
    if 'CFE' in code:
        add('CBOE_Futures')
    if code in ['LN', 'LSE']:
        add('LSE')
    if code in ['HK', 'HKG', 'HKEX']:
        add('HKEX')
    if code in ['JT', 'JP', 'JPX']:
        add('JPX_TSE')
    if code in ['AU', 'ASX']:
        add('ASX')
    if 'TRACE' in code:
        add('SIFMA_US')
    # Ensure current first if present
    if current and current in avail and current not in prefs:
        prefs.insert(0, current)
    # Backfill with popular calendars
    popular = ['NYSE', 'NASDAQ', 'CME_Equity', 'CBOE_Futures', 'LSE', 'HKEX', 'JPX_TSE', 'ASX']
    for c in popular:
        add(c)
    # Finally append first few others
    for c in avail:
        add(c)
    return prefs[:10]


def pmc_bulk_add(pairs: list[tuple[str, str]] | None = None, text: str | None = None, scope: str = 'user') -> dict:
    """Bulk add exch_code->calendar mappings.

    Provide either:
      - pairs: list of (exch_code, calendar)
      - text: newline-separated lines like "US NYSE" or "NASDAQ: NASDAQ"

    Returns a summary dict with counts.
    """
    # Logger is module-level
    if (pairs is None) and (text is None):
        return {'saved': 0, 'skipped': 0}
    items: list[tuple[str, str]] = []
    if text:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            sep = ':' if ':' in line else None
            parts = [p.strip() for p in (line.split(sep) if sep else line.split())]
            if len(parts) >= 2:
                items.append((parts[0], parts[1]))
    if pairs:
        items.extend(pairs)

    saved = skipped = 0
    for code, cal in items:
        code_n = _normalize_exch_code(code)
        if not _validate_calendar_id(cal):
            logger.error('Skipping invalid calendar ID %s for exchange code %s in bulk add operation', cal, code_n)
            skipped += 1
            continue
        pmc_add_mapping(exch_code=code_n, calendar=cal, scope=scope)
        saved += 1
    return {'saved': saved, 'skipped': skipped}


def pmc_bulk_from_tickers(tickers: list[str], scope: str = 'user', **kwargs) -> dict:
    """Bulk wizard flow for a list of tickers; prompts per ticker.

    For each ticker:
      - resolve exch_code (or prompt)
      - suggest calendars and validate selection
      - save mapping
    """
    saved = skipped = 0
    for t in tickers:
        try:
            pmc_wizard(t, scope=scope, **kwargs)
            saved += 1
        except Exception:
            skipped += 1
    return {'saved': saved, 'skipped': skipped}

