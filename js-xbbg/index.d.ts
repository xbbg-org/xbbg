/// <reference types="node" />

import type { Table } from 'apache-arrow';

export interface StringPair {
  key: string;
  value: string;
}

export interface EngineConfig {
  host?: string;
  port?: number;
  requestPoolSize?: number;
  subscriptionPoolSize?: number;
  validationMode?: string;
  subscriptionFlushThreshold?: number;
  maxEventQueueSize?: number;
  commandQueueSize?: number;
  subscriptionStreamCapacity?: number;
  overflowPolicy?: string;
  warmupServices?: string[];
}

export interface RequestInput {
  service: string;
  operation: string;
  requestOperation?: string;
  requestId?: string;
  extractor?: string;
  securities?: string[];
  security?: string;
  fields?: string[];
  overrides?: StringPair[];
  elements?: StringPair[];
  kwargs?: StringPair[];
  jsonElements?: string;
  startDate?: string;
  endDate?: string;
  startDatetime?: string;
  endDatetime?: string;
  requestTz?: string;
  outputTz?: string;
  eventType?: string;
  eventTypes?: string[];
  interval?: number;
  options?: StringPair[];
  fieldTypes?: StringPair[];
  includeSecurityErrors?: boolean;
  validateFields?: boolean;
  searchSpec?: string;
  fieldIds?: string[];
  format?: string;
}

export interface SubscriptionStats {
  messagesReceived: number;
  droppedBatches: number;
  batchesSent: number;
  slowConsumer: boolean;
}

export interface FieldInfo {
  fieldId: string;
  arrowType: string;
  description: string;
  category: string;
}

export interface BdpOptions {
  overrides?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  includeSecurityErrors?: boolean;
}

export interface BdhOptions {
  start?: string;
  end?: string;
  overrides?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
}

export interface BdibOptions {
  start?: string;
  end?: string;
  eventType?: string;
  interval?: number;
  kwargs?: Record<string, string | number | boolean>;
}

export interface BdtickOptions {
  start?: string;
  end?: string;
  eventTypes?: string[];
  kwargs?: Record<string, string | number | boolean>;
}

export interface CdxOptions extends BdpOptions {
  recoveryRate?: number;
  recovery_rate?: number;
}

export class BlpError extends Error {
  readonly name: string;
}
export class BlpSessionError extends BlpError {}
export class BlpRequestError extends BlpError {
  readonly service?: string;
  readonly operation?: string;
  readonly request_id?: string;
  readonly code?: string;
}
export class BlpValidationError extends BlpError {
  readonly element?: string;
  readonly suggestion?: string;
}
export class BlpTimeoutError extends BlpError {}
export class BlpInternalError extends BlpError {}
export function wrapError(napiError: Error): BlpError;

export declare const Backend: Readonly<{
  ARROW: 'arrow';
  JSON: 'json';
  POLARS: 'polars';
}>;
export declare const Format: Readonly<{
  LONG: 'long';
  LONG_TYPED: 'long_typed';
  LONG_WITH_METADATA: 'long_with_metadata';
  SEMI_LONG: 'semi_long';
}>;

export interface BqlOptions {
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface BeqsOptions {
  asof?: string;
  screenType?: string;
  group?: string;
  overrides?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface BsrchOptions {
  overrides?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface BtaOptions {
  studyParams?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  startDate?: string;
  endDate?: string;
  periodicity?: string;
  interval?: number;
  format?: string;
  backend?: string;
}
export interface BfldsOptions {
  fields?: string | string[];
  searchSpec?: string;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface BlkpOptions {
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface BqrOptions {
  startDatetime?: string;
  endDatetime?: string;
  eventTypes?: string[];
  includeBrokerCodes?: boolean;
  backend?: string;
}
export interface RequestOptions {
  overrides?: Record<string, string | number | boolean>;
  kwargs?: Record<string, string | number | boolean>;
  format?: string;
  backend?: string;
}
export interface StreamOptions {
  options?: string[];
  flushThreshold?: number;
  overflowPolicy?: string;
  streamCapacity?: number;
}

export class Subscription implements AsyncIterator<Table> {
  next(): Promise<IteratorResult<Table>>;
  add(tickers: string[]): Promise<void>;
  remove(tickers: string[]): Promise<void>;
  unsubscribe(drain?: boolean): Promise<Table[]>;
  readonly tickers: string[];
  readonly fields: string[];
  readonly isActive: boolean;
  readonly stats: SubscriptionStats;
  [Symbol.asyncIterator](): AsyncIterator<Table>;
}

export class Engine {
  constructor(host?: string, port?: number);
  static withConfig(config?: EngineConfig): Engine;
  request(params: RequestInput): Promise<Table>;
  requestRaw(params: RequestInput): Promise<Buffer>;
  bdp(
    tickers: string[],
    fields: string[],
    options?: BdpOptions,
  ): Promise<Table>;
  bds(
    tickers: string[],
    fields: string[],
    options?: BdpOptions,
  ): Promise<Table>;
  bdh(
    tickers: string[],
    fields: string[],
    options?: BdhOptions,
  ): Promise<Table>;
  bdib(ticker: string, options?: BdibOptions): Promise<Table>;
  bdtick(ticker: string, options?: BdtickOptions): Promise<Table>;
  resolveFieldTypes(
    fields: string[],
    overrides?: Record<string, string | number | boolean>,
    defaultType?: string,
  ): Promise<Record<string, string>>;
  getFieldInfo(field: string): FieldInfo | null;
  clearFieldCache(): void;
  saveFieldCache(): void;
  validateFields(fields: string[]): Promise<string[]>;
  isFieldValidationEnabled(): boolean;
  getSchema(service: string): Promise<unknown>;
  getOperation(service: string, operation: string): Promise<unknown>;
  listOperations(service: string): Promise<string[]>;
  getCachedSchema(service: string): unknown | null;
  invalidateSchema(service: string): void;
  clearSchemaCache(): void;
  listCachedSchemas(): string[];
  getEnumValues(
    service: string,
    operation: string,
    element: string,
  ): Promise<string[] | null>;
  listValidElements(
    service: string,
    operation: string,
  ): Promise<string[] | null>;
  subscribe(tickers: string[], fields: string[]): Promise<Subscription>;
  subscribeWithOptions(
    service: string,
    tickers: string[],
    fields: string[],
    options?: string[],
    flushThreshold?: number,
    overflowPolicy?: string,
    streamCapacity?: number,
  ): Promise<Subscription>;
  signalShutdown(): void;
  isAvailable(): boolean;
  bql(query: string, options?: BqlOptions): Promise<Table>;
  beqs(screen: string, options?: BeqsOptions): Promise<Table>;
  bsrch(searchSpec: string, options?: BsrchOptions): Promise<Table>;
  bta(
    ticker: string,
    study: string | Record<string, unknown>,
    options?: BtaOptions,
  ): Promise<Table>;
  bflds(options: BfldsOptions): Promise<Table>;
  blkp(query: string, options?: BlkpOptions): Promise<Table>;
  bport(
    portfolio: string,
    fields: string | string[],
    options?: RequestOptions,
  ): Promise<Table>;
  bcurves(ticker: string, options?: RequestOptions): Promise<Table>;
  bgovts(ticker: string, options?: RequestOptions): Promise<Table>;
  stream(
    tickers: string[],
    fields: string[],
    options?: StreamOptions,
  ): Promise<Subscription>;
  vwap(
    tickers: string[],
    fields: string[],
    options?: StreamOptions,
  ): Promise<Subscription>;
  mktbar(ticker: string, options?: StreamOptions): Promise<Subscription>;
  depth(ticker: string, options?: StreamOptions): Promise<Subscription>;
  chains(ticker: string, options?: StreamOptions): Promise<Subscription>;
  bops(service: string): Promise<string[]>;
  bschema(service: string, operation?: string): Promise<unknown>;
  fieldInfo(fields: string | string[], options?: BfldsOptions): Promise<Table>;
  fieldSearch(searchSpec: string, options?: BfldsOptions): Promise<Table>;
  bqr(ticker: string, options?: BqrOptions): Promise<Table>;
}

export interface BlpNamespace {
  bdp(
    tickers: string | string[],
    fields: string | string[],
    options?: BdpOptions,
  ): Promise<Table>;
  bdh(
    tickers: string | string[],
    fields: string | string[],
    options?: BdhOptions,
  ): Promise<Table>;
  bds(
    tickers: string | string[],
    fields: string | string[],
    options?: BdpOptions,
  ): Promise<Table>;
  bdib(ticker: string, options?: BdibOptions): Promise<Table>;
  bdtick(ticker: string, options?: BdtickOptions): Promise<Table>;
  subscribe(
    tickers: string | string[],
    fields: string | string[],
  ): Promise<Subscription>;
  abdp(
    tickers: string | string[],
    fields: string | string[],
    options?: BdpOptions,
  ): Promise<Table>;
  abdh(
    tickers: string | string[],
    fields: string | string[],
    start?: string,
    end?: string,
    options?: BdhOptions,
  ): Promise<Table>;
  abds(
    tickers: string | string[],
    fields: string | string[],
    overrides?: Record<string, string | number | boolean>,
    options?: BdpOptions,
  ): Promise<Table>;
  abdib(
    ticker: string,
    dt?: string,
    interval?: number,
    options?: BdibOptions,
  ): Promise<Table>;
  abdtick(
    ticker: string,
    start: string,
    end: string,
    options?: BdtickOptions,
  ): Promise<Table>;
  asubscribe(
    tickers: string | string[],
    fields: string | string[],
  ): Promise<Subscription>;
}

export interface CdxNamespace {
  acdx_info(ticker: string, options?: BdpOptions): Promise<Table>;
  acdx_pricing(ticker: string, options?: CdxOptions): Promise<Table>;
  acdx_risk(ticker: string, options?: CdxOptions): Promise<Table>;
}

export interface ExtNamespace {
  cdx: CdxNamespace;
}

export function connect(config?: EngineConfig): Promise<Engine>;
export function configure(config?: EngineConfig): EngineConfig | undefined;
export function configure(
  host?: string,
  port?: number,
): EngineConfig | undefined;
export function bdp(
  tickers: string | string[],
  fields: string | string[],
  options?: BdpOptions,
): Promise<Table>;
export function bdh(
  tickers: string | string[],
  fields: string | string[],
  options?: BdhOptions,
): Promise<Table>;
export function bds(
  tickers: string | string[],
  fields: string | string[],
  options?: BdpOptions,
): Promise<Table>;
export function bdib(ticker: string, options?: BdibOptions): Promise<Table>;
export function bdtick(ticker: string, options?: BdtickOptions): Promise<Table>;
export function subscribe(
  tickers: string | string[],
  fields: string | string[],
): Promise<Subscription>;
export function abdp(
  tickers: string | string[],
  fields: string | string[],
  options?: BdpOptions,
): Promise<Table>;
export function abdh(
  tickers: string | string[],
  fields: string | string[],
  start?: string,
  end?: string,
  options?: BdhOptions,
): Promise<Table>;
export function abds(
  tickers: string | string[],
  fields: string | string[],
  overrides?: Record<string, string | number | boolean>,
  options?: BdpOptions,
): Promise<Table>;
export function abdib(
  ticker: string,
  dt?: string,
  interval?: number,
  options?: BdibOptions,
): Promise<Table>;
export function abdtick(
  ticker: string,
  start: string,
  end: string,
  options?: BdtickOptions,
): Promise<Table>;
export function asubscribe(
  tickers: string | string[],
  fields: string | string[],
): Promise<Subscription>;
export const blp: BlpNamespace;
export const ext: ExtNamespace;
export function version(): string;
export function setLogLevel(level: string): void;
export function getLogLevel(): string;
