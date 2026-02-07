"""Quote request strategies."""

from __future__ import annotations

import logging
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.core.infra import conn

logger = logging.getLogger(__name__)


class BqrRequestBuilder:
    """Strategy for building Bloomberg Quote Request (BQR) using IntradayTickRequest.

    BQR emulates the Excel =BQR() function by using IntradayTickRequest with
    BID/ASK event types and broker codes enabled. This provides dealer quote
    data similar to what the Excel formula returns.
    """

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BQR request using IntradayTickRequest.

        Args:
            request: Data request containing ticker, date range, and options.
            session_window: Session window (unused for BQR).

        Returns:
            Tuple of (Bloomberg request, context kwargs).
        """
        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Get request options
        opts = request.request_opts
        ticker = opts.get("ticker", request.ticker)
        event_types = opts.get("event_types", ["BID", "ASK"])
        include_broker_codes = opts.get("include_broker_codes", True)
        include_condition_codes = opts.get("include_condition_codes", False)
        include_exchange_codes = opts.get("include_exchange_codes", False)

        # Parse date offset or explicit dates
        date_offset = opts.get("date_offset")
        start_date = opts.get("start_date")
        end_date = opts.get("end_date")

        # Calculate time range
        now = pd.Timestamp.now(tz="UTC")
        time_fmt = "%Y-%m-%dT%H:%M:%S"

        if date_offset:
            # Parse offset like "-2d", "-1w", etc.
            end_dt = now
            start_dt = self._parse_date_offset(date_offset, now)
        elif start_date:
            start_dt = pd.Timestamp(start_date, tz="UTC")
            end_dt = pd.Timestamp(end_date, tz="UTC") if end_date else now
        else:
            # Default: last 2 days
            end_dt = now
            start_dt = now - pd.Timedelta(days=2)

        # Create IntradayTickRequest
        service = conn.bbg_service(service="//blp/refdata", **ctx_kwargs)
        blp_request = service.createRequest("IntradayTickRequest")

        # Set security
        blp_request.set("security", ticker)

        # Set time range
        blp_request.set("startDateTime", start_dt.strftime(time_fmt))
        blp_request.set("endDateTime", end_dt.strftime(time_fmt))

        # Add event types
        event_types_elem = blp_request.getElement("eventTypes")
        for event_type in event_types:
            event_types_elem.appendValue(event_type)

        # Enable broker codes (key for BQR/AllQuotes functionality)
        blp_request.set("includeBrokerCodes", include_broker_codes)

        # Optional: condition and exchange codes
        if include_condition_codes:
            blp_request.set("includeConditionCodes", True)
        if include_exchange_codes:
            blp_request.set("includeExchangeCodes", True)

        logger.debug(
            "Sending BQR request for %s from %s to %s with event types %s",
            ticker,
            start_dt.strftime(time_fmt),
            end_dt.strftime(time_fmt),
            event_types,
        )

        return blp_request, ctx_kwargs

    def _parse_date_offset(self, offset: str, reference: pd.Timestamp) -> pd.Timestamp:
        """Parse date offset string like '-2d', '-1w', '-1m'.

        Args:
            offset: Offset string (e.g., '-2d', '-1w', '-1m', '-3h').
            reference: Reference timestamp.

        Returns:
            Calculated timestamp.
        """
        import re

        offset = offset.strip().lower()

        # Match pattern like -2d, -1w, -1m, -3h
        match = re.match(r"^(-?\d+)([dwmh])$", offset)
        if not match:
            raise ValueError(f"Invalid date offset format: {offset}. Use format like '-2d', '-1w', '-1m', '-3h'")

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "d":
            return reference + pd.Timedelta(days=value)
        if unit == "w":
            return reference + pd.Timedelta(weeks=value)
        if unit == "m":
            # Approximate month as 30 days
            return reference + pd.Timedelta(days=value * 30)
        if unit == "h":
            return reference + pd.Timedelta(hours=value)
        raise ValueError(f"Unknown time unit: {unit}")


class BqrTransformer:
    """Strategy for transforming Bloomberg BQR (Quote Request) responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BQR tick response to Arrow table.

        Args:
            raw_data: Arrow table with tick data including broker codes.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with standardized column names and sorted by time.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Standardize column names
        rename_map = {
            "time": "time",
            "type": "event_type",
            "value": "price",
            "size": "size",
            "brokerBuyCode": "broker_buy",
            "brokerSellCode": "broker_sell",
            "conditionCodes": "condition_codes",
            "exchangeCode": "exchange",
        }

        # Only rename columns that exist
        actual_renames = {k: v for k, v in rename_map.items() if k in df.columns}
        if actual_renames:
            df = df.rename(actual_renames)

        # Add ticker column
        ticker = request.request_opts.get("ticker", request.ticker)
        df = df.with_columns(nw.lit(ticker).alias("ticker"))

        # Sort by time
        if "time" in df.columns:
            df = df.sort("time")

        # Reorder columns: ticker first, then time, then others
        cols = df.columns
        priority_cols = ["ticker", "time", "event_type", "price", "size", "broker_buy", "broker_sell"]
        ordered_cols = [c for c in priority_cols if c in cols]
        other_cols = [c for c in cols if c not in priority_cols]
        df = df.select(ordered_cols + other_cols)

        return nw.to_native(df)
