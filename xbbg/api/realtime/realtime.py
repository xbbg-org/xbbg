"""Bloomberg real-time data API.

Provides functions for real-time market data subscriptions and live data feeds.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from itertools import product
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import asyncio
from queue import Queue

from xbbg import const
from xbbg.core import process
from xbbg.core.infra import conn
from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ['subscribe', 'live']


@contextmanager
def subscribe(
    tickers: str | list[str],
    flds: str | list[str] | None = None,
    identity=None,
    options: str | None = None,
    interval: int | None = None,
    **kwargs,
):
    """Subscribe Bloomberg realtime data.

    Args:
        tickers: list of tickers
        flds: fields to subscribe, default: Last_Price, Bid, Ask
        identity: Bloomberg identity.
        options: Subscription options string (e.g., 'fields=LAST_PRICE,BID,ASK' for event routing).
            Can be combined with interval parameter.
        interval: Subscription interval in seconds. If provided, sets the update frequency
            for the subscription (e.g., interval=10 for 10-second updates).
        **kwargs: Additional options forwarded to session and logging.

    Examples:
        >>> # Subscribe with default fields
        >>> # for _ in blp.subscribe(['AAPL US Equity']): pass
        >>>
        >>> # Subscribe with custom fields
        >>> # for _ in blp.subscribe(['AAPL US Equity'], ['LAST_PRICE', 'VOLUME']): pass
        >>>
        >>> # Subscribe with 10-second interval
        >>> # for _ in blp.subscribe(['AAPL US Equity'], interval=10): pass
        >>>
        >>> # Subscribe with custom options
        >>> # for _ in blp.subscribe(['AAPL US Equity'], options='fields=LAST_PRICE,BID,ASK'): pass
        >>>
        >>> # Subscribe with both interval and custom options
        >>> # for _ in blp.subscribe(['AAPL US Equity'], interval=10, options='fields=LAST_PRICE'): pass
    """
    tickers = utils.normalize_tickers(tickers)
    if flds is None: flds = ['Last_Price', 'Bid', 'Ask']
    flds = utils.normalize_flds(flds)

    # Build options string from interval and options parameters
    opts_parts = []
    if interval is not None:
        opts_parts.append(f'interval={interval}')
    if options:
        opts_parts.append(options)
    final_options = ','.join(opts_parts) if opts_parts else None

    sub_list = conn.blpapi.SubscriptionList()
    for ticker in tickers:
        topic = utils.parse_subscription_topic(ticker)
        cid = conn.blpapi.CorrelationId(ticker)
        logger.debug('Subscribing to Bloomberg market data: %s (correlation ID: %s) with options: %s', topic, cid, final_options)
        sub_list.add(topic, flds, correlationId=cid, options=final_options)

    try:
        conn.bbg_session(**kwargs).subscribe(sub_list, identity)
        yield
    finally:
        conn.bbg_session(**kwargs).unsubscribe(sub_list)


async def live(
    tickers: str | list[str],
    flds: str | list[str] | None = None,
    info: str | list[str] | None = None,
    max_cnt: int = 0,
    options: str | None = None,
    interval: int | None = None,
    **kwargs,
) -> AsyncIterator[dict]:
    """Subscribe and get data feeds.

    Args:
        tickers: list of tickers
        flds: fields to subscribe
        info: list of keys of interests (ticker will be included)
        max_cnt: max number of data points to receive
        options: Subscription options string (e.g., 'fields=LAST_PRICE,BID,ASK' for event routing).
            Can be combined with interval parameter.
        interval: Subscription interval in seconds. If provided, sets the update frequency
            for the subscription (e.g., interval=10 for 10-second updates).
        **kwargs: Additional options forwarded to session and logging.

    Yields:
        dict: Bloomberg market data.

    Examples:
        >>> # async for _ in live('SPY US Equity', info=const.LIVE_INFO): pass
        >>>
        >>> # Subscribe with 10-second interval
        >>> # async for _ in live('SPY US Equity', interval=10): pass
    """
    evt_typs = conn.event_types()

    if flds is None:
        s_flds: list[str] = ['LAST_PRICE', 'BID', 'ASK']
    else:
        flds = utils.normalize_flds(flds)
        s_flds = [fld.upper() for fld in flds]

    if isinstance(info, str):
        info = [info]
    if isinstance(info, Iterable):
        info = [key.upper() for key in info]  # type: ignore[assignment]
    if info is None:
        info = list(const.LIVE_INFO)

    sess_opts = conn.blpapi.SessionOptions()
    if isinstance(kwargs.get('server_host'), str):
        sess_opts.setServerHost(kwargs['server_host'])
    else:
        sess_opts.setServerHost('localhost')
    sess_opts.setServerPort(int(kwargs.get('server_port') or kwargs.get('port') or 8194))

    dispatcher = conn.blpapi.EventDispatcher(2)
    outq: Queue = Queue()

    handler = _make_live_handler(
        evt_typs=evt_typs,
        s_flds=s_flds,
        info=info,
        outq=outq,
    )

    sess = conn.blpapi.Session(sess_opts, handler, dispatcher)
    if not sess.start():
        raise ConnectionError('Failed to start Bloomberg session with dispatcher')

    # Build options string from interval and options parameters
    opts_parts = []
    if interval is not None:
        opts_parts.append(f'interval={interval}')
    if options:
        opts_parts.append(options)
    final_options = ','.join(opts_parts) if opts_parts else None

    sub_list = conn.blpapi.SubscriptionList()
    for ticker in (tickers if isinstance(tickers, list) else [tickers]):
        topic = utils.parse_subscription_topic(ticker)
        cid = conn.blpapi.CorrelationId(ticker)
        logger.debug('Subscribing to Bloomberg market data: %s (correlation ID: %s) with options: %s', topic, cid, final_options)
        sub_list.add(topic, s_flds, correlationId=cid, options=final_options)

    try:
        sess.subscribe(sub_list)
        cnt = 0
        while True and (max_cnt == 0 or cnt <= max_cnt):
            item = await asyncio.to_thread(outq.get)
            yield item
            if max_cnt:
                cnt += 1
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sess.unsubscribe(sub_list)
        finally:
            sess.stop()


def _make_live_handler(
    evt_typs: dict[int, str],
    s_flds: list[str],
    info: list[str] | None,
    outq: Queue,
):
    """Factory for the live subscription event handler.

    Splitting this out keeps ``live`` itself simpler while preserving
    the original behavior of the nested handler.
    """

    def _handler(event, session):  # signature: (Event, Session)
        try:
            # Log event information only if DEBUG is enabled (avoid overhead in hot path)
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    from xbbg.core.infra import blpapi_logging

                    if blpapi_logging:
                        blpapi_logging.log_event_info(event, context='live_subscription')
                except ImportError:
                    pass

            if evt_typs[event.eventType()] != 'SUBSCRIPTION_DATA':
                return

            msg_count = 0
            for msg, fld in product(event, s_flds):
                if not msg.hasElement(fld):
                    continue
                if msg.getElement(fld).isNull():
                    continue

                # Log message information only for first message and only if verbose logging enabled
                # This avoids per-message overhead in tight subscription loops
                if msg_count == 0 and logger.isEnabledFor(logging.DEBUG):
                    try:
                        from xbbg.core.infra import blpapi_logging

                        if blpapi_logging:
                            blpapi_logging.log_message_info(msg, context='live_subscription')
                    except ImportError:
                        pass

                outq.put(
                    {
                        **{
                            'TICKER': msg.correlationIds()[0].value(),
                            'FIELD': fld,
                        },
                        **{
                            str(elem.name()): process.elem_value(elem)
                            for elem in msg.asElement().elements()
                            if (True if not info else str(elem.name()) in info)
                        },
                    }
                )
                msg_count += 1

            # Log summary only if DEBUG enabled (aggregate, not per-message)
            if msg_count > 0 and logger.isEnabledFor(logging.DEBUG):
                logger.debug('Processed %d subscription data message(s) in live handler', msg_count)
        except Exception as e:  # noqa: BLE001
            # Only log exceptions if DEBUG enabled (avoid expensive stack traces in production)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Exception in live subscription handler: %s', e, exc_info=True)
            # For errors/warnings, log without stack trace unless needed
            elif logger.isEnabledFor(logging.WARNING):
                logger.warning('Exception in live subscription handler: %s', e)

    return _handler

