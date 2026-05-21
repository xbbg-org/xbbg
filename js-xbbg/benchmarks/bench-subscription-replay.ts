#!/usr/bin/env node

import type { Table } from 'apache-arrow';

import { tableFromArrays, tableFromIPC, tableToIPC } from 'apache-arrow';
import * as fs from 'node:fs';
import { createRequire } from 'node:module';
import * as path from 'node:path';
import { performance } from 'node:perf_hooks';
import { setTimeout as sleep } from 'node:timers/promises';

const requireDist = createRequire(__filename);

const DEFAULT_FIELDS = ['LAST_PRICE', 'BID', 'ASK'];
const DEFAULT_TOPIC = 'XBTUSD Curncy';
const DEFAULT_ROWS = 100_000;
const DEFAULT_ITERATIONS = 1;
const DEFAULT_CAPTURE_MS = 10_000;
const DEFAULT_STATS_INTERVAL_MS = 1000;
const REPLAY_PATH_VALUES = ['legacy', 'arrow-decode-only', 'subscription-wrapper'] as const;
const CONSUME_MODE_VALUES = ['rows', 'vector', 'schema', 'none'] as const;

type ReplayPath = (typeof REPLAY_PATH_VALUES)[number];
type ConsumeMode = (typeof CONSUME_MODE_VALUES)[number];

type NativeArrowColumnType = 'bool' | 'float64' | 'int64' | 'null' | 'timestamp_us' | 'utf8';

type ReplayRow = Record<string, unknown>;

type BenchmarkResult = Record<string, unknown>;

interface CliArgs {
  captureLive?: string;
  captureMs: number;
  consume: ConsumeMode;
  consumerDelayMs: number;
  fields: string[];
  fixture?: string;
  help?: boolean;
  iterations: number;
  json: boolean;
  out?: string;
  path: ReplayPath;
  rows: number;
  statsIntervalMs: number;
  topic: string;
  warmupIterations: number;
}

interface NativeArrowColumn {
  readonly name: string;
  readonly type: NativeArrowColumnType;
  readonly nullable: boolean;
  readonly length: number;
  readonly nullCount: number;
  readonly data?: Buffer;
  readonly offsets?: Buffer;
}

interface NativeArrowBatch {
  readonly kind: 'zeroCopy';
  readonly numRows: number;
  readonly columns: NativeArrowColumn[];
}

interface SubscriptionStats {
  readonly messagesReceived: number;
  readonly droppedBatches: number;
  readonly batchesSent: number;
  readonly slowConsumer: boolean;
}

interface FakeNativeSubscription {
  readonly fields: string[];
  readonly isActive: boolean;
  readonly stats: SubscriptionStats;
  readonly tickers: string[];
  add(tickers: readonly string[]): Promise<void>;
  nextArrow(): Promise<NativeArrowBatch | null>;
  remove(tickers: readonly string[]): Promise<void>;
  unsubscribeArrow(drain: boolean): Promise<NativeArrowBatch[] | null>;
}

interface ArrowReplaySubscription {
  next(): Promise<IteratorResult<Table>>;
}

type ArrowSubscriptionConstructor = new (inner: FakeNativeSubscription) => ArrowReplaySubscription;

interface CaptureTick {
  toObject(): ReplayRow;
}

interface CaptureSubscription {
  readonly stats: SubscriptionStats;
  next(): Promise<IteratorResult<CaptureTick>>;
  unsubscribe(drain: boolean): Promise<CaptureTick[]>;
}

interface CaptureEngine {
  signalShutdown(): void;
  stream(tickers: readonly string[], fields: readonly string[]): Promise<CaptureSubscription>;
}

interface DistCore {
  connect(config: { readonly host: string; readonly port: number }): Promise<CaptureEngine>;
}

interface DistReplayCore extends DistCore {
  readonly ArrowSubscription: ArrowSubscriptionConstructor;
}

const REPLAY_PATHS: ReadonlySet<string> = new Set(REPLAY_PATH_VALUES);
const CONSUME_MODES: ReadonlySet<string> = new Set(CONSUME_MODE_VALUES);
const DEFAULT_PATH: ReplayPath = 'legacy';

function usage(): string {
  return `Usage:
  tsx benchmarks/bench-subscription-replay.ts [--rows N] [--iterations N] [--consume rows|vector|schema|none]
  tsx benchmarks/bench-subscription-replay.ts --fixture tmp/xbtusd-ticks.jsonl [--iterations N] [--warmup-iterations N]
  tsx benchmarks/bench-subscription-replay.ts --capture-live "XBTUSD Curncy" --capture-ms 10000 --out tmp/xbtusd-ticks.jsonl

Modes:
  synthetic      Default. Generates one tick/update at a time; no batching.
  fixture        Replays JSONL ticks one update at a time; no batching.
  replay paths  legacy (encode+decode), arrow-decode-only, subscription-wrapper (zero-copy descriptors)
  capture-live   Captures live Engine.stream() rows to JSONL and prints existing sub.stats.

Options:
  --rows N                 Synthetic rows per iteration. Default ${DEFAULT_ROWS}
  --iterations N           Replay iterations. Default ${DEFAULT_ITERATIONS}
  --warmup-iterations N    Untimed replay iterations before measurement. Default 0
  --fixture PATH           JSONL fixture to replay.
  --path NAME              Replay path: legacy, arrow-decode-only, subscription-wrapper. Default ${DEFAULT_PATH}
  --capture-live TICKER    Capture live subscription rows for TICKER.
  --capture-ms N           Live capture duration in ms. Default ${DEFAULT_CAPTURE_MS}
  --out PATH               Output JSONL path for live capture.
  --fields A,B,C           Fields for synthetic/capture. Default ${DEFAULT_FIELDS.join(',')}
  --topic TICKER           Synthetic topic. Default ${DEFAULT_TOPIC}
  --consume MODE           Consume decoded tables as rows, vector, schema, or none. Default rows
  --consumer-delay-ms N    Artificial per-update consumer delay after processing.
  --stats-interval-ms N    Live capture stats print interval. Default ${DEFAULT_STATS_INTERVAL_MS}
  --json                   Print only the final JSON result.
  --help                   Show this help.
`;
}

function parseArgs(argv: readonly string[]): CliArgs {
  const args: CliArgs = {
    captureMs: DEFAULT_CAPTURE_MS,
    consume: 'rows',
    consumerDelayMs: 0,
    fields: [...DEFAULT_FIELDS],
    iterations: DEFAULT_ITERATIONS,
    json: false,
    path: DEFAULT_PATH,
    rows: DEFAULT_ROWS,
    statsIntervalMs: DEFAULT_STATS_INTERVAL_MS,
    topic: DEFAULT_TOPIC,
    warmupIterations: 0,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = readArg(argv, index, 'argument');
    const next = (): string => {
      index += 1;
      return readArg(argv, index, arg);
    };

    switch (arg) {
      case '--rows': {
        args.rows = parsePositiveInteger(next(), '--rows');
        break;
      }
      case '--iterations': {
        args.iterations = parsePositiveInteger(next(), '--iterations');
        break;
      }
      case '--warmup-iterations': {
        args.warmupIterations = parseNonNegativeInteger(next(), '--warmup-iterations');
        break;
      }
      case '--fixture': {
        args.fixture = next();
        break;
      }
      case '--path': {
        args.path = parseReplayPath(next());
        break;
      }
      case '--consume': {
        args.consume = parseConsumeMode(next());
        break;
      }
      case '--capture-live': {
        args.captureLive = next();
        break;
      }
      case '--capture-ms': {
        args.captureMs = parsePositiveInteger(next(), '--capture-ms');
        break;
      }
      case '--out': {
        args.out = next();
        break;
      }
      case '--fields': {
        args.fields = parseCsv(next());
        break;
      }
      case '--topic': {
        args.topic = next();
        break;
      }
      case '--consumer-delay-ms': {
        args.consumerDelayMs = parseNonNegativeInteger(next(), '--consumer-delay-ms');
        break;
      }
      case '--stats-interval-ms': {
        args.statsIntervalMs = parsePositiveInteger(next(), '--stats-interval-ms');
        break;
      }
      case '--json': {
        args.json = true;
        break;
      }
      case '--help':
      case '-h': {
        args.help = true;
        break;
      }
      default: {
        throw new Error(`unknown argument: ${arg}`);
      }
    }
  }

  return args;
}

function readArg(argv: readonly string[], index: number, name: string): string {
  const value = argv[index];
  if (value === undefined) {
    throw new Error(`${name} requires a value`);
  }
  return value;
}

function isReplayPath(value: string): value is ReplayPath {
  return REPLAY_PATHS.has(value);
}

function parseReplayPath(value: string): ReplayPath {
  if (!isReplayPath(value)) {
    throw new Error(`--path must be one of: ${REPLAY_PATH_VALUES.join(', ')}`);
  }
  return value;
}

function isConsumeMode(value: string): value is ConsumeMode {
  return CONSUME_MODES.has(value);
}

function parseConsumeMode(value: string): ConsumeMode {
  if (!isConsumeMode(value)) {
    throw new Error(`--consume must be one of: ${CONSUME_MODE_VALUES.join(', ')}`);
  }
  return value;
}

function parseCsv(value: string): string[] {
  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  if (items.length === 0) {
    throw new Error('expected at least one field');
  }
  return items;
}

function parsePositiveInteger(value: string, name: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${name} must be a positive integer`);
  }
  return parsed;
}

function parseNonNegativeInteger(value: string, name: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return parsed;
}

function syntheticTick(index: number, topic: string, fields: readonly string[]): ReplayRow {
  const price = 50_000 + Math.sin(index / 17) * 250 + (index % 97) * 0.25;
  const row: ReplayRow = {
    MKTDATA_EVENT_SUBTYPE: '',
    MKTDATA_EVENT_TYPE: 'TRADE',
    timestamp: new Date(1_735_689_600_000 + index * 100).toISOString(),
    topic,
  };
  for (const field of fields) {
    switch (field) {
      case 'LAST_PRICE': {
        row[field] = round(price);
        break;
      }
      case 'BID': {
        row[field] = round(price - 1.25);
        break;
      }
      case 'ASK': {
        row[field] = round(price + 1.25);
        break;
      }
      default: {
        row[field] = round(price);
        break;
      }
    }
  }
  return row;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

function readJsonl(filePath: string): ReplayRow[] {
  const raw = fs.readFileSync(filePath, 'utf8');
  const rows: ReplayRow[] = [];
  let lineNumber = 0;
  for (const line of raw.split(/\r?\n/u)) {
    lineNumber += 1;
    const trimmed = line.trim();
    if (trimmed.length === 0) {
      continue;
    }
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (!isRecord(parsed)) {
        throw new Error('expected a JSON object row');
      }
      rows.push(parsed);
    } catch (error) {
      throw new Error(`invalid JSONL at ${filePath}:${lineNumber}: ${errorMessage(error)}`, {
        cause: error,
      });
    }
  }
  if (rows.length === 0) {
    throw new Error(`fixture contains no rows: ${filePath}`);
  }
  return rows;
}

function rowToIpc(row: ReplayRow): Uint8Array {
  const arrays: Record<string, readonly unknown[]> = {};
  for (const [key, value] of Object.entries(row)) {
    arrays[key] = [value === undefined ? null : value];
  }
  return tableToIPC(tableFromArrays(arrays));
}

function buildReplayBuffers(rows: readonly ReplayRow[]): Buffer[] {
  return rows.map((row) => Buffer.from(rowToIpc(row)));
}

function typedBuffer(view: ArrayBufferView): Buffer {
  return Buffer.from(view.buffer, view.byteOffset, view.byteLength);
}

function buildReplayNativeBatches(rows: readonly ReplayRow[]): NativeArrowBatch[] {
  return rows.map(rowToNativeArrowBatch);
}

function rowToNativeArrowBatch(row: ReplayRow): NativeArrowBatch {
  const columns = Object.entries(row).map(([name, value]) => nativeArrowColumn(name, value));
  return {
    columns,
    kind: 'zeroCopy',
    numRows: 1,
  };
}

function nativeArrowColumn(name: string, value: unknown): NativeArrowColumn {
  const normalized = value === undefined ? null : value;
  if (normalized === null) {
    return { length: 1, name, nullCount: 1, nullable: true, type: 'null' };
  }
  if (typeof normalized === 'number') {
    return {
      data: typedBuffer(new Float64Array([normalized])),
      length: 1,
      name,
      nullCount: 0,
      nullable: false,
      type: 'float64',
    };
  }
  if (typeof normalized === 'bigint') {
    return {
      data: typedBuffer(new BigInt64Array([normalized])),
      length: 1,
      name,
      nullCount: 0,
      nullable: false,
      type: 'int64',
    };
  }
  if (typeof normalized === 'boolean') {
    return {
      data: Buffer.from([normalized ? 1 : 0]),
      length: 1,
      name,
      nullCount: 0,
      nullable: false,
      type: 'bool',
    };
  }
  if (normalized instanceof Date) {
    return {
      data: typedBuffer(new BigInt64Array([BigInt(normalized.getTime()) * 1000n])),
      length: 1,
      name,
      nullCount: 0,
      nullable: false,
      type: 'timestamp_us',
    };
  }

  const data = Buffer.from(nativeString(normalized));
  return {
    data,
    length: 1,
    name,
    nullCount: 0,
    nullable: false,
    offsets: typedBuffer(new Int32Array([0, data.byteLength])),
    type: 'utf8',
  };
}

function nativeString(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value);
  }
  if (typeof value === 'symbol') {
    return value.description ?? 'Symbol()';
  }
  if (typeof value === 'object') {
    try {
      const json = JSON.stringify(value);
      return json ?? Object.prototype.toString.call(value);
    } catch {
      return Object.prototype.toString.call(value);
    }
  }
  return Object.prototype.toString.call(value);
}

function createFakeNativeSubscription(
  batches: readonly NativeArrowBatch[],
  args: CliArgs,
): FakeNativeSubscription {
  let index = 0;
  return {
    async add(_tickers: readonly string[]): Promise<void> {},
    get fields(): string[] {
      return args.fields;
    },
    get isActive(): boolean {
      return index < batches.length;
    },
    async nextArrow(): Promise<NativeArrowBatch | null> {
      if (index >= batches.length) {
        return null;
      }
      const batch = batches[index];
      index += 1;
      return batch ?? null;
    },
    async remove(_tickers: readonly string[]): Promise<void> {},
    get stats(): SubscriptionStats {
      return {
        messagesReceived: index,
        droppedBatches: 0,
        batchesSent: index,
        slowConsumer: false,
      };
    },
    get tickers(): string[] {
      return [args.topic];
    },
    async unsubscribeArrow(drain: boolean): Promise<NativeArrowBatch[] | null> {
      if (!drain || index >= batches.length) {
        index = batches.length;
        return null;
      }
      const remaining = batches.slice(index);
      index = batches.length;
      return remaining.length > 0 ? remaining : null;
    },
  };
}

function loadDistModule(): unknown {
  return requireDist('../dist/index.js') as unknown;
}

function loadCore(): DistCore {
  const core = loadDistModule();
  if (!isDistCore(core)) {
    throw new Error('built dist/index.js does not expose the expected capture API');
  }
  return core;
}

function loadSubscriptionClass(): ArrowSubscriptionConstructor {
  try {
    const core = loadDistModule();
    if (!isDistReplayCore(core)) {
      throw new Error('built dist/index.js does not expose ArrowSubscription');
    }
    return core.ArrowSubscription;
  } catch (error) {
    throw new Error(
      `subscription-wrapper path requires built dist/index.js; run npm run build:ts first. ${errorMessage(error)}`,
      { cause: error },
    );
  }
}

function consumeDecodedTable(table: Table, mode: ConsumeMode): number {
  switch (mode) {
    case 'rows': {
      // Default: force full row materialization for continuity with prior benchmark results.
      const rows: readonly unknown[] = table.toArray();
      const first = rows[0];
      if (!isRecord(first)) {
        return 0;
      }
      return Object.keys(first).length;
    }
    case 'vector': {
      let checksum = 0;
      for (const field of table.schema.fields) {
        checksum += table.getChild(field.name)?.length ?? 0;
      }
      return checksum;
    }
    case 'schema': {
      return table.schema.fields.length;
    }
    case 'none': {
      return table.numRows;
    }
  }
  throw new Error('unknown consume mode');
}

function percentile(sorted: readonly number[], p: number): number {
  if (sorted.length === 0) {
    return 0;
  }
  const index = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[index] ?? 0;
}

interface MemoryUsageMb {
  readonly arrayBuffers: number;
  readonly external: number;
  readonly heapUsed: number;
  readonly rss: number;
}

function memoryMb(): MemoryUsageMb {
  const mem = process.memoryUsage();
  return {
    arrayBuffers: bytesToMb(mem.arrayBuffers),
    external: bytesToMb(mem.external),
    heapUsed: bytesToMb(mem.heapUsed),
    rss: bytesToMb(mem.rss),
  };
}

function bytesToMb(bytes: number): number {
  return Math.round((bytes / 1024 / 1024) * 100) / 100;
}

interface DurationSummary {
  readonly avg: number;
  readonly max: number;
  readonly p50: number;
  readonly p95: number;
  readonly p99: number;
}

function summarizeDurations(durations: readonly number[]): DurationSummary {
  const sorted = [...durations].toSorted((left, right) => left - right);
  const total = durations.reduce((sum, value) => sum + value, 0);
  return {
    avg: durations.length === 0 ? 0 : total / durations.length,
    max: sorted.at(-1) ?? 0,
    p50: percentile(sorted, 50),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
  };
}

async function runReplay(args: CliArgs): Promise<BenchmarkResult> {
  const rows =
    args.fixture !== undefined
      ? readJsonl(path.resolve(args.fixture))
      : Array.from({ length: args.rows }, (_, index) =>
          syntheticTick(index, args.topic, args.fields),
        );

  const setupStarted = performance.now();
  const replayBuffers = args.path === 'arrow-decode-only' ? buildReplayBuffers(rows) : undefined;
  const replayNativeBatches =
    args.path === 'subscription-wrapper' ? buildReplayNativeBatches(rows) : undefined;
  const setupMs = performance.now() - setupStarted;

  const durations: number[] = [];
  const startMemory = memoryMb();
  let started = performance.now();
  let processed = 0;
  let checksum = 0;

  const totalIterations = args.warmupIterations + args.iterations;
  for (let iteration = 0; iteration < totalIterations; iteration += 1) {
    const isWarmup = iteration < args.warmupIterations;
    if (isWarmup && iteration === 0) {
      started = performance.now();
    }
    if (!isWarmup && iteration === args.warmupIterations) {
      durations.length = 0;
      processed = 0;
      checksum = 0;
      started = performance.now();
    }

    if (args.path === 'subscription-wrapper') {
      if (replayNativeBatches === undefined) {
        throw new Error('internal error: missing subscription-wrapper replay batches');
      }
      const ArrowSubscription = loadSubscriptionClass();
      const sub = new ArrowSubscription(createFakeNativeSubscription(replayNativeBatches, args));
      for (let index = 0; index < rows.length; index += 1) {
        const before = performance.now();
        const result = await sub.next();
        if (result.done === true) {
          throw new Error('fake subscription ended before replay rows were exhausted');
        }
        const consumed = consumeDecodedTable(result.value, args.consume);
        if (!isWarmup) {
          checksum += consumed;
          durations.push(performance.now() - before);
          processed += 1;
        }
        if (args.consumerDelayMs > 0) {
          await sleep(args.consumerDelayMs);
        }
      }
      continue;
    }

    if (args.path === 'legacy') {
      for (const row of rows) {
        const before = performance.now();
        const table = tableFromIPC(rowToIpc(row));
        const consumed = consumeDecodedTable(table, args.consume);
        if (!isWarmup) {
          checksum += consumed;
          durations.push(performance.now() - before);
          processed += 1;
        }
        if (args.consumerDelayMs > 0) {
          await sleep(args.consumerDelayMs);
        }
      }
      continue;
    }

    if (replayBuffers === undefined) {
      throw new Error('internal error: missing Arrow replay buffers');
    }
    for (const buffer of replayBuffers) {
      const before = performance.now();
      const table = tableFromIPC(buffer);
      const consumed = consumeDecodedTable(table, args.consume);
      if (!isWarmup) {
        checksum += consumed;
        durations.push(performance.now() - before);
        processed += 1;
      }
      if (args.consumerDelayMs > 0) {
        await sleep(args.consumerDelayMs);
      }
    }
  }

  const elapsedMs = performance.now() - started;
  return {
    checksum,
    consume: args.consume,
    consumerDelayMs: args.consumerDelayMs,
    elapsedMs,
    fields: args.fields,
    fixture: args.fixture !== undefined ? path.resolve(args.fixture) : undefined,
    iterations: args.iterations,
    memoryMb: {
      end: memoryMb(),
      start: startMemory,
    },
    mode: args.fixture !== undefined ? 'fixture-replay' : 'synthetic-replay',
    path: args.path,
    perUpdateMs: summarizeDurations(durations),
    rowsPerIteration: rows.length,
    setupMs,
    updateModel: 'one-row-per-update',
    updates: processed,
    updatesPerSecond: processed / (elapsedMs / 1000),
    warmupIterations: args.warmupIterations,
  };
}

async function runCapture(args: CliArgs): Promise<BenchmarkResult> {
  if (args.out === undefined || args.out.length === 0) {
    throw new Error('--capture-live requires --out');
  }
  if (args.captureLive === undefined) {
    throw new Error('--capture-live requires a ticker');
  }

  const core = loadCore();
  const outputPath = path.resolve(args.out);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  const engine = await core.connect({
    host: process.env.XBBG_HOST ?? 'localhost',
    port: Number(process.env.XBBG_PORT ?? 8194),
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
        sleep(Math.min(1000, args.captureMs)).then((): null => null),
      ]);
      const now = performance.now();
      if (result !== null && result.done !== true) {
        batches += 1;
        writer.write(`${JSON.stringify(result.value.toObject())}\n`);
        rows += 1;
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
    await new Promise<void>((resolve, reject) => {
      writer.once('error', reject);
      writer.end(() => {
        writer.off('error', reject);
        resolve();
      });
    });
    finalStats = sub.stats;
    await sub.unsubscribe(false).catch((): CaptureTick[] => []);
    engine.signalShutdown();
  }

  const elapsedMs = performance.now() - started;
  return {
    batches,
    consume: args.consume,
    elapsedMs,
    fields: args.fields,
    mode: 'capture-live',
    output: outputPath,
    rows,
    stats: finalStats,
    ticker: args.captureLive,
    updateModel: 'captured-live-stream-rows',
    warmupIterations: args.warmupIterations,
  };
}

function printResult(result: BenchmarkResult, jsonOnly: boolean): void {
  const json = JSON.stringify(result, null, 2);
  if (jsonOnly) {
    console.log(json);
    return;
  }
  console.log(json);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.help === true) {
    process.stdout.write(usage());
    return;
  }
  if (args.captureLive !== undefined && args.fixture !== undefined) {
    throw new Error('--capture-live and --fixture are mutually exclusive');
  }

  const result = args.captureLive !== undefined ? await runCapture(args) : await runReplay(args);
  printResult(result, args.json);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isDistCore(value: unknown): value is DistCore {
  return isRecord(value) && typeof value.connect === 'function';
}

function isDistReplayCore(value: unknown): value is DistReplayCore {
  if (!isRecord(value) || !isDistCore(value)) {
    return false;
  }
  return typeof value.ArrowSubscription === 'function';
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

main().catch((error: unknown) => {
  console.error(errorMessage(error));
  process.exit(1);
});
