import sys
import types

import pandas as pd
import pytest


def _ensure_fake_blpapi():
    if 'blpapi' in sys.modules:
        return
    fake = types.SimpleNamespace(
        Name=lambda x: x,
        Event=types.SimpleNamespace(PARTIAL_RESPONSE=1, RESPONSE=2, TIMEOUT=3),
    )
    sys.modules['blpapi'] = fake


def _setup_mocks(monkeypatch, recorder: dict):
    from xbbg import core
    from xbbg.core import process, conn

    def fake_create_request(*args, **kwargs):
        # return any object that our code won't inspect deeply
        return {'_req': True}

    def fake_init_request(request, tickers, flds, **kwargs):
        recorder['start_date'] = kwargs.get('start_date')
        recorder['end_date'] = kwargs.get('end_date')
        # keep overrides untouched to validate pass-through if present
        recorder['kwargs'] = {k: v for k, v in kwargs.items() if k not in {'start_date', 'end_date'}}

    def fake_send_request(request, **kwargs):
        return {'event_queue': None}

    def fake_rec_events(func, event_queue=None, **kwargs):
        # no actual Bloomberg calls; behave like empty response
        return []

    monkeypatch.setattr(process, 'create_request', fake_create_request, raising=True)
    monkeypatch.setattr(process, 'init_request', fake_init_request, raising=True)
    monkeypatch.setattr(core.process, 'rec_events', fake_rec_events, raising=True)
    monkeypatch.setattr(conn, 'send_request', fake_send_request, raising=True)


def test_bdh_date_only_formats_daily(monkeypatch):
    _ensure_fake_blpapi()
    from xbbg import blp

    recorded = {}
    _setup_mocks(monkeypatch, recorded)

    blp.bdh(
        tickers='AAPL US Equity',
        flds='PX_LAST',
        start_date='2024-01-01',
        end_date='2024-01-31',
    )
    assert recorded['start_date'] == '20240101'
    assert recorded['end_date'] == '20240131'


def test_bdh_datetime_formats_intraday(monkeypatch):
    _ensure_fake_blpapi()
    from xbbg import blp

    recorded = {}
    _setup_mocks(monkeypatch, recorded)

    blp.bdh(
        tickers='ES1 Index',
        flds='PX_LAST',
        start_date='2020-03-20 09:30:00',
        end_date='2020-03-20 16:00:00',
        BarType=True,
        BarSize=5,
        RecurDaily=False,
    )
    assert recorded['start_date'] == '2020-03-20 09:30:00'
    assert recorded['end_date'] == '2020-03-20 16:00:00'
    # overrides are passed through unchanged
    assert recorded['kwargs'].get('BarType') is True
    assert recorded['kwargs'].get('BarSize') == 5
    assert recorded['kwargs'].get('RecurDaily') is False


def test_bdh_mixed_inputs_expand_boundaries(monkeypatch):
    _ensure_fake_blpapi()
    from xbbg import blp

    recorded = {}
    _setup_mocks(monkeypatch, recorded)

    # start has time, end is date-only → end becomes 23:59:59
    blp.bdh(
        tickers='MSFT US Equity',
        flds='PX_LAST',
        start_date='2022-05-10 10:00:00',
        end_date='2022-05-10',
    )
    assert recorded['start_date'] == '2022-05-10 10:00:00'
    assert recorded['end_date'] == '2022-05-10 23:59:59'

    # start date-only, end has time → start becomes 00:00:00
    recorded.clear()
    _setup_mocks(monkeypatch, recorded)
    blp.bdh(
        tickers='MSFT US Equity',
        flds='PX_LAST',
        start_date='2022-05-10',
        end_date='2022-05-10 15:30:00',
    )
    assert recorded['start_date'] == '2022-05-10 00:00:00'
    assert recorded['end_date'] == '2022-05-10 15:30:00'


