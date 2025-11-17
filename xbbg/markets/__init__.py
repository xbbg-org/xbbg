"""Market-related utilities for tickers, exchanges, and resolvers."""

# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import for market functions."""
    if name in ('asset_config', 'ccy_pair', 'exch_info', 'market_info', 'market_timing', 'convert_session_times_to_utc'):
        from xbbg.markets import info  # noqa: PLC0415
        return getattr(info, name)
    if name in ('active_cdx', 'active_futures', 'cdx_ticker', 'fut_ticker'):
        # Use module-level resolvers import (avoid reimport)
        return getattr(resolvers, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Direct imports for modules (no circular dependency)
from xbbg.markets import (  # noqa: E402
    pmc,
    providers,
    resolvers,  # noqa: E402
)

__all__ = [
    # Market info functions (lazy-loaded via __getattr__)
    'asset_config',
    'ccy_pair',
    'convert_session_times_to_utc',
    'exch_info',
    'market_info',
    'market_timing',
    # Resolver functions (lazy-loaded via __getattr__)
    'active_cdx',
    'active_futures',
    'cdx_ticker',
    'fut_ticker',
    # Modules
    'info',
    'pmc',
    'providers',
    'resolvers',
]

