"""Bloomberg service definitions and request operations (v1.0 preview).

This module defines the Bloomberg services and operations used by the xbbg API.
These enums provide documentation and type safety for Bloomberg service URIs
and operation names.

Example::

    from xbbg import Service, Operation

    # These are the Bloomberg service URIs
    print(Service.REFDATA)  # "//blp/refdata"
    print(Service.MKTDATA)  # "//blp/mktdata"

    # These are the operation names
    print(Operation.REFERENCE_DATA)  # "ReferenceDataRequest"
    print(Operation.HISTORICAL_DATA)  # "HistoricalDataRequest"
"""

from __future__ import annotations

from enum import Enum


class Service(str, Enum):
    """Bloomberg service URIs.

    These are the standard Bloomberg API services. Each service provides
    different types of data and functionality.

    Attributes:
        REFDATA: Reference data service for bdp, bdh, bds, bdib, bdtick requests.
        MKTDATA: Real-time market data subscriptions.
        APIFLDS: Field metadata service for field info and search.
        INSTRUMENTS: Instruments service for security lookup.
    """

    REFDATA = "//blp/refdata"
    """Reference data service for bdp, bdh, bds, bdib, bdtick requests."""

    MKTDATA = "//blp/mktdata"
    """Real-time market data subscriptions."""

    APIFLDS = "//blp/apiflds"
    """Field metadata service for field info and search."""

    INSTRUMENTS = "//blp/instruments"
    """Instruments service for security lookup."""


class Operation(str, Enum):
    """Bloomberg request operation names.

    These correspond to Bloomberg API request types. Each operation
    is used with a specific service.

    Attributes:
        REFERENCE_DATA: Single point-in-time data (bdp, bds).
        HISTORICAL_DATA: Historical time series data (bdh).
        INTRADAY_BAR: Intraday OHLCV bars (bdib).
        INTRADAY_TICK: Intraday tick data (bdtick).
        FIELD_INFO: Get field metadata (type, description).
        FIELD_SEARCH: Search for fields by keyword.
        BEQS: Bloomberg Equity Screening (BEQS).
        PORTFOLIO_DATA: Portfolio data request (bport).
        INSTRUMENT_LIST: Security lookup by name (blkp).
    """

    # Reference data operations (//blp/refdata)
    REFERENCE_DATA = "ReferenceDataRequest"
    """Single point-in-time data (bdp, bds)."""

    HISTORICAL_DATA = "HistoricalDataRequest"
    """Historical time series data (bdh)."""

    INTRADAY_BAR = "IntradayBarRequest"
    """Intraday OHLCV bars (bdib)."""

    INTRADAY_TICK = "IntradayTickRequest"
    """Intraday tick data (bdtick)."""

    # Field metadata operations (//blp/apiflds)
    FIELD_INFO = "FieldInfoRequest"
    """Get field metadata (type, description)."""

    FIELD_SEARCH = "FieldSearchRequest"
    """Search for fields by keyword."""

    # Equity screening operations (//blp/refdata)
    BEQS = "BeqsRequest"
    """Bloomberg Equity Screening (BEQS)."""

    PORTFOLIO_DATA = "PortfolioDataRequest"
    """Portfolio data request (bport)."""

    # Instruments operations (//blp/instruments)
    INSTRUMENT_LIST = "instrumentListRequest"
    """Security lookup by name (blkp)."""
