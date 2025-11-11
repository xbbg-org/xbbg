"""Resolvers for market-specific ticker transformations and helpers."""

import pandas as pd

from xbbg import const
from xbbg.io import logs


def active_futures(ticker: str, dt, **kwargs) -> str:
    """Active futures contract.

    Args:
        ticker: futures ticker, i.e., ESA Index, Z A Index, CLA Comdty, etc.
        dt: date
        **kwargs: Passed through to downstream resolvers (e.g., logging).

    Returns:
        str: ticker name
    """
    from xbbg.blp import bdp  # lazy import to avoid circular

    t_info = ticker.split()
    prefix, asset = ' '.join(t_info[:-1]), t_info[-1]
    info = const.market_info(f'{prefix[:-1]}1 {asset}')

    f1, f2 = f'{prefix[:-1]}1 {asset}', f'{prefix[:-1]}2 {asset}'
    raw_freq = info.get('freq')
    if isinstance(raw_freq, str) and raw_freq.strip():
        freq_code = raw_freq.strip()
    else:
        logs.get_logger(active_futures).error(
            f"Missing freq in assets.yml for root '{prefix[:-1]}' ({asset}). Please set 'freq' explicitly."
        )
        return ''

    fut_2 = fut_ticker(gen_ticker=f2, dt=dt, freq=freq_code, **kwargs)
    fut_1 = fut_ticker(gen_ticker=f1, dt=dt, freq=freq_code, **kwargs)

    fut_tk = bdp(tickers=[fut_1, fut_2], flds='last_tradeable_dt')

    first_matu = pd.Timestamp(fut_tk['last_tradeable_dt'].iloc[0])
    if pd.Timestamp(dt).month < first_matu.month: return fut_1

    dts = pd.bdate_range(end=dt, periods=10)
    from xbbg.blp import bdh  # lazy
    volume = bdh(fut_tk.index, flds='volume', start_date=dts[0], end_date=dts[-1])
    if volume.empty: return fut_1
    return volume.iloc[-1].idxmax()[0]


def fut_ticker(gen_ticker: str, dt, freq: str, **kwargs) -> str:
    """Get proper ticker from generic ticker.

    Args:
        gen_ticker: generic ticker
        dt: date
        freq: futures contract frequency
        **kwargs: Passed through to Bloomberg fetch and logging.

    Returns:
        str: exact futures ticker
    """
    logger = logs.get_logger(fut_ticker, **kwargs)
    dt = pd.Timestamp(dt)
    t_info = gen_ticker.split()
    pre_dt = pd.bdate_range(end='today', periods=1)[-1]
    same_month = (pre_dt.month == dt.month) and (pre_dt.year == dt.year)

    asset = t_info[-1]
    if asset in ['Index', 'Curncy', 'Comdty']:
        ticker = ' '.join(t_info[:-1])
        prefix, idx, postfix = ticker[:-1], int(ticker[-1]) - 1, asset

    elif asset == 'Equity':
        ticker = t_info[0]
        prefix, idx, postfix = ticker[:-1], int(ticker[-1]) - 1, ' '.join(t_info[1:])

    else:
        logger.error(f'unkonwn asset type for ticker: {gen_ticker}')
        return ''

    month_ext = 4 if asset == 'Comdty' else 2
    eff_freq = (freq or '').strip().upper() if isinstance(freq, str) else None
    if not eff_freq:
        logger.error(f"Missing/invalid freq for '{gen_ticker}'. Please provide explicit 'freq' in assets.yml.")
        return ''
    # Normalize deprecated pandas offsets
    if eff_freq == 'M':
        eff_freq = 'ME'
    elif eff_freq == 'Q':
        eff_freq = 'QE-DEC'
    months = pd.date_range(start=dt, periods=max(idx + month_ext, 3), freq=eff_freq)
    logger.debug(f'pulling expiry dates for months: {months}')

    def to_fut(month):
        return prefix + const.Futures[month.strftime('%b')] + \
            month.strftime('%y')[-1 if same_month else -2:] + ' ' + postfix

    fut = [to_fut(m) for m in months]
    logger.debug(f'trying futures: {fut}')
    from xbbg.blp import bdp  # lazy
    # noinspection PyBroadException
    try:
        fut_matu = bdp(tickers=fut, flds='last_tradeable_dt')
    except Exception as e1:
        logger.error(f'error downloading futures contracts (1st trial) {e1}:\n{fut}')
        # noinspection PyBroadException
        try:
            fut = fut[:-1]
            logger.debug(f'trying futures (2nd trial): {fut}')
            fut_matu = bdp(tickers=fut, flds='last_tradeable_dt')
        except Exception as e2:
            logger.error(f'error downloading futures contracts (2nd trial) {e2}:\n{fut}')
            return ''

    if 'last_tradeable_dt' not in fut_matu:
        logger.warning(f'no futures found for {fut}')
        return ''

    fut_matu.sort_values(by='last_tradeable_dt', ascending=True, inplace=True)
    sub_fut = fut_matu[pd.DatetimeIndex(fut_matu.last_tradeable_dt) > dt]
    logger.debug(f'futures full chain:\n{fut_matu.to_string()}')
    logger.debug(f'getting index {idx} from:\n{sub_fut.to_string()}')
    return sub_fut.index.values[idx]


def cdx_ticker(gen_ticker: str, dt, **kwargs) -> str:
    """Resolve generic CDX 5Y ticker (e.g., 'CDX IG CDSI GEN 5Y Corp') to concrete series.

    Uses Bloomberg fields:
      - rolling_series: returns current on-the-run series number
      - on_the_run_current_bd_indicator: 'Y' if on-the-run
      - cds_first_accrual_start_date: start date of current series trading
    """
    logger = logs.get_logger(cdx_ticker, **kwargs)
    dt = pd.Timestamp(dt)
    from xbbg.blp import bdp  # lazy

    try:
        info = bdp(
            tickers=gen_ticker,
            flds=['rolling_series', 'on_the_run_current_bd_indicator', 'cds_first_accrual_start_date'],
            **kwargs,
        )
    except Exception as e:
        logger.error(f'error fetching CDX meta for {gen_ticker}: {e}')
        return ''

    if info.empty or 'rolling_series' not in info:
        logger.warning(f'no rolling series for {gen_ticker}')
        return ''

    series = info.loc[gen_ticker, 'rolling_series']
    try:
        series = int(series)
    except Exception:
        series = series

    tokens = gen_ticker.split()
    if 'GEN' not in tokens:
        logger.warning(f'expected GEN token in {gen_ticker}')
        return ''
    tokens[tokens.index('GEN')] = f'S{series}'
    resolved = ' '.join(tokens)

    # If dt is before first accrual date of current series, use prior series
    faccr_col = 'cds_first_accrual_start_date'
    try:
        start_dt = pd.Timestamp(info.loc[gen_ticker, faccr_col]) if faccr_col in info else None
    except Exception:
        start_dt = None

    if (start_dt is not None) and (dt < start_dt) and isinstance(series, int) and series > 1:
        tokens[tokens.index(f'S{series}')] = f'S{series - 1}'
        resolved = ' '.join(tokens)

    return resolved


def active_cdx(gen_ticker: str, dt, lookback_days: int = 10, **kwargs) -> str:
    """Choose active CDX series for a date, preferring on-the-run unless it's not started yet.

    If ambiguous, prefer the series with recent non-empty PX_LAST over the lookback window.
    """
    cur = cdx_ticker(gen_ticker=gen_ticker, dt=dt, **kwargs)
    if not cur:
        return ''

    # Compute previous series candidate
    parts = cur.split()
    prev = ''
    for i, tok in enumerate(parts):
        if tok.startswith('S') and tok[1:].isdigit():
            s = int(tok[1:])
            if s > 1:
                parts[i] = f'S{s - 1}'
                prev = ' '.join(parts)
            break

    # If no prev candidate, return current
    if not prev:
        return cur

    from xbbg.blp import bdh, bdp  # lazy
    # If dt is before accrual start, prefer prev
    try:
        cur_meta = bdp(cur, ['cds_first_accrual_start_date'], **kwargs)
        cur_start = pd.Timestamp(cur_meta.iloc[0, 0]) if not cur_meta.empty else None
    except Exception:
        cur_start = None

    if (cur_start is not None) and (pd.Timestamp(dt) < cur_start):
        return prev

    # Otherwise, pick one with recent activity (PX_LAST availability)
    end = pd.Timestamp(dt)
    start = end - pd.Timedelta(days=lookback_days)
    try:
        px = bdh([cur, prev], ['PX_LAST'], start_date=start, end_date=end, **kwargs)
        if px.empty:
            return cur
        last_non_na = px.xs('PX_LAST', axis=1, level=1).ffill().iloc[-1]
        return last_non_na.dropna().index[0] if last_non_na.notna().any() else cur
    except Exception:
        return cur


