import type * as xbbg from "@xbbg/core";

import type { XbbgCoreLike, XbbgEngineLike } from "./core-loader";

export const BLOOMBERG_TOOL_NAMES = [
  "xbbg_bdp",
  "xbbg_bdh",
  "xbbg_bds",
  "xbbg_bdib",
  "xbbg_bql",
  "xbbg_bsrch",
  "xbbg_bflds",
  "xbbg_ext_ticker",
  "xbbg_ext_futures",
  "xbbg_ext_cdx",
  "xbbg_ext_currency",
  "xbbg_ext_bql_builder",
  "xbbg_ext_market_session",
  "xbbg_ext_yas_overrides",
  "xbbg_ext_constants",
  "xbbg_ext_columns",
  "xbbg_ext_calculate",
] as const;

export type BloombergToolName = (typeof BLOOMBERG_TOOL_NAMES)[number];

export interface BloombergToolsOptions {
  readonly engine?: XbbgEngineLike;
  readonly engineConfig?: xbbg.EngineConfig;
  readonly core?: XbbgCoreLike;
  readonly maxSecurities?: number;
  readonly maxFields?: number;
  readonly maxRows?: number;
  readonly maxStringChars?: number;
  readonly maxBqlQueryChars?: number;
  readonly maxSearchSpecChars?: number;
  readonly validateFields?: boolean;
  readonly disabledTools?: readonly BloombergToolName[];
}

export interface NormalizedBloombergToolsOptions {
  readonly engine?: XbbgEngineLike;
  readonly engineConfig?: xbbg.EngineConfig;
  readonly core?: XbbgCoreLike;
  readonly maxSecurities: number;
  readonly maxFields: number;
  readonly maxRows: number;
  readonly maxStringChars: number;
  readonly maxBqlQueryChars: number;
  readonly maxSearchSpecChars: number;
  readonly validateFields: boolean | undefined;
  readonly disabledTools: ReadonlySet<BloombergToolName>;
}

const DEFAULT_MAX_SECURITIES = 25;
const DEFAULT_MAX_FIELDS = 25;
const DEFAULT_MAX_ROWS = 500;
const DEFAULT_MAX_STRING_CHARS = 2000;
const DEFAULT_MAX_BQL_QUERY_CHARS = 4000;
const DEFAULT_MAX_SEARCH_SPEC_CHARS = 1000;

function positiveInteger(value: number | undefined, fallback: number, name: string): number {
  if (value === undefined) {
    return fallback;
  }
  if (!Number.isInteger(value) || value <= 0) {
    throw new RangeError(`${name} must be a positive integer; got ${String(value)}`);
  }
  return value;
}

function disabledToolSet(
  tools: readonly BloombergToolName[] | undefined,
): ReadonlySet<BloombergToolName> {
  return new Set(tools ?? []);
}

export function normalizeBloombergToolsOptions(
  options: BloombergToolsOptions = {},
): NormalizedBloombergToolsOptions {
  return {
    core: options.core,
    disabledTools: disabledToolSet(options.disabledTools),
    engine: options.engine,
    engineConfig: options.engineConfig,
    maxBqlQueryChars: positiveInteger(
      options.maxBqlQueryChars,
      DEFAULT_MAX_BQL_QUERY_CHARS,
      "maxBqlQueryChars",
    ),
    maxFields: positiveInteger(options.maxFields, DEFAULT_MAX_FIELDS, "maxFields"),
    maxRows: positiveInteger(options.maxRows, DEFAULT_MAX_ROWS, "maxRows"),
    maxSearchSpecChars: positiveInteger(
      options.maxSearchSpecChars,
      DEFAULT_MAX_SEARCH_SPEC_CHARS,
      "maxSearchSpecChars",
    ),
    maxSecurities: positiveInteger(options.maxSecurities, DEFAULT_MAX_SECURITIES, "maxSecurities"),
    maxStringChars: positiveInteger(
      options.maxStringChars,
      DEFAULT_MAX_STRING_CHARS,
      "maxStringChars",
    ),
    validateFields: options.validateFields,
  };
}

export function isToolDisabled(
  options: NormalizedBloombergToolsOptions,
  name: BloombergToolName,
): boolean {
  return options.disabledTools.has(name);
}
