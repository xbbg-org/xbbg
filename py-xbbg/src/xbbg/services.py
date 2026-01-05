"""Bloomberg service definitions and request parameters.

This module defines the Bloomberg services, operations, and request parameters
used by the xbbg API. These definitions are the authoritative source for
service/operation names - the Rust layer accepts these as strings.

Example:
    from xbbg import Service, Operation, RequestParams

    params = RequestParams(
        service=Service.REFDATA,
        operation=Operation.REFERENCE_DATA,
        securities=['AAPL US Equity'],
        fields=['PX_LAST'],
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from xbbg.exceptions import BlpValidationError


class Service(str, Enum):
    """Bloomberg service URIs.

    These are the standard Bloomberg API services. Power users can also
    use raw service URI strings for services not listed here.
    """

    REFDATA = "//blp/refdata"
    """Reference data service for bdp, bdh, bds, bdib, bdtick requests."""

    MKTDATA = "//blp/mktdata"
    """Real-time market data subscriptions."""

    APIFLDS = "//blp/apiflds"
    """Field metadata service for field info and search."""


class Operation(str, Enum):
    """Bloomberg request operation names.

    These correspond to Bloomberg API request types. Power users can also
    use raw operation name strings for operations not listed here.
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


class OutputMode(str, Enum):
    """Output format for generic requests.

    Controls how Bloomberg responses are converted before returning to Python.
    """

    ARROW = "arrow"
    """Convert to Arrow RecordBatch using appropriate extractor.

    For known operations (bdp, bdh, etc.), uses optimized extractors.
    For unknown operations, uses a generic flattener.
    """

    JSON = "json"
    """Return raw JSON as a single-column Arrow table.

    Useful for debugging or when you need the full Bloomberg response structure.
    """


class ExtractorHint(str, Enum):
    """Hint for which Arrow extractor to use.

    This is typically auto-detected from the operation, but can be
    overridden for custom use cases.
    """

    REFDATA = "refdata"
    """Reference data extractor: [ticker, field, value, ...]"""

    HISTDATA = "histdata"
    """Historical data extractor: [ticker, date, field, value, ...]"""

    BULK = "bulk"
    """Bulk data extractor: [ticker, field, row_idx, col1, col2, ...]"""

    INTRADAY_BAR = "intraday_bar"
    """Intraday bar extractor: [ticker, time, open, high, low, close, volume, ...]"""

    INTRADAY_TICK = "intraday_tick"
    """Intraday tick extractor: [ticker, time, type, value, size, ...]"""

    GENERIC = "generic"
    """Generic flattener: [path, type, value_str, value_num, value_date]"""

    RAW_JSON = "raw_json"
    """Raw JSON output: [json]"""

    FIELD_INFO = "fieldinfo"
    """Field info extractor: [field, type, description, category]"""


class Format(str, Enum):
    """Output format for reference data (bdp/bdh).

    Controls the shape and typing of the output DataFrame.
    """

    LONG = "long"
    """Long format with all values as strings (default, backwards-compatible).

    Columns: ticker, field, value
    """

    LONG_TYPED = "long_typed"
    """Long format with typed value columns.

    Columns: ticker, field, value_f64, value_i64, value_str, value_bool, value_date, value_ts
    Each row populates one value column based on the field's data type.
    """

    LONG_WITH_METADATA = "long_metadata"
    """Long format with string values and dtype metadata column.

    Columns: ticker, field, value, dtype
    The dtype column contains the Arrow type name (float64, int64, string, etc.)
    """

    WIDE = "wide"
    """Wide format with fields as columns (DEPRECATED).

    Use df.pivot(on='field', index='ticker', values='value') instead.
    """


# Backwards compatibility alias
LongMode = Format


# Mapping from Operation to default ExtractorHint
_OPERATION_TO_EXTRACTOR: dict[str, ExtractorHint] = {
    Operation.REFERENCE_DATA.value: ExtractorHint.REFDATA,
    Operation.HISTORICAL_DATA.value: ExtractorHint.HISTDATA,
    Operation.INTRADAY_BAR.value: ExtractorHint.INTRADAY_BAR,
    Operation.INTRADAY_TICK.value: ExtractorHint.INTRADAY_TICK,
    Operation.FIELD_INFO.value: ExtractorHint.FIELD_INFO,
    Operation.FIELD_SEARCH.value: ExtractorHint.GENERIC,
}


def _get_default_extractor(operation: str, output: OutputMode) -> ExtractorHint:
    """Get the default extractor hint for an operation."""
    if output == OutputMode.JSON:
        return ExtractorHint.RAW_JSON
    return _OPERATION_TO_EXTRACTOR.get(operation, ExtractorHint.GENERIC)


@dataclass
class RequestParams:
    """Validated request parameters for the Bloomberg API.

    This dataclass holds all possible parameters for Bloomberg requests.
    Not all parameters are used for all request types - the Python layer
    validates that required parameters are present for each operation.

    Parameters are validated before being sent to the Rust layer.

    Attributes:
        service: Bloomberg service URI (e.g., "//blp/refdata").
        operation: Request operation name (e.g., "ReferenceDataRequest").
        securities: List of security identifiers (for multi-security requests).
        security: Single security identifier (for intraday requests).
        fields: List of field names to retrieve.
        overrides: List of (field, value) tuples for field overrides.
        elements: List of (name, value) tuples for generic request elements (BQL, bsrch).
        json_elements: JSON string for complex nested request structures (tasvc).
        start_date: Start date for historical requests (YYYYMMDD format).
        end_date: End date for historical requests (YYYYMMDD format).
        start_datetime: Start datetime for intraday requests (ISO format).
        end_datetime: End datetime for intraday requests (ISO format).
        event_type: Event type for intraday bars (TRADE, BID, ASK, etc.).
        interval: Bar interval in minutes for intraday bars.
        options: Additional Bloomberg options as (key, value) tuples.
        field_types: Manual type overrides for fields (for issue #168).
        output: Output format (arrow or json).
        extractor: Override the auto-detected extractor hint.
        format: Output format (LONG, LONG_TYPED, LONG_WITH_METADATA, WIDE).
    """

    service: str | Service
    operation: str | Operation
    securities: Sequence[str] | None = None
    security: str | None = None
    fields: Sequence[str] | None = None
    overrides: Sequence[tuple[str, str]] | None = None
    elements: Sequence[tuple[str, str]] | None = None
    json_elements: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_datetime: str | None = None
    end_datetime: str | None = None
    event_type: str | None = None
    interval: int | None = None
    options: Sequence[tuple[str, str]] | None = None
    field_types: dict[str, str] | None = None
    output: OutputMode = OutputMode.ARROW
    extractor: ExtractorHint | None = None
    format: Format | None = None

    # Computed fields (set during validation)
    _resolved_extractor: ExtractorHint = field(default=ExtractorHint.GENERIC, init=False, repr=False)

    def __post_init__(self) -> None:
        """Convert enums to strings and set defaults."""
        # Convert enums to their string values
        if isinstance(self.service, Service):
            self.service = self.service.value
        if isinstance(self.operation, Operation):
            self.operation = self.operation.value
        if isinstance(self.output, str):
            self.output = OutputMode(self.output)

        # Resolve extractor hint
        if self.extractor is not None:
            self._resolved_extractor = self.extractor
        else:
            self._resolved_extractor = _get_default_extractor(
                self.operation,
                self.output,  # type: ignore[arg-type]
            )

    def validate(self) -> None:
        """Validate parameters for the given operation.

        Raises:
            BlpValidationError: If required parameters are missing or invalid.
        """
        if not self.service:
            raise BlpValidationError("service is required")
        if not self.operation:
            raise BlpValidationError("operation is required")

        op = self.operation

        # Validate based on operation type
        if op == Operation.REFERENCE_DATA.value:
            self._validate_reference_data()
        elif op == Operation.HISTORICAL_DATA.value:
            self._validate_historical_data()
        elif op == Operation.INTRADAY_BAR.value:
            self._validate_intraday_bar()
        elif op == Operation.INTRADAY_TICK.value:
            self._validate_intraday_tick()
        elif op in (Operation.FIELD_INFO.value, Operation.FIELD_SEARCH.value):
            self._validate_field_request()
        # Unknown operations: no validation (power user mode)

    def _validate_reference_data(self) -> None:
        """Validate ReferenceDataRequest parameters."""
        if not self.securities:
            raise BlpValidationError("securities is required for ReferenceDataRequest")
        if not self.fields:
            raise BlpValidationError("fields is required for ReferenceDataRequest")

    def _validate_historical_data(self) -> None:
        """Validate HistoricalDataRequest parameters."""
        if not self.securities:
            raise BlpValidationError("securities is required for HistoricalDataRequest")
        if not self.fields:
            raise BlpValidationError("fields is required for HistoricalDataRequest")
        if not self.start_date:
            raise BlpValidationError("start_date is required for HistoricalDataRequest")
        if not self.end_date:
            raise BlpValidationError("end_date is required for HistoricalDataRequest")

    def _validate_intraday_bar(self) -> None:
        """Validate IntradayBarRequest parameters."""
        if not self.security:
            raise BlpValidationError("security is required for IntradayBarRequest")
        if not self.event_type:
            raise BlpValidationError("event_type is required for IntradayBarRequest")
        if self.interval is None:
            raise BlpValidationError("interval is required for IntradayBarRequest")
        if not self.start_datetime:
            raise BlpValidationError("start_datetime is required for IntradayBarRequest")
        if not self.end_datetime:
            raise BlpValidationError("end_datetime is required for IntradayBarRequest")

    def _validate_intraday_tick(self) -> None:
        """Validate IntradayTickRequest parameters."""
        if not self.security:
            raise BlpValidationError("security is required for IntradayTickRequest")
        if not self.start_datetime:
            raise BlpValidationError("start_datetime is required for IntradayTickRequest")
        if not self.end_datetime:
            raise BlpValidationError("end_datetime is required for IntradayTickRequest")

    def _validate_field_request(self) -> None:
        """Validate FieldInfoRequest/FieldSearchRequest parameters."""
        if not self.fields:
            raise BlpValidationError("fields is required for field metadata requests")

    def to_dict(self) -> dict:
        """Convert to dictionary for passing to Rust.

        Returns:
            Dictionary with only non-None values, suitable for Rust consumption.
        """
        result: dict = {
            "service": self.service,
            "operation": self.operation,
            "extractor": self._resolved_extractor.value,
        }

        if self.securities is not None:
            result["securities"] = list(self.securities)
        if self.security is not None:
            result["security"] = self.security
        if self.fields is not None:
            # FieldInfoRequest uses "id" array in Bloomberg API, mapped to field_ids in Rust
            if self.operation == Operation.FIELD_INFO.value:
                result["field_ids"] = list(self.fields)
            # FieldSearchRequest uses search_spec (single string)
            elif self.operation == Operation.FIELD_SEARCH.value:
                result["search_spec"] = self.fields[0] if self.fields else ""
            else:
                result["fields"] = list(self.fields)
        if self.overrides is not None:
            result["overrides"] = list(self.overrides)
        if self.elements is not None:
            result["elements"] = list(self.elements)
        if self.json_elements is not None:
            result["json_elements"] = self.json_elements
        if self.start_date is not None:
            result["start_date"] = self.start_date
        if self.end_date is not None:
            result["end_date"] = self.end_date
        if self.start_datetime is not None:
            result["start_datetime"] = self.start_datetime
        if self.end_datetime is not None:
            result["end_datetime"] = self.end_datetime
        if self.event_type is not None:
            result["event_type"] = self.event_type
        if self.interval is not None:
            result["interval"] = self.interval
        if self.options is not None:
            result["options"] = list(self.options)
        if self.field_types is not None:
            result["field_types"] = self.field_types
        if self.format is not None:
            # Pass format value to Rust (handles LONG, LONG_TYPED, LONG_WITH_METADATA)
            # WIDE is handled in Python layer via pivot
            result["format"] = self.format.value if isinstance(self.format, Format) else self.format

        return result
