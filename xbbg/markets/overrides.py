"""Runtime exchange override registry.

This module provides an in-memory registry for overriding exchange metadata
at runtime. Overrides take priority over all other sources in the exchange
resolution waterfall:

1. Runtime Override → This module (highest priority)
2. Cache → ~/.xbbg/cache/exchanges.parquet
3. Bloomberg Query → xbbg.markets.bloomberg
4. PMC Calendar → Use MIC from Bloomberg
5. Country Inference → Infer timezone from COUNTRY_ISO
6. Hardcoded Fallback → Minimal defaults

Usage:
    from xbbg.markets.overrides import set_exchange_override, clear_exchange_override

    # Override timezone for a specific ticker
    set_exchange_override("CUSTOM Equity", timezone="America/Chicago")

    # Override trading hours
    set_exchange_override(
        "ES1 Index",
        sessions={"regular": ("18:00", "17:00")},
        timezone="America/Chicago",
    )

    # Clear override
    clear_exchange_override("CUSTOM Equity")

    # Clear all overrides
    clear_exchange_override()
"""

from __future__ import annotations

from datetime import datetime
import logging
import threading
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from xbbg.markets.bloomberg import ExchangeInfo

logger = logging.getLogger(__name__)


class OverrideData(TypedDict, total=False):
    """Type definition for override data stored in registry."""

    timezone: str
    mic: str
    exch_code: str
    sessions: dict[str, tuple[str, str]]


# Module-level registry for exchange overrides
_override_registry: dict[str, OverrideData] = {}
_registry_lock = threading.Lock()


def set_exchange_override(
    ticker: str,
    *,
    timezone: str | None = None,
    mic: str | None = None,
    exch_code: str | None = None,
    sessions: dict[str, tuple[str, str]] | None = None,
) -> None:
    """Set runtime override for exchange metadata.

    Only specified fields are overridden; others retain Bloomberg/cached values
    when the override is merged with other data sources.

    Args:
        ticker: Ticker symbol to override (e.g., "AAPL US Equity").
        timezone: IANA timezone string (e.g., "America/New_York").
        mic: MIC code (e.g., "XNYS").
        exch_code: Bloomberg exchange code (e.g., "US").
        sessions: Trading sessions as {session_name: (start, end)}.
            Example: {"regular": ("09:30", "16:00"), "pre": ("04:00", "09:30")}

    Raises:
        ValueError: If ticker is empty or no override fields are specified.

    Examples:
        >>> set_exchange_override("CUSTOM Equity", timezone="America/Chicago")
        >>> set_exchange_override(
        ...     "ES1 Index",
        ...     sessions={"regular": ("18:00", "17:00")},
        ...     timezone="America/Chicago",
        ... )
    """
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    ticker = ticker.strip()

    # Check if at least one override field is specified
    if timezone is None and mic is None and exch_code is None and sessions is None:
        raise ValueError("At least one override field must be specified (timezone, mic, exch_code, or sessions)")

    override_data: OverrideData = {}
    if timezone is not None:
        override_data["timezone"] = timezone
    if mic is not None:
        override_data["mic"] = mic
    if exch_code is not None:
        override_data["exch_code"] = exch_code
    if sessions is not None:
        override_data["sessions"] = sessions

    with _registry_lock:
        if ticker in _override_registry:
            # Merge with existing override
            _override_registry[ticker].update(override_data)
            logger.info(
                "Updated exchange override for %s: %s",
                ticker,
                list(override_data.keys()),
            )
        else:
            _override_registry[ticker] = override_data
            logger.info(
                "Set exchange override for %s: %s",
                ticker,
                list(override_data.keys()),
            )


def get_exchange_override(ticker: str) -> ExchangeInfo | None:
    """Get override for ticker if exists.

    Returns a full ExchangeInfo object with source='override' if an override
    exists for the ticker. Only fields that were explicitly overridden will
    have non-default values.

    Args:
        ticker: Ticker symbol to look up.

    Returns:
        ExchangeInfo with overridden fields, or None if no override exists.

    Examples:
        >>> set_exchange_override("TEST Equity", timezone="Asia/Tokyo")
        >>> info = get_exchange_override("TEST Equity")
        >>> info.timezone if info else None
        'Asia/Tokyo'
        >>> get_exchange_override("NONEXISTENT Equity") is None
        True
    """
    from xbbg.markets.bloomberg import ExchangeInfo

    if not ticker:
        return None

    ticker = ticker.strip()

    with _registry_lock:
        override_data = _override_registry.get(ticker)
        if override_data is None:
            return None

        # Build ExchangeInfo from override data
        return ExchangeInfo(
            ticker=ticker,
            mic=override_data.get("mic"),
            exch_code=override_data.get("exch_code"),
            timezone=override_data.get("timezone", "UTC"),
            utc_offset=None,
            sessions=override_data.get("sessions", {}),
            source="override",
            cached_at=datetime.now(),
        )


def clear_exchange_override(ticker: str | None = None) -> None:
    """Clear override for ticker, or all overrides if ticker is None.

    Args:
        ticker: Ticker symbol to clear, or None to clear all overrides.

    Examples:
        >>> set_exchange_override("TEST1 Equity", timezone="Asia/Tokyo")
        >>> set_exchange_override("TEST2 Equity", timezone="Europe/London")
        >>> clear_exchange_override("TEST1 Equity")  # Clear one
        >>> clear_exchange_override()  # Clear all remaining
    """
    with _registry_lock:
        if ticker is None:
            count = len(_override_registry)
            _override_registry.clear()
            logger.info("Cleared all %d exchange overrides", count)
        else:
            ticker = ticker.strip()
            if ticker in _override_registry:
                del _override_registry[ticker]
                logger.info("Cleared exchange override for %s", ticker)
            else:
                logger.debug("No override to clear for %s", ticker)


def list_exchange_overrides() -> dict[str, ExchangeInfo]:
    """List all current overrides.

    Returns:
        Dict mapping ticker to ExchangeInfo for all overridden tickers.

    Examples:
        >>> clear_exchange_override()  # Start fresh
        >>> set_exchange_override("A Equity", timezone="Asia/Tokyo")
        >>> set_exchange_override("B Equity", mic="XNYS")
        >>> overrides = list_exchange_overrides()
        >>> len(overrides)
        2
    """
    from xbbg.markets.bloomberg import ExchangeInfo

    with _registry_lock:
        result: dict[str, ExchangeInfo] = {}
        for ticker, override_data in _override_registry.items():
            result[ticker] = ExchangeInfo(
                ticker=ticker,
                mic=override_data.get("mic"),
                exch_code=override_data.get("exch_code"),
                timezone=override_data.get("timezone", "UTC"),
                utc_offset=None,
                sessions=override_data.get("sessions", {}),
                source="override",
                cached_at=datetime.now(),
            )
        return result


def has_override(ticker: str) -> bool:
    """Check if an override exists for the given ticker.

    Args:
        ticker: Ticker symbol to check.

    Returns:
        True if an override exists, False otherwise.

    Examples:
        >>> clear_exchange_override()
        >>> has_override("TEST Equity")
        False
        >>> set_exchange_override("TEST Equity", timezone="UTC")
        >>> has_override("TEST Equity")
        True
    """
    if not ticker:
        return False

    ticker = ticker.strip()
    with _registry_lock:
        return ticker in _override_registry


def get_override_fields(ticker: str) -> OverrideData | None:
    """Get raw override fields for a ticker without creating ExchangeInfo.

    This is useful for merging override fields with data from other sources.

    Args:
        ticker: Ticker symbol to look up.

    Returns:
        Dict of overridden fields, or None if no override exists.
        Only contains fields that were explicitly set.

    Examples:
        >>> clear_exchange_override()
        >>> set_exchange_override("TEST Equity", timezone="Asia/Tokyo", mic="XTKS")
        >>> fields = get_override_fields("TEST Equity")
        >>> fields["timezone"]
        'Asia/Tokyo'
        >>> "sessions" in fields  # Not set, so not in dict
        False
    """
    if not ticker:
        return None

    ticker = ticker.strip()
    with _registry_lock:
        override_data = _override_registry.get(ticker)
        if override_data is None:
            return None
        # Return a copy to prevent external modification
        return OverrideData(**override_data)
