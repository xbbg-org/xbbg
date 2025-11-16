"""Tests for intraday pipeline refactor.

These tests verify that the new pipeline structure works correctly
and maintains backward compatibility with the legacy API.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from xbbg.core.domain.contracts import CachePolicy, DataRequest
from xbbg.core.pipeline import RequestBuilder


class TestRequestBuilder:
    """Test RequestBuilder functionality."""

    def test_builder_fluent_api(self):
        """Test fluent builder API."""
        builder = RequestBuilder()
        request = (
            builder
            .ticker('AAPL US Equity')
            .date('2025-01-01')
            .session('day')
            .event_type('TRADE')
            .interval(5)
            .cache_policy(enabled=True, reload=False)
            .build()
        )

        assert request.ticker == 'AAPL US Equity'
        assert request.session == 'day'
        assert request.event_type == 'TRADE'
        assert request.interval == 5
        assert request.cache_policy.enabled is True
        assert request.cache_policy.reload is False

    def test_builder_from_legacy_kwargs(self):
        """Test building from legacy kwargs."""
        request = RequestBuilder.from_legacy_kwargs(
            ticker='AAPL US Equity',
            dt='2025-01-01',
            session='day',
            typ='TRADE',
            interval=5,
            cache=True,
            reload=False,
        )

        assert request.ticker == 'AAPL US Equity'
        assert request.session == 'day'
        assert request.event_type == 'TRADE'
        assert request.interval == 5
        assert request.cache_policy.enabled is True
        assert request.cache_policy.reload is False

    def test_builder_requires_ticker(self):
        """Test that builder requires ticker."""
        builder = RequestBuilder()
        builder.date('2025-01-01')
        with pytest.raises(ValueError, match='ticker is required'):
            builder.build()

    def test_builder_requires_date(self):
        """Test that builder requires date."""
        builder = RequestBuilder()
        builder.ticker('AAPL US Equity')
        with pytest.raises(ValueError, match='dt is required'):
            builder.build()


class TestDataRequest:
    """Test DataRequest value object."""

    def test_data_request_immutable(self):
        """Test that DataRequest is immutable."""
        request = DataRequest(
            ticker='AAPL US Equity',
            dt='2025-01-01',
        )

        # Should not be able to modify
        with pytest.raises(dataclasses.FrozenInstanceError):  # dataclass frozen raises FrozenInstanceError
            request.ticker = 'MSFT US Equity'  # type: ignore

    def test_to_date_string(self):
        """Test date string conversion."""
        request = DataRequest(
            ticker='AAPL US Equity',
            dt='2025-01-01',
        )
        assert request.to_date_string() == '2025-01-01'

        request2 = DataRequest(
            ticker='AAPL US Equity',
            dt=pd.Timestamp('2025-01-01'),
        )
        assert request2.to_date_string() == '2025-01-01'


class TestSessionWindow:
    """Test SessionWindow value object."""

    def test_session_window_valid(self):
        """Test session window validation."""
        from xbbg.core.domain.contracts import SessionWindow

        window = SessionWindow(
            start_time='2025-01-01T09:30:00',
            end_time='2025-01-01T16:00:00',
            session_name='day',
        )
        assert window.is_valid() is True

        invalid = SessionWindow(
            start_time=None,
            end_time='2025-01-01T16:00:00',
            session_name='day',
        )
        assert invalid.is_valid() is False


class TestCachePolicy:
    """Test CachePolicy value object."""

    def test_cache_policy_defaults(self):
        """Test cache policy defaults."""
        policy = CachePolicy()
        assert policy.enabled is True
        assert policy.reload is False

    def test_cache_policy_custom(self):
        """Test custom cache policy."""
        policy = CachePolicy(enabled=False, reload=True)
        assert policy.enabled is False
        assert policy.reload is True


class TestResolverChain:
    """Test resolver chain functionality."""

    def test_exchange_yaml_resolver_can_resolve(self):
        """Test ExchangeYamlResolver can_resolve."""
        from xbbg.markets.resolver_chain import ExchangeYamlResolver

        resolver = ExchangeYamlResolver()
        request = DataRequest(ticker='AAPL US Equity', dt='2025-01-01')
        assert resolver.can_resolve(request) is True

    def test_futures_resolver_can_resolve_futures(self):
        """Test FuturesRollResolver can_resolve futures."""
        from xbbg.markets.resolver_chain import FuturesRollResolver

        resolver = FuturesRollResolver()
        request = DataRequest(ticker='ES1 Index', dt='2025-01-01')
        assert resolver.can_resolve(request) is True

        request2 = DataRequest(ticker='AAPL US Equity', dt='2025-01-01')
        # Should still return True (checks in resolve method)
        assert resolver.can_resolve(request2) is True

    def test_fixed_income_resolver_can_resolve(self):
        """Test FixedIncomeDefaultResolver can_resolve."""
        from xbbg.markets.resolver_chain import FixedIncomeDefaultResolver

        resolver = FixedIncomeDefaultResolver()
        request = DataRequest(ticker='/isin/US912810FE39', dt='2025-01-01')
        assert resolver.can_resolve(request) is True

        request2 = DataRequest(ticker='US912810FE39 Govt', dt='2025-01-01')
        assert resolver.can_resolve(request2) is True

        request3 = DataRequest(ticker='AAPL US Equity', dt='2025-01-01')
        assert resolver.can_resolve(request3) is False

    def test_pmc_resolver_can_resolve(self):
        """Test PmcCalendarResolver can_resolve."""
        from xbbg.markets.resolver_chain import PmcCalendarResolver

        resolver = PmcCalendarResolver()
        request = DataRequest(ticker='AAPL US Equity', dt='2025-01-01', session='day')
        assert resolver.can_resolve(request) is True

        request2 = DataRequest(ticker='AAPL US Equity', dt='2025-01-01', session='am')
        assert resolver.can_resolve(request2) is False

    def test_create_default_resolver_chain(self):
        """Test creating default resolver chain."""
        from xbbg.markets.resolver_chain import create_default_resolver_chain

        chain = create_default_resolver_chain()
        assert len(chain) == 4
        assert all(hasattr(r, 'can_resolve') and hasattr(r, 'resolve') for r in chain)

