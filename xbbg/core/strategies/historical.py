"""Historical data strategies."""

from __future__ import annotations

import logging
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.core.utils import utils as utils_module

logger = logging.getLogger(__name__)


class HistoricalRequestBuilder:
    """Strategy for building Bloomberg historical data (BDH) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build historical data request."""
        tickers = request.request_opts.get("tickers", [request.ticker])
        flds = request.request_opts.get("flds", ["Last_Price"])
        start_date = request.request_opts.get("start_date")
        end_date = request.request_opts.get("end_date", "today")
        adjust = request.request_opts.get("adjust")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        e_dt = utils_module.fmt_dt(end_date, fmt="%Y%m%d")
        if start_date is None:
            start_date = pd.Timestamp(e_dt) - pd.Timedelta(weeks=8)
        s_dt = utils_module.fmt_dt(start_date, fmt="%Y%m%d")

        blp_request = process.create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            **all_kwargs,
        )
        process.init_request(
            request=blp_request,
            tickers=tickers,
            flds=flds,
            start_date=s_dt,
            end_date=e_dt,
            adjust=adjust,
            **all_kwargs,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Sending Bloomberg historical data request for %d ticker(s), %d field(s)",
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class HistoricalTransformer:
    """Strategy for transforming Bloomberg historical data responses.

    Returns data in semi-long format (ticker, date, field1, field2, ...).
    MultiIndex creation is handled by to_output() if format='wide' and backend='pandas'.
    """

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform historical data response.

        Args:
            raw_data: Arrow table with columns: ticker, date, field1, field2, ...
            request: Data request containing tickers and fields.
            exchange_info: Exchange information (unused in Arrow path).
            session_window: Session window (unused in Arrow path).

        Returns:
            Arrow table in semi-long format, sorted by ticker and date.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return raw_data

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Lowercase field column names for backwards compatibility with v0.10.x
        # Bloomberg returns field names in uppercase, but v0.10 always lowercased them
        # Skip 'ticker' and 'date' columns which should stay as-is
        rename_map = {col: col.lower() for col in df.columns if col not in ("ticker", "date")}
        if rename_map:
            df = df.rename(rename_map)

        # Sort by ticker and date for consistent output
        df = df.sort("ticker", "date")

        # Return as Arrow table
        return nw.to_native(df)


__all__ = ["HistoricalRequestBuilder", "HistoricalTransformer"]
