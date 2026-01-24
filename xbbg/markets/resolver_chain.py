"""Market resolver chain implementations (Chain of Responsibility).

This module provides concrete resolver implementations that can be chained
together to resolve tickers and exchange information.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from xbbg.core.domain.contracts import DataRequest, MarketResolver, ResolverResult
from xbbg.io.cache import load_exchange_info, save_exchange_info
from xbbg.markets.bloomberg import ExchangeInfo, fetch_exchange_info
from xbbg.markets.overrides import OverrideData, get_exchange_override, get_override_fields

if TYPE_CHECKING:
    from xbbg.markets.providers import MarketInfoProvider

logger = logging.getLogger(__name__)


def _exchange_info_to_series(info: ExchangeInfo) -> pd.Series:
    """Convert ExchangeInfo dataclass to pd.Series for ResolverResult.

    Args:
        info: ExchangeInfo dataclass from Bloomberg/cache/override.

    Returns:
        pd.Series with exchange metadata fields.
    """
    data: dict[str, object] = {
        "tz": info.timezone,
    }
    if info.mic:
        data["mic"] = info.mic
    if info.exch_code:
        data["exch_code"] = info.exch_code
    # Add sessions as lists
    for session_name, (start, end) in info.sessions.items():
        data[session_name] = [start, end]
    return pd.Series(data)


def _merge_exchange_info(
    base: ExchangeInfo,
    override_fields: OverrideData,
) -> ExchangeInfo:
    """Merge override fields into base ExchangeInfo.

    Args:
        base: Base ExchangeInfo from cache or Bloomberg.
        override_fields: Dict of fields to override.

    Returns:
        New ExchangeInfo with merged fields.
    """
    return ExchangeInfo(
        ticker=base.ticker,
        mic=override_fields.get("mic", base.mic),  # type: ignore[arg-type]
        exch_code=override_fields.get("exch_code", base.exch_code),  # type: ignore[arg-type]
        timezone=override_fields.get("timezone", base.timezone),  # type: ignore[arg-type]
        utc_offset=base.utc_offset,
        sessions=override_fields.get("sessions", base.sessions),  # type: ignore[arg-type]
        source="override",
        cached_at=base.cached_at,
    )


class BloombergExchangeResolver:
    """Resolver using Bloomberg API with caching and override support.

    Resolution priority (waterfall):
    1. Runtime overrides (highest priority)
    2. Cached data (if not stale)
    3. Bloomberg API query (caches result)

    This resolver integrates:
    - xbbg.markets.overrides: Runtime override registry
    - xbbg.io.cache: Exchange metadata cache (parquet-based)
    - xbbg.markets.bloomberg: Bloomberg API queries
    """

    def __init__(self, max_cache_age_hours: float = 24.0):
        """Initialize resolver.

        Args:
            max_cache_age_hours: Maximum age in hours before cache is stale.
                Use float('inf') to never consider cache stale.
        """
        self._max_cache_age = max_cache_age_hours

    def can_resolve(self, request: DataRequest) -> bool:
        """Can resolve any ticker via Bloomberg API.

        Returns:
            True always - this resolver can attempt any ticker.
        """
        return True

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve using override → cache → Bloomberg waterfall.

        Args:
            request: Data request with ticker and context.

        Returns:
            ResolverResult with exchange_info as pd.Series.
        """
        ticker = request.ticker
        ctx = request.context

        # Get partial override fields for potential merge with cache/Bloomberg
        # Note: We don't early-return on override because partial overrides
        # should be merged with cache/Bloomberg data to fill in missing fields
        override_fields = get_override_fields(ticker)

        # 2. Check cache
        cached_info = load_exchange_info(ticker, max_age_hours=self._max_cache_age)
        if cached_info is not None:
            # Merge with override fields if any
            if override_fields:
                cached_info = _merge_exchange_info(cached_info, override_fields)
                logger.debug("Using cached data with override merge for %s", ticker)
            else:
                logger.debug("Using cached exchange info for %s", ticker)
            return ResolverResult(
                resolved_ticker=ticker,
                exchange_info=_exchange_info_to_series(cached_info),
                success=True,
                resolver_name="BloombergExchangeResolver",
            )

        # 3. Query Bloomberg
        try:
            ctx_kwargs = ctx.to_kwargs() if ctx else {}
            bbg_info = fetch_exchange_info(ticker, ctx, **ctx_kwargs)

            # Check if we got valid data
            if bbg_info.source == "fallback":
                logger.debug("Bloomberg returned fallback for %s", ticker)
                # If we have override fields, use them as fallback
                if override_fields:
                    override_info = get_exchange_override(ticker)
                    if override_info is not None:
                        logger.debug("Using override as fallback for %s", ticker)
                        return ResolverResult(
                            resolved_ticker=ticker,
                            exchange_info=_exchange_info_to_series(override_info),
                            success=True,
                            resolver_name="BloombergExchangeResolver",
                        )
                return ResolverResult(
                    resolved_ticker=ticker,
                    exchange_info=pd.Series(dtype=object),
                    success=False,
                    resolver_name="BloombergExchangeResolver",
                )

            # 4. Cache the result
            save_exchange_info(bbg_info)
            logger.debug("Cached Bloomberg exchange info for %s", ticker)

            # Merge with override fields if any
            if override_fields:
                bbg_info = _merge_exchange_info(bbg_info, override_fields)

            return ResolverResult(
                resolved_ticker=ticker,
                exchange_info=_exchange_info_to_series(bbg_info),
                success=True,
                resolver_name="BloombergExchangeResolver",
            )

        except Exception as e:
            logger.warning("Bloomberg exchange query failed for %s: %s", ticker, e)
            # If we have override fields, use them as fallback
            if override_fields:
                override_info = get_exchange_override(ticker)
                if override_info is not None:
                    logger.debug("Using override as fallback after error for %s", ticker)
                    return ResolverResult(
                        resolved_ticker=ticker,
                        exchange_info=_exchange_info_to_series(override_info),
                        success=True,
                        resolver_name="BloombergExchangeResolver",
                    )
            return ResolverResult(
                resolved_ticker=ticker,
                exchange_info=pd.Series(dtype=object),
                success=False,
                resolver_name="BloombergExchangeResolver",
            )


class ExchangeMetadataResolver:
    """Resolver using Bloomberg-backed exchange metadata (primary resolver)."""

    def __init__(self, info_provider: MarketInfoProvider | None = None):
        """Initialize resolver.

        Args:
            info_provider: Market info provider (defaults to metadata provider).
        """
        if info_provider is None:
            from xbbg.markets.providers import get_default_provider

            info_provider = get_default_provider()
        self._info_provider = info_provider

    def can_resolve(self, request: DataRequest) -> bool:
        """Always try this resolver first."""
        return True

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve using exchange metadata."""
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        ex_info = self._info_provider.get_exchange_info(ticker=request.ticker, **ctx_kwargs)

        return ResolverResult(
            resolved_ticker=request.ticker,
            exchange_info=ex_info,
            success=not ex_info.empty,
            resolver_name="ExchangeMetadataResolver",
        )


# Backward compatibility alias
ExchangeYamlResolver = ExchangeMetadataResolver


class FuturesRollResolver:
    """Resolver for futures ticker rolling."""

    def __init__(self, info_provider: MarketInfoProvider | None = None):
        """Initialize resolver."""
        if info_provider is None:
            from xbbg.markets.providers import get_default_provider

            info_provider = get_default_provider()
        self._info_provider = info_provider

    def can_resolve(self, request: DataRequest) -> bool:
        """Check if ticker is a futures ticker."""
        t_info = request.ticker.split()
        return bool(t_info and t_info[-1] in ["Index", "Comdty", "Curncy", "Equity"])

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve futures ticker."""
        from xbbg.markets import resolvers

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        ex_info = self._info_provider.get_exchange_info(ticker=request.ticker, **ctx_kwargs)

        if ex_info.empty:
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=False,
                resolver_name="FuturesRollResolver",
            )

        # Not a futures contract or spread - return as-is
        if not ex_info.get("is_fut", False) or (
            ex_info.get("has_sprd", False) and len(request.ticker[:-1]) != ex_info.get("tickers", [0])[0]
        ):
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=True,
                resolver_name="FuturesRollResolver",
            )

        # Resolve futures ticker
        if not (
            resolved := resolvers.fut_ticker(
                gen_ticker=request.ticker,
                dt=request.dt,
                freq=ex_info.get("freq", ""),
                **ctx_kwargs,
            )
        ):
            logger.error("Unable to resolve futures ticker for generic ticker: %s", request.ticker)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=False,
                resolver_name="FuturesRollResolver",
            )

        return ResolverResult(
            resolved_ticker=resolved,
            exchange_info=ex_info,
            success=True,
            resolver_name="FuturesRollResolver",
        )


class FixedIncomeDefaultResolver:
    """Resolver for fixed income securities with default exchange info."""

    def can_resolve(self, request: DataRequest) -> bool:
        """Check if ticker is a fixed income security."""
        ticker = request.ticker
        if any(ticker.startswith(prefix) for prefix in ["/isin/", "/cusip/", "/sedol/"]):
            return True
        t_info = ticker.split()
        return bool(
            t_info
            and t_info[-1] in ["Govt", "Corp", "Mtge", "Muni"]
            and len(t_info[0]) >= 2
            and t_info[0][:2].isalpha()
        )

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve fixed income ticker with default exchange info."""
        from xbbg.api.intraday.intraday import _get_default_exchange_info

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        try:
            ex_info = _get_default_exchange_info(
                ticker=request.ticker,
                dt=request.dt,
                session=request.session,
                **ctx_kwargs,
            )
            logger.debug("Using default exchange info for fixed income security: %s", request.ticker)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=True,
                resolver_name="FixedIncomeDefaultResolver",
            )
        except Exception as e:
            logger.debug("Fixed income resolver failed: %s", e)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=pd.Series(dtype=object),
                success=False,
                resolver_name="FixedIncomeDefaultResolver",
            )


def create_default_resolver_chain(
    info_provider: MarketInfoProvider | None = None,
    max_cache_age_hours: float = 24.0,
) -> list[MarketResolver]:
    """Create default resolver chain for intraday data.

    Args:
        info_provider: Optional market info provider (defaults to metadata provider).
        max_cache_age_hours: Maximum age in hours for Bloomberg exchange cache.

    Returns:
        List of resolvers in order of precedence.
    """
    return [
        BloombergExchangeResolver(max_cache_age_hours=max_cache_age_hours),
        ExchangeMetadataResolver(info_provider),
        FuturesRollResolver(info_provider),
        FixedIncomeDefaultResolver(),
    ]
