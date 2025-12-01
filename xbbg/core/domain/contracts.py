"""Core contracts for Bloomberg data pipeline.

This module defines immutable Value Objects and Protocols that represent
the domain model for Bloomberg data requests, sessions, caching, and resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext


@dataclass(frozen=True)
class SessionWindow:
    """Trading session time window (Value Object).

    Represents a time range for a trading session, with start and end times
    in ISO format strings (YYYY-MM-DDTHH:MM:SS).

    Attributes:
        start_time: Session start time in ISO format, or None if not resolved.
        end_time: Session end time in ISO format, or None if not resolved.
        session_name: Name of the session (e.g., 'allday', 'day', 'am').
        timezone: Target timezone for the session window.
    """
    start_time: str | None
    end_time: str | None
    session_name: str
    timezone: str = 'UTC'

    def is_valid(self) -> bool:
        """Check if session window is valid (both times present)."""
        return self.start_time is not None and self.end_time is not None


@dataclass(frozen=True)
class CachePolicy:
    """Cache policy configuration (Value Object).

    Encapsulates caching behavior for data requests.

    Attributes:
        enabled: Whether caching is enabled.
        reload: Force reload even if cache exists.
        cache_days: Number of days to keep cache valid.
    """
    enabled: bool = True
    reload: bool = False
    cache_days: int | None = None


@dataclass(frozen=True)
class ResolverResult:
    """Result from a market resolver (Value Object).

    Represents the outcome of resolving a ticker or market configuration.

    Attributes:
        resolved_ticker: The resolved ticker string, or original if no resolution needed.
        exchange_info: Exchange information as pd.Series (may be empty).
        success: Whether resolution was successful.
        resolver_name: Name of the resolver that produced this result.
    """
    resolved_ticker: str
    exchange_info: pd.Series = field(default_factory=pd.Series)
    success: bool = True
    resolver_name: str = ''

    def is_empty(self) -> bool:
        """Check if exchange info is empty."""
        return self.exchange_info.empty


@dataclass(frozen=True)
class DataRequest:
    """Bloomberg data request (Value Object).

    Encapsulates all parameters needed to fetch Bloomberg data.

    Attributes:
        ticker: Ticker symbol (may be generic, e.g., 'ES1 Index').
        dt: Date for the request (used for single-day requests).
        session: Trading session name (e.g., 'allday', 'day').
        event_type: Event type (e.g., 'TRADE', 'BID', 'ASK').
        interval: Bar interval in minutes (or seconds if interval_has_seconds=True).
        interval_has_seconds: If True, interpret interval as seconds.
        start_datetime: Explicit start datetime for multi-day requests (optional).
        end_datetime: Explicit end datetime for multi-day requests (optional).
        context: Bloomberg infrastructure context.
        cache_policy: Cache policy configuration.
        request_opts: Request-specific options (not Bloomberg overrides).
        override_kwargs: Bloomberg field overrides and element options.
    """
    ticker: str
    dt: str | pd.Timestamp
    session: str = 'allday'
    event_type: str = 'TRADE'
    interval: int = 1
    interval_has_seconds: bool = False
    start_datetime: str | pd.Timestamp | None = None
    end_datetime: str | pd.Timestamp | None = None
    context: BloombergContext | None = None
    cache_policy: CachePolicy = field(default_factory=CachePolicy)
    request_opts: dict[str, Any] = field(default_factory=dict)
    override_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_date_string(self) -> str:
        """Convert dt to YYYY-MM-DD string."""
        return pd.Timestamp(self.dt).strftime('%Y-%m-%d')

    def is_multi_day(self) -> bool:
        """Check if this is a multi-day request (explicit datetime range)."""
        return self.start_datetime is not None and self.end_datetime is not None


class MarketResolver(Protocol):
    """Protocol for market resolvers (Strategy pattern).

    Resolvers implement chain-of-responsibility to resolve tickers,
    exchange info, or other market-specific configurations.
    """

    def can_resolve(self, request: DataRequest) -> bool:
        """Check if this resolver can handle the request.

        Args:
            request: Data request to check.

        Returns:
            True if this resolver can handle the request.
        """
        ...

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve the request.

        Args:
            request: Data request to resolve.

        Returns:
            ResolverResult with resolved ticker and exchange info.
        """
        ...


class CacheAdapter(Protocol):
    """Protocol for cache adapters (Repository pattern).

    Cache adapters handle loading and saving of cached Bloomberg data.
    """

    def load(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> pd.DataFrame | None:
        """Load cached data if available.

        Args:
            request: Data request.
            session_window: Session window to filter by.

        Returns:
            Cached DataFrame if available and valid, None otherwise.
        """
        ...

    def save(
        self,
        data: pd.DataFrame,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> None:
        """Save data to cache.

        Args:
            data: DataFrame to save.
            request: Original data request.
            session_window: Session window that was used.
        """
        ...


class BaseContextAware:
    """Mixin for classes that need Bloomberg context.

    Provides helper methods to materialize BloombergContext from kwargs
    or use an existing context.
    """

    def _get_context(self, ctx: BloombergContext | None = None, **kwargs) -> BloombergContext:
        """Get Bloomberg context from kwargs or use provided.

        Args:
            ctx: Explicit context (preferred).
            **kwargs: Legacy kwargs support.

        Returns:
            BloombergContext instance.
        """
        if ctx is not None:
            return ctx

        from xbbg.core.domain.context import split_kwargs
        split = split_kwargs(**kwargs)
        return split.infra

