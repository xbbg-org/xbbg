"""CDX index resolution utilities.

This module provides functions for resolving generic CDX tickers to specific
series tickers and selecting active CDX contracts.
"""

from __future__ import annotations

import contextlib
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import narwhals as nw

from xbbg.backend import Backend, Format
from xbbg.core.utils.dates import parse_date as _parse_date
from xbbg.io.convert import is_empty

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

__all__ = [
    "cdx_ticker",
    "active_cdx",
    "cdx_info",
    "cdx_defaults",
    "cdx_pricing",
    "cdx_risk",
    "cdx_basis",
    "cdx_default_prob",
    "cdx_cashflows",
    "cdx_curve",
]

# Bloomberg field mnemonics for CDX resolution (canonical uppercase).
# ReferenceTransformer lowercases field values in SEMI_LONG output,
# so comparisons below use the lowercase forms.
_FLD_ROLLING_SERIES = "ROLLING_SERIES"
_FLD_OTR_INDICATOR = "ON_THE_RUN_CURRENT_BD_INDICATOR"
_FLD_ACCRUAL_START = "CDS_FIRST_ACCRUAL_START_DATE"
_FLD_VERSION = "VERSION"

_CDX_FIELDS: list[str] = [_FLD_ROLLING_SERIES, _FLD_OTR_INDICATOR, _FLD_ACCRUAL_START, _FLD_VERSION]


def cdx_ticker(
    gen_ticker: str,
    dt,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Resolve generic CDX ticker (e.g., 'CDX IG CDSI GEN 5Y Corp') to concrete series.

    Uses Bloomberg fields (via ``bdp`` with ``SEMI_LONG`` format):

    * ``ROLLING_SERIES`` -- current on-the-run series number
    * ``VERSION`` -- current version (increments on credit events, e.g. CDX HY)
    * ``ON_THE_RUN_CURRENT_BD_INDICATOR`` -- ``'Y'`` if on-the-run
    * ``CDS_FIRST_ACCRUAL_START_DATE`` -- start date of current series trading

    Version handling:
        When ``VERSION > 1`` (credit events have occurred, common for CDX HY),
        a separate version token is inserted: ``S45`` -> ``S45 V2``.  When
        ``VERSION == 1`` (no defaults, typical for CDX IG) the ticker is left
        as ``S45`` since Bloomberg treats ``S45`` and ``S45 V1`` identically.

    Args:
        gen_ticker: Generic CDX ticker containing ``GEN`` token.
        dt: Date to resolve for.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Resolved ticker string, or ``""`` on failure.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    dt_parsed = _parse_date(dt)

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    # Convert context to kwargs for bdp call
    safe_kwargs = ctx.to_kwargs()

    try:
        info = bdp(
            tickers=gen_ticker,
            flds=_CDX_FIELDS,
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
    except Exception as e:
        logger.error("Failed to fetch CDX metadata for generic ticker %s: %s", gen_ticker, e)
        return ""

    if is_empty(info):
        logger.warning("No data returned from Bloomberg for CDX ticker: %s", gen_ticker)
        return ""

    # bdp SEMI_LONG returns columns: ticker, field, value (one row per field).
    # ReferenceTransformer already lowercases field values.
    nw_info = nw.from_native(info, eager_only=True)

    # Filter for the target ticker
    ticker_data = nw_info.filter(nw.col("ticker") == gen_ticker)

    # --- Validate on-the-run indicator ---
    otr = _extract_field_value(ticker_data, _FLD_OTR_INDICATOR.lower())
    if otr is not None and str(otr).upper() != "Y":
        logger.warning(
            "Generic ticker %s has ON_THE_RUN_CURRENT_BD_INDICATOR=%r (expected 'Y'); resolution may be stale",
            gen_ticker,
            otr,
        )

    # --- Extract series ---
    series = _extract_field_value(ticker_data, _FLD_ROLLING_SERIES.lower())
    if series is None:
        logger.warning("No rolling series found for CDX ticker: %s", gen_ticker)
        return ""

    with contextlib.suppress(ValueError, TypeError):
        series = int(series)

    # --- Extract version (credit-event counter) ---
    version: int | None = None
    version_raw = _extract_field_value(ticker_data, _FLD_VERSION.lower())
    if version_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            version = int(version_raw)

    # --- Extract accrual start date (for date-based fallback) ---
    start_dt = None
    start_dt_raw = _extract_field_value(ticker_data, _FLD_ACCRUAL_START.lower())
    if start_dt_raw is not None:
        with contextlib.suppress(ValueError, TypeError):
            start_dt = _parse_date(start_dt_raw)

    # --- Build resolved ticker ---
    tokens = gen_ticker.split()
    if "GEN" not in tokens:
        logger.warning("Generic ticker %s does not contain expected GEN token for CDX resolution", gen_ticker)
        return ""

    gen_idx = tokens.index("GEN")

    # Build series + version tokens: "S45" alone, or "S45 V2" as two tokens when version > 1.
    # Bloomberg expects: CDX HY CDSI S44 V1 5Y Corp (version is a separate space-delimited token).
    tokens[gen_idx] = f"S{series}"
    if version is not None and version > 1:
        tokens.insert(gen_idx + 1, f"V{version}")
    resolved = " ".join(tokens)

    # If dt is before first accrual date of current series, fall back to prior series.
    # Note: prior-series version is unknown here; we omit it and let the caller
    # re-resolve if needed (version for off-the-run series may differ).
    if (start_dt is not None) and (dt_parsed < start_dt) and isinstance(series, int) and series > 1:
        # Remove any version token that was inserted after the series token
        tokens = resolved.split()
        series_idx = _find_series_token_index(tokens)
        if series_idx is not None:
            # Remove version token if present right after series
            if (
                series_idx + 1 < len(tokens)
                and tokens[series_idx + 1].startswith("V")
                and tokens[series_idx + 1][1:].isdigit()
            ):
                tokens.pop(series_idx + 1)
            tokens[series_idx] = f"S{series - 1}"
        resolved = " ".join(tokens)

    return resolved


def _extract_field_value(ticker_data, field_name: str):
    """Extract a single field value from SEMI_LONG narwhals frame.

    Args:
        ticker_data: Narwhals DataFrame already filtered to one ticker,
            with columns ``ticker``, ``field``, ``value``.
        field_name: Lowercase field name to look up in the ``field`` column.

    Returns:
        The scalar value, or ``None`` if not found.
    """
    rows = ticker_data.filter(nw.col("field") == field_name).select("value")
    if rows.shape[0] > 0:
        return rows.item(0, 0)
    return None


def _resolve_version_for_ticker(ticker: str, safe_kwargs: dict[str, object]) -> str:
    """Look up VERSION for an already-resolved (series-only) ticker and append V suffix.

    If ``VERSION > 1``, returns the ticker with a separate version token
    inserted after the series token (e.g. ``S44`` -> ``S44 V2``).  Otherwise
    returns *ticker* unchanged.
    """
    from xbbg.api.reference import bdp

    try:
        meta = bdp(
            ticker,
            [_FLD_VERSION],
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
        if is_empty(meta):
            return ticker
        nw_meta = nw.from_native(meta, eager_only=True)
        td = nw_meta.filter(nw.col("ticker") == ticker)
        ver_raw = _extract_field_value(td, _FLD_VERSION.lower())
        if ver_raw is not None:
            ver = int(ver_raw)
            if ver > 1:
                return _append_version_to_ticker(ticker, ver)
    except Exception:
        pass
    return ticker


def _append_version_to_ticker(ticker: str, version: int) -> str:
    """Insert ``V{version}`` as a separate token after the series token.

    Bloomberg expects version as its own space-separated token:
    ``CDX HY CDSI S44 5Y Corp`` -> ``CDX HY CDSI S44 V2 5Y Corp``.

    If the ticker already has a version token (``V{n}``), it is replaced.

    >>> _append_version_to_ticker("CDX HY CDSI S44 5Y Corp", 2)
    'CDX HY CDSI S44 V2 5Y Corp'
    """
    tokens = ticker.split()
    idx = _find_series_token_index(tokens)
    if idx is None:
        return ticker

    # Remove existing version token if present (right after series)
    if idx + 1 < len(tokens) and tokens[idx + 1].startswith("V") and tokens[idx + 1][1:].isdigit():
        tokens.pop(idx + 1)

    # Insert version as separate token after series
    tokens.insert(idx + 1, f"V{version}")
    return " ".join(tokens)


def _parse_series_token(tok: str) -> int | None:
    """Parse a pure series token like ``S45`` and return the series number.

    Only matches ``S{digits}``.  Does **not** match version tokens like ``V2``.
    Returns ``None`` if the token is not a series token.
    """
    if not tok.startswith("S"):
        return None
    rest = tok[1:]
    if rest.isdigit():
        return int(rest)
    return None


def _find_series_token_index(tokens: list[str]) -> int | None:
    """Return the index of the series token (``S{n}``) within *tokens*.

    Returns ``None`` if no series token is found.
    """
    for i, tok in enumerate(tokens):
        if _parse_series_token(tok) is not None:
            return i
    return None


def _strip_version_from_ticker(ticker: str) -> str:
    """Remove the version token (``V{n}``) from a resolved CDX ticker.

    >>> _strip_version_from_ticker("CDX HY CDSI S44 V2 5Y Corp")
    'CDX HY CDSI S44 5Y Corp'
    """
    tokens = ticker.split()
    idx = _find_series_token_index(tokens)
    if idx is not None and idx + 1 < len(tokens):
        next_tok = tokens[idx + 1]
        if next_tok.startswith("V") and next_tok[1:].isdigit():
            tokens.pop(idx + 1)
    return " ".join(tokens)


def active_cdx(
    gen_ticker: str,
    dt,
    lookback_days: int = 10,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Choose active CDX series for a date, preferring on-the-run unless it hasn't started yet.

    Resolution steps:

    1. Call :func:`cdx_ticker` to get the on-the-run series (with version).
    2. Derive the previous-series candidate (``S{n-1}``), then look up its
       ``VERSION`` to build the full versioned ticker.
    3. If *dt* is before the current series' accrual start -> return previous.
    4. Otherwise compare ``PX_LAST`` availability over *lookback_days* and
       return whichever series traded most recently.

    Args:
        gen_ticker: Generic CDX ticker.
        dt: Date to resolve for.
        lookback_days: Number of days to look back for activity.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Active ticker string, or ``""`` on failure.
    """
    from xbbg.api.historical import bdh
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    dt_parsed = _parse_date(dt)

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    cur = cdx_ticker(gen_ticker=gen_ticker, dt=dt, ctx=ctx)
    if not cur:
        return ""

    # Convert context to kwargs for bdp/bdh calls
    safe_kwargs = ctx.to_kwargs()

    # Compute previous series candidate (version-aware).
    # Strip version token first (prior series has its own version), then decrement series.
    prev = ""
    prev_base = _strip_version_from_ticker(cur)
    parts = prev_base.split()
    idx = _find_series_token_index(parts)
    if idx is not None:
        s = _parse_series_token(parts[idx])
        if s is not None and s > 1:
            parts[idx] = f"S{s - 1}"
            prev = " ".join(parts)

    # If no prev candidate, current is series 1 -- nothing to compare
    if not prev:
        return cur

    # Resolve version for the previous series (e.g. S44 -> S44 V2 for CDX HY)
    prev = _resolve_version_for_ticker(prev, safe_kwargs)

    # If dt is before accrual start of current series, prefer previous
    try:
        cur_meta = bdp(
            cur,
            [_FLD_ACCRUAL_START],
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
        cur_start = None
        if not is_empty(cur_meta):
            nw_meta = nw.from_native(cur_meta, eager_only=True)
            val = _extract_field_value(nw_meta, _FLD_ACCRUAL_START.lower())
            if val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    cur_start = _parse_date(val)
    except Exception:
        cur_start = None

    if (cur_start is not None) and (dt_parsed < cur_start):
        return prev

    # Otherwise, pick whichever series has the most recent PX_LAST
    end_date = dt_parsed
    start_date = dt_parsed - timedelta(days=lookback_days)

    try:
        px = bdh(
            [cur, prev],
            ["PX_LAST"],
            start_date=start_date,
            end_date=end_date,
            backend=Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
        if is_empty(px):
            return cur

        nw_px = nw.from_native(px, eager_only=True)

        # Normalize column name (handle both PX_LAST and px_last)
        px_col = "PX_LAST" if "PX_LAST" in nw_px.columns else "px_last"

        # Find ticker with most recent non-null PX_LAST
        ticker_latest = (
            nw_px.filter(~nw.col(px_col).is_null()).group_by("ticker").agg(nw.col("date").max().alias("latest_date"))
        )

        if ticker_latest.shape[0] == 0:
            return cur

        latest_dates: dict[str, str] = {}
        for row in ticker_latest.iter_rows(named=True):
            ticker = row.get("ticker")
            date_val = row.get("latest_date")
            if ticker and date_val:
                latest_dates[ticker] = str(date_val)

        best_ticker = cur
        best_date = latest_dates.get(cur, "")

        if prev in latest_dates and latest_dates[prev] > best_date:
            best_ticker = prev

        return best_ticker

    except Exception:
        return cur


# ---------------------------------------------------------------------------
# CDX metadata & defaults
# ---------------------------------------------------------------------------

# Additional Bloomberg fields for cdx_info
_FLD_NAME = "NAME"
_FLD_NUM_CURRENT = "NUM_CURRENT_COMPANIES_CCY_TKR"
_FLD_NUM_ORIG = "NUM_ORIG_COMPANIES_CRNCY_TKR"
_FLD_PX_LAST = "PX_LAST"

_CDX_INFO_FIELDS: list[str] = [
    _FLD_ROLLING_SERIES,
    _FLD_VERSION,
    _FLD_OTR_INDICATOR,
    _FLD_ACCRUAL_START,
    _FLD_NAME,
    _FLD_NUM_CURRENT,
    _FLD_NUM_ORIG,
    _FLD_PX_LAST,
]

# Pricing fields
_FLD_PX_BID = "PX_BID"
_FLD_PX_ASK = "PX_ASK"
_FLD_UPFRONT_LAST = "UPFRONT_LAST"
_FLD_UPFRONT_BID = "UPFRONT_BID"
_FLD_UPFRONT_ASK = "UPFRONT_ASK"
_FLD_CDS_FLAT_SPREAD = "CDS_FLAT_SPREAD"
_FLD_UPFRONT_FEE = "UPFRONT_FEE"
_FLD_PV_CDS_PREMIUM_LEG = "PV_CDS_PREMIUM_LEG"
_FLD_PV_CDS_DEFAULT_LEG = "PV_CDS_DEFAULT_LEG"

_CDX_PRICING_FIELDS: list[str] = [
    _FLD_PX_LAST,
    _FLD_PX_BID,
    _FLD_PX_ASK,
    _FLD_UPFRONT_LAST,
    _FLD_UPFRONT_BID,
    _FLD_UPFRONT_ASK,
    _FLD_CDS_FLAT_SPREAD,
    _FLD_UPFRONT_FEE,
    _FLD_PV_CDS_PREMIUM_LEG,
    _FLD_PV_CDS_DEFAULT_LEG,
]

# Risk fields
_FLD_SW_CNV_BPV = "SW_CNV_BPV"
_FLD_SW_EQV_BPV = "SW_EQV_BPV"
_FLD_CDS_SPREAD_MID_MODIFIED_DURATION = "CDS_SPREAD_MID_MODIFIED_DURATION"
_FLD_CDS_SPREAD_MID_CONVEXITY = "CDS_SPREAD_MID_CONVEXITY"
_FLD_RECOVERY_RATE_SEN = "RECOVERY_RATE_SEN"
_FLD_CDS_RECOVERY_RT = "CDS_RECOVERY_RT"

_CDX_RISK_FIELDS: list[str] = [
    _FLD_SW_CNV_BPV,
    _FLD_SW_EQV_BPV,
    _FLD_CDS_SPREAD_MID_MODIFIED_DURATION,
    _FLD_CDS_SPREAD_MID_CONVEXITY,
    _FLD_RECOVERY_RATE_SEN,
    _FLD_CDS_RECOVERY_RT,
]

# Basis fields
_FLD_CDS_INDEX_INTRINSIC_VALUE = "CDS_INDEX_INTRINSIC_VALUE"
_FLD_CDS_INDEX_INTRINSIC_BASIS_VALUE = "CDS_INDEX_INTRINSIC_BASIS_VALUE"
_FLD_CDS_IDX_DUR_BASED_INTRINSIC_VAL = "CDS_IDX_DUR_BASED_INTRINSIC_VAL"
_FLD_CDS_INDEX_DUR_BASED_BASIS_VAL = "CDS_INDEX_DUR_BASED_BASIS_VAL"

_CDX_BASIS_FIELDS: list[str] = [
    _FLD_CDS_INDEX_INTRINSIC_VALUE,
    _FLD_CDS_INDEX_INTRINSIC_BASIS_VALUE,
    _FLD_CDS_IDX_DUR_BASED_INTRINSIC_VAL,
    _FLD_CDS_INDEX_DUR_BASED_BASIS_VAL,
    _FLD_PX_LAST,
]

# Default probability and cashflow fields
_FLD_CDS_DEFAULT_PROB = "CDS_DEFAULT_PROB"
_FLD_CASHFLOW_SCHEDULE = "CASHFLOW_SCHEDULE"

# Curve fields
_FLD_CURRENT_TENOR = "CURRENT_TENOR"

_CDX_CURVE_FIELDS: list[str] = [
    _FLD_PX_LAST,
    _FLD_UPFRONT_LAST,
    _FLD_CDS_FLAT_SPREAD,
    _FLD_SW_CNV_BPV,
    _FLD_CURRENT_TENOR,
]

_CDX_COMMON_TENORS: list[str] = ["1Y", "2Y", "3Y", "4Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"]
_CDX_CURVE_DEFAULT_TENORS: list[str] = ["3Y", "5Y", "7Y", "10Y"]


def cdx_info(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return key metadata for a CDX ticker in a single ``bdp`` call.

    Works with both generic (``CDX IG CDSI GEN 5Y Corp``) and resolved
    (``CDX HY CDSI S45 V2 5Y Corp``) tickers.

    Fields returned (SEMI_LONG rows):

    * ``ROLLING_SERIES``, ``VERSION``, ``ON_THE_RUN_CURRENT_BD_INDICATOR``
    * ``CDS_FIRST_ACCRUAL_START_DATE``
    * ``NAME``, ``NUM_CURRENT_COMPANIES_CCY_TKR``, ``NUM_ORIG_COMPANIES_CRNCY_TKR``
    * ``PX_LAST``

    Args:
        ticker: Any CDX ticker (generic or resolved).
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Legacy kwargs support.

    Returns:
        DataFrame in the requested backend format (default SEMI_LONG).
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    return bdp(
        tickers=ticker,
        flds=_CDX_INFO_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **safe_kwargs,
    )


def cdx_defaults(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return credit-event (default) history for a CDX series.

    Wraps the ``CDS_INDEX_DEFAULT_INFORMATION`` bulk field via ``bds``.
    Returns one row per default with columns including ``company_name``,
    ``event_date``, ``cds_recovery_rate``, ``auction_date``, and
    ``previous_weight``.

    An empty frame is returned for series with no defaults (e.g. CDX IG).

    Args:
        ticker: Resolved CDX ticker (e.g. ``CDX HY CDSI S45 V2 5Y Corp``).
            Also works without the version token.
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Legacy kwargs support.

    Returns:
        DataFrame with default information (empty if no defaults).
    """
    from xbbg.api.reference.reference import bds
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    try:
        return bds(
            ticker,
            "CDS_INDEX_DEFAULT_INFORMATION",
            backend=backend or Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )
    except Exception as e:
        logger.warning("Failed to fetch default information for %s: %s", ticker, e)
        # Return empty via bdp fallback -- guarantees consistent return type
        from xbbg.api.reference import bdp

        return bdp(
            tickers=ticker,
            flds=["NAME"],
            backend=backend or Backend.NARWHALS,
            format=Format.SEMI_LONG,
            **safe_kwargs,
        )


def cdx_pricing(
    ticker: str,
    *,
    recovery_rate: float | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return CDX pricing and valuation analytics in one ``bdp`` call.

    Fields returned (SEMI_LONG rows):

    * ``PX_LAST``, ``PX_BID``, ``PX_ASK``
    * ``UPFRONT_LAST``, ``UPFRONT_BID``, ``UPFRONT_ASK``
    * ``CDS_FLAT_SPREAD``
    * ``UPFRONT_FEE``
    * ``PV_CDS_PREMIUM_LEG``, ``PV_CDS_DEFAULT_LEG``

    Args:
        ticker: CDX ticker (generic or resolved).
        recovery_rate: Recovery-rate override as a decimal (e.g. ``0.30``
            for 30%).  Mapped to the ``CDS_RR`` Bloomberg override.
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with CDX pricing analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    if recovery_rate is not None:
        overrides["CDS_RR"] = recovery_rate
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=ticker,
        flds=_CDX_PRICING_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def cdx_risk(
    ticker: str,
    *,
    recovery_rate: float | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return CDX risk analytics in one ``bdp`` call.

    Fields returned (SEMI_LONG rows):

    * ``SW_CNV_BPV`` (conventional DV01)
    * ``SW_EQV_BPV`` (equivalent DV01)
    * ``CDS_SPREAD_MID_MODIFIED_DURATION``
    * ``CDS_SPREAD_MID_CONVEXITY``
    * ``RECOVERY_RATE_SEN``
    * ``CDS_RECOVERY_RT``

    Args:
        ticker: CDX ticker (generic or resolved).
        recovery_rate: Recovery-rate override as a decimal (e.g. ``0.30``
            for 30%).  Mapped to the ``CDS_RR`` Bloomberg override.
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides (kwargs override named params).

    Returns:
        DataFrame with CDX risk analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    if recovery_rate is not None:
        overrides["CDS_RR"] = recovery_rate
    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bdp(
        tickers=ticker,
        flds=_CDX_RISK_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def cdx_basis(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return CDX intrinsic value and basis analytics via ``bdp``.

    Fields returned (SEMI_LONG rows):

    * ``CDS_INDEX_INTRINSIC_VALUE``
    * ``CDS_INDEX_INTRINSIC_BASIS_VALUE``
    * ``CDS_IDX_DUR_BASED_INTRINSIC_VAL``
    * ``CDS_INDEX_DUR_BASED_BASIS_VAL``
    * ``PX_LAST``

    Args:
        ticker: CDX ticker (generic or resolved).
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides.

    Returns:
        DataFrame with CDX basis analytics.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    call_kwargs = {**safe_kwargs, **kwargs}
    return bdp(
        tickers=ticker,
        flds=_CDX_BASIS_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def cdx_default_prob(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return CDX default-probability term structure via ``bds``.

    Wraps the ``CDS_DEFAULT_PROB`` bulk field and returns term-structure rows,
    including tenor dates and cumulative default probabilities.

    Args:
        ticker: CDX ticker (generic or resolved).
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides.

    Returns:
        DataFrame with default-probability term structure.
    """
    from xbbg.api.reference.reference import bds
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    call_kwargs = {**safe_kwargs, **kwargs}
    return bds(
        ticker,
        _FLD_CDS_DEFAULT_PROB,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def cdx_cashflows(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return CDX cashflow schedule via ``bds``.

    Wraps the ``CASHFLOW_SCHEDULE`` bulk field and returns projected coupon and
    accrual cashflows with associated schedule analytics.

    Args:
        ticker: CDX ticker (generic or resolved).
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides.

    Returns:
        DataFrame with cashflow schedule information.
    """
    from xbbg.api.reference.reference import bds
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    call_kwargs = {**safe_kwargs, **kwargs}
    return bds(
        ticker,
        _FLD_CASHFLOW_SCHEDULE,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def cdx_curve(
    gen_ticker: str,
    tenors: list[str] | None = None,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return a CDX tenor curve by querying multiple tenor tickers in one ``bdp`` call.

    The function replaces the tenor token in *gen_ticker* across *tenors* and
    fetches curve analytics for each resulting ticker.

    Args:
        gen_ticker: Generic CDX ticker with a tenor token (e.g. ``5Y``).
        tenors: Tenors to query. Defaults to ``["3Y", "5Y", "7Y", "10Y"]``.
        backend: Output backend. If ``None``, uses the global default.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides.

    Returns:
        DataFrame combining curve analytics across all requested tenors.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    call_kwargs = {**safe_kwargs, **kwargs}

    requested_tenors = tenors or _CDX_CURVE_DEFAULT_TENORS

    seen_tenors: set[str] = set()
    normalized_tenors: list[str] = []
    for tenor in requested_tenors:
        if tenor not in seen_tenors:
            normalized_tenors.append(tenor)
            seen_tenors.add(tenor)

    tokens = gen_ticker.split()
    tenor_idx = next((idx for idx, tok in enumerate(tokens) if tok in _CDX_COMMON_TENORS), None)

    if tenor_idx is None:
        curve_tickers = [gen_ticker]
    else:
        curve_tickers = []
        for tenor in normalized_tenors:
            tenor_tokens = list(tokens)
            tenor_tokens[tenor_idx] = tenor
            curve_tickers.append(" ".join(tenor_tokens))

    return bdp(
        tickers=curve_tickers,
        flds=_CDX_CURVE_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )
