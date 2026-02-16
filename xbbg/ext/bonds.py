"""Bloomberg Fixed Income Bond Analytics API.

This module provides convenience functions for bond analytics including
risk measures, spread analysis, cash flows, and key rate durations.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING

from xbbg.backend import Backend, Format

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

__all__ = [
    "bond_info",
    "bond_risk",
    "bond_spreads",
    "bond_cashflows",
    "bond_key_rates",
    "bond_curve",
]

# Bond metadata fields
_FLD_NAME = "NAME"
_FLD_SECURITY_DES = "SECURITY_DES"
_FLD_CRNCY = "CRNCY"
_FLD_CPNTYP = "CPN_TYP"
_FLD_CPN = "CPN"
_FLD_MATURITY = "MATURITY"
_FLD_PAR_AMT = "PAR_AMT"
_FLD_AMT_OUTSTANDING = "AMT_OUTSTANDING"
_FLD_ISSUE_DT = "ISSUE_DT"
_FLD_COUNTRY = "COUNTRY_ISO"
_FLD_INDUSTRY_SECTOR = "INDUSTRY_SECTOR"
_FLD_BB_COMPOSITE = "BB_COMPOSITE"
_FLD_RTG_SP = "RTG_SP"
_FLD_RTG_MOODY = "RTG_MOODY"
_FLD_RTG_FITCH = "RTG_FITCH"
_FLD_CALLABLE = "CALLABLE"
_FLD_PUTABLE = "PUTABLE"
_FLD_SINKABLE = "SINKABLE"

_BOND_INFO_FIELDS: list[str] = [
    _FLD_NAME,
    _FLD_SECURITY_DES,
    _FLD_CRNCY,
    _FLD_CPNTYP,
    _FLD_CPN,
    _FLD_MATURITY,
    _FLD_PAR_AMT,
    _FLD_AMT_OUTSTANDING,
    _FLD_ISSUE_DT,
    _FLD_COUNTRY,
    _FLD_INDUSTRY_SECTOR,
    _FLD_BB_COMPOSITE,
    _FLD_RTG_SP,
    _FLD_RTG_MOODY,
    _FLD_RTG_FITCH,
    _FLD_CALLABLE,
    _FLD_PUTABLE,
    _FLD_SINKABLE,
]

# Bond risk fields
_FLD_DUR_ADJ_MID = "DUR_ADJ_MID"
_FLD_DUR_MID = "DUR_MID"
_FLD_CNVX_MID = "CNVX_MID"
_FLD_DUR_ADJ_OAS_MID = "DUR_ADJ_OAS_MID"
_FLD_OAS_SPREAD_DUR_MID = "OAS_SPREAD_DUR_MID"
_FLD_CNVX_OAS_MID = "CNVX_OAS_MID"
_FLD_RISK_MID = "RISK_MID"
_FLD_RISK_OAS_MID = "RISK_OAS_MID"
_FLD_YAS_MOD_DUR = "YAS_MOD_DUR"
_FLD_YAS_RISK = "YAS_RISK"

_BOND_RISK_FIELDS: list[str] = [
    _FLD_DUR_ADJ_MID,
    _FLD_DUR_MID,
    _FLD_CNVX_MID,
    _FLD_DUR_ADJ_OAS_MID,
    _FLD_OAS_SPREAD_DUR_MID,
    _FLD_CNVX_OAS_MID,
    _FLD_RISK_MID,
    _FLD_RISK_OAS_MID,
    _FLD_YAS_MOD_DUR,
    _FLD_YAS_RISK,
]

# Bond spread fields
_FLD_YAS_OAS_SPRD = "YAS_OAS_SPRD"
_FLD_YAS_ZSPREAD = "YAS_ZSPREAD"
_FLD_YAS_ISPREAD = "YAS_ISPREAD"
_FLD_YAS_ASW_SPREAD = "YAS_ASW_SPREAD"
_FLD_YAS_ISPREAD_TO_GOVT = "YAS_ISPREAD_TO_GOVT"
_FLD_YAS_YLD_SPREAD = "YAS_YLD_SPREAD"
_FLD_Z_SPRD_MID = "Z_SPRD_MID"
_FLD_OAS_SPREAD_MID = "OAS_SPREAD_MID"
_FLD_YAS_BNCHMRK_BOND = "YAS_BNCHMRK_BOND"
_FLD_YAS_BNCHMRK_BOND_YLD = "YAS_BNCHMRK_BOND_YLD"

_BOND_SPREAD_FIELDS: list[str] = [
    _FLD_YAS_OAS_SPRD,
    _FLD_YAS_ZSPREAD,
    _FLD_YAS_ISPREAD,
    _FLD_YAS_ASW_SPREAD,
    _FLD_YAS_ISPREAD_TO_GOVT,
    _FLD_YAS_YLD_SPREAD,
    _FLD_Z_SPRD_MID,
    _FLD_OAS_SPREAD_MID,
    _FLD_YAS_BNCHMRK_BOND,
    _FLD_YAS_BNCHMRK_BOND_YLD,
]

# Bond cashflow field
_FLD_DES_CASH_FLOW = "DES_CASH_FLOW"

# Bond key rate duration/risk fields
_FLD_KRD_1YR = "KEY_RATE_DUR_1YR"
_FLD_KRD_2YR = "KEY_RATE_DUR_2YR"
_FLD_KRD_3YR = "KEY_RATE_DUR_3YR"
_FLD_KRD_4YR = "KEY_RATE_DUR_4YR"
_FLD_KRD_5YR = "KEY_RATE_DUR_5YR"
_FLD_KRD_7YR = "KEY_RATE_DUR_7YR"
_FLD_KRD_8YR = "KEY_RATE_DUR_8YR"
_FLD_KRD_9YR = "KEY_RATE_DUR_9YR"
_FLD_KRD_10YR = "KEY_RATE_DUR_10YR"
_FLD_KRD_15YR = "KEY_RATE_DUR_15YR"
_FLD_KRD_20YR = "KEY_RATE_DUR_20YR"
_FLD_KRD_25YR = "KEY_RATE_DUR_25YR"
_FLD_KRD_30YR = "KEY_RATE_DUR_30YR"
_FLD_KRR_1Y = "KEY_RATE_RISK_1Y"
_FLD_KRR_2Y = "KEY_RATE_RISK_2Y"
_FLD_KRR_3Y = "KEY_RATE_RISK_3Y"
_FLD_KRR_5Y = "KEY_RATE_RISK_5Y"
_FLD_KRR_7Y = "KEY_RATE_RISK_7Y"
_FLD_KRR_10Y = "KEY_RATE_RISK_10Y"
_FLD_KRR_20Y = "KEY_RATE_RISK_20Y"
_FLD_KRR_30Y = "KEY_RATE_RISK_30Y"

_BOND_KEY_RATE_FIELDS: list[str] = [
    _FLD_KRD_1YR,
    _FLD_KRD_2YR,
    _FLD_KRD_3YR,
    _FLD_KRD_4YR,
    _FLD_KRD_5YR,
    _FLD_KRD_7YR,
    _FLD_KRD_8YR,
    _FLD_KRD_9YR,
    _FLD_KRD_10YR,
    _FLD_KRD_15YR,
    _FLD_KRD_20YR,
    _FLD_KRD_25YR,
    _FLD_KRD_30YR,
    _FLD_KRR_1Y,
    _FLD_KRR_2Y,
    _FLD_KRR_3Y,
    _FLD_KRR_5Y,
    _FLD_KRR_7Y,
    _FLD_KRR_10Y,
    _FLD_KRR_20Y,
    _FLD_KRR_30Y,
]

_BOND_CURVE_DEFAULT_FIELDS: list[str] = [
    "YAS_BOND_YLD",
    "YAS_MOD_DUR",
    "YAS_RISK",
    "YAS_ZSPREAD",
    "YAS_OAS_SPRD",
    "DUR_ADJ_MID",
    "CNVX_MID",
]


def _format_settle_dt(settle_dt: datetime | str | None) -> str | None:
    """Format settlement date for Bloomberg overrides.

    Uses the same conversion behavior as ``ext.yas``:

    * Parse date strings via ``datetime.fromisoformat`` after replacing ``/`` with ``-``.
    * Return ``YYYYMMDD`` for parsed strings and ``datetime`` inputs.
    * If parsing fails, pass the original string through unchanged.

    Args:
        settle_dt: Settlement date as datetime, string, or None.

    Returns:
        Formatted settlement date string, or None.
    """
    if settle_dt is None:
        return None

    if isinstance(settle_dt, str):
        try:
            dt = datetime.fromisoformat(settle_dt.replace("/", "-"))
            return f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
        except (ValueError, TypeError):
            return settle_dt

    if isinstance(settle_dt, datetime):
        return f"{settle_dt.year:04d}{settle_dt.month:02d}{settle_dt.day:02d}"

    return str(settle_dt)


def bond_info(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return static bond reference metadata in one ``bdp`` call.

    Fields returned (SEMI_LONG rows):

    * ``NAME``, ``SECURITY_DES``, ``CRNCY``
    * ``CPN_TYP``, ``CPN``, ``MATURITY``
    * ``PAR_AMT``, ``AMT_OUTSTANDING``, ``ISSUE_DT``
    * ``COUNTRY_ISO``, ``INDUSTRY_SECTOR``
    * ``BB_COMPOSITE``, ``RTG_SP``, ``RTG_MOODY``, ``RTG_FITCH``
    * ``CALLABLE``, ``PUTABLE``, ``SINKABLE``

    Args:
        ticker: Bond ticker or identifier.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Legacy kwargs support.

    Returns:
        DataFrame with bond reference metadata.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    return bdp(
        tickers=ticker,
        flds=_BOND_INFO_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **safe_kwargs,
    )


def bond_risk(
    ticker: str,
    *,
    settle_dt: datetime | str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return bond duration, convexity, and DV01 analytics via ``bdp``.

    Fields returned (SEMI_LONG rows):

    * ``DUR_ADJ_MID``, ``DUR_MID``, ``CNVX_MID``
    * ``DUR_ADJ_OAS_MID``, ``OAS_SPREAD_DUR_MID``, ``CNVX_OAS_MID``
    * ``RISK_MID``, ``RISK_OAS_MID``
    * ``YAS_MOD_DUR``, ``YAS_RISK``

    Args:
        ticker: Bond ticker or identifier.
        settle_dt: Settlement date override. Maps to ``SETTLE_DT`` override.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with bond risk analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    formatted_dt = _format_settle_dt(settle_dt)
    if formatted_dt is not None:
        overrides["SETTLE_DT"] = formatted_dt
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=ticker,
        flds=_BOND_RISK_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def bond_spreads(
    ticker: str,
    *,
    settle_dt: datetime | str | None = None,
    benchmark: str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return bond spread analytics and benchmark-relative measures via ``bdp``.

    Fields returned (SEMI_LONG rows):

    * ``YAS_OAS_SPRD``, ``YAS_ZSPREAD``, ``YAS_ISPREAD``
    * ``YAS_ASW_SPREAD``, ``YAS_ISPREAD_TO_GOVT``, ``YAS_YLD_SPREAD``
    * ``Z_SPRD_MID``, ``OAS_SPREAD_MID``
    * ``YAS_BNCHMRK_BOND``, ``YAS_BNCHMRK_BOND_YLD``

    Args:
        ticker: Bond ticker or identifier.
        settle_dt: Settlement date override. Maps to ``SETTLE_DT`` override.
        benchmark: Benchmark bond override. Maps to ``YAS_BNCHMRK_BOND`` override.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with bond spread analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    formatted_dt = _format_settle_dt(settle_dt)
    if formatted_dt is not None:
        overrides["SETTLE_DT"] = formatted_dt
    if benchmark is not None:
        overrides["YAS_BNCHMRK_BOND"] = benchmark
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=ticker,
        flds=_BOND_SPREAD_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def bond_cashflows(
    ticker: str,
    *,
    settle_dt: datetime | str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return projected bond cash flow schedule via ``bds``.

    Wraps the ``DES_CASH_FLOW`` bulk field and returns schedule rows including
    coupon and principal cash flows by payment date.

    Args:
        ticker: Bond ticker or identifier.
        settle_dt: Settlement date override. Maps to ``SETTLE_DT`` override.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with bond cash flow schedule.
    """
    from xbbg.api.reference.reference import bds
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    formatted_dt = _format_settle_dt(settle_dt)
    if formatted_dt is not None:
        overrides["SETTLE_DT"] = formatted_dt
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bds(
        ticker,
        _FLD_DES_CASH_FLOW,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def bond_key_rates(
    ticker: str,
    *,
    settle_dt: datetime | str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return bond key rate durations and key rate risks via ``bdp``.

    Fields returned (SEMI_LONG rows):

    * ``KEY_RATE_DUR_1YR`` through ``KEY_RATE_DUR_30YR``
    * ``KEY_RATE_RISK_1Y``, ``KEY_RATE_RISK_2Y``, ``KEY_RATE_RISK_3Y``
    * ``KEY_RATE_RISK_5Y``, ``KEY_RATE_RISK_7Y``, ``KEY_RATE_RISK_10Y``
    * ``KEY_RATE_RISK_20Y``, ``KEY_RATE_RISK_30Y``

    Args:
        ticker: Bond ticker or identifier.
        settle_dt: Settlement date override. Maps to ``SETTLE_DT`` override.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with key rate duration and risk analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    formatted_dt = _format_settle_dt(settle_dt)
    if formatted_dt is not None:
        overrides["SETTLE_DT"] = formatted_dt
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=ticker,
        flds=_BOND_KEY_RATE_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def bond_curve(
    tickers: list[str],
    flds: list[str] | None = None,
    *,
    settle_dt: datetime | str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return multi-bond relative-value analytics in one ``bdp`` call.

    If *flds* is not provided, defaults to:

    * ``YAS_BOND_YLD``, ``YAS_MOD_DUR``, ``YAS_RISK``
    * ``YAS_ZSPREAD``, ``YAS_OAS_SPRD``
    * ``DUR_ADJ_MID``, ``CNVX_MID``

    Args:
        tickers: List of bond tickers or identifiers.
        flds: Optional list of fields to request.
        settle_dt: Settlement date override. Maps to ``SETTLE_DT`` override.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with requested analytics for all provided tickers.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    formatted_dt = _format_settle_dt(settle_dt)
    if formatted_dt is not None:
        overrides["SETTLE_DT"] = formatted_dt
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=tickers,
        flds=flds or _BOND_CURVE_DEFAULT_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )
