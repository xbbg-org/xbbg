"""Intraday data strategies."""

from __future__ import annotations

import logging
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.contracts import DataRequest, SessionWindow

logger = logging.getLogger(__name__)


class IntradayRequestBuilder:
    """Strategy for building Bloomberg intraday bar data requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build intraday bar data request."""
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **request.request_opts}

        # Check if this is a multi-day request with explicit datetime range
        if request.is_multi_day():
            # Use explicit datetime range - convert to UTC ISO format
            time_fmt = "%Y-%m-%dT%H:%M:%S"
            assert request.start_datetime is not None  # guaranteed by is_multi_day()
            assert request.end_datetime is not None
            start_ts = pd.Timestamp(request.start_datetime)
            end_ts = pd.Timestamp(request.end_datetime)

            # If timestamps are timezone-aware, convert to UTC
            # If timezone-naive, assume they are already in UTC
            if start_ts.tzinfo is not None:
                start_dt = start_ts.tz_convert("UTC").strftime(time_fmt)
            else:
                start_dt = start_ts.strftime(time_fmt)

            if end_ts.tzinfo is not None:
                end_dt = end_ts.tz_convert("UTC").strftime(time_fmt)
            else:
                end_dt = end_ts.strftime(time_fmt)
        else:
            # Use session window for single-day requests
            start_dt = session_window.start_time
            end_dt = session_window.end_time

            if not start_dt or not end_dt:
                raise ValueError("Invalid session window for Bloomberg request")

            # Convert session window times from exchange timezone to UTC
            # Session window times are timezone-naive strings in the exchange timezone,
            # but Bloomberg expects UTC times
            if session_window.timezone:
                from xbbg.markets import convert_session_times_to_utc

                start_dt, end_dt = convert_session_times_to_utc(
                    start_time=start_dt,
                    end_time=end_dt,
                    exchange_tz=session_window.timezone,
                )
            else:
                # No timezone info - assume UTC (fallback)
                logger.warning("Session window has no timezone info, assuming UTC for Bloomberg request")

        settings = [
            ("security", request.ticker),
            ("eventType", request.event_type),
            ("interval", request.interval),
            ("startDateTime", start_dt),
            ("endDateTime", end_dt),
        ]
        if request.interval_has_seconds:
            settings.append(("intervalHasSeconds", True))

        blp_request = process.create_request(
            service="//blp/refdata",
            request="IntradayBarRequest",
            settings=settings,
            **all_kwargs,
        )

        if request.is_multi_day():
            logger.debug(
                "Sending Bloomberg intraday bar data request for %s / %s to %s / %s",
                request.ticker,
                start_dt,
                end_dt,
                request.event_type,
            )
        else:
            logger.debug(
                "Sending Bloomberg intraday bar data request for %s / %s / %s",
                request.ticker,
                request.to_date_string(),
                request.event_type,
            )

        return blp_request, ctx_kwargs


class IntradayTransformer:
    """Strategy for transforming Bloomberg intraday bar data responses.

    Timezone behaviour (restored from v0.7.x):
        Bloomberg returns intraday bar timestamps in UTC.  By default,
        this transformer converts them to the **exchange local timezone**
        so the output matches what ``bdtick`` returns and what v0.7.x
        ``bdib`` returned.

        The target timezone is resolved in this order:
        1. ``request.tz`` — explicit caller override (e.g. ``tz='UTC'``).
        2. ``exchange_info.tz`` — exchange local timezone from Bloomberg.
        3. Fall through with no conversion (data stays in UTC).

        Pass ``tz='UTC'`` to ``bdib()`` / ``abdib()`` to keep timestamps
        in UTC and skip conversion entirely.
    """

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform intraday bar data response.

        Args:
            raw_data: Arrow table with intraday bar data.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information including timezone.
            session_window: Session window for filtering (single-day requests).

        Returns:
            Arrow table in semi-long format (ticker, time, field1, field2, ...).
        """
        # Wrap Arrow table with narwhals
        df = nw.from_native(raw_data, eager_only=True)

        # Check for empty data or missing time column
        if df.shape[0] == 0 or "time" not in df.columns:
            # Return empty Arrow table with expected schema
            return pa.table({"ticker": [], "time": []})

        # Rename numEvents to num_trds for consistency
        if "numEvents" in df.columns:
            df = df.rename({"numEvents": "num_trds"})

        # Add ticker column for semi-long format
        df = df.with_columns(nw.lit(request.ticker).alias("ticker"))

        # Sort by time column
        df = df.sort("time")

        # ------------------------------------------------------------------
        # Timezone conversion: UTC → target timezone
        #
        # Bloomberg IntradayBarRequest always returns timestamps in UTC.
        # Convert to the target timezone so the caller sees exchange-local
        # times by default (matching v0.7.x behaviour and bdtick).
        # ------------------------------------------------------------------
        target_tz = request.tz  # explicit caller override
        if target_tz is None and not exchange_info.empty and "tz" in exchange_info.index:
            target_tz = exchange_info.tz  # exchange local timezone

        if target_tz is not None:
            # Convert via pandas (narwhals tz support is limited)
            native = nw.to_native(df)
            time_col = native.column("time")
            as_pd = time_col.to_pandas()

            # Localize to UTC first (Bloomberg returns UTC), then convert
            if as_pd.dt.tz is None:
                as_pd = as_pd.dt.tz_localize("UTC")
            as_pd = as_pd.dt.tz_convert(target_tz)

            # Rebuild Arrow column and replace in table
            new_time = pa.Array.from_pandas(as_pd)
            col_idx = native.schema.get_field_index("time")
            native = native.set_column(col_idx, "time", new_time)
            df = nw.from_native(native, eager_only=True)

        # Reorder columns to have ticker first, then time, then other fields
        cols = df.columns
        other_cols = [c for c in cols if c not in ("ticker", "time")]
        df = df.select(["ticker", "time"] + other_cols)

        # Return as Arrow table
        return nw.to_native(df)


__all__ = ["IntradayRequestBuilder", "IntradayTransformer"]
