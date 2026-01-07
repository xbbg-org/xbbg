"""Streaming data types for real-time market data (v1.0 preview).

This module provides type definitions for the v1.0 streaming API.
These types are provided for documentation and type hints - the actual
streaming implementation will be available in v1.0.

In v1.0, the streaming API changes from:
    - live() / subscribe() returning async generators

To:
    - asubscribe() / subscribe() returning Subscription objects
    - Subscription supports dynamic add/remove of securities
    - Yields Tick objects or Arrow batches
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class Tick:
    """Single tick data point from a subscription.

    This dataclass represents a single market data update received
    from a Bloomberg subscription.

    Attributes:
        ticker: Security identifier (e.g., "AAPL US Equity")
        field: Bloomberg field name (e.g., "LAST_PRICE", "BID", "ASK")
        value: Field value (type depends on field - float, str, int, etc.)
        timestamp: Time the tick was received

    Example::

        async for tick in subscription:
            if tick.field == "LAST_PRICE":
                print(f"{tick.ticker}: {tick.value} @ {tick.timestamp}")
    """

    ticker: str
    field: str
    value: Any
    timestamp: datetime


class Subscription:
    """Subscription handle with async iteration and dynamic control (v1.0 preview).

    This class is a preview of the v1.0 streaming API. In the current version,
    use live() or subscribe() instead.

    v1.0 Features:
        - Async iteration: ``async for tick in sub``
        - Dynamic add/remove: ``await sub.add(['MSFT US Equity'])``
        - Context manager: ``async with xbbg.asubscribe(...) as sub:``
        - Explicit unsubscribe: ``await sub.unsubscribe(drain=True)``

    Example (v1.0)::

        # Create subscription
        sub = await xbbg.asubscribe(
            ["AAPL US Equity", "GOOGL US Equity"],
            ["LAST_PRICE", "BID", "ASK"]
        )

        # Iterate over ticks
        async for batch in sub:
            df = batch.to_pandas()
            print(df)

            # Dynamically add more securities
            if should_add_msft:
                await sub.add(["MSFT US Equity"])

            # Dynamically remove securities
            if should_remove_googl:
                await sub.remove(["GOOGL US Equity"])

        # Clean up
        await sub.unsubscribe()

    Note:
        This is a preview stub. The actual implementation requires the
        v1.0 Rust backend. In the current version, use:

        - ``xbbg.blp.live()`` for real-time data
        - ``xbbg.blp.subscribe()`` for subscriptions
    """

    def __init__(self) -> None:
        """Initialize subscription (v1.0 preview stub)."""
        raise NotImplementedError(
            "Subscription requires xbbg v1.0. "
            "In the current version, use xbbg.blp.live() or xbbg.blp.subscribe() instead."
        )

    async def add(self, tickers: str | list[str]) -> None:
        """Add securities to the subscription dynamically.

        Args:
            tickers: Security identifier(s) to add
        """
        raise NotImplementedError("Subscription.add() requires xbbg v1.0")

    async def remove(self, tickers: str | list[str]) -> None:
        """Remove securities from the subscription.

        Args:
            tickers: Security identifier(s) to remove
        """
        raise NotImplementedError("Subscription.remove() requires xbbg v1.0")

    async def unsubscribe(self, *, drain: bool = True) -> None:
        """Unsubscribe and clean up.

        Args:
            drain: If True, wait for pending data before closing
        """
        raise NotImplementedError("Subscription.unsubscribe() requires xbbg v1.0")

    def __aiter__(self):
        """Async iterator protocol."""
        return self

    async def __anext__(self):
        """Get next batch of data."""
        raise NotImplementedError("Subscription iteration requires xbbg v1.0")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.unsubscribe()
