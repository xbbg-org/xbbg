"""Market information providers (Strategy pattern).

Provides pluggable implementations for resolving market and exchange information.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class MarketInfoProvider(Protocol):
    """Protocol for market information providers."""

    def get_exchange_info(self, ticker: str, **kwargs) -> pd.Series:
        """Get exchange information for a ticker."""
        ...

    def get_market_info(self, ticker: str) -> pd.Series:
        """Get market metadata for a ticker."""
        ...


class MetadataProvider:
    """Provider using Bloomberg-backed metadata."""

    def get_exchange_info(self, ticker: str, **kwargs) -> pd.Series:
        """Get exchange info from Bloomberg metadata."""
        from xbbg.markets.info import exch_info

        return exch_info(ticker=ticker, **kwargs)

    def get_market_info(self, ticker: str) -> pd.Series:
        """Get market info from Bloomberg metadata."""
        from xbbg.markets.info import market_info

        return market_info(ticker=ticker)


# Backward compatibility alias
YamlMarketInfoProvider = MetadataProvider


# Default provider instance (singleton pattern for performance)
_default_provider: MarketInfoProvider | None = None


def get_default_provider() -> MarketInfoProvider:
    """Get default market info provider."""
    global _default_provider
    if _default_provider is None:
        _default_provider = MetadataProvider()
    return _default_provider
