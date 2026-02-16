"""Bloomberg Options Analytics API.

This module provides convenience functions for equity option analytics including
option metadata, Greeks, pricing, option chain retrieval with filtering, and
multi-option comparison.

The functions mirror the API patterns used across ``xbbg.ext`` modules:

* Lazy imports for Bloomberg request functions.
* Context extraction via ``split_kwargs`` for compatibility.
* Default output to ``Backend.NARWHALS`` and ``Format.SEMI_LONG``.
* Named parameters for commonly-used overrides.

All Bloomberg field mnemonics and ``CHAIN_TICKERS`` override names in this
module are explicit constants so users can quickly inspect the supported scope.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING

from xbbg.backend import Backend, Format

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)

__all__ = [
    # Enums
    "PutCall",
    "ChainPeriodicity",
    "StrikeRef",
    "ExerciseType",
    "ExpiryMatch",
    # Functions
    "option_info",
    "option_greeks",
    "option_pricing",
    "option_chain",
    "option_chain_bql",
    "option_screen",
]


class PutCall(StrEnum):
    """Put/call filter for CHAIN_PUT_CALL_TYPE_OVRD."""

    CALL = "C"
    PUT = "P"


class ChainPeriodicity(StrEnum):
    """Expiry periodicity for CHAIN_PERIODICITY_OVRD."""

    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    YEARLY = "Y"
    ALL = ""


class StrikeRef(StrEnum):
    """Strike reference for CHAIN_STRIKE_PX_OVRD."""

    ATM = "ATM"


class ExerciseType(StrEnum):
    """Exercise type for CHAIN_EXERCISE_TYPE_OVRD."""

    AMERICAN = "A"
    EUROPEAN = "E"


class ExpiryMatch(StrEnum):
    """Expiry date matching for CHAIN_EXP_MATCH_OVRD."""

    EXACT = "E"
    CLOSEST = "C"


# ---------------------------------------------------------------------------
# Bloomberg field constants: option metadata
# ---------------------------------------------------------------------------

_FLD_OPT_STRIKE_PX = "OPT_STRIKE_PX"
_FLD_OPT_EXPIRE_DT = "OPT_EXPIRE_DT"
_FLD_OPT_PUT_CALL = "OPT_PUT_CALL"
_FLD_OPT_EXER_TYP = "OPT_EXER_TYP"
_FLD_OPT_UNDL_TICKER = "OPT_UNDL_TICKER"
_FLD_OPT_UNDL_PX = "OPT_UNDL_PX"
_FLD_OPT_CONT_SIZE = "OPT_CONT_SIZE"
_FLD_OPT_MULTIPLIER = "OPT_MULTIPLIER"
_FLD_NAME = "NAME"
_FLD_SECURITY_DES = "SECURITY_DES"

_OPTION_INFO_FIELDS: list[str] = [
    _FLD_OPT_STRIKE_PX,
    _FLD_OPT_EXPIRE_DT,
    _FLD_OPT_PUT_CALL,
    _FLD_OPT_EXER_TYP,
    _FLD_OPT_UNDL_TICKER,
    _FLD_OPT_UNDL_PX,
    _FLD_OPT_CONT_SIZE,
    _FLD_OPT_MULTIPLIER,
    _FLD_NAME,
    _FLD_SECURITY_DES,
]


# ---------------------------------------------------------------------------
# Bloomberg field constants: option Greeks and implied volatility
# ---------------------------------------------------------------------------

_FLD_DELTA_MID = "DELTA_MID"
_FLD_GAMMA_MID = "GAMMA_MID"
_FLD_VEGA_MID = "VEGA_MID"
_FLD_THETA_MID = "THETA_MID"
_FLD_RHO_MID = "RHO_MID"

_FLD_DELTA = "DELTA"
_FLD_DELTA_BID = "DELTA_BID"
_FLD_DELTA_ASK = "DELTA_ASK"
_FLD_GAMMA = "GAMMA"
_FLD_GAMMA_BID = "GAMMA_BID"
_FLD_GAMMA_ASK = "GAMMA_ASK"
_FLD_VEGA = "VEGA"
_FLD_VEGA_BID = "VEGA_BID"
_FLD_VEGA_ASK = "VEGA_ASK"
_FLD_THETA_BID = "THETA_BID"
_FLD_THETA_ASK = "THETA_ASK"
_FLD_RHO_BID = "RHO_BID"
_FLD_RHO_ASK = "RHO_ASK"

_FLD_IVOL_MID = "IVOL_MID"
_FLD_IVOL_BID = "IVOL_BID"
_FLD_IVOL_ASK = "IVOL_ASK"

_OPTION_GREEKS_FIELDS: list[str] = [
    _FLD_DELTA_MID,
    _FLD_GAMMA_MID,
    _FLD_VEGA_MID,
    _FLD_THETA_MID,
    _FLD_RHO_MID,
    _FLD_DELTA,
    _FLD_DELTA_BID,
    _FLD_DELTA_ASK,
    _FLD_GAMMA,
    _FLD_GAMMA_BID,
    _FLD_GAMMA_ASK,
    _FLD_VEGA,
    _FLD_VEGA_BID,
    _FLD_VEGA_ASK,
    _FLD_THETA_BID,
    _FLD_THETA_ASK,
    _FLD_RHO_BID,
    _FLD_RHO_ASK,
    _FLD_IVOL_MID,
    _FLD_IVOL_BID,
    _FLD_IVOL_ASK,
]


# ---------------------------------------------------------------------------
# Bloomberg field constants: option pricing and activity
# ---------------------------------------------------------------------------

_FLD_PX_LAST = "PX_LAST"
_FLD_PX_BID = "PX_BID"
_FLD_PX_ASK = "PX_ASK"
_FLD_OPT_INTRINSIC_VAL = "OPT_INTRINSIC_VAL"
_FLD_OPT_TRUE_INTRINSIC = "OPT_TRUE_INTRINSIC"
_FLD_OPT_TIME_VAL = "OPT_TIME_VAL"
_FLD_OPEN_INT = "OPEN_INT"
_FLD_PX_VOLUME = "PX_VOLUME"
_FLD_OPEN_INT_CHANGE = "OPEN_INT_CHANGE"

_OPTION_PRICING_FIELDS: list[str] = [
    _FLD_PX_LAST,
    _FLD_PX_BID,
    _FLD_PX_ASK,
    _FLD_OPT_INTRINSIC_VAL,
    _FLD_OPT_TRUE_INTRINSIC,
    _FLD_OPT_TIME_VAL,
    _FLD_OPEN_INT,
    _FLD_PX_VOLUME,
    _FLD_OPEN_INT_CHANGE,
]


# ---------------------------------------------------------------------------
# Bloomberg field constants: option chain bulk field and overrides
# ---------------------------------------------------------------------------

_FLD_CHAIN_TICKERS = "CHAIN_TICKERS"

_OVRD_CHAIN_PUT_CALL_TYPE = "CHAIN_PUT_CALL_TYPE_OVRD"
_OVRD_CHAIN_EXP_DT = "CHAIN_EXP_DT_OVRD"
_OVRD_CHAIN_STRIKE_PX = "CHAIN_STRIKE_PX_OVRD"
_OVRD_CHAIN_POINTS = "CHAIN_POINTS_OVRD"
_OVRD_CHAIN_PERIODICITY = "CHAIN_PERIODICITY_OVRD"
_OVRD_CHAIN_EXERCISE_TYPE = "CHAIN_EXERCISE_TYPE_OVRD"
_OVRD_CHAIN_EXP_MATCH = "CHAIN_EXP_MATCH_OVRD"


_OPTION_SCREEN_DEFAULT_FIELDS: list[str] = [
    _FLD_NAME,
    _FLD_SECURITY_DES,
    _FLD_OPT_STRIKE_PX,
    _FLD_OPT_EXPIRE_DT,
    _FLD_OPT_PUT_CALL,
    _FLD_OPT_EXER_TYP,
    _FLD_OPT_UNDL_TICKER,
    _FLD_OPT_UNDL_PX,
    _FLD_PX_LAST,
    _FLD_PX_BID,
    _FLD_PX_ASK,
    _FLD_IVOL_MID,
    _FLD_DELTA_MID,
    _FLD_GAMMA_MID,
    _FLD_VEGA_MID,
    _FLD_THETA_MID,
    _FLD_RHO_MID,
    _FLD_OPEN_INT,
    _FLD_PX_VOLUME,
]


def _enum_value(value) -> str | int | float:
    """Return raw enum value for StrEnum-compatible inputs.

    Args:
        value: Value that may be an enum member or plain scalar.

    Returns:
        Underlying scalar value to send in Bloomberg overrides.
    """
    if isinstance(value, StrEnum):
        return value.value
    return value


def _format_expiry_dt(expiry_dt: str | None) -> str | None:
    """Normalize chain expiry override into ``YYYYMMDD`` when possible.

    Bloomberg accepts ``CHAIN_EXP_DT_OVRD`` as text.  This helper mirrors the
    tolerant date behavior used in other ``xbbg.ext`` modules:

    * If *expiry_dt* is ``None`` -> returns ``None``.
    * If parseable as an ISO-style date (``YYYY-MM-DD`` / ``YYYY/MM/DD``) ->
      returns ``YYYYMMDD``.
    * If parsing fails -> returns the original text unchanged.

    Args:
        expiry_dt: Requested expiry date override.

    Returns:
        Formatted date override or original string.
    """
    if expiry_dt is None:
        return None

    try:
        dt = datetime.fromisoformat(expiry_dt.replace("/", "-"))
        return f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
    except (ValueError, TypeError):
        return expiry_dt


def _format_strike(strike: str | float | None) -> str | None:
    """Normalize chain strike override.

    ``CHAIN_STRIKE_PX_OVRD`` can be passed as:

    * ``StrikeRef.ATM`` / ``"ATM"`` for at-the-money anchoring.
    * A numeric value as text (for example ``"600"``).
    * A float value (for example ``600.0``) which is converted to string.

    Args:
        strike: Strike selector for chain retrieval.

    Returns:
        Strike override string or ``None``.
    """
    if strike is None:
        return None

    if isinstance(strike, StrEnum):
        return strike.value

    if isinstance(strike, str):
        return strike

    return str(strike)


def option_info(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return static option reference metadata in one ``bdp`` call.

    Fields returned (SEMI_LONG rows):

    * ``OPT_STRIKE_PX``
    * ``OPT_EXPIRE_DT``
    * ``OPT_PUT_CALL``
    * ``OPT_EXER_TYP``
    * ``OPT_UNDL_TICKER``
    * ``OPT_UNDL_PX``
    * ``OPT_CONT_SIZE``
    * ``OPT_MULTIPLIER``
    * ``NAME``
    * ``SECURITY_DES``

    This function is useful for quickly validating an option contract's static
    setup before running any pricing or Greeks workflow.  It includes the
    contract mechanics (strike, expiry, exercise style, multiplier) and links
    the option to its underlying instrument.

    Args:
        ticker: Bloomberg option ticker.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides and legacy kwargs support.

    Returns:
        DataFrame with option reference metadata.
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
        flds=_OPTION_INFO_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def option_greeks(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return option Greeks and implied volatility in one ``bdp`` call.

    Fields returned (SEMI_LONG rows):

    Mid Greeks:

    * ``DELTA_MID``
    * ``GAMMA_MID``
    * ``VEGA_MID``
    * ``THETA_MID``
    * ``RHO_MID``

    Bid/ask Greeks:

    * ``DELTA``, ``DELTA_BID``, ``DELTA_ASK``
    * ``GAMMA``, ``GAMMA_BID``, ``GAMMA_ASK``
    * ``VEGA``, ``VEGA_BID``, ``VEGA_ASK``
    * ``THETA_BID``, ``THETA_ASK``
    * ``RHO_BID``, ``RHO_ASK``

    Implied volatility:

    * ``IVOL_MID``
    * ``IVOL_BID``
    * ``IVOL_ASK``

    The output combines model sensitivities and vol marks so users can run both
    directional and relative-value diagnostics from a single request.

    Args:
        ticker: Bloomberg option ticker.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides and legacy kwargs support.

    Returns:
        DataFrame with option Greeks and volatility analytics.
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
        flds=_OPTION_GREEKS_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def option_pricing(
    ticker: str,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return option pricing, value decomposition, and activity metrics.

    Fields returned (SEMI_LONG rows):

    Pricing:

    * ``PX_LAST``
    * ``PX_BID``
    * ``PX_ASK``

    Intrinsic/time decomposition:

    * ``OPT_INTRINSIC_VAL``
    * ``OPT_TRUE_INTRINSIC``
    * ``OPT_TIME_VAL``

    Activity and positioning:

    * ``OPEN_INT``
    * ``PX_VOLUME``
    * ``OPEN_INT_CHANGE``

    This function is designed for practical tape-reading workflows that need
    quote levels, valuation breakdown, and flow context in one table.

    Args:
        ticker: Bloomberg option ticker.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides and legacy kwargs support.

    Returns:
        DataFrame with option pricing and activity fields.
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
        flds=_OPTION_PRICING_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def option_chain(
    underlying: str,
    *,
    put_call: PutCall | str | None = None,
    expiry_dt: str | None = None,
    strike: StrikeRef | str | float | None = None,
    points: int | None = None,
    periodicity: ChainPeriodicity | str | None = None,
    exercise_type: ExerciseType | str | None = None,
    expiry_match: ExpiryMatch | str | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return an option chain via ``CHAIN_TICKERS`` bulk field.

    This function wraps Bloomberg ``bds`` with the ``CHAIN_TICKERS`` field and
    exposes common chain filters as typed named parameters.

    Named parameters map to Bloomberg overrides:

    * ``put_call`` -> ``CHAIN_PUT_CALL_TYPE_OVRD``
    * ``expiry_dt`` -> ``CHAIN_EXP_DT_OVRD``
    * ``strike`` -> ``CHAIN_STRIKE_PX_OVRD``
    * ``points`` -> ``CHAIN_POINTS_OVRD``
    * ``periodicity`` -> ``CHAIN_PERIODICITY_OVRD``
    * ``exercise_type`` -> ``CHAIN_EXERCISE_TYPE_OVRD``
    * ``expiry_match`` -> ``CHAIN_EXP_MATCH_OVRD``

    Notes:
    * ``expiry_dt`` is normalized to ``YYYYMMDD`` when parseable.
    * ``strike`` accepts ``StrikeRef.ATM`` / ``"ATM"`` or a numeric strike.
    * Any explicit ``kwargs`` values take precedence over named parameters.
    * Chain output schema is Bloomberg-defined and may vary by asset class.

    Args:
        underlying: Underlying ticker used to request chain members.
        put_call: Put/call selector.
        expiry_dt: Target expiry date (prefer ``YYYYMMDD``).
        strike: Strike selector (``ATM`` or specific strike).
        points: Number of strikes around reference strike.
        periodicity: Expiry periodicity filter.
        exercise_type: Exercise-style filter.
        expiry_match: Expiry matching mode.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides and legacy kwargs support.

    Returns:
        DataFrame with option chain rows from ``CHAIN_TICKERS``.
    """
    from xbbg.api.reference.reference import bds
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    overrides: dict[str, object] = {}
    if put_call is not None:
        overrides[_OVRD_CHAIN_PUT_CALL_TYPE] = _enum_value(put_call)

    formatted_expiry = _format_expiry_dt(expiry_dt)
    if formatted_expiry is not None:
        overrides[_OVRD_CHAIN_EXP_DT] = formatted_expiry

    formatted_strike = _format_strike(strike)
    if formatted_strike is not None:
        overrides[_OVRD_CHAIN_STRIKE_PX] = formatted_strike

    if points is not None:
        overrides[_OVRD_CHAIN_POINTS] = points

    if periodicity is not None:
        overrides[_OVRD_CHAIN_PERIODICITY] = _enum_value(periodicity)

    if exercise_type is not None:
        overrides[_OVRD_CHAIN_EXERCISE_TYPE] = _enum_value(exercise_type)

    if expiry_match is not None:
        overrides[_OVRD_CHAIN_EXP_MATCH] = _enum_value(expiry_match)

    overrides.update(kwargs)

    call_kwargs = {**safe_kwargs, **overrides}
    return bds(
        underlying,
        _FLD_CHAIN_TICKERS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )


def option_chain_bql(
    underlying: str,
    *,
    put_call: PutCall | str | None = None,
    expiry_start: str | None = None,
    expiry_end: str | None = None,
    strike_low: float | None = None,
    strike_high: float | None = None,
    delta_low: float | None = None,
    delta_high: float | None = None,
    gamma_low: float | None = None,
    gamma_high: float | None = None,
    vega_low: float | None = None,
    vega_high: float | None = None,
    theta_low: float | None = None,
    theta_high: float | None = None,
    ivol_low: float | None = None,
    ivol_high: float | None = None,
    moneyness_low: float | None = None,
    moneyness_high: float | None = None,
    min_open_int: int | None = None,
    min_volume: int | None = None,
    min_bid: float | None = None,
    max_ask: float | None = None,
    exch_code: str | None = None,
    exercise_type: ExerciseType | str | None = None,
    extra_filters: str | None = None,
    get_fields: list[str] | None = None,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return a filtered option chain via BQL.

    BQL provides richer filtering than ``CHAIN_TICKERS`` overrides: filter by
    Greeks, implied volatility, open interest, moneyness, bid/ask prices,
    exchange, and arbitrary combinations.

    Filter parameters map to BQL ``filter()`` predicates on the
    ``options('<underlying>')`` universe:

    * ``put_call`` -> ``put_call=='Call'`` / ``put_call=='Put'``
    * ``expiry_start`` / ``expiry_end`` -> ``expire_dt()>=`` / ``expire_dt()<=``
    * ``strike_low`` / ``strike_high`` -> ``between(strike_px(), low, high)``
    * ``delta_low`` / ``delta_high`` -> ``delta().value>=`` / ``delta().value<=``
    * ``gamma_low`` / ``gamma_high`` -> ``gamma().value>=`` / ``gamma().value<=``
    * ``vega_low`` / ``vega_high`` -> ``vega().value>=`` / ``vega().value<=``
    * ``theta_low`` / ``theta_high`` -> ``theta().value>=`` / ``theta().value<=``
    * ``ivol_low`` / ``ivol_high`` -> ``ivol().value>=`` / ``ivol().value<=``
    * ``moneyness_low`` / ``moneyness_high`` -> ``pct_moneyness().value>=`` / ``<=``
    * ``min_open_int`` -> ``open_int().value>=``
    * ``min_volume`` -> ``volume().value>=``
    * ``min_bid`` -> ``px_bid().value>=``
    * ``max_ask`` -> ``px_ask().value<=``
    * ``exch_code`` -> ``exch_code=='<code>'`` (e.g. ``'Z'`` for CBOE)
    * ``exercise_type`` -> ``exer_typ=='American'`` / ``exer_typ=='European'``
    * ``extra_filters`` -> appended verbatim (for custom BQL predicates)

    If *get_fields* is not provided, defaults to::

        (
            strike_px(),
            expire_dt(),
            ivol(),
            delta(),
        )
        open_int(), px_last(), px_bid(), px_ask()

    Notes:
    * Date values use ISO format (``YYYY-MM-DD``) in BQL predicates.
    * ``extra_filters`` allows arbitrary BQL syntax for advanced use cases
      (e.g. ``"theta().value>=-0.5"``).

    Args:
        underlying: Underlying ticker (e.g. ``'SPY US Equity'``).
        put_call: ``'Call'`` or ``'Put'`` (or :class:`PutCall` enum).
        expiry_start: Earliest expiry date (``YYYY-MM-DD``).
        expiry_end: Latest expiry date (``YYYY-MM-DD``).
        strike_low: Minimum strike price.
        strike_high: Maximum strike price.
        delta_low: Minimum delta (e.g. ``0.3``).
        delta_high: Maximum delta (e.g. ``0.7``).
        gamma_low: Minimum gamma.
        gamma_high: Maximum gamma.
        vega_low: Minimum vega.
        vega_high: Maximum vega.
        theta_low: Minimum theta (note: theta is typically negative).
        theta_high: Maximum theta.
        ivol_low: Minimum implied volatility.
        ivol_high: Maximum implied volatility.
        moneyness_low: Minimum percent moneyness (e.g. ``98`` for 2% OTM).
        moneyness_high: Maximum percent moneyness (e.g. ``102`` for 2% ITM).
        min_open_int: Minimum open interest.
        min_volume: Minimum trading volume.
        min_bid: Minimum bid price (filters illiquid options).
        max_ask: Maximum ask price.
        exch_code: Exchange code filter (e.g. ``'Z'`` for CBOE).
        exercise_type: American or European.
        extra_filters: Additional BQL filter predicates (appended with ``and``).
        get_fields: BQL ``get()`` fields.  Defaults to core pricing/greeks.
        backend: Output backend.
        ctx: Bloomberg context.
        **kwargs: Forwarded to ``blp.bql()``.

    Returns:
        DataFrame with filtered option chain from BQL.
    """
    from xbbg.api.screening import bql as _bql
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()

    # Build get fields
    default_get = [
        "strike_px()",
        "expire_dt()",
        "ivol()",
        "delta()",
        "open_int()",
        "px_last()",
        "px_bid()",
        "px_ask()",
    ]
    get_list = get_fields or default_get
    get_clause = ", ".join(get_list)

    # Build filter predicates
    filters: list[str] = []
    if put_call is not None:
        pc_val = "Call" if str(put_call).upper() in ("C", "CALL") else "Put"
        filters.append(f"put_call=='{pc_val}'")

    if expiry_start is not None:
        filters.append(f"expire_dt()>='{expiry_start}'")
    if expiry_end is not None:
        filters.append(f"expire_dt()<='{expiry_end}'")

    if strike_low is not None and strike_high is not None:
        filters.append(f"between(strike_px(), {strike_low}, {strike_high})")
    elif strike_low is not None:
        filters.append(f"strike_px()>={strike_low}")
    elif strike_high is not None:
        filters.append(f"strike_px()<={strike_high}")

    if delta_low is not None:
        filters.append(f"delta().value>={delta_low}")
    if delta_high is not None:
        filters.append(f"delta().value<={delta_high}")

    if gamma_low is not None:
        filters.append(f"gamma().value>={gamma_low}")
    if gamma_high is not None:
        filters.append(f"gamma().value<={gamma_high}")

    if vega_low is not None:
        filters.append(f"vega().value>={vega_low}")
    if vega_high is not None:
        filters.append(f"vega().value<={vega_high}")

    if theta_low is not None:
        filters.append(f"theta().value>={theta_low}")
    if theta_high is not None:
        filters.append(f"theta().value<={theta_high}")

    if ivol_low is not None:
        filters.append(f"ivol().value>={ivol_low}")
    if ivol_high is not None:
        filters.append(f"ivol().value<={ivol_high}")

    if moneyness_low is not None:
        filters.append(f"pct_moneyness().value>={moneyness_low}")
    if moneyness_high is not None:
        filters.append(f"pct_moneyness().value<={moneyness_high}")

    if min_open_int is not None:
        filters.append(f"open_int().value>={min_open_int}")

    if min_volume is not None:
        filters.append(f"volume().value>={min_volume}")

    if min_bid is not None:
        filters.append(f"px_bid().value>={min_bid}")
    if max_ask is not None:
        filters.append(f"px_ask().value<={max_ask}")

    if exch_code is not None:
        filters.append(f"exch_code=='{exch_code}'")

    if exercise_type is not None:
        ex_val = "American" if str(exercise_type).upper() in ("A", "AMERICAN") else "European"
        filters.append(f"exer_typ=='{ex_val}'")

    if extra_filters:
        filters.append(extra_filters)

    # Build universe clause
    universe = f"options('{underlying}')"
    if filters:
        filter_str = " and ".join(filters)
        for_clause = f"filter({universe}, {filter_str})"
    else:
        for_clause = universe

    query = f"get({get_clause}) for({for_clause})"
    logger.debug("BQL option chain query: %s", query)

    call_kwargs = {**safe_kwargs, **kwargs}
    return _bql(query, backend=backend, **call_kwargs)


def option_screen(
    tickers: list[str],
    flds: list[str] | None = None,
    *,
    backend: Backend | None = None,
    ctx: BloombergContext | None = None,
    **kwargs,
):
    """Return cross-option comparison analytics in one ``bdp`` call.

    ``option_screen`` is intended for multi-contract comparison workflows where
    users want one output table for several option tickers at once.

    If *flds* is not provided, defaults to:

    * Contract descriptors: ``NAME``, ``SECURITY_DES``
    * Contract terms: ``OPT_STRIKE_PX``, ``OPT_EXPIRE_DT``, ``OPT_PUT_CALL``,
      ``OPT_EXER_TYP``, ``OPT_UNDL_TICKER``
    * Underlying/price context: ``OPT_UNDL_PX``, ``PX_LAST``, ``PX_BID``,
      ``PX_ASK``
    * Core risk: ``IVOL_MID``, ``DELTA_MID``, ``GAMMA_MID``, ``VEGA_MID``,
      ``THETA_MID``, ``RHO_MID``
    * Liquidity/positioning: ``OPEN_INT``, ``PX_VOLUME``

    Args:
        tickers: List of Bloomberg option tickers.
        flds: Optional list of fields to request.
        backend: Output backend. If ``None``, uses ``Backend.NARWHALS``.
        ctx: Bloomberg context. If ``None``, extracted from *kwargs*.
        **kwargs: Additional Bloomberg overrides and legacy kwargs support.

    Returns:
        DataFrame with requested analytics across all provided options.
    """
    from xbbg.api.reference import bdp
    from xbbg.core.domain.context import split_kwargs

    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    safe_kwargs = ctx.to_kwargs()
    call_kwargs = {**safe_kwargs, **kwargs}
    return bdp(
        tickers=tickers,
        flds=flds or _OPTION_SCREEN_DEFAULT_FIELDS,
        backend=backend or Backend.NARWHALS,
        format=Format.SEMI_LONG,
        **call_kwargs,
    )
