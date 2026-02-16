"""Block data strategies."""

from __future__ import annotations

import logging
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.contracts import DataRequest, SessionWindow

logger = logging.getLogger(__name__)


class BlockDataRequestBuilder:
    """Strategy for building Bloomberg block data (BDS) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build block data request."""
        ticker = request.ticker
        fld = request.request_opts.get("fld", "")
        use_port = request.request_opts.get("use_port", False)

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        # Exclude request-specific options (fld, use_port) from kwargs passed to create_request
        # These are not Bloomberg overrides and should not be added to the request
        request_specific_opts = {"fld", "use_port"}
        filtered_request_opts = {k: v for k, v in request.request_opts.items() if k not in request_specific_opts}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **filtered_request_opts}

        # Set has_date if not already set
        if "has_date" not in all_kwargs:
            all_kwargs["has_date"] = True

        blp_request = process.create_request(
            service="//blp/refdata",
            request="PortfolioDataRequest" if use_port else "ReferenceDataRequest",
            **all_kwargs,
        )
        process.init_request(request=blp_request, tickers=ticker, flds=fld, **all_kwargs)

        logger.debug("Sending Bloomberg block data request for ticker: %s, field: %s", ticker, fld)

        return blp_request, ctx_kwargs


class BlockDataTransformer:
    """Strategy for transforming Bloomberg block data (BDS) responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform block data response."""
        if raw_data.num_rows == 0:
            return pa.table({})

        df = nw.from_native(raw_data, eager_only=True)

        # Get column name mappings from context (if provided via col_maps kwarg)
        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        col_maps = ctx_kwargs.get("col_maps", {}) or {}

        # Standardize column names to snake_case (backwards compatibility with v0.10.x)
        # e.g., "Declared Date" -> "declared_date"
        def standardize_col_name(name: str) -> str:
            if name in col_maps:
                return col_maps[name]
            return name.lower().replace(" ", "_").replace("-", "_")

        rename_map = {col: standardize_col_name(col) for col in df.columns}

        # Deduplicate: when different original names map to the same
        # standardized name (e.g. "ticker" and "Ticker" both → "ticker"),
        # suffix later occurrences so narwhals/polars don't reject the rename.
        seen: dict[str, int] = {}
        for old_name in list(rename_map):
            new_name = rename_map[old_name]
            if new_name in seen:
                seen[new_name] += 1
                rename_map[old_name] = f"{new_name}_{seen[new_name]}"
            else:
                seen[new_name] = 0

        df = df.rename(rename_map)

        return nw.to_native(df)


__all__ = ["BlockDataRequestBuilder", "BlockDataTransformer"]
