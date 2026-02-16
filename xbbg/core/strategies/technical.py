"""Technical analysis strategies."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import pyarrow as pa

from xbbg.core.domain.contracts import DataRequest, SessionWindow
from xbbg.core.infra import conn

logger = logging.getLogger(__name__)


class BtaRequestBuilder:
    """Strategy for building Bloomberg Technical Analysis (TASVC) requests."""

    def build_request(
        self,
        request: DataRequest,
        session_window: SessionWindow,
    ) -> tuple[Any, dict[str, Any]]:
        """Build TASVC studyRequest.

        The TASVC request has a nested structure:
        studyRequest = {
            priceSource = {
                securityName = "IBM US Equity"
                dataRange = {
                    historical = {
                        startDate, endDate, periodicitySelection, ...
                    }
                }
            }
            studyAttributes = {
                <studyType>StudyAttributes = {
                    period, priceSourceClose, ...
                }
            }
        }
        """
        ctx_kwargs = request.context.to_kwargs() if request.context else {}

        # Get request options
        opts = request.request_opts
        study = opts.get("study", "SMA")
        study_attribute = opts.get("study_attribute", "smavgStudyAttributes")
        study_params = opts.get("study_params", {})
        start_date = opts.get("start_date")
        end_date = opts.get("end_date")
        periodicity = opts.get("periodicity", "DAILY")

        # Format dates
        if start_date:
            start_date = pd.Timestamp(start_date).strftime("%Y%m%d")
        else:
            # Default to 1 year ago
            start_date = (pd.Timestamp("today") - pd.Timedelta(days=365)).strftime("%Y%m%d")

        end_date = pd.Timestamp(end_date).strftime("%Y%m%d") if end_date else pd.Timestamp("today").strftime("%Y%m%d")

        # Get service and create request
        service = conn.bbg_service(service="//blp/tasvc", **ctx_kwargs)
        blp_request = service.createRequest("studyRequest")

        # Set up priceSource
        price_source = blp_request.getElement("priceSource")
        price_source.setElement("securityName", request.ticker)

        # Set up dataRange.historical
        data_range = price_source.getElement("dataRange")
        historical = data_range.getElement("historical")
        historical.setElement("startDate", start_date)
        historical.setElement("endDate", end_date)
        historical.setElement("periodicitySelection", periodicity)

        # Set up studyAttributes
        study_attrs = blp_request.getElement("studyAttributes")
        study_elem = study_attrs.getElement(study_attribute)

        for param_name, param_value in study_params.items():
            study_elem.setElement(param_name, param_value)

        logger.debug("Sending TASVC studyRequest for %s with %s study", request.ticker, study)

        return blp_request, ctx_kwargs


class BtaTransformer:
    """Strategy for transforming Bloomberg TASVC responses."""

    def transform(
        self,
        raw_data: pa.Table,
        request: DataRequest,
        exchange_info: pd.Series,
        session_window: SessionWindow,
    ) -> pa.Table:
        """Transform TASVC response to Arrow table.

        Args:
            raw_data: Arrow table with date and study value columns.
            request: Data request with ticker and other metadata.
            exchange_info: Exchange information (unused).
            session_window: Session window (unused).

        Returns:
            Arrow table with date column converted to datetime.
        """
        # Handle empty table
        if raw_data.num_rows == 0:
            return pa.table({})

        # Convert to pandas for date parsing (handles timezone-aware strings)
        df_pd = raw_data.to_pandas()

        # Convert date column to datetime if present
        if "date" in df_pd.columns and df_pd["date"].dtype == object:
            df_pd["date"] = pd.to_datetime(df_pd["date"], utc=True)

        # Sort by date for consistent output
        if "date" in df_pd.columns:
            df_pd = df_pd.sort_values("date").reset_index(drop=True)

        # Return as Arrow table
        return pa.Table.from_pandas(df_pd, preserve_index=False)


__all__ = ["BtaRequestBuilder", "BtaTransformer"]
