"""Processing utilities for Bloomberg event messages and requests.

Includes helpers to create requests, initialize overrides, iterate
Bloomberg event streams, and parse reference, historical, and intraday data.
"""

from __future__ import annotations

from collections.abc import Iterator
import importlib
from itertools import starmap
import logging
from typing import TYPE_CHECKING, Any

pd = importlib.import_module("pandas")

from xbbg import const  # noqa: E402
from xbbg.core.config import intervals, overrides  # noqa: E402
from xbbg.core.infra import conn  # noqa: E402
from xbbg.core.infra.blpapi_wrapper import blpapi, is_available  # noqa: E402
from xbbg.core.utils import timezone, utils as utils_module  # noqa: E402

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

DEFAULT_TZ = timezone.DEFAULT_TZ

logger = logging.getLogger(__name__)

try:
    from xbbg.core.infra import blpapi_logging
except ImportError:
    blpapi_logging = None  # type: ignore[assignment]

# Pre-create blpapi.Name objects for performance (avoid repeated string lookups)
# Guard with is_available() to allow import when blpapi is not installed
RESPONSE_ERROR = blpapi.Name("responseError") if is_available() else None
SESSION_TERMINATED = blpapi.Name("SessionTerminated") if is_available() else None
CATEGORY = blpapi.Name("category") if is_available() else None
MESSAGE = blpapi.Name("message") if is_available() else None
BAR_DATA = blpapi.Name("barData") if is_available() else None
BAR_TICK = blpapi.Name("barTickData") if is_available() else None
TICK_DATA = blpapi.Name("tickData") if is_available() else None
RESULTS = blpapi.Name("results") if is_available() else None
TABLE = blpapi.Name("table") if is_available() else None
COLUMNS = blpapi.Name("columns") if is_available() else None
ROWS = blpapi.Name("rows") if is_available() else None
VALUES = blpapi.Name("values") if is_available() else None
NAME = blpapi.Name("name") if is_available() else None
FIELD = blpapi.Name("field") if is_available() else None


def create_request(
    service: str,
    request: str,
    settings: list[tuple[str, Any]] | None = None,
    ovrds: list[tuple[str, Any]] | dict[str, Any] | None = None,
    append: dict[str, Any] | None = None,
    **kwargs,
) -> Any:
    """Create a Bloomberg request for a given service and request type.

    Args:
        service: service name
        request: request name
        settings: list of settings
        ovrds: overrides as list of (field, value) tuples or dict mapping field to value
        append: info to be appended to request directly
        **kwargs: Additional options forwarded to session/service helpers.

    Returns:
        Bloomberg request.
    """
    srv = conn.bbg_service(service=service, **kwargs)
    req = srv.createRequest(request)

    list(starmap(req.set, settings if settings else []))
    if ovrds:
        if isinstance(ovrds, dict):
            ovrds = list(ovrds.items())
        ovrd = req.getElement(blpapi.Name("overrides"))
        for fld, val in ovrds:
            item = ovrd.appendElement()
            item.setElement(blpapi.Name("fieldId"), fld)
            item.setElement(blpapi.Name("value"), val)
    if append:
        for key, val in append.items():
            vals = [val] if isinstance(val, str) else val
            for v in vals:
                req.append(blpapi.Name(key), v)

    return req


def init_request(request: Any, tickers, flds, **kwargs):
    """Initiate a Bloomberg request instance.

    Args:
        request: Bloomberg request to initiate and append.
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields.
        **kwargs: Overrides and element options; supports shorthand keys
            parsed by ``overrides.proc_elms`` and ``overrides.proc_ovrds``.
    """
    tickers = utils_module.normalize_tickers(tickers)
    for ticker in tickers:
        request.append(blpapi.Name("securities"), ticker)

    flds = utils_module.normalize_flds(flds)
    for fld in flds:
        request.append(blpapi.Name("fields"), fld)

    # Pop explicit ovrds to prevent proc_ovrds from treating the key itself
    # as a Bloomberg override field.  create_request() (which is always called
    # before init_request) already applies ovrds to the request correctly.
    kwargs.pop("ovrds", None)

    adjust = kwargs.pop("adjust", None)
    if isinstance(adjust, str) and adjust:
        if adjust == "all":
            kwargs["CshAdjNormal"] = True
            kwargs["CshAdjAbnormal"] = True
            kwargs["CapChg"] = True
        else:
            kwargs["CshAdjNormal"] = "normal" in adjust or "dvd" in adjust
            kwargs["CshAdjAbnormal"] = "abn" in adjust or "dvd" in adjust
            kwargs["CapChg"] = "split" in adjust

    if "start_date" in kwargs:
        request.set(blpapi.Name("startDate"), kwargs.pop("start_date"))
    if "end_date" in kwargs:
        request.set(blpapi.Name("endDate"), kwargs.pop("end_date"))

    for elem_name, elem_val in overrides.proc_elms(**kwargs):
        request.set(elem_name, elem_val)

    ovrds = request.getElement(blpapi.Name("overrides"))
    for ovrd_fld, ovrd_val in overrides.proc_ovrds(**kwargs):
        ovrd = ovrds.appendElement()
        ovrd.setElement(blpapi.Name("fieldId"), ovrd_fld)
        ovrd.setElement(blpapi.Name("value"), ovrd_val)


def time_range(
    dt,
    ticker,
    session: str = "allday",
    tz: str = "UTC",
    ctx: BloombergContext | None = None,
    **kwargs,
) -> intervals.Session:
    """Time range in UTC (for intraday bar) or other timezone.

    Args:
        dt: Date-like input to compute the range for.
        ticker: Ticker.
        session: Market session defined in exchange metadata.
        tz: Target timezone name or tz-resolvable input.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        intervals.Session.
    """
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra
    # Ignore pmc_extended in kwargs for backward compatibility
    kwargs.pop("pmc_extended", None)

    session_kwargs = ctx.to_kwargs()

    # Resolve session from exchange metadata
    result = _time_range_from_exch_metadata(
        dt=dt,
        ticker=ticker,
        session=session,
        tz=tz,
        session_kwargs=session_kwargs,
    )
    if result is not None:
        return result

    # Nothing worked -- propagate a clear error
    raise ValueError(
        f'Unable to resolve trading session "{session}" for ticker {ticker} on date {dt}. '
        f"Session is not defined in exchange metadata."
    )


def _normalize_dest_tz(tz: str) -> str:
    """Normalize destination timezone aliases (e.g., 'NY' -> full tz)."""
    try:
        return timezone.get_tz(tz)
    except (ValueError, KeyError, TypeError):
        return tz


def _time_range_from_exch_metadata(
    dt,
    ticker: str,
    session: str,
    tz: str,
    session_kwargs: dict[str, Any],
) -> intervals.Session | None:
    """Resolve time range using exchange metadata, or return None on failure."""
    logger = logging.getLogger(__name__)

    try:
        ss = intervals.get_interval(ticker=ticker, session=session, **session_kwargs)
        ex_info = const.exch_info(ticker=ticker, **session_kwargs)
    except ValueError:
        # ValueError from get_interval means session is not defined - propagate
        raise
    except (KeyError, AttributeError, TypeError, IndexError):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Primary session resolution failed for %s on %s; falling back to PMC",
                ticker,
                dt,
                exc_info=True,
            )
        return None

    has_session = (ss.start_time is not None) and (ss.end_time is not None)
    has_tz = hasattr(ex_info, "index") and ("tz" in ex_info.index)
    if not (has_session and has_tz):
        return None

    cur_dt = pd.Timestamp(dt).strftime("%Y-%m-%d")
    time_fmt = "%Y-%m-%dT%H:%M:%S"
    dest_tz = _normalize_dest_tz(tz)

    time_idx = (
        pd.DatetimeIndex(
            [
                f"{cur_dt} {ss.start_time}",
                f"{cur_dt} {ss.end_time}",
            ],
        )
        .tz_localize(ex_info.tz)
        .tz_convert(DEFAULT_TZ)
        .tz_convert(dest_tz)
    )
    if time_idx[0] > time_idx[1]:
        time_idx -= pd.TimedeltaIndex(["1D", "0D"])
    return intervals.Session(
        time_idx[0].strftime(time_fmt),
        time_idx[1].strftime(time_fmt),
    )


def process_ref(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process reference messages from Bloomberg.

    Args:
        msg: Bloomberg reference data messages from events.
        **kwargs: Additional options (unused).

    Returns:
        dict.
    """
    kwargs.pop("(@_<)", None)
    data = None
    if msg.hasElement(blpapi.Name("securityData")):
        data = msg.getElement(blpapi.Name("securityData"))
    elif msg.hasElement(blpapi.Name("data")) and msg.getElement(blpapi.Name("data")).hasElement(
        blpapi.Name("securityData")
    ):
        data = msg.getElement(blpapi.Name("data")).getElement(blpapi.Name("securityData"))
    if not data:
        logger.debug("No securityData found in reference message - returning empty result")
        return iter([])

    for sec in data.values():
        ticker = sec.getElement("security").getValue()
        for fld in sec.getElement("fieldData").elements():
            info = [("ticker", ticker), ("field", str(fld.name()))]
            if fld.isArray():
                for item in fld.values():
                    yield dict(
                        info
                        + [(str(elem.name()), None if elem.isNull() else elem.getValue()) for elem in item.elements()]
                    )
            else:
                yield dict(
                    info
                    + [
                        ("value", None if fld.isNull() else fld.getValue()),
                    ]
                )


def process_hist(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process historical data messages from Bloomberg.

    Args:
        msg: Bloomberg historical data messages from events.
        **kwargs: Additional options (unused).

    Returns:
        dict.
    """
    kwargs.pop("(>_<)", None)
    if not msg.hasElement(blpapi.Name("securityData")):
        logger.debug("No securityData found in historical message - returning empty result")
        return {}
    ticker = msg.getElement(blpapi.Name("securityData")).getElement(blpapi.Name("security")).getValue()
    for val in msg.getElement(blpapi.Name("securityData")).getElement(blpapi.Name("fieldData")).values():
        if val.hasElement(blpapi.Name("date")):
            yield dict([("ticker", ticker)] + [(str(elem.name()), elem.getValue()) for elem in val.elements()])


def process_bar(msg: Any, typ="bar", **kwargs) -> Iterator[dict[str, Any]]:
    """Process Bloomberg intraday bar messages.

    Args:
        msg: Bloomberg intraday bar messages from events.
        typ: ``bar`` or ``tick``.
        **kwargs: Additional options (unused).

    Yields:
        dict.
    """
    kwargs.pop("(#_#)", None)
    check_error(msg=msg)
    lvls = [TICK_DATA, TICK_DATA] if typ[0].lower() == "t" else [BAR_DATA, BAR_TICK]

    if msg.hasElement(lvls[0]):
        for bar in msg.getElement(lvls[0]).getElement(lvls[1]).values():
            yield {str(elem.name()): elem.getValue() for elem in bar.elements()}


def check_error(msg):
    """Check error in message."""
    if msg.hasElement(RESPONSE_ERROR):
        error = msg.getElement(RESPONSE_ERROR)
        category = error.getElementAsString(CATEGORY)
        message = error.getElementAsString(MESSAGE)
        # Log error before raising - ensures diagnostic info is captured even if exception is swallowed
        logger.error("Bloomberg API error: category=%s, message=%s", category, message)
        raise ValueError(f"[Intraday Bar Error] {category}: {message}")


def elem_value(element: Any):
    """Get value from element.

    Args:
        element: Bloomberg element.

    Returns:
        Value.
    """
    if element.isNull():
        return None
    try:
        value = element.getValue()
    except ValueError:
        return None
    # Handle numpy scalar types (bool_, int64, float64, etc.) without importing numpy
    if hasattr(value, "item") and hasattr(type(value), "__module__") and "numpy" in str(type(value).__module__):
        return value.item()
    if isinstance(value, blpapi.Name):
        return str(value)
    return value


def _flatten_element(element: Any) -> dict[str, Any]:
    """Recursively flatten a generic Bloomberg element to a dict."""
    out: dict[str, Any] = {}
    for elem in element.elements():
        key = str(elem.name())
        if elem.isArray():
            out[key] = [elem_value(v) if not v.isComplexType() else _flatten_element(v) for v in elem.values()]
        elif elem.isComplexType():
            out[key] = _flatten_element(elem)
        else:
            out[key] = elem_value(elem)
    return out


def process_bql(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process BQL response messages into row dictionaries.

    Attempts to parse tabular BQL results; falls back to flattened dicts.
    Handles both structured ``results`` element and JSON string ``result``
    element. The detailed parsing is delegated to helpers for readability.

    Args:
        msg: Bloomberg BQL message.
        **kwargs: Unused.

    Yields:
        dict: Row-like mappings parsed from BQL results.
    """
    kwargs.pop("(^_^)", None)

    # Gate: Only process messages with BQL-specific message type "result"
    # This ensures we don't accidentally process non-BQL messages
    if str(msg.messageType()) != "result":
        return iter([])

    # 1) Try JSON-string payload format first
    handled_any = False
    for row in _iter_bql_json_rows(msg):
        handled_any = True
        yield row
    if handled_any:
        return

    # 2) Fallback: structured BQL elements (RESULTS/TABLE)
    if msg.hasElement(RESULTS):
        yield from _iter_bql_structured_rows(msg)


def _iter_bql_json_rows(msg: Any) -> Iterator[dict[str, Any]]:
    """Iterate rows from JSON-string BQL result payload, if present.

    Merges multiple fields by ID to avoid duplicate rows when multiple fields
    are requested in a single query.
    """
    from collections import defaultdict
    import json

    msg_elem = msg.asElement()
    if msg_elem.datatype() != blpapi.DataType.STRING:
        return iter(())

    try:
        result_str = msg_elem.getValue()
        if not isinstance(result_str, str):
            return iter(())
        result_json = json.loads(result_str)

        # Check for errors first - raise exception if errors found
        if "responseExceptions" in result_json and result_json["responseExceptions"]:
            errors = result_json["responseExceptions"]
            error_messages = []
            for exc in errors:
                msg_text = exc.get("message", exc.get("internalMessage", "Unknown error"))
                error_messages.append(msg_text)
            error_msg = "; ".join(error_messages)
            raise ValueError(f"BQL query error: {error_msg}")

        if "results" not in result_json:
            return iter(())

        results_data = result_json.get("results")
        # Handle None results (empty query result)
        if results_data is None or not isinstance(results_data, dict):
            return iter(())

        # Collect all rows by ID to merge fields
        rows_by_id: dict[str, dict[str, Any]] = defaultdict(dict)
        has_structured_fields = False

        for field_name, field_data in results_data.items():
            if not isinstance(field_data, dict):
                continue

            # idColumn / valuesColumn schema
            if "idColumn" in field_data and "valuesColumn" in field_data:
                has_structured_fields = True
                ids = field_data["idColumn"].get("values", [])
                values = field_data["valuesColumn"].get("values", [])
                secondary_cols: dict[str, list[Any]] = {}
                if "secondaryColumns" in field_data:
                    for sec_col in field_data["secondaryColumns"]:
                        col_name = sec_col.get("name", "")
                        col_values = sec_col.get("values", [])
                        secondary_cols[col_name] = col_values

                # Check if IDs have duplicates (like eco_calendar where all rows have same ID)
                # In that case, we can't merge by ID - yield rows directly
                has_duplicate_ids = len(ids) != len(set(ids))
                if has_duplicate_ids:
                    # Duplicate IDs - yield rows directly, don't merge by ID
                    for i, (ticker, value) in enumerate(zip(ids, values, strict=False)):
                        row: dict[str, Any] = {
                            "ID": ticker,
                            field_name: value,
                        }
                        for col_name, col_values in secondary_cols.items():
                            if i < len(col_values):
                                row[col_name] = col_values[i]
                        yield row
                else:
                    # Unique IDs: merge fields by ID
                    for i, (ticker, value) in enumerate(zip(ids, values, strict=False)):
                        if ticker not in rows_by_id:
                            rows_by_id[ticker]["ID"] = ticker
                        rows_by_id[ticker][field_name] = value

                        # Add secondary columns
                        for col_name, col_values in secondary_cols.items():
                            if i < len(col_values):
                                rows_by_id[ticker][col_name] = col_values[i]
            # rows schema (e.g., other table-based BQL results)
            elif "rows" in field_data and isinstance(field_data["rows"], list):
                rows_list = field_data["rows"]
                for row_data in rows_list:
                    if isinstance(row_data, dict):
                        yield row_data
                    else:
                        yield {field_name: row_data}
            else:
                # Fallback: flatten arbitrary dict structure
                # For non-structured fields, yield immediately (can't merge by ID)
                yield dict(_flatten_dict(field_data))

        # Yield merged rows if we had structured fields
        if has_structured_fields:
            yield from rows_by_id.values()
    except (json.JSONDecodeError, KeyError, TypeError):
        # Let caller fall back to structured-element parsing
        return iter(())


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """Flatten a nested dict using ``sep`` between levels."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _iter_bql_structured_rows(msg: Any) -> Iterator[dict[str, Any]]:
    """Iterate rows from structured ``RESULTS/TABLE`` BQL format."""
    for res in msg.getElement(RESULTS).values():
        if not res.hasElement(TABLE):
            # Fallback: flatten entire result element
            yield dict(_flatten_element(res))
            continue

        table = res.getElement(TABLE)
        if not (table.hasElement(COLUMNS) and table.hasElement(ROWS)):
            yield dict(_flatten_element(res))
            continue

        cols: list[str] = []
        for col in table.getElement(COLUMNS).values():
            if col.hasElement(NAME):
                cols.append(col.getElement(NAME).getValue())
            elif col.hasElement(FIELD):
                cols.append(str(col.getElement(FIELD).getValue()))
            else:
                cols.append(str(col.name()))

        for row in table.getElement(ROWS).values():
            values: list[Any] = []
            if row.hasElement(VALUES):
                for v in row.getElement(VALUES).values():
                    values.append(elem_value(v) if not v.isComplexType() else _flatten_element(v))
            # Defensive: skip rows with mismatched column/value counts
            if len(values) != len(cols):
                continue
            yield dict(zip(cols, values, strict=False))


def earning_pct(data: Any, yr):
    """Calculate % of earnings by year.

    Optimized implementation using vectorized operations where possible.
    """
    pct = f"{yr}_pct"
    data.loc[:, pct] = float("nan")

    # Calculate level 1 percentage (vectorized)
    level_1_mask = data.level == 1
    if level_1_mask.any():
        level_1_sum = data.loc[level_1_mask, yr].sum()
        if level_1_sum != 0:
            data.loc[level_1_mask, pct] = 100 * data.loc[level_1_mask, yr] / level_1_sum

    # Calculate level 2 percentage
    # Iterate backwards to group level 2 rows by their level 1 parent
    # Use vectorized operations for the actual percentage calculation
    data_reset = data.reset_index()
    level_2_indices = []

    for i in range(len(data_reset) - 1, -1, -1):
        row_level = data_reset.iloc[i]["level"]
        if row_level > 2:
            continue
        if row_level == 1:
            if level_2_indices:
                # Calculate percentage for level 2 group (vectorized)
                level_2_idx = data_reset.iloc[level_2_indices].index
                group_sum = data.loc[level_2_idx, yr].sum()
                if group_sum != 0:
                    data.loc[level_2_idx, pct] = 100 * data.loc[level_2_idx, yr] / group_sum
            level_2_indices = []
        if row_level == 2:
            level_2_indices.append(i)

    # Handle remaining level 2 positions at the beginning
    if level_2_indices:
        level_2_idx = data_reset.iloc[level_2_indices].index
        group_sum = data.loc[level_2_idx, yr].sum()
        if group_sum != 0:
            data.loc[level_2_idx, pct] = 100 * data.loc[level_2_idx, yr] / group_sum


def process_bsrch(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process BSRCH GridResponse messages from Bloomberg Excel service.

    Args:
        msg: Bloomberg GridResponse message from exrsvc.
        **kwargs: Additional options (unused).

    Yields:
        dict: Row dictionaries with column names as keys.
    """
    kwargs.pop("(^_^)", None)

    if str(msg.messageType()) != "GridResponse":
        return iter([])

    try:
        # Get grid structure
        num_records_elem = msg.getElement(blpapi.Name("NumOfRecords"))
        num_records = int(num_records_elem.getValue())

        column_titles = msg.getElement(blpapi.Name("ColumnTitles"))
        num_cols = column_titles.numValues()

        # Extract column names
        col_names = []
        for i in range(num_cols):
            col_names.append(column_titles.getValue(i))

        # Extract data records
        data_records = msg.getElement(blpapi.Name("DataRecords"))

        # Process all records
        for i in range(num_records):
            data_record = data_records.getValueAsElement(i)
            data_fields = data_record.getElement(blpapi.Name("DataFields"))

            row = {}
            for j in range(num_cols):
                data_field = data_fields.getValueAsElement(j)
                data_value = data_field.getChoice()

                # Extract value - Python blpapi getValue() returns appropriate type
                try:
                    val = data_value.getValue()
                    row[col_names[j]] = val
                except Exception:
                    row[col_names[j]] = str(data_value)

            yield row

    except Exception as e:
        logger.exception("Error processing BSRCH GridResponse: %s", e)
        return iter([])


def check_current(dt, logger, **kwargs) -> bool:
    """Check current time against T-1.

    Uses UTC for current time to ensure consistent behavior across servers.
    """
    # Use UTC for 'today' to avoid server location dependencies
    t_1 = pd.Timestamp("today", tz="UTC").date() - pd.Timedelta("1D")
    whole_day = pd.Timestamp(dt).date() < t_1
    if (not whole_day) and kwargs.get("batch", False):
        logger.warning("Query date %s is too close to current time, skipping download to avoid incomplete data", t_1)
        return False
    return True


def process_tasvc(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process TASVC (Technical Analysis) studyResponse messages.

    Args:
        msg: Bloomberg TASVC message.
        **kwargs: Unused.

    Yields:
        dict: Row-like mappings with date and study values.
    """
    kwargs.pop("(^_^)", None)

    # Only process studyResponse messages
    if str(msg.messageType()) != "studyResponse":
        return iter([])

    try:
        # Check for field exceptions
        if msg.hasElement("fieldExceptions"):
            field_exceptions = msg.getElement("fieldExceptions")
            if field_exceptions.numValues() > 0:
                logger.warning("TASVC field exceptions: %s", field_exceptions)

        # Get studyData array
        if not msg.hasElement("studyData"):
            logger.warning("No studyData in TASVC response")
            return iter([])

        study_data = msg.getElement("studyData")
        num_records = study_data.numValues()

        for i in range(num_records):
            record = study_data.getValueAsElement(i)
            row = {}

            # Extract all elements from the record
            for j in range(record.numElements()):
                elem = record.getElement(j)
                elem_name = str(elem.name())
                try:
                    row[elem_name] = elem.getValue()
                except Exception:
                    row[elem_name] = str(elem)

            yield row

    except Exception as e:
        logger.exception("Error processing TASVC studyResponse: %s", e)
        return iter([])


def process_bqr(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    """Process BQR (Quote Request) tick messages with broker codes.

    BQR is implemented as an IntradayTickRequest with BID/ASK event types
    and includeBrokerCodes=true. This function extracts the tick data
    including broker information for dealer quotes.

    Args:
        msg: Bloomberg IntradayTickResponse message.
        **kwargs: Additional options (unused).

    Yields:
        dict: Row dictionaries with time, type, value, size, and broker codes.
    """
    kwargs.pop("(^_^)", None)
    check_error(msg=msg)

    tick_data_name = blpapi.Name("tickData")

    if not msg.hasElement(tick_data_name):
        return iter([])

    try:
        tick_element = msg.getElement(tick_data_name)

        # tickData contains another tickData array with the actual ticks
        if not tick_element.hasElement(tick_data_name):
            return iter([])

        tick_array = tick_element.getElement(tick_data_name)

        for i in range(tick_array.numValues()):
            tick = tick_array.getValueAsElement(i)
            row = {}

            # Extract all elements from the tick
            for j in range(tick.numElements()):
                elem = tick.getElement(j)
                elem_name = str(elem.name())
                try:
                    if elem.isNull():
                        row[elem_name] = None
                    else:
                        value = elem.getValue()
                        # Convert blpapi.Name to string for serialization
                        if isinstance(value, blpapi.Name):
                            value = str(value)
                        row[elem_name] = value
                except Exception:
                    row[elem_name] = str(elem)

            yield row

    except Exception as e:
        logger.exception("Error processing BQR tick response: %s", e)
        return iter([])
