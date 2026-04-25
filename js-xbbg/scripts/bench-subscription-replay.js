#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const { setTimeout: sleep } = require('node:timers/promises');
const { tableFromArrays, tableFromIPC, tableToIPC } = require('apache-arrow');

const DEFAULT_FIELDS = ['LAST_PRICE', 'BID', 'ASK'];
const DEFAULT_TOPIC = 'XBTUSD Curncy';
const DEFAULT_ROWS = 100_000;
const DEFAULT_ITERATIONS = 1;
const DEFAULT_CAPTURE_MS = 10_000;
const DEFAULT_STATS_INTERVAL_MS = 1_000;
const DEFAULT_PATH = 'legacy';
const REPLAY_PATHS = new Set(['legacy', 'arrow-decode-only', 'subscription-wrapper']);

function usage() {
  return `Usage:
  node scripts/bench-subscription-replay.js [--rows N] [--iterations N]
  node scripts/bench-subscription-replay.js --fixture tmp/xbtusd-ticks.jsonl [--iterations N]
  node scripts/bench-subscription-replay.js --capture-live "XBTUSD Curncy" --capture-ms 10000 --out tmp/xbtusd-ticks.jsonl

Modes:
  synthetic      Default. Generates one tick/update at a time; no batching.
  fixture        Replays JSONL ticks one update at a time; no batching.
  replay paths  legacy (encode+decode), arrow-decode-only, subscription-wrapper (zero-copy descriptors)
  capture-live   Captures live Engine.stream() rows to JSONL and prints existing sub.stats.

Options:
  --rows N                 Synthetic rows per iteration. Default ${DEFAULT_ROWS}
  --iterations N           Replay iterations. Default ${DEFAULT_ITERATIONS}
  --fixture PATH           JSONL fixture to replay.
  --path NAME              Replay path: legacy, arrow-decode-only, subscription-wrapper. Default ${DEFAULT_PATH}
  --capture-live TICKER    Capture live subscription rows for TICKER.
  --capture-ms N           Live capture duration in ms. Default ${DEFAULT_CAPTURE_MS}
  --out PATH               Output JSONL path for live capture.
  --fields A,B,C           Fields for synthetic/capture. Default ${DEFAULT_FIELDS.join(',')}
  --topic TICKER           Synthetic topic. Default ${DEFAULT_TOPIC}
  --consumer-delay-ms N    Artificial per-update consumer delay after processing.
  --stats-interval-ms N    Live capture stats print interval. Default ${DEFAULT_STATS_INTERVAL_MS}
  --json                   Print only the final JSON result.
  --help                   Show this help.
`;
}

function parseArgs(argv) {
  const args = {
    rows: DEFAULT_ROWS,
    iterations: DEFAULT_ITERATIONS,
    fields: DEFAULT_FIELDS,
    topic: DEFAULT_TOPIC,
    captureMs: DEFAULT_CAPTURE_MS,
    statsIntervalMs: DEFAULT_STATS_INTERVAL_MS,
    consumerDelayMs: 0,
    path: DEFAULT_PATH,
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`${arg} requires a value`);
      }
      return argv[index];
    };

    switch (arg) {
      case '--rows':
        args.rows = parsePositiveInteger(next(), '--rows');
        break;
      case '--iterations':
        args.iterations = parsePositiveInteger(next(), '--iterations');
        break;
      case '--fixture':
        args.fixture = next();
        break;
      case '--path':
        args.path = parseReplayPath(next());
        break;
      case '--capture-live':
        args.captureLive = next();
        break;
      case '--capture-ms':
        args.captureMs = parsePositiveInteger(next(), '--capture-ms');
        break;
      case '--out':
        args.out = next();
        break;
      case '--fields':
        args.fields = parseCsv(next());
        break;
      case '--topic':
        args.topic = next();
        break;
      case '--consumer-delay-ms':
        args.consumerDelayMs = parseNonNegativeInteger(next(), '--consumer-delay-ms');
        break;
      case '--stats-interval-ms':
        args.statsIntervalMs = parsePositiveInteger(next(), '--stats-interval-ms');
        break;
      case '--json':
        args.json = true;
        break;
      case '--help':
      case '-h':
        args.help = true;
        break;
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }

  return args;
}

function parseReplayPath(value) {
  if (!REPLAY_PATHS.has(value)) {
    throw new Error(`--path must be one of: ${Array.from(REPLAY_PATHS).join(', ')}`);
  }
  return value;
}


function parseCsv(value) {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  if (items.length === 0) {
    throw new Error('expected at least one field');
  }
  return items;
}

function parsePositiveInteger(value, name) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${name} must be a positive integer`);
  }
  return parsed;
}

function parseNonNegativeInteger(value, name) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return parsed;
}

function syntheticTick(index, topic, fields) {
  const price = 50_000 + Math.sin(index / 17) * 250 + (index % 97) * 0.25;
  const row = {
    timestamp: new Date(1_735_689_600_000 + index * 100).toISOString(),
    topic,
    MKTDATA_EVENT_TYPE: 'TRADE',
    MKTDATA_EVENT_SUBTYPE: '',
  };
  for (const field of fields) {
    switch (field) {
      case 'LAST_PRICE':
        row[field] = round(price);
        break;
      case 'BID':
        row[field] = round(price - 1.25);
        break;
      case 'ASK':
        row[field] = round(price + 1.25);
        break;
      default:
        row[field] = round(price);
        break;
    }
  }
  return row;
}

function round(value) {
  return Math.round(value * 100) / 100;
}

function readJsonl(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const rows = [];
  let lineNumber = 0;
  for (const line of raw.split(/\r?\n/)) {
    lineNumber += 1;
    const trimmed = line.trim();
    if (trimmed.length === 0) {
      continue;
    }
    try {
      rows.push(JSON.parse(trimmed));
    } catch (err) {
      throw new Error(`invalid JSONL at ${filePath}:${lineNumber}: ${err.message}`);
    }
  }
  if (rows.length === 0) {
    throw new Error(`fixture contains no rows: ${filePath}`);
  }
  return rows;
}

function rowToIpc(row) {
  const arrays = {};
  for (const [key, value] of Object.entries(row)) {
    arrays[key] = [value === undefined ? null : value];
  }
  return tableToIPC(tableFromArrays(arrays));
}

function buildReplayBuffers(rows) {
  return rows.map((row) => Buffer.from(rowToIpc(row)));
}

function typedBuffer(view) {
  return Buffer.from(view.buffer, view.byteOffset, view.byteLength);
}

function buildReplayNativeBatches(rows) {
  return rows.map(rowToNativeArrowBatch);
}

function rowToNativeArrowBatch(row) {
  const columns = Object.entries(row).map(([name, value]) => nativeArrowColumn(name, value));
  return {
    kind: 'zeroCopy',
    numRows: 1,
    columns,
  };
}

function nativeArrowColumn(name, value) {
  const normalized = value === undefined ? null : value;
  if (normalized === null) {
    return { name, type: 'null', nullable: true, length: 1, nullCount: 1 };
  }
  if (typeof normalized === 'number') {
    return {
      name,
      type: 'float64',
      nullable: false,
      length: 1,
      nullCount: 0,
      data: typedBuffer(new Float64Array([normalized])),
    };
  }
  if (typeof normalized === 'bigint') {
    return {
      name,
      type: 'int64',
      nullable: false,
      length: 1,
      nullCount: 0,
      data: typedBuffer(new BigInt64Array([normalized])),
    };
  }
  if (typeof normalized === 'boolean') {
    return {
      name,
      type: 'bool',
      nullable: false,
      length: 1,
      nullCount: 0,
      data: Buffer.from([normalized ? 1 : 0]),
    };
  }
  if (normalized instanceof Date) {
    return {
      name,
      type: 'timestamp_us',
      nullable: false,
      length: 1,
      nullCount: 0,
      data: typedBuffer(new BigInt64Array([BigInt(normalized.getTime()) * 1000n])),
    };
  }

  const data = Buffer.from(String(normalized));
  return {
    name,
    type: 'utf8',
    nullable: false,
    length: 1,
    nullCount: 0,
    offsets: typedBuffer(new Int32Array([0, data.byteLength])),
    data,
  };
}

function createFakeNativeSubscription(batches, args) {
  let index = 0;
  return {
    async nextArrow() {
      if (index >= batches.length) {
        return null;
      }
      const batch = batches[index];
      index += 1;
      return batch;
    },
    async add() {},
    async remove() {},
    async unsubscribeArrow(drain) {
      if (!drain || index >= batches.length) {
        index = batches.length;
        return null;
      }
      const remaining = batches.slice(index);
      index = batches.length;
      return remaining.length > 0 ? remaining : null;
    },
    get tickers() {
      return [args.topic];
    },
    get fields() {
      return args.fields;
    },
    get isActive() {
      return index < batches.length;
    },
    get stats() {
      return {
        messagesReceived: index,
        droppedBatches: 0,
        batchesSent: index,
        slowConsumer: false,
      };
    },
  };
}

function loadSubscriptionClass() {
  try {
    return require('../dist/index.js').Subscription;
  } catch (err) {
    throw new Error(
      `subscription-wrapper path requires built dist/index.js; run npm run build:ts first. ${err.message}`,
    );
  }
}

function consumeDecodedTable(table) {
  // Force materialization so tableFromIPC work cannot be optimized away.
  const rows = table.toArray();
  if (rows.length === 0) {
    return 0;
  }
  return Object.keys(rows[0]).length;
}

function percentile(sorted, p) {
  if (sorted.length === 0) {
    return 0;
  }
  const index = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[index];
}

function memoryMb() {
  const mem = process.memoryUsage();
  return {
    rss: bytesToMb(mem.rss),
    heapUsed: bytesToMb(mem.heapUsed),
    external: bytesToMb(mem.external),
    arrayBuffers: bytesToMb(mem.arrayBuffers),
  };
}

function bytesToMb(bytes) {
  return Math.round((bytes / 1024 / 1024) * 100) / 100;
}

function summarizeDurations(durations) {
  const sorted = [...durations].sort((left, right) => left - right);
  const total = durations.reduce((sum, value) => sum + value, 0);
  return {
    avg: durations.length === 0 ? 0 : total / durations.length,
    p50: percentile(sorted, 50),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
    max: sorted.at(-1) ?? 0,
  };
}

async function runReplay(args) {
  const rows = args.fixture
    ? readJsonl(path.resolve(args.fixture))
    : Array.from({ length: args.rows }, (_, index) => syntheticTick(index, args.topic, args.fields));

  const setupStarted = performance.now();
  const replayBuffers = args.path === 'arrow-decode-only' ? buildReplayBuffers(rows) : undefined;
  const replayNativeBatches =
    args.path === 'subscription-wrapper' ? buildReplayNativeBatches(rows) : undefined;
  const setupMs = performance.now() - setupStarted;

  const durations = [];
  const startMemory = memoryMb();
  const started = performance.now();
  let processed = 0;
  let checksum = 0;

  for (let iteration = 0; iteration < args.iterations; iteration += 1) {
    if (args.path === 'subscription-wrapper') {
      const Subscription = loadSubscriptionClass();
      const sub = new Subscription(createFakeNativeSubscription(replayNativeBatches, args));
      for (let index = 0; index < rows.length; index += 1) {
        const before = performance.now();
        const result = await sub.next();
        if (result.done) {
          throw new Error('fake subscription ended before replay rows were exhausted');
        }
        checksum += consumeDecodedTable(result.value);
        durations.push(performance.now() - before);
        processed += 1;
        if (args.consumerDelayMs > 0) {
          await sleep(args.consumerDelayMs);
        }
      }
      continue;
    }

    const buffers = replayBuffers ?? rows;
    for (const item of buffers) {
      const before = performance.now();
      const table = args.path === 'legacy' ? tableFromIPC(rowToIpc(item)) : tableFromIPC(item);
      checksum += consumeDecodedTable(table);
      durations.push(performance.now() - before);
      processed += 1;
      if (args.consumerDelayMs > 0) {
        await sleep(args.consumerDelayMs);
      }
    }
  }

  const elapsedMs = performance.now() - started;
  return {
    mode: args.fixture ? 'fixture-replay' : 'synthetic-replay',
    path: args.path,
    fixture: args.fixture ? path.resolve(args.fixture) : undefined,
    updateModel: 'one-row-per-update',
    rowsPerIteration: rows.length,
    iterations: args.iterations,
    updates: processed,
    setupMs,
    elapsedMs,
    updatesPerSecond: processed / (elapsedMs / 1000),
    perUpdateMs: summarizeDurations(durations),
    consumerDelayMs: args.consumerDelayMs,
    fields: args.fields,
    memoryMb: {
      start: startMemory,
      end: memoryMb(),
    },
    checksum,
  };
}

async function runCapture(args) {
  if (!args.out) {
    throw new Error('--capture-live requires --out');
  }
  const core = require('../dist/index.js');
  const outputPath = path.resolve(args.out);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  const engine = await core.connect({
    host: process.env.XBBG_HOST || 'localhost',
    port: Number(process.env.XBBG_PORT || 8194),
  });

  const sub = await engine.stream([args.captureLive], args.fields);
  const writer = fs.createWriteStream(outputPath, { encoding: 'utf8' });
  const started = performance.now();
  let lastStatsAt = started;
  let rows = 0;
  let batches = 0;
  let finalStats = sub.stats;

  try {
    while (performance.now() - started < args.captureMs) {
      const result = await Promise.race([
        sub.next(),
        sleep(Math.min(1_000, args.captureMs)).then(() => null),
      ]);
      const now = performance.now();
      if (result !== null && !result.done) {
        batches += 1;
        for (const row of result.value.toArray()) {
          writer.write(`${JSON.stringify(row)}\n`);
          rows += 1;
        }
      }
      if (now - lastStatsAt >= args.statsIntervalMs) {
        finalStats = sub.stats;
        if (!args.json) {
          console.error(`stats ${JSON.stringify(finalStats)} rows=${rows} batches=${batches}`);
        }
        lastStatsAt = now;
      }
    }
  } finally {
    await new Promise((resolve, reject) => {
      writer.end((err) => (err ? reject(err) : resolve()));
    });
    finalStats = sub.stats;
    await sub.unsubscribe(false).catch(() => []);
    engine.signalShutdown();
  }

  const elapsedMs = performance.now() - started;
  return {
    mode: 'capture-live',
    ticker: args.captureLive,
    fields: args.fields,
    output: outputPath,
    elapsedMs,
    rows,
    batches,
    updateModel: 'captured-live-stream-rows',
    stats: finalStats,
  };
}

function printResult(result, jsonOnly) {
  const json = JSON.stringify(result, null, 2);
  if (jsonOnly) {
    console.log(json);
    return;
  }
  console.log(json);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(usage());
    return;
  }
  if (args.captureLive && args.fixture) {
    throw new Error('--capture-live and --fixture are mutually exclusive');
  }

  const result = args.captureLive ? await runCapture(args) : await runReplay(args);
  printResult(result, args.json);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
