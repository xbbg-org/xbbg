"""Processing utilities for Bloomberg event messages and requests.

Includes helpers to create requests, initialize overrides, iterate
Bloomberg event streams, and parse reference, historical, and intraday data.
"""

from collections import OrderedDict
from collections.abc import Iterator
from itertools import starmap
from typing import Any

import numpy as np
import pandas as pd

try:
    import blpapi  # type: ignore[reportMissingImports]
except (ImportError, AttributeError):
    import pytest  # type: ignore[reportMissingImports]
    blpapi = pytest.importorskip('blpapi')

import logging

from xbbg import const
from xbbg.core import conn, intervals, overrides
from xbbg.core.timezone import DEFAULT_TZ

logger = logging.getLogger(__name__)

# Import blpapi logging helpers (optional, won't break if blpapi unavailable)
try:
    from xbbg.core import blpapi_logging
except ImportError:
    blpapi_logging = None  # type: ignore[assignment]

RESPONSE_ERROR = blpapi.Name("responseError")
SESSION_TERMINATED = blpapi.Name("SessionTerminated")
CATEGORY = blpapi.Name("category")
MESSAGE = blpapi.Name("message")
BAR_DATA = blpapi.Name('barData')
BAR_TICK = blpapi.Name('barTickData')
TICK_DATA = blpapi.Name('tickData')
RESULTS = blpapi.Name('results')
TABLE = blpapi.Name('table')
COLUMNS = blpapi.Name('columns')
ROWS = blpapi.Name('rows')
VALUES = blpapi.Name('values')
NAME = blpapi.Name('name')
FIELD = blpapi.Name('field')


def create_request(
        service: str,
        request: str,
        settings: list | None = None,
        ovrds: list | None = None,
        append: dict | None = None,
        **kwargs,
) -> blpapi.Request:
    """Create a Bloomberg request for a given service and request type.

    Args:
        service: service name
        request: request name
        settings: list of settings
        ovrds: list of overrides
        append: info to be appended to request directly
        **kwargs: Additional options forwarded to session/service helpers.

    Returns:
        Bloomberg request.
    """
    srv = conn.bbg_service(service=service, **kwargs)
    req = srv.createRequest(request)

    list(starmap(req.set, settings if settings else []))
    if ovrds:
        ovrd = req.getElement(blpapi.Name('overrides'))
        for fld, val in ovrds:
            item = ovrd.appendElement()
            item.setElement(blpapi.Name('fieldId'), fld)
            item.setElement(blpapi.Name('value'), val)
    if append:
        for key, val in append.items():
            vals = [val] if isinstance(val, str) else val
            for v in vals: req.append(blpapi.Name(key), v)

    return req


def init_request(request: blpapi.Request, tickers, flds, **kwargs):
    """Initiate a Bloomberg request instance.

    Args:
        request: Bloomberg request to initiate and append.
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields.
        **kwargs: Overrides and element options; supports shorthand keys
            parsed by ``overrides.proc_elms`` and ``overrides.proc_ovrds``.
    """
    while conn.bbg_session(**kwargs).tryNextEvent(): pass

    if isinstance(tickers, str): tickers = [tickers]
    for ticker in tickers: request.append(blpapi.Name('securities'), ticker)

    if isinstance(flds, str): flds = [flds]
    for fld in flds: request.append(blpapi.Name('fields'), fld)

    adjust = kwargs.pop('adjust', None)
    if isinstance(adjust, str) and adjust:
        if adjust == 'all':
            kwargs['CshAdjNormal'] = True
            kwargs['CshAdjAbnormal'] = True
            kwargs['CapChg'] = True
        else:
            kwargs['CshAdjNormal'] = 'normal' in adjust or 'dvd' in adjust
            kwargs['CshAdjAbnormal'] = 'abn' in adjust or 'dvd' in adjust
            kwargs['CapChg'] = 'split' in adjust

    if 'start_date' in kwargs: request.set(blpapi.Name('startDate'), kwargs.pop('start_date'))
    if 'end_date' in kwargs: request.set(blpapi.Name('endDate'), kwargs.pop('end_date'))

    for elem_name, elem_val in overrides.proc_elms(**kwargs):
        request.set(elem_name, elem_val)

    ovrds = request.getElement(blpapi.Name('overrides'))
    for ovrd_fld, ovrd_val in overrides.proc_ovrds(**kwargs):
        ovrd = ovrds.appendElement()
        ovrd.setElement(blpapi.Name('fieldId'), ovrd_fld)
        ovrd.setElement(blpapi.Name('value'), ovrd_val)


def time_range(dt, ticker, session='allday', tz='UTC', **kwargs) -> intervals.Session:
    """Time range in UTC (for intraday bar) or other timezone.

    Args:
        dt: Date-like input to compute the range for.
        ticker: Ticker.
        session: Market session defined in ``markets/exch.yml``.
        tz: Target timezone name or tz-resolvable input.
        **kwargs: Passed to exchange/session resolvers.

    Returns:
        intervals.Session.
    """
    pmc_extended = bool(kwargs.pop('pmc_extended', False))

    logger = logging.getLogger(__name__)

    # First try legacy exch.yml-based sessions
    try:
        ss = intervals.get_interval(ticker=ticker, session=session, **kwargs)
        ex_info = const.exch_info(ticker=ticker, **kwargs)
        has_session = (ss.start_time is not None) and (ss.end_time is not None)
        has_tz = ('tz' in ex_info.index) if hasattr(ex_info, 'index') else False
        if has_session and has_tz:
            cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
            time_fmt = '%Y-%m-%dT%H:%M:%S'
            # Normalize destination timezone aliases (e.g., 'NY' -> full tz)
            try:
                from xbbg.core import timezone as _tz
                dest_tz = _tz.get_tz(tz)
            except Exception:
                dest_tz = tz
            time_idx = (
                pd.DatetimeIndex([
                    f'{cur_dt} {ss.start_time}',
                    f'{cur_dt} {ss.end_time}'],
                )
                .tz_localize(ex_info.tz)
                .tz_convert(DEFAULT_TZ)
                .tz_convert(dest_tz)
            )
            if time_idx[0] > time_idx[1]: time_idx -= pd.TimedeltaIndex(['1D', '0D'])
            return intervals.Session(time_idx[0].strftime(time_fmt), time_idx[1].strftime(time_fmt))
    except Exception:  # noqa: BLE001
        # Fall through to PMC fallback - exception is expected and handled by fallback logic.
        # We intentionally do not re-raise here because the PMC-based fallback below
        # provides a secondary path to resolve the session.
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                'Primary session resolution failed for %s on %s; falling back to PMC',
                ticker,
                dt,
                exc_info=True,
            )

    # Fallback: try pandas-market-calendars via exch_code mapping
    try:
        from xbbg.markets.pmc import pmc_session_for_date
        pmc_ss = pmc_session_for_date(
            ticker=ticker, dt=dt, session=session, include_extended=pmc_extended, **kwargs
        )
    except Exception:
        pmc_ss = None
    if pmc_ss is not None:
        logger.warning('Exchange session metadata not available for %s (session=%s), falling back to pandas-market-calendars', ticker, session)
        cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
        time_fmt = '%Y-%m-%dT%H:%M:%S'
        try:
            from xbbg.core import timezone as _tz
            dest_tz = _tz.get_tz(tz)
        except Exception:
            dest_tz = tz
        time_idx = (
            pd.DatetimeIndex([
                f'{cur_dt} {pmc_ss.start}',
                f'{cur_dt} {pmc_ss.end}'],
            )
            .tz_localize(pmc_ss.tz)
            .tz_convert(DEFAULT_TZ)
            .tz_convert(dest_tz)
        )
        if time_idx[0] > time_idx[1]: time_idx -= pd.TimedeltaIndex(['1D', '0D'])
        return intervals.Session(time_idx[0].strftime(time_fmt), time_idx[1].strftime(time_fmt))

    # If all fails, return an empty session in UTC day bounds (conservative)
    logger.error('Unable to resolve trading session for ticker %s on date %s', ticker, dt)
    return intervals.SessNA


def _process_response_event(ev: blpapi.Event, func, **kwargs):
    """Process RESPONSE or PARTIAL_RESPONSE event.

    Args:
        ev: Bloomberg event.
        func: Generator function yielding parsed messages.
        **kwargs: Arguments forwarded to func.

    Yields:
        Elements from func.

    Returns:
        True if final RESPONSE received (should stop), False otherwise.
    """
    msg_count = 0
    for msg in ev:
        msg_count += 1
        if blpapi_logging:
            blpapi_logging.log_message_info(msg, context='rec_events')
        yield from func(msg=msg, **kwargs)

    if logger.isEnabledFor(logging.DEBUG):
        event_type_str = 'RESPONSE' if ev.eventType() == blpapi.Event.RESPONSE else 'PARTIAL_RESPONSE'
        logger.debug('Processed %d message(s) from %s event', msg_count, event_type_str)

    is_final = ev.eventType() == blpapi.Event.RESPONSE
    if is_final and logger.isEnabledFor(logging.DEBUG):
        logger.debug('Received final RESPONSE event, completing event processing')
    # Return value from generator - will be available via StopIteration.value
    return is_final


def _handle_timeout(timeout_counts: int, max_timeouts: int) -> tuple[int, bool]:
    """Handle timeout event.

    Args:
        timeout_counts: Current timeout count.
        max_timeouts: Maximum allowed timeouts.

    Returns:
        Tuple of (updated_timeout_counts, should_stop_flag).
    """
    timeout_counts += 1
    should_stop = timeout_counts > max_timeouts

    if timeout_counts % 5 == 0 or should_stop:
        if should_stop:
            logger.warning('Maximum timeout count (%d) reached, stopping event processing', max_timeouts)
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug('Event timeout %d/%d', timeout_counts, max_timeouts)

    return timeout_counts, should_stop


def _handle_other_event(ev: blpapi.Event) -> bool:
    """Handle other event types (e.g., SESSION_TERMINATED).

    Args:
        ev: Bloomberg event.

    Returns:
        True if should stop processing, False otherwise.
    """
    for _ in ev:
        if getattr(ev, 'messageType', lambda: None)() == SESSION_TERMINATED:
            logger.warning('Session terminated event received, stopping event processing')
            return True
    return False


def rec_events(func, event_queue: blpapi.EventQueue | None = None, **kwargs):
    """Receive and iterate events from Bloomberg.

    Args:
        func: Generator function yielding parsed messages.
        event_queue: Optional queue to read events from; defaults to session queue.
        **kwargs: Arguments forwarded to ``func`` and session access.

    Yields:
        Elements of Bloomberg responses.
    """
    timeout_counts = 0
    responses = [blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE]
    timeout = kwargs.pop('timeout', 500)
    max_timeouts = kwargs.pop('max_timeouts', 20)  # Allow configurable max timeouts

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Starting Bloomberg event processing (timeout=%dms, max_timeouts=%d)', timeout, max_timeouts)
    while True:
        if event_queue is not None:
            ev = event_queue.nextEvent(timeout=timeout)
        else:
            ev = conn.bbg_session(**kwargs).nextEvent(timeout=timeout)

        if blpapi_logging and logger.isEnabledFor(logging.DEBUG):
            blpapi_logging.log_event_info(ev, context='rec_events')

        if ev.eventType() in responses:
            # Process response event (generator that yields messages)
            gen = _process_response_event(ev, func, **kwargs)
            # Yield all values from the generator
            try:
                while True:
                    yield next(gen)
            except StopIteration as e:
                # Generator exhausted, check return value
                if e.value:  # True if final RESPONSE
                    break
        elif ev.eventType() == blpapi.Event.TIMEOUT:
            timeout_counts, should_stop = _handle_timeout(timeout_counts, max_timeouts)
            if should_stop:
                break
        else:
            if _handle_other_event(ev):
                break


def process_ref(msg: blpapi.Message, **kwargs) -> Iterator[dict]:
    """Process reference messages from Bloomberg.

    Args:
        msg: Bloomberg reference data messages from events.
        **kwargs: Additional options (unused).

    Returns:
        dict.
    """
    kwargs.pop('(@_<)', None)
    data = None
    if msg.hasElement(blpapi.Name('securityData')):
        data = msg.getElement(blpapi.Name('securityData'))
    elif msg.hasElement(blpapi.Name('data')) and \
            msg.getElement(blpapi.Name('data')).hasElement(blpapi.Name('securityData')):
        data = msg.getElement(blpapi.Name('data')).getElement(blpapi.Name('securityData'))
    if not data: return iter([])

    for sec in data.values():
        ticker = sec.getElement('security').getValue()
        for fld in sec.getElement('fieldData').elements():
            info = [('ticker', ticker), ('field', str(fld.name()))]
            if fld.isArray():
                for item in fld.values():
                    yield OrderedDict(info + [
                        (
                            str(elem.name()),
                            None if elem.isNull() else elem.getValue()
                        )
                        for elem in item.elements()
                    ])
            else:
                yield OrderedDict(info + [
                    ('value', None if fld.isNull() else fld.getValue()),
                ])


def process_hist(msg: blpapi.Message, **kwargs) -> Iterator[dict]:
    """Process historical data messages from Bloomberg.

    Args:
        msg: Bloomberg historical data messages from events.
        **kwargs: Additional options (unused).

    Returns:
        dict.
    """
    kwargs.pop('(>_<)', None)
    if not msg.hasElement(blpapi.Name('securityData')): return {}
    ticker = msg.getElement(blpapi.Name('securityData')).getElement(blpapi.Name('security')).getValue()
    for val in msg.getElement(blpapi.Name('securityData')).getElement(blpapi.Name('fieldData')).values():
        if val.hasElement(blpapi.Name('date')):
            yield OrderedDict([('ticker', ticker)] + [
                (str(elem.name()), elem.getValue()) for elem in val.elements()
            ])


def process_bar(msg: blpapi.Message, typ='bar', **kwargs) -> Iterator[OrderedDict]:
    """Process Bloomberg intraday bar messages.

    Args:
        msg: Bloomberg intraday bar messages from events.
        typ: ``bar`` or ``tick``.
        **kwargs: Additional options (unused).

    Yields:
        OrderedDict.
    """
    kwargs.pop('(#_#)', None)
    check_error(msg=msg)
    lvls = [TICK_DATA, TICK_DATA] if typ[0].lower() == 't' else [BAR_DATA, BAR_TICK]

    if msg.hasElement(lvls[0]):
        for bar in msg.getElement(lvls[0]).getElement(lvls[1]).values():
            yield OrderedDict([
                (str(elem.name()), elem.getValue())
                for elem in bar.elements()
            ])


def check_error(msg):
    """Check error in message."""
    if msg.hasElement(RESPONSE_ERROR):
        error = msg.getElement(RESPONSE_ERROR)
        raise ValueError(
            f'[Intraday Bar Error] '
            f'{error.getElementAsString(CATEGORY)}: '
            f'{error.getElementAsString(MESSAGE)}'
        )


def elem_value(element: blpapi.Element):
    """Get value from element.

    Args:
        element: Bloomberg element.

    Returns:
        Value.
    """
    if element.isNull(): return None
    try: value = element.getValue()
    except ValueError: return None
    if isinstance(value, np.bool_): return bool(value)
    if isinstance(value, blpapi.Name): return str(value)
    return value


def _flatten_element(element: blpapi.Element) -> dict[str, Any]:
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


def process_bql(msg: blpapi.Message, **kwargs) -> Iterator[OrderedDict]:
    """Process BQL response messages into row dictionaries.

    Attempts to parse tabular BQL results; falls back to flattened dicts.
    Handles both structured 'results' element and JSON string 'result' element.

    This function is BQL-specific and should only be called for BQL queries
    (via blp.bql()). It checks for BQL-specific message formats.

    Args:
        msg: Bloomberg BQL message.
        **kwargs: Unused.

    Yields:
        OrderedDict: Row-like mappings parsed from BQL results.
    """
    import json

    kwargs.pop('(^_^)', None)

    # Gate: Only process messages with BQL-specific message type "result"
    # This ensures we don't accidentally process non-BQL messages
    if str(msg.messageType()) != 'result':
        return iter([])

    # Check if message element itself is a JSON string (BQL format)
    msg_elem = msg.asElement()
    if msg_elem.datatype() == blpapi.DataType.STRING:
        try:
            result_str = msg_elem.getValue()
            if not isinstance(result_str, str):
                return iter([])
            result_json = json.loads(result_str)
            if 'results' in result_json:
                results_data = result_json.get('results')
                if not results_data or not isinstance(results_data, dict):
                    return iter([])
                # Extract data from JSON structure
                for field_name, field_data in results_data.items():
                    if isinstance(field_data, dict):
                        # Check for idColumn and valuesColumn structure
                        if 'idColumn' in field_data and 'valuesColumn' in field_data:
                            ids = field_data['idColumn'].get('values', [])
                            values = field_data['valuesColumn'].get('values', [])
                            # Also check for secondary columns (like DATE, CURRENCY)
                            secondary_cols = {}
                            if 'secondaryColumns' in field_data:
                                for sec_col in field_data['secondaryColumns']:
                                    col_name = sec_col.get('name', '')
                                    col_values = sec_col.get('values', [])
                                    secondary_cols[col_name] = col_values

                            # Yield rows
                            for i, (ticker, value) in enumerate(zip(ids, values, strict=False)):
                                row = OrderedDict([
                                    ('ID', ticker),
                                    (field_name, value),
                                ])
                                # Add secondary columns
                                for col_name, col_values in secondary_cols.items():
                                    if i < len(col_values):
                                        row[col_name] = col_values[i]
                                yield row
                        else:
                            # Fallback: flatten the structure
                            def _flatten_dict(d: dict, parent_key: str = '', sep: str = '_') -> dict:
                                items = []
                                for k, v in d.items():
                                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                                    if isinstance(v, dict):
                                        items.extend(_flatten_dict(v, new_key, sep=sep).items())
                                    else:
                                        items.append((new_key, v))
                                return dict(items)
                            yield OrderedDict(_flatten_dict(field_data))
                return
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Check for structured 'results' element (plural) - older BQL format
    if msg.hasElement(RESULTS):
        for res in msg.getElement(RESULTS).values():
            if res.hasElement(TABLE):
                table = res.getElement(TABLE)
                if not (table.hasElement(COLUMNS) and table.hasElement(ROWS)):
                    yield OrderedDict(_flatten_element(res))
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
                    yield OrderedDict(zip(cols, values, strict=False))
            else:
                yield OrderedDict(_flatten_element(res))


def earning_pct(data: pd.DataFrame, yr):
    """Calculate % of earnings by year."""
    pct = f'{yr}_pct'
    data.loc[:, pct] = np.nan

    # Calculate level 1 percentage
    data.loc[data.level == 1, pct] = \
        100 * data.loc[data.level == 1, yr] / data.loc[data.level == 1, yr].sum()

    # Calculate level 2 percentage (higher levels will be ignored)
    sub_pct = []
    for r, snap in data.reset_index()[::-1].iterrows():
        if snap.level > 2: continue
        if snap.level == 1:
            if len(sub_pct) == 0: continue
            data.iloc[sub_pct, data.columns.get_loc(pct)] = \
                100 * data[yr].iloc[sub_pct] / data[yr].iloc[sub_pct].sum()
            sub_pct = []
        if snap.level == 2: sub_pct.append(r)


def check_current(dt, logger, **kwargs) -> bool:
    """Check current time against T-1."""
    t_1 = pd.Timestamp('today').date() - pd.Timedelta('1D')
    whole_day = pd.Timestamp(dt).date() < t_1
    if (not whole_day) and kwargs.get('batch', False):
        logger.warning('Query date %s is too close to current time, skipping download to avoid incomplete data', t_1)
        return False
    return True
