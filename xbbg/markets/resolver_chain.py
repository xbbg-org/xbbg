"""Market resolver chain implementations (Chain of Responsibility).

This module provides concrete resolver implementations that can be chained
together to resolve tickers and exchange information.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from xbbg.core.domain.contracts import DataRequest, MarketResolver, ResolverResult

if TYPE_CHECKING:
    from xbbg.markets.providers import MarketInfoProvider

logger = logging.getLogger(__name__)


class ExchangeYamlResolver:
    """Resolver using exch.yml configuration (primary resolver)."""

    def __init__(self, info_provider: MarketInfoProvider | None = None):
        """Initialize resolver.

        Args:
            info_provider: Market info provider (defaults to YAML provider).
        """
        if info_provider is None:
            from xbbg.markets.providers import get_default_provider
            info_provider = get_default_provider()
        self._info_provider = info_provider

    def can_resolve(self, request: DataRequest) -> bool:
        """Always try this resolver first."""
        return True

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve using exch.yml."""
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        ex_info = self._info_provider.get_exchange_info(ticker=request.ticker, **ctx_kwargs)

        return ResolverResult(
            resolved_ticker=request.ticker,
            exchange_info=ex_info,
            success=not ex_info.empty,
            resolver_name='ExchangeYamlResolver',
        )


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
        return bool(t_info and t_info[-1] in ['Index', 'Comdty', 'Curncy', 'Equity'])

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
                resolver_name='FuturesRollResolver',
            )

        # Not a futures contract or spread - return as-is
        if not ex_info.get('is_fut', False) or \
           (ex_info.get('has_sprd', False) and
            len(request.ticker[:-1]) != ex_info.get('tickers', [0])[0]):
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=True,
                resolver_name='FuturesRollResolver',
            )

        # Resolve futures ticker
        if not (resolved := resolvers.fut_ticker(
            gen_ticker=request.ticker,
            dt=request.dt,
            freq=ex_info.get('freq', ''),
            **ctx_kwargs,
        )):
            logger.error('Unable to resolve futures ticker for generic ticker: %s', request.ticker)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=False,
                resolver_name='FuturesRollResolver',
            )

        return ResolverResult(
            resolved_ticker=resolved,
            exchange_info=ex_info,
            success=True,
            resolver_name='FuturesRollResolver',
        )


class FixedIncomeDefaultResolver:
    """Resolver for fixed income securities with default exchange info."""

    def can_resolve(self, request: DataRequest) -> bool:
        """Check if ticker is a fixed income security."""
        ticker = request.ticker
        if any(ticker.startswith(prefix) for prefix in ['/isin/', '/cusip/', '/sedol/']):
            return True
        t_info = ticker.split()
        return bool(t_info and t_info[-1] in ['Govt', 'Corp', 'Mtge', 'Muni'] and
                    len(t_info[0]) >= 2 and t_info[0][:2].isalpha())

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
            logger.debug('Using default exchange info for fixed income security: %s', request.ticker)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=ex_info,
                success=True,
                resolver_name='FixedIncomeDefaultResolver',
            )
        except Exception as e:
            logger.debug('Fixed income resolver failed: %s', e)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=pd.Series(dtype=object),
                success=False,
                resolver_name='FixedIncomeDefaultResolver',
            )


class PmcCalendarResolver:
    """Resolver using pandas-market-calendars (PMC) as fallback."""

    def can_resolve(self, request: DataRequest) -> bool:
        """Only support 'day' and 'allday' sessions."""
        return request.session in {'day', 'allday'}

    def resolve(self, request: DataRequest) -> ResolverResult:
        """Resolve using PMC calendars."""
        try:
            from xbbg.markets.pmc import pmc_session_for_date

            if not (pmc_ss := pmc_session_for_date(
                ticker=request.ticker,
                dt=request.dt,
                session=request.session,
                include_extended=request.request_opts.get('pmc_extended', False),
                ctx=request.context,
            )):
                return ResolverResult(
                    resolved_ticker=request.ticker,
                    exchange_info=pd.Series(dtype=object),
                    success=False,
                    resolver_name='PmcCalendarResolver',
                )

            logger.warning(
                'Exchange session metadata not available for %s (session=%s), falling back to pandas-market-calendars',
                request.ticker,
                request.session,
            )

            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=pd.Series({
                    'tz': pmc_ss.tz,
                    request.session: [pmc_ss.start, pmc_ss.end],
                }),
                success=True,
                resolver_name='PmcCalendarResolver',
            )
        except Exception as e:
            logger.debug('PMC resolver failed: %s', e)
            return ResolverResult(
                resolved_ticker=request.ticker,
                exchange_info=pd.Series(dtype=object),
                success=False,
                resolver_name='PmcCalendarResolver',
            )


def create_default_resolver_chain(
    info_provider: MarketInfoProvider | None = None,
) -> list[MarketResolver]:
    """Create default resolver chain for intraday data.

    Args:
        info_provider: Optional market info provider (defaults to YAML provider).

    Returns:
        List of resolvers in order of precedence.
    """
    return [
        ExchangeYamlResolver(info_provider),
        FuturesRollResolver(info_provider),
        FixedIncomeDefaultResolver(),
        PmcCalendarResolver(),
    ]

