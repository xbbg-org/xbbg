"""Bloomberg Technical Analysis API (TASVC).

Provides functions for technical analysis studies like SMA, EMA, RSI, MACD, etc.
Studies are dynamically discovered from the Bloomberg service schema and cached.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from xbbg.api.technical.schema import get_studies, refresh_cache

logger = logging.getLogger(__name__)

__all__ = ["bta", "bta_studies", "refresh_studies"]


def _get_study_types() -> dict[str, dict[str, Any]]:
    """Get study types, loading from cache or discovering from service."""
    return get_studies()


def bta_studies(study: str | None = None) -> pd.DataFrame:
    """List available technical analysis studies and their parameters.

    Args:
        study: Optional study name to get details for a specific study.
            If None, returns all available studies.

    Returns:
        pd.DataFrame: DataFrame with study information.
            If study is None: columns are [study, description, output_field]
            If study is specified: columns are [parameter, type, default, description]

    Examples:
        >>> from xbbg import blp  # doctest: +SKIP
        >>> # List all available studies
        >>> studies = blp.bta_studies()  # doctest: +SKIP
        >>> print(studies.head())  # doctest: +SKIP

        >>> # Get parameters for a specific study
        >>> params = blp.bta_studies('RSI')  # doctest: +SKIP
        >>> print(params)  # doctest: +SKIP
    """
    study_types = _get_study_types()

    if study is None:
        # Return list of all studies
        data = []
        for name, info in study_types.items():
            data.append(
                {
                    "study": name,
                    "description": info["description"],
                    "output_field": info["output"],
                }
            )
        return pd.DataFrame(data).set_index("study")

    # Return parameters for specific study
    study_upper = study.upper()
    if study_upper not in study_types:
        available = ", ".join(sorted(study_types.keys()))
        raise ValueError(f"Unknown study '{study}'. Available studies: {available}")

    info = study_types[study_upper]
    data = []
    for param_name, param_info in info["params"].items():
        type_val = param_info["type"]
        type_name = type_val.__name__ if isinstance(type_val, type) else str(type_val)
        data.append(
            {
                "parameter": param_name,
                "type": type_name,
                "default": param_info["default"],
                "description": param_info["description"],
            }
        )
    return pd.DataFrame(data).set_index("parameter")


def refresh_studies() -> pd.DataFrame:
    """Refresh the study cache from Bloomberg service.

    Call this to update the cached studies when connected to Bloomberg.

    Returns:
        pd.DataFrame: Updated list of available studies.
    """
    refresh_cache()
    return bta_studies()


def bta(
    ticker: str,
    study: str,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    periodicity: str = "DAILY",
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg Technical Analysis - retrieve technical study data.

    Args:
        ticker: Bloomberg security identifier (e.g., 'IBM US Equity').
        study: Technical study name (e.g., 'SMA', 'RSI', 'MACD').
            Use bta_studies() to see available studies.
        start_date: Start date for the study data.
        end_date: End date for the study data.
        periodicity: Data periodicity ('DAILY', 'WEEKLY', 'MONTHLY').
        **kwargs: Study-specific parameters (e.g., period=20 for SMA).
            Use bta_studies(study) to see available parameters.

    Returns:
        pd.DataFrame: DataFrame with date index and study values.

    Examples:
        >>> from xbbg import blp  # doctest: +SKIP
        >>> # 20-period Simple Moving Average
        >>> sma = blp.bta('IBM US Equity', 'SMA', period=20,
        ...               start_date='2024-01-01', end_date='2024-06-30')  # doctest: +SKIP

        >>> # 14-period RSI
        >>> rsi = blp.bta('AAPL US Equity', 'RSI', period=14,
        ...               start_date='2024-01-01')  # doctest: +SKIP

        >>> # MACD with custom parameters
        >>> macd = blp.bta('MSFT US Equity', 'MACD',
        ...                maPeriod1=12, maPeriod2=26, sigPeriod=9,
        ...                start_date='2024-01-01')  # doctest: +SKIP

        >>> # Bollinger Bands
        >>> boll = blp.bta('SPY US Equity', 'BOLLINGER',
        ...                period=20, upperBand=2.0, lowerBand=2.0,
        ...                start_date='2024-01-01')  # doctest: +SKIP
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, bta_pipeline_config

    study_types = _get_study_types()

    # Validate study
    study_upper = study.upper()
    if study_upper not in study_types:
        available = ", ".join(sorted(study_types.keys()))
        raise ValueError(f"Unknown study '{study}'. Available studies: {available}")

    study_info = study_types[study_upper]

    # Split kwargs into infrastructure and study params
    split = split_kwargs(**kwargs)

    # Build study parameters with defaults
    study_params = {}
    for param_name, param_info in study_info["params"].items():
        # Check if provided in kwargs, otherwise use default
        if param_name in split.override_like:
            study_params[param_name] = split.override_like[param_name]
        else:
            study_params[param_name] = param_info["default"]

    # Build request
    request = (
        RequestBuilder()
        .ticker(ticker)
        .date(end_date if end_date else "today")
        .context(split.infra)
        .cache_policy(enabled=False)  # TA typically not cached
        .request_opts(
            study=study_upper,
            study_attribute=study_info["attribute"],
            study_params=study_params,
            start_date=start_date,
            end_date=end_date,
            periodicity=periodicity,
        )
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=bta_pipeline_config())
    return pipeline.run(request)
