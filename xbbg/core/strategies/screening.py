"""Screening and query strategies."""

from __future__ import annotations

import logging
from typing import Any

import narwhals as nw
import pandas as pd
import pyarrow as pa

from xbbg.core import process
from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.core.infra import conn
from xbbg.core.utils import utils as utils_module

logger = logging.getLogger(__name__)


class BeqsRequestBuilder:
    """Strategy for building Bloomberg BEQS requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BEQS request."""
        screen = request.request_opts.get("screen", "")
        asof = request.request_opts.get("asof")
        typ = request.request_opts.get("typ", "PRIVATE")
        group = request.request_opts.get("group", "General")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        all_kwargs = {**ctx_kwargs, **request.override_kwargs, **request.request_opts}

        blp_request = process.create_request(
            service="//blp/refdata",
            request="BeqsRequest",
            settings=[
                ("screenName", screen),
                ("screenType", "GLOBAL" if typ[0].upper() in ["G", "B"] else "PRIVATE"),
                ("Group", group),
            ],
            ovrds=[("PiTDate", utils_module.fmt_dt(asof, "%Y%m%d"))] if asof else [],
            **all_kwargs,
        )

        logger.debug(
            "Sending Bloomberg Equity Screening (BEQS) request for screen: %s, type: %s, group: %s",
            screen,
            typ,
            group,
        )

        return blp_request, ctx_kwargs


class BeqsTransformer:
    """Strategy for transforming Bloomberg BEQS responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BEQS response.

        Args:
            raw_data: Arrow table with columns: ticker, field, value
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with tickers as rows and fields as columns.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Check for required columns
        if "ticker" not in df.columns or "field" not in df.columns:
            return pa.table({})

        # Pivot using narwhals: ticker as index, field as columns, value as values
        pivoted = df.pivot(on="field", index="ticker", values="value")

        # Standardize column names to snake_case
        rename_map = {col: str(col).lower().replace(" ", "_").replace("-", "_") for col in pivoted.columns}
        pivoted = pivoted.rename(rename_map)

        # Return as Arrow table
        return nw.to_native(pivoted)


class BsrchRequestBuilder:
    """Strategy for building Bloomberg BSRCH requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BSRCH request."""
        from xbbg.core.infra.blpapi_wrapper import blpapi

        domain = request.request_opts.get("domain", "")
        overrides = request.request_opts.get("overrides")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Create request using exrsvc service
        exr_service = conn.bbg_service(service="//blp/exrsvc", **ctx_kwargs)
        blp_request = exr_service.createRequest("ExcelGetGridRequest")

        # Set Domain element
        blp_request.getElement(blpapi.Name("Domain")).setValue(domain)

        # Add overrides if provided
        if overrides:
            overrides_elem = blp_request.getElement(blpapi.Name("Overrides"))
            for name, value in overrides.items():
                override_item = overrides_elem.appendElement()
                override_item.setElement(blpapi.Name("name"), name)
                override_item.setElement(blpapi.Name("value"), str(value))

        if logger.isEnabledFor(logging.DEBUG):
            override_info = f" with {len(overrides)} override(s)" if overrides else ""
            logger.debug("Sending Bloomberg SRCH request for domain: %s%s", domain, override_info)

        return blp_request, ctx_kwargs


class BsrchTransformer:
    """Strategy for transforming Bloomberg BSRCH responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BSRCH response.

        Args:
            raw_data: Arrow table with search results.
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table (pass-through, no transformation needed).
        """
        # BSRCH returns data in a good format already, just pass through
        return raw_data


class BqlRequestBuilder:
    """Strategy for building Bloomberg BQL requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build BQL request."""
        query = request.request_opts.get("query", "")
        params = request.request_opts.get("params")
        overrides = request.request_opts.get("overrides")

        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        settings = [("expression", query)]
        if params:
            settings.extend([(str(k), v) for k, v in params.items()])

        blp_request = process.create_request(
            service="//blp/bqlsvc",
            request="sendQuery",
            settings=settings,
            ovrds=overrides or [],
            **ctx_kwargs,
        )

        logger.debug("Sending Bloomberg Query Language (BQL) request")

        return blp_request, ctx_kwargs


class BqlTransformer:
    """Strategy for transforming Bloomberg BQL responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform BQL response.

        Args:
            raw_data: Arrow table with BQL query results.
            request: Data request (unused).
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with date columns auto-converted.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return raw_data

        # Wrap with narwhals for transformations
        df = nw.from_native(raw_data, eager_only=True)

        # Auto-convert date columns by name pattern
        # Identify potential date columns by name
        date_cols = [
            col for col in df.columns if any(keyword in str(col).lower() for keyword in ["date", "dt", "time"])
        ]

        if not date_cols:
            return nw.to_native(df)

        # Process each potential date column using narwhals
        for col in date_cols:
            # Get the column dtype - only convert string columns
            col_dtype = df.select(col).schema[col]

            # Check if it's a string type (narwhals String dtype)
            if col_dtype == nw.String:
                from contextlib import suppress

                # Attempt datetime conversion using narwhals
                with suppress(Exception):
                    df = df.with_columns(nw.col(col).str.to_datetime(format=None).alias(col))

        return nw.to_native(df)
