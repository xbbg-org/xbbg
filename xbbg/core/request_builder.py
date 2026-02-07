"""Request builder for pipeline requests."""

from __future__ import annotations

from xbbg.core.domain.context import split_kwargs
from xbbg.core.domain.contracts import CachePolicy, DataRequest


class RequestBuilder:
    """Builder for DataRequest objects (Builder pattern).

    Provides fluent API to construct DataRequest from legacy kwargs.
    """

    def __init__(self):
        """Initialize builder."""
        self._ticker: str | None = None
        self._dt = None
        self._session: str = "allday"
        self._event_type: str = "TRADE"
        self._interval: int = 1
        self._interval_has_seconds: bool = False
        self._start_datetime = None
        self._end_datetime = None
        self._context = None
        self._cache_policy = CachePolicy()
        self._request_opts: dict = {}
        self._override_kwargs: dict = {}
        self._backend: str | None = None
        self._format: str | None = None

    def ticker(self, ticker: str) -> RequestBuilder:
        """Set ticker."""
        self._ticker = ticker
        return self

    def date(self, dt) -> RequestBuilder:
        """Set date."""
        self._dt = dt
        return self

    def session(self, session: str) -> RequestBuilder:
        """Set session."""
        self._session = session
        return self

    def event_type(self, typ: str) -> RequestBuilder:
        """Set event type."""
        self._event_type = typ
        return self

    def interval(self, interval: int, has_seconds: bool = False) -> RequestBuilder:
        """Set interval."""
        self._interval = interval
        self._interval_has_seconds = has_seconds
        return self

    def datetime_range(self, start_datetime, end_datetime) -> RequestBuilder:
        """Set explicit datetime range for multi-day requests."""
        self._start_datetime = start_datetime
        self._end_datetime = end_datetime
        return self

    def context(self, ctx) -> RequestBuilder:
        """Set Bloomberg context."""
        self._context = ctx
        return self

    def cache_policy(self, enabled: bool = True, reload: bool = False) -> RequestBuilder:
        """Set cache policy."""
        self._cache_policy = CachePolicy(enabled=enabled, reload=reload)
        return self

    def request_opts(self, **opts) -> RequestBuilder:
        """Add request-specific options."""
        self._request_opts.update(opts)
        return self

    def override_kwargs(self, **kwargs) -> RequestBuilder:
        """Add Bloomberg override kwargs."""
        self._override_kwargs.update(kwargs)
        return self

    def with_output(self, backend: str, output_format: str) -> RequestBuilder:
        """Set output backend and format.

        Args:
            backend: Output backend (e.g., 'pandas', 'polars').
            output_format: Output format (e.g., 'dataframe', 'series').

        Returns:
            Self for method chaining.
        """
        self._backend = backend
        self._format = output_format
        return self

    def build(self) -> DataRequest:
        """Build DataRequest from builder state.

        Returns:
            DataRequest instance.

        Raises:
            ValueError: If required fields are missing.
        """
        if self._ticker is None:
            raise ValueError("ticker is required")
        if self._dt is None:
            raise ValueError("dt is required")

        return DataRequest(
            ticker=self._ticker,
            dt=self._dt,
            session=self._session,
            event_type=self._event_type,
            interval=self._interval,
            interval_has_seconds=self._interval_has_seconds,
            start_datetime=self._start_datetime,
            end_datetime=self._end_datetime,
            context=self._context,
            cache_policy=self._cache_policy,
            request_opts=self._request_opts,
            override_kwargs=self._override_kwargs,
            backend=self._backend,
            format=self._format,
        )

    @classmethod
    def from_legacy_kwargs(
        cls,
        ticker: str,
        dt,
        session: str = "allday",
        typ: str = "TRADE",
        start_datetime=None,
        end_datetime=None,
        backend: str | None = None,
        output_format: str | None = None,
        **kwargs,
    ) -> DataRequest:
        """Build from legacy function signature.

        Args:
            ticker: Ticker symbol.
            dt: Date.
            session: Session name.
            typ: Event type.
            start_datetime: Optional explicit start datetime for multi-day requests.
            end_datetime: Optional explicit end datetime for multi-day requests.
            backend: Backend for data processing (e.g., 'pandas', 'polars').
            output_format: Output format for the data (e.g., 'long', 'wide').
            **kwargs: Legacy kwargs (will be split).

        Returns:
            DataRequest instance.
        """
        split = split_kwargs(**kwargs)
        builder = cls()
        builder.ticker(ticker).date(dt).session(session).event_type(typ)
        builder.context(split.infra)
        builder.cache_policy(
            enabled=split.infra.cache,
            reload=split.infra.reload,
        )

        # Extract interval and intervalHasSeconds from request_opts
        interval = split.request_opts.get("interval", 1)
        interval_has_seconds = split.request_opts.get("intervalHasSeconds", False)
        builder.interval(interval, interval_has_seconds)

        # Set datetime range if provided
        if start_datetime is not None and end_datetime is not None:
            builder.datetime_range(start_datetime, end_datetime)

        # Merge remaining request_opts and override_kwargs
        builder.request_opts(**split.request_opts)
        builder.override_kwargs(**split.override_like)

        # Set output backend and format if provided
        if backend is not None or output_format is not None:
            builder.with_output(backend, output_format)

        return builder.build()
