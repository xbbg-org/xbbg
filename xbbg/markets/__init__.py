"""Market-related utilities for tickers, exchanges, and resolvers."""

# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import for market functions."""
    if name in ('asset_config', 'ccy_pair', 'exch_info', 'market_info', 'market_timing'):
        from xbbg.markets import info  # noqa: PLC0415
        return getattr(info, name)
    if name in ('active_cdx', 'active_futures', 'cdx_ticker', 'fut_ticker'):
        from xbbg.markets import resolvers  # noqa: PLC0415
        return getattr(resolvers, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Direct imports for modules (no circular dependency)
from xbbg.markets import pmc, resolvers  # noqa: E402

__all__ = [
    # Market info functions
    'asset_config',
    'ccy_pair',
    'exch_info',
    'market_info',
    'market_timing',
    # Resolver functions
    'active_cdx',
    'active_futures',
    'cdx_ticker',
    'fut_ticker',
    # Modules
    'info',
    'pmc',
    'resolvers',
]

