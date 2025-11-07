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

from xbbg import const
from xbbg.core import conn, intervals, overrides
from xbbg.core.timezone import DEFAULT_TZ

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
    ss = intervals.get_interval(ticker=ticker, session=session, **kwargs)
    ex_info = const.exch_info(ticker=ticker, **kwargs)
    cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
    time_fmt = '%Y-%m-%dT%H:%M:%S'
    time_idx = (
        pd.DatetimeIndex([
            f'{cur_dt} {ss.start_time}',
            f'{cur_dt} {ss.end_time}'],
        )
        .tz_localize(ex_info.tz)
        .tz_convert(DEFAULT_TZ)
        .tz_convert(tz)
    )
    if time_idx[0] > time_idx[1]: time_idx -= pd.TimedeltaIndex(['1D', '0D'])
    return intervals.Session(time_idx[0].strftime(time_fmt), time_idx[1].strftime(time_fmt))


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
    while True:
        if event_queue is not None:
            ev = event_queue.nextEvent(timeout=timeout)
        else:
            ev = conn.bbg_session(**kwargs).nextEvent(timeout=timeout)
        if ev.eventType() in responses:
            for msg in ev:
                yield from func(msg=msg, **kwargs)
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        elif ev.eventType() == blpapi.Event.TIMEOUT:
            timeout_counts += 1
            if timeout_counts > 20:
                break
        else:
            for _ in ev:
                if getattr(ev, 'messageType', lambda: None)() \
                    == SESSION_TERMINATED: break


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

    Args:
        msg: Bloomberg BQL message.
        **kwargs: Unused.

    Yields:
        OrderedDict: Row-like mappings parsed from BQL results.
    """
    kwargs.pop('(^_^)', None)
    if not msg.hasElement(RESULTS):
        return iter([])

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
        logger.warning(f'Querying date {t_1} is too close, ignoring download ...')
        return False
    return True
