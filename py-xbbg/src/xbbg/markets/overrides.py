"""Runtime exchange override registry."""

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
    """Set runtime override for exchange metadata."""
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    ticker = ticker.strip()
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
            _override_registry[ticker].update(override_data)
            logger.info("Updated exchange override for %s: %s", ticker, list(override_data.keys()))
        else:
            _override_registry[ticker] = override_data
            logger.info("Set exchange override for %s: %s", ticker, list(override_data.keys()))


def get_exchange_override(ticker: str) -> ExchangeInfo | None:
    """Get override for ticker if exists."""
    from xbbg.markets.bloomberg import ExchangeInfo

    if not ticker:
        return None

    ticker = ticker.strip()
    with _registry_lock:
        override_data = _override_registry.get(ticker)
        if override_data is None:
            return None
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
    """Clear override for ticker, or all overrides if ticker is None."""
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
    """List all current overrides."""
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
    """Check if an override exists for the given ticker."""
    if not ticker:
        return False
    ticker = ticker.strip()
    with _registry_lock:
        return ticker in _override_registry


def get_override_fields(ticker: str) -> OverrideData | None:
    """Get raw override fields for a ticker without creating ExchangeInfo."""
    if not ticker:
        return None

    ticker = ticker.strip()
    with _registry_lock:
        override_data = _override_registry.get(ticker)
        if override_data is None:
            return None
        return OverrideData(**override_data)
