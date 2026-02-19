"""Reference data strategies."""

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


class ReferenceRequestBuilder:
    """Strategy for building Bloomberg reference data (BDP) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build reference data request."""
        tickers = request.request_opts.get("tickers", [request.ticker])
        flds = request.request_opts.get("flds", [])

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs}

        tickers = utils_module.normalize_tickers(tickers)
        flds = utils_module.normalize_flds(flds)

        blp_request = process.create_request(
            service="//blp/refdata",
            request="ReferenceDataRequest",
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=tickers, flds=flds, **all_kwargs)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Sending Bloomberg reference data request for %d ticker(s), %d field(s)",
                len(tickers),
                len(flds),
            )

        return blp_request, ctx_kwargs


class ReferenceTransformer:
    """Strategy for transforming Bloomberg reference data responses to Arrow format."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform reference data response.

        Args:
            raw_data: Arrow table with columns: ticker, field, value
            request: Data request containing context and options
            exchange_info: Exchange information (unused in Arrow path)
            session_window: Session window (unused in Arrow path)

        Returns:
            Arrow table sorted by ticker with standardized column names
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Check for empty result (all values null in required columns)
        required_cols = ["ticker", "field"]
        for col in required_cols:
            if col not in df.columns:
                return pa.table({})

        # Get column name mappings from context
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        col_maps = ctx_kwargs.get("col_maps", {}) or {}

        # Lowercase field names for backwards compatibility with v0.10.x
        # Bloomberg returns field names in uppercase, but v0.10 always lowercased them
        if "field" in df.columns:
            df = df.with_columns(nw.col("field").str.to_lowercase().alias("field"))

        # Get original ticker order from request for sorting
        original_tickers = request.request_opts.get("tickers", [request.ticker])
        original_tickers = utils_module.normalize_tickers(original_tickers)
        if original_tickers is None:
            original_tickers = []
        elif not isinstance(original_tickers, list):
            original_tickers = list(original_tickers)

        # Create ticker order mapping for sorting
        ticker_order = {t: i for i, t in enumerate(original_tickers)}

        # Add sort order column based on original ticker order
        # Tickers not in original list get a high order value
        max_order = len(original_tickers)
        df = df.with_columns(
            nw.col("ticker")
            .replace_strict(
                ticker_order,
                default=max_order,
            )
            .alias("_ticker_order")
        )

        # Sort by ticker order to preserve original request order
        df = df.sort("_ticker_order", "_ticker_order")

        # Drop the temporary sort column
        df = df.drop("_ticker_order")

        # Standardize column names to snake_case
        def standardize_col_name(name: str) -> str:
            if name in col_maps:
                return col_maps[name]
            return name.lower().replace(" ", "_").replace("-", "_")

        # Rename columns
        rename_map = {col: standardize_col_name(col) for col in df.columns}
        df = df.rename(rename_map)

        # Convert back to Arrow table
        return nw.to_native(df)


__all__ = ["ReferenceRequestBuilder", "ReferenceTransformer"]
