"""Market-related utilities for tickers, exchanges, and resolvers."""


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import for market functions."""
    if name in (
        "asset_config",
        "ccy_pair",
        "exch_info",
        "market_info",
        "market_timing",
        "convert_session_times_to_utc",
    ):
        from xbbg.markets import info  # noqa: PLC0415

        return getattr(info, name)
    if name in ("active_cdx", "active_futures", "cdx_ticker", "fut_ticker"):
        # Use module-level resolvers import (avoid reimport)
        return getattr(resolvers, name)
    # Bloomberg exchange metadata functions
    if name in ("ExchangeInfo", "fetch_exchange_info", "afetch_exchange_info"):
        from xbbg.markets import bloomberg  # noqa: PLC0415

        return getattr(bloomberg, name)
    # Runtime override functions
    if name in (
        "set_exchange_override",
        "get_exchange_override",
        "clear_exchange_override",
        "list_exchange_overrides",
    ):
        from xbbg.markets import overrides  # noqa: PLC0415

        return getattr(overrides, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Direct imports for modules (no circular dependency)
from xbbg.markets import (  # noqa: E402
    bloomberg,
    info,
    overrides,
    providers,
    resolvers,  # noqa: E402
)

__all__ = [
    # Market info functions (lazy-loaded via __getattr__)
    "asset_config",
    "ccy_pair",
    "convert_session_times_to_utc",
    "exch_info",
    "market_info",
    "market_timing",
    # Resolver functions (lazy-loaded via __getattr__)
    "active_cdx",
    "active_futures",
    "cdx_ticker",
    "fut_ticker",
    # Bloomberg exchange metadata (lazy-loaded via __getattr__)
    "ExchangeInfo",
    "afetch_exchange_info",
    "fetch_exchange_info",
    # Runtime overrides (lazy-loaded via __getattr__)
    "clear_exchange_override",
    "get_exchange_override",
    "list_exchange_overrides",
    "set_exchange_override",
    # Modules
    "bloomberg",
    "info",
    "overrides",
    "providers",
    "resolvers",
]
