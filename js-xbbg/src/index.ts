import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { tableFromIPC, type Table } from 'apache-arrow';

import {
  BlpError,
  BlpInternalError,
  BlpRequestError,
  BlpSessionError,
  BlpTimeoutError,
  BlpValidationError,
  wrapError,
} from './errors';
import { resolveNativeAddon } from './native/resolve-native';
import type {
  ActiveCdxOptions,
  AuthConfig,
  BackendKind,
  BdhOptions,
  BdibOptions,
  BdpOptions,
  BdtickOptions,
  BeqsOptions,
  BfldsOptions,
  BlkpOptions,
  BqlOptions,
  BqrOptions,
  BsrchOptions,
  BtaOptions,
  CdxOptions,
  CdxTickerInfo,
  CorporateBondsOptions,
  DividendOptions,
  EngineConfig,
  EtfHoldingsOptions,
  ExchangeInfoResult,
  ExchangeOverrideInput,
  FieldInfo,
  FormatKind,
  FuturesCandidate,
  FuturesResolveOptions,
  FxPairInfo,
  MarketRule,
  OverridesMap,
  PreferredsOptions,
  PrimitiveValue,
  RecipeBackendOptions,
  RequestInput,
  RequestOptions,
  ServerAddress,
  SessionWindowsInfo,
  Socks5Config,
  StreamOptions,
  StringPair,
  SubscriptionStats,
  TickerParts,
  TimeRange,
  TlsConfig,
  TurnoverOptions,
  YasOptions,
} from './types';
import type { NativeAddon, NativeEngine, NativeSubscription } from './napi';

const nodeRequire = createRequire(__filename);

interface PackageJsonShape {
  readonly version: string;
}

interface PolarsModule {
  readIPC(buffer: Buffer): unknown;
}

const packageJson = nodeRequire('../package.json') as PackageJsonShape;

function containsBlpapiRuntime(dir: string): boolean {
  if (dir.length === 0 || !fs.existsSync(dir)) {
    return false;
  }
  return [
    'blpapi3_64.dll',
    'blpapi3_32.dll',
    'libblpapi3.dylib',
    'libblpapi3_64.so',
    'libblpapi3.so',
  ].some((name) => fs.existsSync(path.join(dir, name)));
}

function configureRuntimeSearchPath(): void {
  if (process.platform !== 'win32') {
    return;
  }

  const candidates: string[] = [];
  const libDir = process.env['BLPAPI_LIB_DIR'];
  if (libDir !== undefined && libDir.length > 0) {
    candidates.push(path.resolve(libDir));
  }
  const root = process.env['BLPAPI_ROOT'];
  if (root !== undefined && root.length > 0) {
    const resolved = path.resolve(root);
    candidates.push(resolved, path.join(resolved, 'bin'), path.join(resolved, 'lib'));
  }

  for (const candidate of candidates) {
    if (!containsBlpapiRuntime(candidate)) {
      continue;
    }
    const currentPath = process.env['PATH'] ?? '';
    const parts = currentPath.split(';').filter((part) => part.length > 0);
    if (!parts.includes(candidate)) {
      process.env['PATH'] =
        currentPath.length > 0 ? `${candidate};${currentPath}` : candidate;
    }
    break;
  }
}

configureRuntimeSearchPath();

function loadNative(): NativeAddon {
  const root = path.resolve(__dirname, '..', '..');

  const candidates = [
    path.join(__dirname, 'napi_xbbg.node'),
    path.join(__dirname, '..', 'napi_xbbg.node'),
    path.join(__dirname, 'napi-xbbg.node'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return nodeRequire(candidate) as NativeAddon;
    }
  }

  const { key, packageName, binaryPath } = resolveNativeAddon(root);
  if (binaryPath !== null) {
    return nodeRequire(binaryPath) as NativeAddon;
  }
  if (packageName === null) {
    throw new Error(
      `No packaged @xbbg/core native addon is available for ${key}. Build it locally with "npm run build" from js-xbbg.`,
    );
  }

  throw new Error(
    `Unable to load native napi-xbbg module for ${key}. Install ${packageName} via Bun/npm, or build it locally with "npm run build" from js-xbbg.`,
  );
}

const native = loadNative();

// ── Constants ───────────────────────────────────────────────────────────

export const Backend = Object.freeze({
  ARROW: 'arrow',
  JSON: 'json',
  POLARS: 'polars',
}) satisfies Readonly<Record<string, BackendKind>>;

export const Format = Object.freeze({
  LONG: 'long',
  LONG_TYPED: 'long_typed',
  LONG_WITH_METADATA: 'long_with_metadata',
  SEMI_LONG: 'semi_long',
}) satisfies Readonly<Record<string, FormatKind>>;

const CDX_INFO_FIELDS = Object.freeze([
  'ROLLING_SERIES',
  'VERSION',
  'ON_THE_RUN_CURRENT_BD_INDICATOR',
  'CDS_FIRST_ACCRUAL_START_DATE',
  'NAME',
  'NUM_CURRENT_COMPANIES_CCY_TKR',
  'NUM_ORIG_COMPANIES_CRNCY_TKR',
  'PX_LAST',
]);

const CDX_PRICING_FIELDS = Object.freeze([
  'PX_LAST',
  'PX_BID',
  'PX_ASK',
  'UPFRONT_LAST',
  'UPFRONT_BID',
  'UPFRONT_ASK',
  'CDS_FLAT_SPREAD',
  'UPFRONT_FEE',
  'PV_CDS_PREMIUM_LEG',
  'PV_CDS_DEFAULT_LEG',
]);

const CDX_RISK_FIELDS = Object.freeze([
  'SW_CNV_BPV',
  'SW_EQV_BPV',
  'CDS_SPREAD_MID_MODIFIED_DURATION',
  'CDS_SPREAD_MID_CONVEXITY',
  'RECOVERY_RATE_SEN',
  'CDS_RECOVERY_RT',
]);

const TA_STUDIES: Readonly<Record<string, string>> = Object.freeze({
  smavg: 'smavgStudyAttributes',
  sma: 'smavgStudyAttributes',
  emavg: 'emavgStudyAttributes',
  ema: 'emavgStudyAttributes',
  wmavg: 'wmavgStudyAttributes',
  wma: 'wmavgStudyAttributes',
  vmavg: 'vmavgStudyAttributes',
  vma: 'vmavgStudyAttributes',
  tmavg: 'tmavgStudyAttributes',
  tma: 'tmavgStudyAttributes',
  ipmavg: 'ipmavgStudyAttributes',
  rsi: 'rsiStudyAttributes',
  macd: 'macdStudyAttributes',
  mao: 'maoStudyAttributes',
  momentum: 'momentumStudyAttributes',
  mom: 'momentumStudyAttributes',
  roc: 'rocStudyAttributes',
  boll: 'bollStudyAttributes',
  bb: 'bollStudyAttributes',
  kltn: 'kltnStudyAttributes',
  keltner: 'kltnStudyAttributes',
  mae: 'maeStudyAttributes',
  te: 'teStudyAttributes',
  al: 'alStudyAttributes',
  dmi: 'dmiStudyAttributes',
  adx: 'dmiStudyAttributes',
  tas: 'tasStudyAttributes',
  stoch: 'tasStudyAttributes',
  trender: 'trenderStudyAttributes',
  ptps: 'ptpsStudyAttributes',
  parabolic: 'ptpsStudyAttributes',
  sar: 'ptpsStudyAttributes',
  chko: 'chkoStudyAttributes',
  ado: 'adoStudyAttributes',
  vat: 'vatStudyAttributes',
  tvat: 'tvatStudyAttributes',
  atr: 'atrStudyAttributes',
  hurst: 'hurstStudyAttributes',
  fg: 'fgStudyAttributes',
  fear_greed: 'fgStudyAttributes',
  goc: 'gocStudyAttributes',
  ichimoku: 'gocStudyAttributes',
  cmci: 'cmciStudyAttributes',
  wlpr: 'wlprStudyAttributes',
  williams: 'wlprStudyAttributes',
  maxmin: 'maxminStudyAttributes',
  rex: 'rexStudyAttributes',
  etd: 'etdStudyAttributes',
  pd: 'pdStudyAttributes',
  rv: 'rvStudyAttributes',
  pivot: 'pivotStudyAttributes',
  or: 'orStudyAttributes',
  pcr: 'pcrStudyAttributes',
  bs: 'bsStudyAttributes',
});

type StudyParams = Record<string, PrimitiveValue>;

const TA_DEFAULTS: Readonly<Record<string, Readonly<StudyParams>>> = Object.freeze({
  smavgStudyAttributes: Object.freeze({ period: 20, priceSourceClose: 'PX_LAST' }),
  emavgStudyAttributes: Object.freeze({ period: 20, priceSourceClose: 'PX_LAST' }),
  wmavgStudyAttributes: Object.freeze({ period: 20, priceSourceClose: 'PX_LAST' }),
  vmavgStudyAttributes: Object.freeze({ period: 20, priceSourceClose: 'PX_LAST' }),
  tmavgStudyAttributes: Object.freeze({ period: 20, priceSourceClose: 'PX_LAST' }),
  rsiStudyAttributes: Object.freeze({ period: 14, priceSourceClose: 'PX_LAST' }),
  macdStudyAttributes: Object.freeze({
    maPeriod1: 12,
    maPeriod2: 26,
    sigPeriod: 9,
    priceSourceClose: 'PX_LAST',
  }),
  bollStudyAttributes: Object.freeze({
    period: 20,
    upperBand: 2.0,
    lowerBand: 2.0,
    priceSourceClose: 'PX_LAST',
  }),
  dmiStudyAttributes: Object.freeze({
    period: 14,
    priceSourceHigh: 'PX_HIGH',
    priceSourceLow: 'PX_LOW',
    priceSourceClose: 'PX_LAST',
  }),
  atrStudyAttributes: Object.freeze({
    maType: 'Simple',
    period: 14,
    priceSourceHigh: 'PX_HIGH',
    priceSourceLow: 'PX_LOW',
    priceSourceClose: 'PX_LAST',
  }),
  tasStudyAttributes: Object.freeze({
    periodK: 14,
    periodD: 3,
    periodDS: 3,
    periodDSS: 3,
    priceSourceHigh: 'PX_HIGH',
    priceSourceLow: 'PX_LOW',
    priceSourceClose: 'PX_LAST',
  }),
});

// ── Helpers ─────────────────────────────────────────────────────────────

function toArrowTable(ipcBuffer: Buffer): Table {
  return tableFromIPC(ipcBuffer);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function mapObjectToPairs(
  obj: OverridesMap | undefined,
): StringPair[] | undefined {
  if (obj === undefined) {
    return undefined;
  }
  return Object.entries(obj).map(([key, value]) => ({
    key: String(key),
    value: String(value),
  }));
}

function toStringArray(value: string | readonly string[] | null | undefined): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  if (value === null || value === undefined) {
    return [];
  }
  return [String(value)];
}

function normalizeConfigureArgs(
  configOrHost?: EngineConfig | string,
  port?: number,
): EngineConfig | undefined {
  if (configOrHost === undefined || configOrHost === null) {
    return undefined;
  }
  if (typeof configOrHost === 'string' || port !== undefined) {
    const config: EngineConfig = {};
    if (typeof configOrHost === 'string') {
      config.host = configOrHost;
    }
    if (port !== undefined && port !== null) {
      config.port = Number(port);
    }
    return config;
  }
  if (isPlainObject(configOrHost)) {
    return { ...(configOrHost as EngineConfig) };
  }
  throw new TypeError(
    'configure expects either a config object or host/port arguments',
  );
}

function normalizeRecoveryOptions(options: CdxOptions = {}): BdpOptions {
  const normalized: CdxOptions = { ...options };
  const recoveryRate = normalized.recoveryRate ?? normalized.recovery_rate;
  delete normalized.recoveryRate;
  delete normalized.recovery_rate;
  if (recoveryRate !== undefined && recoveryRate !== null) {
    normalized.overrides = {
      ...(normalized.overrides ?? {}),
      CDS_RR: String(recoveryRate),
    };
  }
  return normalized;
}

function fullDayRange(dt: string): TimeRange {
  const normalized = String(dt).trim().replace(' ', 'T');
  const day = normalized.split('T')[0];
  if (day === undefined || day.length === 0) {
    throw new TypeError('dt must be a non-empty ISO date string');
  }
  return {
    start: `${day}T00:00:00`,
    end: `${day}T23:59:59`,
  };
}

function normalizeDate(value: string | undefined): string | undefined {
  return value === undefined ? undefined : String(value).replace(/[-/]/g, '');
}

function getStudyAttrName(study: string): string {
  const normalized = study.toLowerCase().replace(/-/g, '_').replace(/ /g, '_');
  const mapped = TA_STUDIES[normalized];
  if (mapped !== undefined) {
    return mapped;
  }
  if (normalized.endsWith('studyattributes')) {
    return normalized;
  }
  return `${normalized}StudyAttributes`;
}

interface RawStudy {
  studyType?: string;
  study?: string;
  calcInterval?: string;
  interval?: number | string;
  length?: number;
  period?: number;
  [key: string]: PrimitiveValue | undefined;
}

function buildTaRequest(
  ticker: string,
  study: string | RawStudy,
  options: BtaOptions = {},
): StringPair[] {
  const rawStudy: RawStudy =
    typeof study === 'string' ? { studyType: study } : { ...study };
  const studyType = rawStudy.studyType ?? rawStudy.study ?? (typeof study === 'string' ? study : '');
  const attrName = getStudyAttrName(String(studyType));

  const kwargs: Record<string, PrimitiveValue> = { ...(options.kwargs ?? {}) };
  const startDate = normalizeDate(
    stringOrUndef(kwargs['startDate']) ??
      stringOrUndef(kwargs['start_date']) ??
      options.startDate ??
      options.start_date,
  );
  const endDate = normalizeDate(
    stringOrUndef(kwargs['endDate']) ??
      stringOrUndef(kwargs['end_date']) ??
      options.endDate ??
      options.end_date,
  );
  const periodicity = String(
    stringOrUndef(kwargs['periodicitySelection']) ??
      stringOrUndef(kwargs['periodicity']) ??
      rawStudy.calcInterval ??
      options.periodicity ??
      'DAILY',
  ).toUpperCase();
  const interval =
    kwargs['interval'] ?? rawStudy.interval ?? options.interval;

  delete kwargs['startDate'];
  delete kwargs['start_date'];
  delete kwargs['endDate'];
  delete kwargs['end_date'];
  delete kwargs['periodicitySelection'];
  delete kwargs['periodicity'];
  delete rawStudy.studyType;
  delete rawStudy.study;
  delete rawStudy.calcInterval;

  if (rawStudy.length !== undefined && rawStudy.period === undefined) {
    rawStudy.period = rawStudy.length;
  }
  delete rawStudy.length;

  const params: StudyParams = {
    ...(TA_DEFAULTS[attrName] ?? {}),
    ...(options.studyParams ?? {}),
    ...(rawStudy as StudyParams),
  };

  if (params['length'] !== undefined && params['period'] === undefined) {
    params['period'] = params['length'];
  }
  delete params['length'];
  delete params['calcInterval'];

  const elements: StringPair[] = [
    { key: 'priceSource.securityName', value: String(ticker) },
  ];

  if (periodicity === 'INTRADAY') {
    const prefix = 'priceSource.dataRange.intraday';
    if (startDate !== undefined) {
      elements.push({ key: `${prefix}.startDate`, value: startDate });
    }
    if (endDate !== undefined) {
      elements.push({ key: `${prefix}.endDate`, value: endDate });
    }
    elements.push({ key: `${prefix}.eventType`, value: 'TRADE' });
    if (interval !== undefined && interval !== null) {
      elements.push({ key: `${prefix}.interval`, value: String(interval) });
    }
  } else {
    const prefix = 'priceSource.dataRange.historical';
    if (startDate !== undefined) {
      elements.push({ key: `${prefix}.startDate`, value: startDate });
    }
    if (endDate !== undefined) {
      elements.push({ key: `${prefix}.endDate`, value: endDate });
    }
    elements.push({ key: `${prefix}.periodicitySelection`, value: periodicity });
  }

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) {
      continue;
    }
    elements.push({
      key: `studyAttributes.${attrName}.${key}`,
      value: String(value),
    });
  }

  for (const [key, value] of Object.entries(kwargs)) {
    if (value === undefined || value === null) {
      continue;
    }
    elements.push({ key: String(key), value: String(value) });
  }

  return elements;
}

function stringOrUndef(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function loadPolars(): PolarsModule {
  try {
    return nodeRequire('nodejs-polars') as PolarsModule;
  } catch {
    throw new Error(
      'nodejs-polars is required for Polars backend. Install: npm install nodejs-polars',
    );
  }
}

function ipcToBackend(buffer: Buffer, backend: string): unknown {
  if (backend === Backend.JSON) {
    return Array.from(tableFromIPC(buffer));
  }
  if (backend === Backend.POLARS) {
    return loadPolars().readIPC(buffer);
  }
  return tableFromIPC(buffer);
}

// ── Configured engine state ─────────────────────────────────────────────

let configuredEngineConfig: EngineConfig | undefined;
let configuredEnginePromise: Promise<Engine> | undefined;

function clearConfiguredEngine(): void {
  const existing = configuredEnginePromise;
  configuredEnginePromise = undefined;
  if (existing !== undefined) {
    existing
      .then((engine) => {
        engine.signalShutdown();
      })
      .catch(() => {
        /* ignore shutdown errors */
      });
  }
}

async function getConfiguredEngine(): Promise<Engine> {
  if (configuredEnginePromise === undefined) {
    const pending = connect(configuredEngineConfig);
    pending.catch(() => {
      if (configuredEnginePromise === pending) {
        configuredEnginePromise = undefined;
      }
    });
    configuredEnginePromise = pending;
  }
  return await configuredEnginePromise;
}

// ── Subscription class ──────────────────────────────────────────────────

export class Subscription implements AsyncIterator<Table>, AsyncIterable<Table> {
  private readonly _inner: NativeSubscription;

  public constructor(inner: NativeSubscription) {
    this._inner = inner;
  }

  public async next(): Promise<IteratorResult<Table>> {
    try {
      const batch = await this._inner.next();
      if (batch === null) {
        return { done: true, value: undefined };
      }
      return { done: false, value: toArrowTable(batch) };
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async add(tickers: readonly string[]): Promise<void> {
    try {
      await this._inner.add(tickers);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async remove(tickers: readonly string[]): Promise<void> {
    try {
      await this._inner.remove(tickers);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async unsubscribe(drain = false): Promise<Table[]> {
    const drained = await this._inner.unsubscribe(Boolean(drain));
    if (drained === null) {
      return [];
    }
    return drained.map(toArrowTable);
  }

  public get tickers(): string[] {
    return this._inner.tickers;
  }

  public get fields(): string[] {
    return this._inner.fields;
  }

  public get isActive(): boolean {
    return this._inner.isActive;
  }

  public get stats(): SubscriptionStats {
    return this._inner.stats;
  }

  public [Symbol.asyncIterator](): this {
    return this;
  }
}

// ── Engine class ────────────────────────────────────────────────────────

export class Engine {
  // Set via constructor or via `withConfig` (which instantiates via Object.create).
  private _inner!: NativeEngine;

  public constructor(host = 'localhost', port = 8194) {
    try {
      this._inner = new native.JsEngine(host, port);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public static withConfig(config: EngineConfig = {}): Engine {
    const engine: Engine = Object.create(Engine.prototype) as Engine;
    try {
      engine._inner = native.JsEngine.withConfig(config);
    } catch (err) {
      throw wrapError(err);
    }
    return engine;
  }

  public async request(params: RequestInput): Promise<unknown> {
    const backend = params.backend ?? Backend.ARROW;
    const { backend: _discarded, ...nativeParams } = params;
    try {
      const buffer = await this._inner.request(nativeParams);
      return ipcToBackend(buffer, backend);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async requestRaw(params: RequestInput): Promise<Buffer> {
    try {
      return await this._inner.request(params);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async bdp(
    tickers: readonly string[],
    fields: readonly string[],
    options: BdpOptions = {},
  ): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'ReferenceDataRequest',
      securities: tickers,
      fields,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      backend: options.backend,
      includeSecurityErrors: Boolean(options.includeSecurityErrors),
      extractor: 'refdata',
    });
  }

  public async bds(
    tickers: readonly string[],
    fields: readonly string[],
    options: BdpOptions = {},
  ): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'ReferenceDataRequest',
      securities: tickers,
      fields,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      backend: options.backend,
      extractor: 'bulk',
    });
  }

  public async bdh(
    tickers: readonly string[],
    fields: readonly string[],
    options: BdhOptions = {},
  ): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'HistoricalDataRequest',
      securities: tickers,
      fields,
      startDate: options.start,
      endDate: options.end,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      backend: options.backend,
      extractor: 'histdata',
    });
  }

  public async bdib(ticker: string, options: BdibOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'IntradayBarRequest',
      security: ticker,
      eventType: options.eventType ?? 'TRADE',
      interval: options.interval ?? 1,
      startDatetime: options.start,
      endDatetime: options.end,
      kwargs: mapObjectToPairs(options.kwargs),
      backend: options.backend,
      extractor: 'intraday_bar',
    });
  }

  public async bdtick(ticker: string, options: BdtickOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'IntradayTickRequest',
      security: ticker,
      eventTypes: options.eventTypes ?? ['TRADE'],
      startDatetime: options.start,
      endDatetime: options.end,
      kwargs: mapObjectToPairs(options.kwargs),
      backend: options.backend,
      extractor: 'intraday_tick',
    });
  }

  public async bql(query: string, options: BqlOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/bqlsvc',
      operation: 'sendQuery',
      elements: [{ key: 'expression', value: String(query) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      extractor: 'bql',
    });
  }

  public async beqs(screen: string, options: BeqsOptions = {}): Promise<unknown> {
    const elements: StringPair[] = [
      { key: 'screenName', value: String(screen) },
      { key: 'screenType', value: String(options.screenType ?? 'PRIVATE') },
      { key: 'Group', value: String(options.group ?? 'General') },
    ];
    if (options.asof !== undefined) {
      elements.push({ key: 'asOfDate', value: String(options.asof) });
    }
    const overrides: OverridesMap = { ...(options.overrides ?? {}) };
    return await this.request({
      service: '//blp/refdata',
      operation: 'BeqsRequest',
      elements,
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      overrides: mapObjectToPairs(overrides),
      format: options.format,
      extractor: 'generic',
    });
  }

  public async bsrch(searchSpec: string, options: BsrchOptions = {}): Promise<unknown> {
    const elements: OverridesMap = {
      Domain: String(searchSpec),
      ...(options.overrides ?? {}),
      ...(options.kwargs ?? {}),
    };
    return await this.request({
      service: '//blp/exrsvc',
      operation: 'ExcelGetGridRequest',
      backend: options.backend,
      elements: mapObjectToPairs(elements),
      format: options.format,
      extractor: 'bsrch',
    });
  }

  public async bta(
    ticker: string,
    study: string | RawStudy,
    options: BtaOptions = {},
  ): Promise<unknown> {
    return await this.request({
      service: '//blp/tasvc',
      operation: 'studyRequest',
      elements: buildTaRequest(ticker, study, options),
      backend: options.backend,
      format: options.format,
      extractor: 'generic',
    });
  }

  public async bflds(options: BfldsOptions = {}): Promise<unknown> {
    if (options.searchSpec !== undefined) {
      return await this.request({
        service: '//blp/apiflds',
        operation: 'FieldSearchRequest',
        searchSpec: String(options.searchSpec),
        backend: options.backend,
        kwargs: mapObjectToPairs(options.kwargs),
        format: options.format,
      });
    }
    const fields: string[] = Array.isArray(options.fields)
      ? (options.fields as string[])
      : typeof options.fields === 'string'
        ? [options.fields]
        : [];
    return await this.request({
      service: '//blp/apiflds',
      operation: 'FieldInfoRequest',
      fieldIds: fields,
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  public async blkp(query: string, options: BlkpOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/instruments',
      operation: 'instrumentListRequest',
      elements: [{ key: 'query', value: String(query) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  public async bport(
    portfolio: string,
    fields: string | readonly string[],
    options: RequestOptions = {},
  ): Promise<unknown> {
    return await this.request({
      service: '//blp/refdata',
      operation: 'PortfolioDataRequest',
      security: String(portfolio),
      fields: Array.isArray(fields) ? fields : [String(fields)],
      backend: options.backend,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  public async bcurves(ticker: string, options: RequestOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/instruments',
      operation: 'curveListRequest',
      elements: [{ key: 'query', value: String(ticker) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  public async bgovts(ticker: string, options: RequestOptions = {}): Promise<unknown> {
    return await this.request({
      service: '//blp/instruments',
      operation: 'govtListRequest',
      elements: [{ key: 'query', value: String(ticker) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  public async resolveFieldTypes(
    fields: readonly string[],
    overrides: OverridesMap | undefined = undefined,
    defaultType = 'string',
  ): Promise<Record<string, string>> {
    const items = await this._inner.resolveFieldTypes(
      fields,
      mapObjectToPairs(overrides),
      defaultType,
    );
    return Object.fromEntries(items.map((item) => [item.key, item.value]));
  }

  public getFieldInfo(field: string): FieldInfo | null {
    return this._inner.getFieldInfo(field);
  }

  public clearFieldCache(): void {
    this._inner.clearFieldCache();
  }

  public saveFieldCache(): void {
    this._inner.saveFieldCache();
  }

  public async validateFields(fields: readonly string[]): Promise<string[]> {
    return await this._inner.validateFields(fields);
  }

  public isFieldValidationEnabled(): boolean {
    return this._inner.isFieldValidationEnabled();
  }

  public async getSchema(service: string): Promise<unknown> {
    const json = await this._inner.getSchema(service);
    return JSON.parse(json) as unknown;
  }

  public async getOperation(service: string, operation: string): Promise<unknown> {
    const json = await this._inner.getOperation(service, operation);
    return JSON.parse(json) as unknown;
  }

  public async listOperations(service: string): Promise<string[]> {
    return await this._inner.listOperations(service);
  }

  public getCachedSchema(service: string): unknown | null {
    const json = this._inner.getCachedSchema(service);
    return json === null ? null : (JSON.parse(json) as unknown);
  }

  public invalidateSchema(service: string): void {
    this._inner.invalidateSchema(service);
  }

  public clearSchemaCache(): void {
    this._inner.clearSchemaCache();
  }

  public listCachedSchemas(): string[] {
    return this._inner.listCachedSchemas();
  }

  public async getEnumValues(
    service: string,
    operation: string,
    element: string,
  ): Promise<string[] | null> {
    return await this._inner.getEnumValues(service, operation, element);
  }

  public async listValidElements(
    service: string,
    operation: string,
  ): Promise<string[] | null> {
    return await this._inner.listValidElements(service, operation);
  }

  public async subscribe(
    tickers: readonly string[],
    fields: readonly string[],
  ): Promise<Subscription> {
    try {
      const stream = await this._inner.subscribe(tickers, fields);
      return new Subscription(stream);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async subscribeWithOptions(
    service: string,
    tickers: readonly string[],
    fields: readonly string[],
    options: readonly string[] | undefined = undefined,
    flushThreshold: number | undefined = undefined,
    overflowPolicy: string | undefined = undefined,
    streamCapacity: number | undefined = undefined,
  ): Promise<Subscription> {
    try {
      const stream = await this._inner.subscribeWithOptions(
        service,
        tickers,
        fields,
        options,
        flushThreshold,
        overflowPolicy,
        streamCapacity,
      );
      return new Subscription(stream);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public signalShutdown(): void {
    this._inner.signalShutdown();
  }

  public isAvailable(): boolean {
    return this._inner.isAvailable();
  }

  public async stream(
    tickers: readonly string[],
    fields: readonly string[],
    options: StreamOptions = {},
  ): Promise<Subscription> {
    return await this.subscribeWithOptions(
      '//blp/mktdata',
      tickers,
      fields,
      options.options,
      options.flushThreshold,
      options.overflowPolicy,
      options.streamCapacity,
    );
  }

  public async vwap(
    tickers: readonly string[],
    fields: readonly string[],
    options: StreamOptions = {},
  ): Promise<Subscription> {
    return await this.subscribeWithOptions(
      '//blp/mktvwap',
      tickers,
      fields,
      options.options,
      options.flushThreshold,
      options.overflowPolicy,
      options.streamCapacity,
    );
  }

  public async mktbar(ticker: string, options: StreamOptions = {}): Promise<Subscription> {
    return await this.subscribeWithOptions(
      '//blp/mktbar',
      [ticker],
      options.fields ?? [],
      options.options,
      options.flushThreshold,
      options.overflowPolicy,
      options.streamCapacity,
    );
  }

  public async depth(ticker: string, options: StreamOptions = {}): Promise<Subscription> {
    return await this.subscribeWithOptions(
      '//blp/mktdepthdata',
      [ticker],
      options.fields ?? [],
      options.options,
      options.flushThreshold,
      options.overflowPolicy,
      options.streamCapacity,
    );
  }

  public async chains(ticker: string, options: StreamOptions = {}): Promise<Subscription> {
    return await this.subscribeWithOptions(
      '//blp/mktlist',
      [ticker],
      options.fields ?? [],
      options.options,
      options.flushThreshold,
      options.overflowPolicy,
      options.streamCapacity,
    );
  }

  public async bops(service: string): Promise<string[]> {
    return await this._inner.listOperations(service);
  }

  public async bschema(service: string, operation?: string): Promise<unknown> {
    if (operation !== undefined) {
      const json = await this._inner.getOperation(service, operation);
      return JSON.parse(json) as unknown;
    }
    const json = await this._inner.getSchema(service);
    return JSON.parse(json) as unknown;
  }

  public async fieldInfo(
    fields: string | readonly string[],
    options: BfldsOptions = {},
  ): Promise<unknown> {
    return await this.bflds({
      fields: Array.isArray(fields) ? (fields as string[]) : [String(fields)],
      ...options,
    });
  }

  public async fieldSearch(
    searchSpec: string,
    options: BfldsOptions = {},
  ): Promise<unknown> {
    return await this.bflds({ searchSpec: String(searchSpec), ...options });
  }

  // ── Recipes ─────────────────────────────────────────────────────────

  public async bqr(ticker: string, options: BqrOptions = {}): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeBqr(
        String(ticker),
        options.startDatetime ?? undefined,
        options.endDatetime ?? undefined,
        options.eventTypes ?? null,
        options.includeBrokerCodes !== false,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async yas(
    tickers: string | readonly string[],
    fields: string | readonly string[],
    options: YasOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeYas(
        toStringArray(tickers),
        toStringArray(fields),
        options.settleDt ?? undefined,
        options.yieldType ?? undefined,
        options.spread ?? undefined,
        options.yieldVal ?? undefined,
        options.price ?? undefined,
        options.benchmark ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async preferreds(
    equityTicker: string,
    options: PreferredsOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipePreferreds(
        String(equityTicker),
        options.fields !== undefined ? toStringArray(options.fields) : null,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async corporateBonds(
    ticker: string,
    options: CorporateBondsOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeCorporateBonds(
        String(ticker),
        options.ccy ?? undefined,
        options.fields !== undefined ? toStringArray(options.fields) : null,
        options.activeOnly !== false,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async futTicker(
    genTicker: string,
    dt: string,
    options: FuturesResolveOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeFutTicker(
        String(genTicker),
        String(dt),
        options.freq ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async activeFutures(
    genTicker: string,
    dt: string,
    options: FuturesResolveOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeActiveFutures(
        String(genTicker),
        String(dt),
        options.freq ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async cdxTicker(
    genTicker: string,
    dt: string,
    options: RecipeBackendOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeCdxTicker(
        String(genTicker),
        String(dt),
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async activeCdx(
    genTicker: string,
    dt: string,
    options: ActiveCdxOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeActiveCdx(
        String(genTicker),
        String(dt),
        options.lookbackDays ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async dividend(
    tickers: string | readonly string[],
    startDate: string,
    endDate: string,
    options: DividendOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeDividend(
        toStringArray(tickers),
        String(startDate),
        String(endDate),
        options.dvdType ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async turnover(
    tickers: string | readonly string[],
    startDate: string,
    endDate: string,
    options: TurnoverOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeTurnover(
        toStringArray(tickers),
        String(startDate),
        String(endDate),
        options.ccy ?? undefined,
        options.factor ?? undefined,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async etfHoldings(
    etfTicker: string,
    options: EtfHoldingsOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeEtfHoldings(
        String(etfTicker),
        options.fields !== undefined ? toStringArray(options.fields) : null,
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }

  public async currencyConversion(
    ticker: string,
    targetCcy: string,
    startDate: string,
    endDate: string,
    options: RecipeBackendOptions = {},
  ): Promise<unknown> {
    try {
      const buffer = await this._inner.recipeCurrencyConversion(
        String(ticker),
        String(targetCcy),
        String(startDate),
        String(endDate),
      );
      return ipcToBackend(buffer, options.backend ?? Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }
}

// ── Top-level wrappers ──────────────────────────────────────────────────

export async function connect(config?: EngineConfig): Promise<Engine> {
  if (config === undefined) {
    return new Engine();
  }
  return Engine.withConfig(config);
}

export function configure(config?: EngineConfig): EngineConfig | undefined;
export function configure(host?: string, port?: number): EngineConfig | undefined;
export function configure(
  configOrHost?: EngineConfig | string,
  port?: number,
): EngineConfig | undefined {
  configuredEngineConfig = normalizeConfigureArgs(configOrHost, port);
  clearConfiguredEngine();
  return configuredEngineConfig;
}

export async function abdp(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  options: BdpOptions = {},
): Promise<unknown> {
  const engine = await getConfiguredEngine();
  return await engine.bdp(toStringArray(tickers), toStringArray(fields), options);
}

export async function bdp(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  options: BdpOptions = {},
): Promise<unknown> {
  return await abdp(tickers, fields, options);
}

export async function abdh(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  start?: string | BdhOptions,
  end?: string,
  options: BdhOptions = {},
): Promise<unknown> {
  const engine = await getConfiguredEngine();
  if (isPlainObject(start) && end === undefined) {
    return await engine.bdh(
      toStringArray(tickers),
      toStringArray(fields),
      start as BdhOptions,
    );
  }
  return await engine.bdh(toStringArray(tickers), toStringArray(fields), {
    ...options,
    start: typeof start === 'string' ? start : undefined,
    end,
  });
}

export async function bdh(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  options: BdhOptions = {},
): Promise<unknown> {
  return await abdh(tickers, fields, options);
}

export async function abds(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  overrides: OverridesMap | undefined = undefined,
  options: BdpOptions = {},
): Promise<unknown> {
  const engine = await getConfiguredEngine();
  const normalizedOptions: BdpOptions = isPlainObject(overrides)
    ? { ...options, overrides: { ...(options.overrides ?? {}), ...overrides } }
    : options;
  return await engine.bds(
    toStringArray(tickers),
    toStringArray(fields),
    normalizedOptions,
  );
}

export async function bds(
  tickers: string | readonly string[],
  fields: string | readonly string[],
  options: BdpOptions = {},
): Promise<unknown> {
  return await abds(tickers, fields, undefined, options);
}

export async function abdib(
  ticker: string,
  dt?: string | BdibOptions,
  interval: number | BdibOptions = 1,
  options: BdibOptions = {},
): Promise<unknown> {
  const engine = await getConfiguredEngine();
  if (
    isPlainObject(dt) &&
    interval === 1 &&
    Object.keys(options).length === 0
  ) {
    return await engine.bdib(String(ticker), dt as BdibOptions);
  }
  const normalizedOptions: BdibOptions = isPlainObject(interval)
    ? { ...(interval as BdibOptions) }
    : { ...options, interval: typeof interval === 'number' ? interval : 1 };
  if (
    normalizedOptions.start === undefined &&
    normalizedOptions.end === undefined
  ) {
    if (dt === undefined || dt === null) {
      throw new TypeError('abdib requires dt or explicit start/end options');
    }
    const range = fullDayRange(typeof dt === 'string' ? dt : '');
    normalizedOptions.start = range.start;
    normalizedOptions.end = range.end;
  }
  return await engine.bdib(String(ticker), normalizedOptions);
}

export async function bdib(ticker: string, options: BdibOptions = {}): Promise<unknown> {
  return await abdib(ticker, options);
}

export async function abdtick(
  ticker: string,
  start: string,
  end: string,
  options: BdtickOptions = {},
): Promise<unknown> {
  if (start === undefined || start === null || end === undefined || end === null) {
    throw new TypeError('abdtick requires both start and end datetimes');
  }
  const engine = await getConfiguredEngine();
  return await engine.bdtick(String(ticker), { ...options, start, end });
}

export async function bdtick(ticker: string, options: BdtickOptions = {}): Promise<unknown> {
  const engine = await getConfiguredEngine();
  return await engine.bdtick(String(ticker), options);
}

export async function asubscribe(
  tickers: string | readonly string[],
  fields: string | readonly string[],
): Promise<Subscription> {
  const engine = await getConfiguredEngine();
  return await engine.subscribe(toStringArray(tickers), toStringArray(fields));
}

export async function subscribe(
  tickers: string | readonly string[],
  fields: string | readonly string[],
): Promise<Subscription> {
  return await asubscribe(tickers, fields);
}

async function acdxInfo(ticker: string, options: BdpOptions = {}): Promise<unknown> {
  const engine = await getConfiguredEngine();
  return await engine.bdp([String(ticker)], [...CDX_INFO_FIELDS], options);
}

async function acdxPricing(ticker: string, options: CdxOptions = {}): Promise<unknown> {
  const engine = await getConfiguredEngine();
  return await engine.bdp(
    [String(ticker)],
    [...CDX_PRICING_FIELDS],
    normalizeRecoveryOptions(options),
  );
}

async function acdxRisk(ticker: string, options: CdxOptions = {}): Promise<unknown> {
  const engine = await getConfiguredEngine();
  return await engine.bdp(
    [String(ticker)],
    [...CDX_RISK_FIELDS],
    normalizeRecoveryOptions(options),
  );
}

export const blp = Object.freeze({
  bdp,
  bdh,
  bds,
  bdib,
  bdtick,
  subscribe,
  abdp,
  abdh,
  abds,
  abdib,
  abdtick,
  asubscribe,
});

export const ext = Object.freeze({
  cdx: Object.freeze({
    acdx_info: acdxInfo,
    acdx_pricing: acdxPricing,
    acdx_risk: acdxRisk,
  }),

  parseDate: native.extParseDate,
  fmtDate: native.extFmtDate,

  pivotToWide: native.extPivotToWide,
  isLongFormat: native.extIsLongFormat,

  parseTicker: native.extParseTicker,
  isSpecificContract: native.extIsSpecificContract,
  buildFuturesTicker: native.extBuildFuturesTicker,
  normalizeTickers: native.extNormalizeTickers,
  filterEquityTickers: native.extFilterEquityTickers,

  generateFuturesCandidates: native.extGenerateFuturesCandidates,
  validateGenericTicker: native.extValidateGenericTicker,
  contractIndex: native.extContractIndex,
  filterCandidatesByCycle: native.extFilterCandidatesByCycle,
  filterValidContracts: native.extFilterValidContracts,

  parseCdxTicker: native.extParseCdxTicker,
  previousCdxSeries: native.extPreviousCdxSeries,
  cdxGenToSpecific: native.extCdxGenToSpecific,

  buildFxPair: native.extBuildFxPair,
  sameCurrency: native.extSameCurrency,
  currenciesNeedingConversion: native.extCurrenciesNeedingConversion,

  renameDividendColumns: native.extRenameDividendColumns,
  renameEtfColumns: native.extRenameEtfColumns,

  getMonthCode: native.extGetMonthCode,
  getMonthName: native.extGetMonthName,
  getFuturesMonths: native.extGetFuturesMonths,
  getDvdType: native.extGetDvdType,
  getDvdTypes: native.extGetDvdTypes,
  getDvdCols: native.extGetDvdCols,
  getEtfCols: native.extGetEtfCols,

  buildYasOverrides: native.extBuildYasOverrides,

  buildEarningHeaderRename: native.extBuildEarningHeaderRename,
  calculateLevelPercentages: native.extCalculateLevelPercentages,

  buildPreferredsQuery: native.extBuildPreferredsQuery,
  buildCorporateBondsQuery: native.extBuildCorporateBondsQuery,
  buildEtfHoldingsQuery: native.extBuildEtfHoldingsQuery,

  defaultTurnoverDates: native.extDefaultTurnoverDates,
  defaultBqrDatetimes: native.extDefaultBqrDatetimes,

  deriveSessions: native.extDeriveSessions,
  getMarketRule: native.extGetMarketRule,
  inferTimezone: native.extInferTimezone,
  setExchangeOverride: native.extSetExchangeOverride,
  getExchangeOverride: native.extGetExchangeOverride,
  clearExchangeOverride: native.extClearExchangeOverride,
  listExchangeOverrides: native.extListExchangeOverrides,
  sessionTimesToUtc: native.extSessionTimesToUtc,
});

export function version(): string {
  return packageJson.version;
}

export const setLogLevel = native.setLogLevel;
export const getLogLevel = native.getLogLevel;

export {
  BlpError,
  BlpSessionError,
  BlpRequestError,
  BlpValidationError,
  BlpTimeoutError,
  BlpInternalError,
  wrapError,
};

export type {
  ActiveCdxOptions,
  AuthConfig,
  BackendKind,
  BdhOptions,
  BdibOptions,
  BdpOptions,
  BdtickOptions,
  BeqsOptions,
  BfldsOptions,
  BlkpOptions,
  BqlOptions,
  BqrOptions,
  BsrchOptions,
  BtaOptions,
  CdxOptions,
  CdxTickerInfo,
  CorporateBondsOptions,
  DividendOptions,
  EngineConfig,
  EtfHoldingsOptions,
  ExchangeInfoResult,
  ExchangeOverrideInput,
  FieldInfo,
  FormatKind,
  FuturesCandidate,
  FuturesResolveOptions,
  FxPairInfo,
  MarketRule,
  OverridesMap,
  PreferredsOptions,
  PrimitiveValue,
  RecipeBackendOptions,
  RequestInput,
  RequestOptions,
  ServerAddress,
  SessionWindowsInfo,
  Socks5Config,
  StreamOptions,
  StringPair,
  SubscriptionStats,
  TickerParts,
  TimeRange,
  TlsConfig,
  TurnoverOptions,
  YasOptions,
};
