"""Bloomberg API context management.

This module provides a structured approach to handling kwargs across API boundaries,
separating infrastructure/context kwargs from Bloomberg overrides and request-specific options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from xbbg.core.config import overrides

# Infrastructure kwargs that are safe to pass to internal Bloomberg API calls
# These are connection/logging/caching options, not Bloomberg field overrides
_INFRA_KWARGS = {
    'sess',           # Bloomberg session
    'port',           # Port number
    'timeout',        # Timeout in milliseconds
    'log',            # Logging level
    'raw',            # Return raw response
    'cache',          # Enable caching
    'cache_days',     # Cache expiration days
    'col_maps',       # Column mapping
    'keep_one',       # Keep one result
    'price_only',     # Price only flag
    'has_date',       # Has date flag
    'batch',          # Batch processing flag
    'reload',         # Force reload flag
    # Exchange/session resolution context (safe for internal lookups)
    'ref',            # Reference ticker/exchange
    'original',       # Original ticker (for logging)
    'config',         # Exchange config override
}


@dataclass(frozen=True)
class BloombergContext:
    """Infrastructure context for Bloomberg API calls.

    This context contains only safe infrastructure kwargs that can be passed
    to internal Bloomberg API calls without risk of being interpreted as
    override fields.

    Attributes:
        sess: Bloomberg session (optional)
        port: Port number (optional)
        timeout: Timeout in milliseconds (optional)
        log: Logging level (optional)
        raw: Return raw response (optional)
        cache: Enable caching (optional)
        cache_days: Cache expiration days (optional)
        col_maps: Column mapping (optional)
        keep_one: Keep one result (optional)
        price_only: Price only flag (optional)
        has_date: Has date flag (optional)
        batch: Batch processing flag (optional)
        reload: Force reload flag (optional)
        ref: Reference ticker/exchange (optional)
        original: Original ticker for logging (optional)
        config: Exchange config override (optional)
        _extra: Additional safe kwargs not explicitly listed
    """
    sess: Any = None
    port: int | None = None
    timeout: int | None = None
    log: str | int | None = None
    raw: bool = False
    cache: bool = True
    cache_days: int | None = None
    col_maps: dict | None = None
    keep_one: bool = False
    price_only: bool = False
    has_date: bool = False
    batch: bool = False
    reload: bool = False
    ref: str | None = None
    original: str | None = None
    config: Any = None
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_kwargs(self) -> dict[str, Any]:
        """Convert context to kwargs dict for backward compatibility.

        Only includes non-None values to avoid overriding defaults.
        """
        result = {}
        for key in _INFRA_KWARGS:
            value = getattr(self, key, None)
            if value is not None:
                result[key] = value
        result.update(self._extra)
        return result

    @classmethod
    def from_kwargs(cls, kwargs: dict[str, Any]) -> BloombergContext:
        """Create context from kwargs, extracting only infrastructure fields."""
        infra_kwargs = {}
        extra = {}

        for key, value in kwargs.items():
            if key in _INFRA_KWARGS:
                infra_kwargs[key] = value

        # Only pass explicitly provided kwargs, let defaults handle the rest
        return cls(**infra_kwargs, _extra=extra)


class KwargsSplit:
    """Result of splitting user kwargs into categories."""

    def __init__(
        self,
        infra: BloombergContext,
        override_like: dict[str, Any],
        request_opts: dict[str, Any],
    ):
        """Initialize kwargs split.

        Args:
            infra: Infrastructure context (safe for internal calls)
            override_like: Bloomberg overrides/elements (for main request)
            request_opts: Request-specific options (local to public API)
        """
        self.infra = infra
        self.override_like = override_like
        self.request_opts = request_opts


def split_kwargs(**kwargs) -> KwargsSplit:
    """Split user kwargs into infrastructure, overrides, and request options.

    This function categorizes kwargs into three buckets:
    1. Infrastructure kwargs: Safe to pass to internal Bloomberg API calls
    2. Override-like kwargs: Bloomberg field overrides and element options
    3. Request-specific options: Options specific to the calling function

    Args:
        **kwargs: User-provided kwargs

    Returns:
        KwargsSplit with infra, override_like, and request_opts

    Example:
        >>> split = split_kwargs(
        ...     interval=5, typ='TRADE', sess=None, timeout=1000,
        ...     DVD_Start_Dt='20180101', Period='W'
        ... )
        >>> 'interval' in split.request_opts
        True
        >>> 'DVD_Start_Dt' in split.override_like
        True
        >>> 'timeout' in split.infra.to_kwargs()
        True
    """
    # Request-specific parameters (not Bloomberg overrides, not infrastructure)
    request_specific = {
        'interval', 'typ', 'types', 'intervalHasSeconds', 'time_range',
        'pmc_extended',  # PMC-specific flag
    }

    infra_dict = {}
    override_like = {}
    request_opts = {}

    # Get all keys that proc_ovrds excludes (won't be treated as overrides)
    excluded_by_overrides = set(
        overrides.PRSV_COLS + list(overrides.ELEM_KEYS.keys()) +
        list(overrides.ELEM_KEYS.values())
    )

    for key, value in kwargs.items():
        if key in _INFRA_KWARGS:
            infra_dict[key] = value
        elif key in request_specific:
            request_opts[key] = value
        elif key not in excluded_by_overrides:
            # This is likely a Bloomberg override field
            override_like[key] = value
        # Keys in excluded_by_overrides but not in _INFRA_KWARGS or request_specific
        # are handled by proc_elms/proc_ovrds, so we include them in override_like
        elif key in overrides.ELEM_KEYS or key in overrides.ELEM_KEYS.values():
            override_like[key] = value

    infra = BloombergContext.from_kwargs(infra_dict)

    return KwargsSplit(
        infra=infra,
        override_like=override_like,
        request_opts=request_opts,
    )

