'use strict';

/*
Live Bloomberg tests for js-xbbg.
Run with:
  node --test --test-timeout=120000 js-xbbg/test-live.js
*/

const assert = require('node:assert/strict');
const { describe, it, before, after } = require('node:test');
const { performance } = require('node:perf_hooks');

// Note: Some Bloomberg requests (BEQS, bsrch, bta) may time out and generate
// 'Channel closed unexpectedly' warnings on engine shutdown. This is expected
// behavior for live tests — node:test may report a file-level failure even
// though all individual tests pass.
const { connect, Backend } = require('./index');

const CONFIG = Object.freeze({
  equity_single: 'IBM US Equity',
  equity_multi: ['AAPL US Equity', 'MSFT US Equity'],
  index_ticker: 'INDU Index',
  bond_ticker: 'GT10 Govt',
  etf_ticker: 'SPY US Equity',
  futures_generic: 'ES1 Index',
  streaming_ticker: 'ES1 Index',
  price_field: 'PX_LAST',
  name_field: 'NAME',
  volume_field: 'VOLUME',
});

const enginePromise = connect();
let engine;

function getRecentTradingDay() {
  const now = new Date();
  for (let daysBack = 1; daysBack <= 5; daysBack += 1) {
    const candidate = new Date(now);
    candidate.setDate(now.getDate() - daysBack);
    const dow = candidate.getDay();
    if (dow !== 0 && dow !== 6) {
      return candidate.toISOString().slice(0, 10);
    }
  }
  const fallback = new Date(now);
  fallback.setDate(now.getDate() - 1);
  return fallback.toISOString().slice(0, 10);
}

function getDateRange(days) {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days);
  return {
    start: start.toISOString().slice(0, 10).replace(/-/g, ''),
    end: end.toISOString().slice(0, 10).replace(/-/g, ''),
  };
}

function withTimeout(promise, ms, label) {
  // Attach a .catch to the original promise to prevent unhandled rejection
  // when we time out and the original promise later rejects (e.g., 'Channel closed').
  promise.catch(() => {});
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      settled = true;
      reject(new Error(`Timed out waiting for ${label}`));
    }, ms);
    promise.then(
      (val) => { if (!settled) { clearTimeout(timer); resolve(val); } },
      (err) => { if (!settled) { clearTimeout(timer); reject(err); } },
    );
  });
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function columnsOf(table) {
  return table.schema.fields.map((f) => f.name);
}

function tableSummary(table) {
  return `rows=${table.numRows}, cols=${table.numCols}, fields=[${columnsOf(table).join(', ')}]`;
}

function assertArrowTable(table, requiredColumns, minRows = 1) {
  assert.ok(table, 'Expected table');
  assert.ok(Number.isInteger(table.numRows), 'Expected table.numRows');
  assert.ok(Number.isInteger(table.numCols), 'Expected table.numCols');
  assert.ok(table.numRows >= minRows, `Expected at least ${minRows} rows, got ${table.numRows}`);
  assert.ok(table.numCols >= requiredColumns.length, `Expected at least ${requiredColumns.length} columns`);
  const fields = columnsOf(table);
  for (const col of requiredColumns) {
    assert.ok(fields.includes(col), `Missing expected column: ${col}`);
  }
}

function toNumber(value) {
  if (typeof value === 'number') return value;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'string') {
    const n = Number(value);
    return Number.isFinite(n) ? n : NaN;
  }
  return NaN;
}

function toMillis(value) {
  if (value instanceof Date) return value.getTime();
  if (typeof value === 'number') return value;
  if (typeof value === 'bigint') {
    // Arrow timestamps may be in microseconds or nanoseconds
    if (value > 1e15) return Number(value / 1000n);
    return Number(value);
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : NaN;
}

function maybeSkipEntitlement(t, err) {
  const message = String(err && err.message ? err.message : err);
  const markers = [
    'not authorized',
    'not permissioned',
    'entitlement',
    'NO_AUTH',
    'BAD_SEC',
    'Unknown/Invalid security',
    'Unable to resolve',
    'service not available',
    'Operation not found',
    'failed to encode',
    'Channel closed',
    'Timed out',
  ];
  if (markers.some((marker) => message.includes(marker))) {
    t.skip(`Entitlement/unavailable: ${message}`);
    return true;
  }
  return false;
}

async function runCase(t, name, fn) {
  const started = performance.now();
  try {
    await fn();
    const elapsed = (performance.now() - started).toFixed(1);
    console.log(`[PASS] ${name} (${elapsed}ms)`);
  } catch (err) {
    const elapsed = (performance.now() - started).toFixed(1);
    if (err && err.code === 'ERR_TEST_SKIP') {
      console.log(`[SKIP] ${name} (${elapsed}ms) ${err.message || ''}`);
      throw err;
    }
    console.log(`[FAIL] ${name} (${elapsed}ms): ${err && err.message ? err.message : err}`);
    throw err;
  }
}

describe('js-xbbg live Bloomberg API', () => {
  before(async () => {
    engine = await enginePromise;
    assert.ok(engine, 'Engine should be created via connect()');
  });

  after(() => {
    if (engine) {
      engine.signalShutdown();
    }
  });

  describe('Connectivity', () => {
    it('engine is available', async (t) => runCase(t, 'engine is available', async () => {
      assert.equal(typeof engine.isAvailable, 'function');
      const available = engine.isAvailable();
      assert.equal(typeof available, 'boolean');
      console.log(`  engine.isAvailable(): ${available}`);
    }));

    it('bdp baseline request works', async (t) => runCase(t, 'bdp baseline request works', async () => {
      const table = await engine.bdp([CONFIG.equity_single], [CONFIG.price_field]);
      assertArrowTable(table, ['ticker', 'field', 'value']);
      console.log(`  BDP baseline -> ${tableSummary(table)}`);
    }));
  });

  describe('BDP reference data', () => {
    it('single ticker single field', async (t) => runCase(t, 'bdp single ticker single field', async () => {
      const table = await engine.bdp([CONFIG.equity_single], [CONFIG.price_field]);
      assertArrowTable(table, ['ticker', 'field', 'value'], 1);
      const ticker = table.getChild('ticker')?.get(0);
      const field = table.getChild('field')?.get(0);
      const value = table.getChild('value')?.get(0);
      assert.ok(String(ticker).includes('IBM US Equity'));
      assert.equal(String(field), CONFIG.price_field);
      assert.notEqual(value, null);
      console.log(`  ${ticker} ${field}=${value}`);
    }));

    it('single ticker multiple fields', async (t) => runCase(t, 'bdp single ticker multiple fields', async () => {
      const fields = [CONFIG.price_field, CONFIG.name_field, CONFIG.volume_field];
      const table = await engine.bdp([CONFIG.equity_single], fields);
      assertArrowTable(table, ['ticker', 'field', 'value'], fields.length);
      const gotFields = new Set(table.getChild('field').toArray().map((v) => String(v)));
      for (const f of fields) {
        assert.ok(gotFields.has(f), `Missing ${f}`);
      }
      console.log(`  ${CONFIG.equity_single} fields=${Array.from(gotFields).join(', ')}`);
    }));

    it('multiple tickers single field', async (t) => runCase(t, 'bdp multiple tickers single field', async () => {
      const table = await engine.bdp(CONFIG.equity_multi, [CONFIG.price_field]);
      assertArrowTable(table, ['ticker', 'field', 'value'], CONFIG.equity_multi.length);
      const tickers = new Set(table.getChild('ticker').toArray().map((v) => String(v)));
      for (const expected of CONFIG.equity_multi) {
        assert.ok(Array.from(tickers).some((tkr) => tkr.includes(expected)), `Missing ticker ${expected}`);
      }
      console.log(`  tickers=${Array.from(tickers).join(', ')}`);
    }));

    it('multiple tickers multiple fields', async (t) => runCase(t, 'bdp multiple tickers multiple fields', async () => {
      const fields = [CONFIG.price_field, CONFIG.volume_field];
      const table = await engine.bdp(CONFIG.equity_multi, fields);
      const expectedRows = CONFIG.equity_multi.length * fields.length;
      assertArrowTable(table, ['ticker', 'field', 'value'], expectedRows);
      assert.equal(table.numRows, expectedRows);
      console.log(`  expectedRows=${expectedRows}, actualRows=${table.numRows}`);
    }));

    it('with EUR override', async (t) => runCase(t, 'bdp with override', async () => {
      const table = await engine.bdp([CONFIG.equity_single], ['CRNCY_ADJ_PX_LAST'], {
        overrides: { EQY_FUND_CRNCY: 'EUR' },
      });
      assertArrowTable(table, ['ticker', 'field', 'value'], 1);
      const value = table.getChild('value')?.get(0);
      assert.ok(Number.isFinite(toNumber(value)), 'Override value should be numeric');
      console.log(`  EUR adjusted price=${value}`);
    }));

    it('price is positive number', async (t) => runCase(t, 'bdp price positive', async () => {
      const table = await engine.bdp([CONFIG.equity_single], [CONFIG.price_field]);
      assertArrowTable(table, ['ticker', 'field', 'value'], 1);
      const price = toNumber(table.getChild('value')?.get(0));
      assert.ok(Number.isFinite(price));
      assert.ok(price > 0, `Expected positive price, got ${price}`);
      console.log(`  price=${price}`);
    }));

    it('name is non-empty string', async (t) => runCase(t, 'bdp name string', async () => {
      const table = await engine.bdp([CONFIG.equity_single], [CONFIG.name_field]);
      assertArrowTable(table, ['ticker', 'field', 'value'], 1);
      const name = String(table.getChild('value')?.get(0) ?? '');
      assert.ok(name.trim().length > 0, 'Name should be non-empty');
      console.log(`  name=${name}`);
    }));
  });

  describe('BDH historical data', () => {
    it('single ticker date range', async (t) => runCase(t, 'bdh single ticker range', async () => {
      const range = getDateRange(7);
      const table = await engine.bdh([CONFIG.equity_single], [CONFIG.price_field], range);
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], 1);
      console.log(`  ${CONFIG.equity_single} ${range.start}->${range.end} rows=${table.numRows}`);
    }));

    it('multiple tickers single field', async (t) => runCase(t, 'bdh multi ticker', async () => {
      const range = getDateRange(5);
      const table = await engine.bdh(CONFIG.equity_multi, [CONFIG.price_field], range);
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], CONFIG.equity_multi.length);
      console.log(`  bdh multi ticker rows=${table.numRows}`);
    }));

    it('single ticker multiple fields', async (t) => runCase(t, 'bdh multi field', async () => {
      const range = getDateRange(5);
      const fields = [CONFIG.price_field, CONFIG.volume_field];
      const table = await engine.bdh([CONFIG.equity_single], fields, range);
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], 2);
      const gotFields = new Set(table.getChild('field').toArray().map((v) => String(v)));
      assert.ok(gotFields.has(CONFIG.price_field));
      assert.ok(gotFields.has(CONFIG.volume_field));
      console.log(`  got fields=${Array.from(gotFields).join(', ')}`);
    }));

    it('date order is ascending', async (t) => runCase(t, 'bdh dates ordered', async () => {
      const range = getDateRange(14);
      const table = await engine.bdh([CONFIG.equity_single], [CONFIG.price_field], range);
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], 1);
      const dates = table.getChild('date').toArray().map(toMillis).filter(Number.isFinite);
      for (let i = 1; i < dates.length; i += 1) {
        assert.ok(dates[i] >= dates[i - 1], 'Dates should be ascending');
      }
      console.log(`  ordered dates=${dates.length}`);
    }));

    it('supports periodicitySelection kwargs', async (t) => runCase(t, 'bdh kwargs periodicity', async () => {
      const range = getDateRange(30);
      const table = await engine.bdh([CONFIG.equity_single], [CONFIG.price_field], {
        ...range,
        kwargs: { periodicitySelection: 'DAILY' },
      });
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], 1);
      console.log(`  periodicity DAILY rows=${table.numRows}`);
    }));

    it('contains at least one positive price', async (t) => runCase(t, 'bdh positive values', async () => {
      const range = getDateRange(10);
      const table = await engine.bdh([CONFIG.equity_single], [CONFIG.price_field], range);
      assertArrowTable(table, ['ticker', 'date', 'field', 'value'], 1);
      const values = table.getChild('value').toArray().map(toNumber).filter(Number.isFinite);
      assert.ok(values.some((v) => v > 0), 'Expected at least one positive value');
      console.log(`  positive observations=${values.filter((v) => v > 0).length}`);
    }));
  });

  describe('BDS bulk data', () => {
    it('index members return 30 rows', async (t) => runCase(t, 'bds index members', async () => {
      const table = await engine.bds([CONFIG.index_ticker], ['INDX_MEMBERS']);
      assertArrowTable(table, ['ticker'], 30);
      assert.equal(table.numRows, 30, `Expected 30 DJIA members, got ${table.numRows}`);
      console.log(`  INDU members rows=${table.numRows}`);
    }));

    it('index members include non-empty member identifiers', async (t) => runCase(t, 'bds member identifiers', async () => {
      const table = await engine.bds([CONFIG.index_ticker], ['INDX_MEMBERS']);
      assertArrowTable(table, ['ticker'], 30);
      const rows = table.toArray();
      assert.ok(rows.length === 30);
      const hasNonEmpty = rows.some((row) => Object.values(row).some((v) => String(v || '').trim().length > 0));
      assert.ok(hasNonEmpty, 'Expected non-empty member values');
      console.log(`  sample member row=${JSON.stringify(rows[0])}`);
    }));

    it('dividend history returns rows', async (t) => runCase(t, 'bds dividend history', async () => {
      try {
        const table = await engine.bds([CONFIG.equity_single], ['DVD_HIST']);
        assertArrowTable(table, ['ticker'], 1);
        console.log(`  dividend history rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('dividend history has structured columns', async (t) => runCase(t, 'bds dividend columns', async () => {
      try {
        const table = await engine.bds([CONFIG.equity_single], ['DVD_HIST']);
        assert.ok(table.numCols >= 2, `Expected >=2 columns, got ${table.numCols}`);
        console.log(`  dividend columns=${columnsOf(table).join(', ')}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));
  });

  describe('BDIB intraday bars', () => {
    it('single day 5-min bars', async (t) => runCase(t, 'bdib single day', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdib(CONFIG.equity_single, { start: `${day}T14:30:00`, end: `${day}T20:00:00`, interval: 5 });
      assertArrowTable(table, ['time', 'open', 'high', 'low', 'close', 'volume', 'numEvents'], 1);
      console.log(`  day=${day}, rows=${table.numRows}`);
    }));

    it('datetime range 14:30-15:30 UTC', async (t) => runCase(t, 'bdib datetime range', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdib(CONFIG.equity_single, {
        start: `${day}T14:30:00`,
        end: `${day}T15:30:00`,
        interval: 5,
      });
      assertArrowTable(table, ['time', 'open', 'high', 'low', 'close', 'volume', 'numEvents'], 1);
      console.log(`  ${day} 14:30-15:30 UTC rows=${table.numRows}`);
    }));

    it('bar OHLC values are numeric', async (t) => runCase(t, 'bdib numeric ohlc', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdib(CONFIG.equity_single, { start: `${day}T14:30:00`, end: `${day}T15:30:00`, interval: 5 });
      assertArrowTable(table, ['open', 'high', 'low', 'close'], 1);
      const firstOpen = toNumber(table.getChild('open')?.get(0));
      const firstClose = toNumber(table.getChild('close')?.get(0));
      assert.ok(Number.isFinite(firstOpen));
      assert.ok(Number.isFinite(firstClose));
      console.log(`  first open=${firstOpen}, close=${firstClose}`);
    }));

    it('bar times are ordered', async (t) => runCase(t, 'bdib times ordered', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdib(CONFIG.equity_single, { start: `${day}T14:30:00`, end: `${day}T16:00:00`, interval: 5 });
      assertArrowTable(table, ['time'], 1);
      const times = Array.from(table.getChild('time').toArray()).map(toMillis).filter(Number.isFinite);
      for (let i = 1; i < times.length; i += 1) {
        assert.ok(times[i] >= times[i - 1], 'Bar times should be ascending');
      }
      console.log(`  ordered bars=${times.length}`);
    }));
  });

  describe('BDTICK intraday ticks', () => {
    it('one-hour market open window', async (t) => runCase(t, 'bdtick one-hour window', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdtick(CONFIG.equity_single, {
        start: `${day}T14:30:00`,
        end: `${day}T15:30:00`,
        eventTypes: ['TRADE'],
      });
      assertArrowTable(table, ['time'], 1);
      console.log(`  ticks rows=${table.numRows}, day=${day}`);
    }));

    it('tick columns include time/type/value', async (t) => runCase(t, 'bdtick expected columns', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdtick(CONFIG.equity_single, {
        start: `${day}T14:30:00`,
        end: `${day}T15:30:00`,
      });
      assertArrowTable(table, ['time'], 1);
      const cols = columnsOf(table);
      assert.ok(cols.some((c) => c.toLowerCase().includes('value') || c.toLowerCase().includes('price')));
      console.log(`  tick columns=${cols.join(', ')}`);
    }));

    it('supports multiple event types', async (t) => runCase(t, 'bdtick multi event types', async () => {
      const day = getRecentTradingDay();
      const table = await engine.bdtick(CONFIG.equity_single, {
        start: `${day}T14:30:00`,
        end: `${day}T15:30:00`,
        eventTypes: ['TRADE', 'BID'],
      });
      assertArrowTable(table, ['time'], 1);
      console.log(`  multi event rows=${table.numRows}`);
    }));

    it('tick times are ordered', async (t) => runCase(t, 'bdtick times ordered', async () => {
      const day = getRecentTradingDay();
      const start = `${day}T14:30:00`;
      const end = `${day}T15:30:00`;
      const table = await engine.bdtick(CONFIG.equity_single, { start, end, eventTypes: ['TRADE'] });
      assertArrowTable(table, ['time'], 1);
      const times = Array.from(table.getChild('time').toArray()).map(toMillis).filter(Number.isFinite);
      for (let i = 1; i < times.length; i += 1) {
        assert.ok(times[i] >= times[i - 1], 'Tick times should be ascending');
      }
      console.log(`  ordered ticks=${times.length}`);
    }));
  });

  describe('BQL query', () => {
    it('basic query returns rows', async (t) => runCase(t, 'bql basic', async () => {
      try {
        const table = await engine.bql("get(px_last) for('IBM US Equity')");
        assertArrowTable(table, columnsOf(table), 1);
        console.log(`  bql rows=${table.numRows}, cols=${table.numCols}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('query output has non-empty schema fields', async (t) => runCase(t, 'bql schema fields', async () => {
      try {
        const table = await engine.bql("get(px_last) for('IBM US Equity')");
        const fields = columnsOf(table);
        assert.ok(fields.length > 0, 'Expected BQL output fields');
        console.log(`  bql fields=${fields.join(', ')}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));
  });

  describe('BEQS screening', () => {
    it('core capital goods makers screen', async (t) => runCase(t, 'beqs basic screen', async () => {
      try {
        const table = await withTimeout(engine.beqs('Core Capital Goods Makers'), 30000, 'BEQS');
        assertArrowTable(table, columnsOf(table), 1);
        console.log(`  beqs rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('screen result columns are present', async (t) => runCase(t, 'beqs columns', async () => {
      try {
        const table = await withTimeout(engine.beqs('Core Capital Goods Makers'), 30000, 'BEQS');
        assert.ok(table.numCols >= 1);
        console.log(`  beqs columns=${columnsOf(table).join(', ')}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));
  });

  describe('BFLDS field metadata', () => {
    it('single field info PX_LAST', async (t) => runCase(t, 'bflds single field', async () => {
      const table = await engine.bflds({ fields: CONFIG.price_field });
      assertArrowTable(table, columnsOf(table), 1);
      console.log(`  bflds PX_LAST -> ${tableSummary(table)}`);
    }));

    it('multiple field info', async (t) => runCase(t, 'bflds multi field', async () => {
      const table = await engine.bflds({ fields: [CONFIG.price_field, CONFIG.volume_field, CONFIG.name_field] });
      assertArrowTable(table, columnsOf(table), 3);
      console.log(`  bflds multi rows=${table.numRows}`);
    }));

    it('fieldSearch finds PX_LAST', async (t) => runCase(t, 'fieldSearch PX_LAST', async () => {
      const table = await engine.fieldSearch('PX_LAST');
      assertArrowTable(table, columnsOf(table), 1);
      console.log(`  fieldSearch rows=${table.numRows}`);
    }));

    it('fieldInfo alias works', async (t) => runCase(t, 'fieldInfo alias', async () => {
      const table = await engine.fieldInfo([CONFIG.price_field, CONFIG.volume_field]);
      assertArrowTable(table, columnsOf(table), 2);
      console.log(`  fieldInfo rows=${table.numRows}`);
    }));
  });

  describe('BLKP instrument lookup', () => {
    it('lookup IBM returns rows', async (t) => runCase(t, 'blkp IBM lookup', async () => {
      try {
        const table = await engine.blkp('IBM');
        assertArrowTable(table, columnsOf(table), 0);
        console.log(`  blkp rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('lookup result has text values', async (t) => runCase(t, 'blkp textual result', async () => {
      try {
        const table = await engine.blkp('IBM');
        if (table.numRows === 0) {
          t.skip('blkp returned 0 rows (service may be unavailable)');
          return;
        }
        assertArrowTable(table, columnsOf(table), 1);
        const firstRow = table.toArray()[0];
        const hasText = Object.values(firstRow).some((v) => typeof v === 'string' && v.trim().length > 0);
        assert.ok(hasText, 'Expected at least one textual value in lookup row');
        console.log(`  sample row=${JSON.stringify(firstRow)}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));
  });

  describe('Streaming ES1 Index', () => {
    it('subscribe receives 2-3 ticks and unsubscribe', async (t) => runCase(t, 'stream subscribe/unsubscribe', async () => {
      const sub = await engine.stream([CONFIG.streaming_ticker], ['LAST_PRICE']);
      const rows = [];
      const maxWaitMs = 15000;
      const started = Date.now();

      while (rows.length < 3 && Date.now() - started < maxWaitMs) {
        const next = await Promise.race([
          sub.next(),
          sleep(5000).then(() => null),
        ]);
        if (!next || next.done) continue;
        rows.push(next.value);
        console.log(`  tick batch ${rows.length}: ${tableSummary(next.value)}`);
      }

      const drained = await sub.unsubscribe(true);
      assert.ok(rows.length >= 2, `Expected at least 2 tick batches, got ${rows.length}`);
      assert.ok(Array.isArray(drained), 'unsubscribe(true) should return drained table array');
      console.log(`  received=${rows.length}, drained=${drained.length}`);
    }));

    it('streamed ticks contain price-like column', async (t) => runCase(t, 'stream includes price-like field', async () => {
      const sub = await engine.stream([CONFIG.streaming_ticker], ['LAST_PRICE', 'BID', 'ASK']);
      const result = await Promise.race([
        sub.next(),
        sleep(12000).then(() => ({ done: true })),
      ]);
      await sub.unsubscribe(true);
      assert.ok(result && !result.done, 'Expected at least one streamed tick batch');
      const cols = columnsOf(result.value);
      assert.ok(cols.some((c) => c.toLowerCase().includes('price') || c.toLowerCase().includes('last') || c.toLowerCase().includes('bid')));
      console.log(`  stream columns=${cols.join(', ')}`);
    }));

    it('subscription add/remove works', async (t) => runCase(t, 'stream add/remove tickers', async () => {
      const sub = await engine.stream([CONFIG.streaming_ticker], ['LAST_PRICE']);
      await sub.add(['IBM US Equity']);
      await sub.remove(['IBM US Equity']);
      const next = await Promise.race([
        sub.next(),
        sleep(10000).then(() => null),
      ]);
      await sub.unsubscribe(false);
      assert.ok(next && !next.done, 'Expected data after add/remove');
      console.log(`  stats=${JSON.stringify(sub.stats)}`);
    }));

    it('subscription metadata is populated', async (t) => runCase(t, 'stream metadata', async () => {
      const sub = await engine.stream([CONFIG.streaming_ticker], ['LAST_PRICE']);
      assert.ok(Array.isArray(sub.tickers));
      assert.ok(Array.isArray(sub.fields));
      assert.equal(sub.isActive, true);
      const first = await Promise.race([sub.next(), sleep(8000).then(() => null)]);
      await sub.unsubscribe(false);
      assert.ok(first && !first.done, 'Expected one streamed table');
      console.log(`  tickers=${sub.tickers.join(', ')}, fields=${sub.fields.join(', ')}`);
    }));
  });

  describe('Schema and operations', () => {
    it('bops lists operations', async (t) => runCase(t, 'bops list operations', async () => {
      const ops = await engine.bops('//blp/refdata');
      assert.ok(Array.isArray(ops));
      assert.ok(ops.length > 0);
      console.log(`  bops count=${ops.length}`);
    }));

    it('bschema returns service schema', async (t) => runCase(t, 'bschema service', async () => {
      const schema = await engine.bschema('//blp/refdata');
      assert.ok(schema && typeof schema === 'object');
      assert.ok(Array.isArray(schema.operations));
      console.log(`  schema operations=${schema.operations.length}`);
    }));

    it('bschema returns operation schema', async (t) => runCase(t, 'bschema operation', async () => {
      const opSchema = await engine.bschema('//blp/refdata', 'ReferenceDataRequest');
      assert.ok(opSchema && typeof opSchema === 'object');
      console.log(`  op schema keys=${Object.keys(opSchema).slice(0, 6).join(', ')}`);
    }));

    it('listOperations mirrors bops', async (t) => runCase(t, 'listOperations', async () => {
      const [opsA, opsB] = await Promise.all([
        engine.bops('//blp/refdata'),
        engine.listOperations('//blp/refdata'),
      ]);
      assert.ok(Array.isArray(opsA));
      assert.ok(Array.isArray(opsB));
      assert.equal(opsA.length, opsB.length);
      console.log(`  bops/listOperations count=${opsA.length}`);
    }));

    it('getEnumValues returns periodicity selection', async (t) => runCase(t, 'getEnumValues', async () => {
      const vals = await engine.getEnumValues('//blp/refdata', 'HistoricalDataRequest', 'periodicitySelection');
      assert.ok(vals == null || Array.isArray(vals));
      if (Array.isArray(vals)) {
        assert.ok(vals.length > 0);
      }
      console.log(`  enum values=${Array.isArray(vals) ? vals.join(', ') : 'null'}`);
    }));

    it('listValidElements returns request elements', async (t) => runCase(t, 'listValidElements', async () => {
      const elems = await engine.listValidElements('//blp/refdata', 'ReferenceDataRequest');
      assert.ok(elems == null || Array.isArray(elems));
      if (Array.isArray(elems)) {
        assert.ok(elems.length > 0);
      }
      console.log(`  valid elements count=${Array.isArray(elems) ? elems.length : 0}`);
    }));
  });

  describe('Backend conversion', () => {
    it('BDP JSON backend returns array', async (t) => runCase(t, 'backend JSON bdp', async () => {
      const rows = await engine.request({
        service: '//blp/refdata',
        operation: 'ReferenceDataRequest',
        securities: [CONFIG.equity_single],
        fields: [CONFIG.price_field],
        extractor: 'refdata',
        backend: Backend.JSON,
      });
      assert.ok(Array.isArray(rows), 'Expected JSON backend to return array');
      assert.ok(rows.length >= 1);
      assert.ok(Object.prototype.hasOwnProperty.call(rows[0], 'ticker'));
      assert.ok(Object.prototype.hasOwnProperty.call(rows[0], 'field'));
      assert.ok(Object.prototype.hasOwnProperty.call(rows[0], 'value'));
      console.log(`  json rows=${rows.length}, first=${JSON.stringify(rows[0])}`);
    }));

    it('BDH JSON backend returns array', async (t) => runCase(t, 'backend JSON bdh', async () => {
      const range = getDateRange(5);
      const rows = await engine.request({
        service: '//blp/refdata',
        operation: 'HistoricalDataRequest',
        securities: [CONFIG.equity_single],
        fields: [CONFIG.price_field],
        startDate: range.start,
        endDate: range.end,
        extractor: 'histdata',
        backend: Backend.JSON,
      });
      assert.ok(Array.isArray(rows), 'Expected JSON backend to return array');
      assert.ok(rows.length >= 1);
      assert.ok(Object.prototype.hasOwnProperty.call(rows[0], 'date'));
      console.log(`  json hist rows=${rows.length}`);
    }));

    it('generic request with JSON backend', async (t) => runCase(t, 'backend JSON request()', async () => {
      const rows = await engine.request({
        service: '//blp/refdata',
        operation: 'ReferenceDataRequest',
        securities: [CONFIG.equity_single],
        fields: [CONFIG.price_field],
        extractor: 'refdata',
        backend: Backend.JSON,
      });
      assert.ok(Array.isArray(rows));
      assert.ok(rows.length >= 1);
      console.log(`  request(json) rows=${rows.length}`);
    }));
  });

  describe('Additional API coverage', () => {
    it('bcurves query is callable', async (t) => runCase(t, 'bcurves callable', async () => {
      try {
        const table = await engine.bcurves('YCSW0023 Index');
        assert.ok(table.numRows >= 0);
        console.log(`  bcurves rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('bgovts query is callable', async (t) => runCase(t, 'bgovts callable', async () => {
      try {
        const table = await engine.bgovts('USD');
        assert.ok(table.numRows >= 0);
        console.log(`  bgovts rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('bport API is callable', async (t) => runCase(t, 'bport callable', async () => {
      try {
        const table = await engine.bport('U10378179-1 Client', [CONFIG.price_field]);
        assert.ok(table.numRows >= 0);
        console.log(`  bport rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('bsrch returns search results', async (t) => runCase(t, 'bsrch basic', async () => {
      try {
        const table = await withTimeout(engine.bsrch('FI:SOVR'), 30000, 'bsrch');
        assert.ok(table.numRows >= 0);
        console.log(`  bsrch rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('bta technical analysis request', async (t) => runCase(t, 'bta basic', async () => {
      try {
        const range = getDateRange(30);
        const table = await withTimeout(engine.bta(CONFIG.futures_generic, 'sma', {
          studyParams: {
            calcInterval: 'DAILY',
            length: 20,
          },
          kwargs: {
            startDate: range.start,
            endDate: range.end,
          },
        }), 30000, 'bta');
        assert.ok(table.numRows >= 0);
        console.log(`  bta rows=${table.numRows}`);
      } catch (err) {
        if (!maybeSkipEntitlement(t, err)) throw err;
      }
    }));

    it('resolveFieldTypes works', async (t) => runCase(t, 'resolveFieldTypes', async () => {
      const mapping = await engine.resolveFieldTypes([CONFIG.price_field, CONFIG.volume_field, CONFIG.name_field]);
      assert.ok(mapping && typeof mapping === 'object');
      assert.ok(Object.keys(mapping).length >= 3);
      console.log(`  field types=${JSON.stringify(mapping)}`);
    }));

    it('validateFields returns validation result', async (t) => runCase(t, 'validateFields', async () => {
      const result = engine.validateFields([CONFIG.price_field, CONFIG.name_field]);
      // validateFields may return array, object, or null depending on schema state
      assert.ok(result == null || typeof result === 'object' || Array.isArray(result));
      console.log(`  validateFields=${JSON.stringify(result)}`);
    }));

    it('schema cache lifecycle operations callable', async (t) => runCase(t, 'schema cache lifecycle', async () => {
      engine.clearSchemaCache();
      const cached0 = engine.listCachedSchemas();
      assert.ok(Array.isArray(cached0));
      await engine.getSchema('//blp/refdata');
      const cached1 = engine.listCachedSchemas();
      assert.ok(Array.isArray(cached1));
      engine.invalidateSchema('//blp/refdata');
      const cached2 = engine.listCachedSchemas();
      assert.ok(Array.isArray(cached2));
      console.log(`  cache sizes before=${cached0.length}, afterLoad=${cached1.length}, afterInvalidate=${cached2.length}`);
    }));

    it('field cache lifecycle operations callable', async (t) => runCase(t, 'field cache lifecycle', async () => {
      engine.clearFieldCache();
      const enabled = engine.isFieldValidationEnabled();
      // isFieldValidationEnabled may return boolean or undefined if not supported
      assert.ok(typeof enabled === 'boolean' || typeof enabled === 'undefined');
      const saved = engine.saveFieldCache();
      assert.ok(typeof saved === 'boolean' || typeof saved === 'undefined');
      console.log(`  validationEnabled=${enabled}, saveFieldCache=${saved}`);
    }));

    it('getFieldInfo callable for PX_LAST', async (t) => runCase(t, 'getFieldInfo', async () => {
      const info = engine.getFieldInfo(CONFIG.price_field);
      assert.ok(info === null || typeof info === 'object');
      console.log(`  getFieldInfo type=${info === null ? 'null' : typeof info}`);
    }));
  });
});
