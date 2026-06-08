import * as z from "zod/v3";

import type { NormalizedBloombergToolsOptions } from "./options";
type ZodOutput<T> = z.ZodType<T, z.ZodTypeDef, unknown>;

export type PrimitiveValue = string | number | boolean;
export type PrimitiveMap = Record<string, PrimitiveValue>;

export const REFERENCE_FORMATS = ["long", "long_typed", "long_metadata"] as const;
export const HISTORICAL_FORMATS = [
  "long",
  "long_typed",
  "long_metadata",
  "semi_long",
  "wide",
] as const;

export type ReferenceFormat = (typeof REFERENCE_FORMATS)[number];
export type HistoricalFormat = (typeof HISTORICAL_FORMATS)[number];

export interface ReferenceCallOptions {
  readonly overrides?: PrimitiveMap;
  readonly kwargs?: PrimitiveMap;
  readonly format?: ReferenceFormat;
  readonly validateFields?: boolean;
}

export interface BdpInput extends ReferenceCallOptions {
  readonly securities: readonly string[];
  readonly fields: readonly string[];
  readonly includeSecurityErrors?: boolean;
}

export interface BdsInput extends ReferenceCallOptions {
  readonly securities: readonly string[];
  readonly field: string;
}

export interface BdhInput {
  readonly securities: readonly string[];
  readonly fields: readonly string[];
  readonly start: string;
  readonly end: string;
  readonly overrides?: PrimitiveMap;
  readonly kwargs?: PrimitiveMap;
  readonly format?: HistoricalFormat;
  readonly validateFields?: boolean;
}

export interface BdibInput {
  readonly ticker: string;
  readonly start: string;
  readonly end: string;
  readonly interval: number;
  readonly eventType?: string;
  readonly requestTz?: string;
  readonly outputTz?: string;
  readonly kwargs?: PrimitiveMap;
}

export interface BdtickInput {
  readonly ticker: string;
  readonly start: string;
  readonly end: string;
  readonly eventTypes?: readonly string[];
  readonly includeConditionCodes?: boolean;
  readonly includeExchangeCodes?: boolean;
  readonly includeBrokerCodes?: boolean;
  readonly includeRpsCodes?: boolean;
  readonly includeBicMicCodes?: boolean;
  readonly includeNonPlottableEvents?: boolean;
  readonly includeBloombergStandardConditionCodes?: boolean;
  readonly requestTz?: string;
  readonly outputTz?: string;
  readonly kwargs?: PrimitiveMap;
}

export interface BqlInput {
  readonly query: string;
  readonly kwargs?: PrimitiveMap;
  readonly format?: ReferenceFormat;
}

export interface BsrchInput {
  readonly searchSpec: string;
  readonly overrides?: PrimitiveMap;
  readonly kwargs?: PrimitiveMap;
  readonly format?: ReferenceFormat;
}

export interface BqrInput {
  readonly ticker: string;
  readonly start: string;
  readonly end: string;
  readonly eventTypes?: readonly string[];
  readonly includeBrokerCodes?: boolean;
}

export interface BfldsInput {
  readonly fields?: readonly string[];
  readonly searchSpec?: string;
  readonly kwargs?: PrimitiveMap;
  readonly format?: ReferenceFormat;
}

export interface BeqsInput {
  readonly screen: string;
  readonly asof?: string;
  readonly screenType?: string;
  readonly group?: string;
  readonly overrides?: PrimitiveMap;
  readonly kwargs?: PrimitiveMap;
  readonly format?: ReferenceFormat;
}

export interface YasInput {
  readonly tickers: readonly string[];
  readonly fields: readonly string[];
  readonly settleDt?: string;
  readonly yieldType?: number;
  readonly spread?: number;
  readonly yieldVal?: number;
  readonly price?: number;
  readonly benchmark?: string;
}

export interface PreferredsInput {
  readonly equityTicker: string;
  readonly fields?: readonly string[];
}

export interface CorporateBondsInput {
  readonly ticker: string;
  readonly ccy?: string;
  readonly fields?: readonly string[];
  readonly activeOnly?: boolean;
}

export interface IndexMembersInput {
  readonly index: string;
  readonly field?: "INDX_MWEIGHT" | "INDX_MEMBERS" | "INDX_MEMBERS3";
  readonly asof?: string;
}

export interface ResolveIsinsInput {
  readonly isins: readonly string[];
}

export interface IssuerIsinsInput {
  readonly bondIsins: readonly string[];
}

export interface EtfHoldingsInput {
  readonly etfTicker: string;
  readonly fields?: readonly string[];
}

export interface StreamSnapshotInput {
  readonly tickers: readonly string[];
  readonly fields: readonly string[];
  readonly maxUpdates: number;
  readonly timeoutMs: number;
  readonly drain?: boolean;
  readonly options?: readonly string[];
  readonly conflate?: boolean;
  readonly flushThreshold?: number;
  readonly overflowPolicy?: string;
  readonly streamCapacity?: number;
  readonly allFields?: boolean;
}

export interface MktbarSnapshotInput {
  readonly ticker: string;
  readonly fields?: readonly string[];
  readonly maxUpdates: number;
  readonly timeoutMs: number;
  readonly drain?: boolean;
  readonly options?: readonly string[];
  readonly conflate?: boolean;
  readonly flushThreshold?: number;
  readonly overflowPolicy?: string;
  readonly streamCapacity?: number;
  readonly allFields?: boolean;
}

export interface DepthSnapshotInput {
  readonly ticker: string;
  readonly fields?: readonly string[];
  readonly maxUpdates: number;
  readonly timeoutMs: number;
  readonly drain?: boolean;
  readonly options?: readonly string[];
  readonly conflate?: boolean;
  readonly flushThreshold?: number;
  readonly overflowPolicy?: string;
  readonly streamCapacity?: number;
  readonly allFields?: boolean;
}

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/u;
const BBG_DATE_RE = /^\d{8}$/u;
const AMBIGUOUS_DATE_RE = /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}([T \D]|$)/u;
const ISO_DATE_TIME_RE =
  /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/u;

const primitiveSchema = z.union([
  z.string().transform((value) => value.trim()),
  z.number(),
  z.boolean(),
]);

function dateFromParts(year: string, month: string, day: string): string {
  const formatted = `${year}${month}${day}`;
  const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getUTCFullYear() !== Number(year) ||
    parsed.getUTCMonth() + 1 !== Number(month) ||
    parsed.getUTCDate() !== Number(day)
  ) {
    throw new TypeError(`Invalid date ${formatted}; expected a real calendar date like 2024-01-31`);
  }
  return formatted;
}

function dateToBbg(value: Date | number): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new TypeError("Invalid date value; expected YYYY-MM-DD, YYYYMMDD, Date, or epoch ms");
  }
  const year = String(date.getUTCFullYear()).padStart(4, "0");
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function normalizeDate(value: string | Date | number): string {
  if (value instanceof Date || typeof value === "number") {
    return dateToBbg(value);
  }
  const text = value.trim();
  if (text.length === 0) {
    throw new TypeError("Date must be non-empty; use YYYY-MM-DD or YYYYMMDD");
  }
  if (AMBIGUOUS_DATE_RE.test(text)) {
    throw new TypeError(`Ambiguous date ${JSON.stringify(text)}; use YYYY-MM-DD or YYYYMMDD`);
  }
  if (BBG_DATE_RE.test(text)) {
    return dateFromParts(text.slice(0, 4), text.slice(4, 6), text.slice(6, 8));
  }
  if (ISO_DATE_RE.test(text)) {
    return dateFromParts(text.slice(0, 4), text.slice(5, 7), text.slice(8, 10));
  }
  throw new TypeError(`Invalid date ${JSON.stringify(text)}; use YYYY-MM-DD or YYYYMMDD`);
}

function normalizeDateTime(value: string | Date | number): string {
  if (value instanceof Date || typeof value === "number") {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) {
      throw new TypeError("Invalid datetime value; expected ISO 8601 datetime, Date, or epoch ms");
    }
    return date.toISOString();
  }
  const text = value.trim();
  if (text.length === 0) {
    throw new TypeError("Datetime must be non-empty; use an ISO 8601 datetime");
  }
  if (AMBIGUOUS_DATE_RE.test(text)) {
    throw new TypeError(`Ambiguous datetime ${JSON.stringify(text)}; use ISO 8601`);
  }
  if (BBG_DATE_RE.test(text) || ISO_DATE_RE.test(text)) {
    throw new TypeError(
      `Invalid datetime ${JSON.stringify(text)}; include an explicit time component such as YYYY-MM-DDT09:30:00`,
    );
  }
  if (!ISO_DATE_TIME_RE.test(text)) {
    throw new TypeError(`Invalid datetime ${JSON.stringify(text)}; use ISO 8601`);
  }
  return text.replace(" ", "T");
}

function nonEmptyString(
  tool: string,
  field: string,
  maxChars: number,
  example: string,
): ZodOutput<string> {
  return z
    .string()
    .transform((value) => value.trim())
    .pipe(
      z
        .string()
        .min(1, `${tool}: ${field} must be a non-empty string. Example: ${example}`)
        .max(
          maxChars,
          `${tool}: ${field} is too long; expected at most ${maxChars} characters. Example: ${example}`,
        ),
    );
}

function stringArray(
  tool: string,
  field: string,
  maxItems: number,
  maxChars: number,
  example: string,
): ZodOutput<string[]> {
  return z
    .array(nonEmptyString(tool, field, maxChars, example))
    .min(1, `${tool}: ${field} must contain at least one non-empty string. Example: ${example}`)
    .max(maxItems, `${tool}: ${field} can contain at most ${maxItems} values`);
}

function primitiveMap(tool: string, field: string): ZodOutput<PrimitiveMap | undefined> {
  return z
    .record(z.string().min(1), primitiveSchema)
    .optional()
    .transform((value) => {
      if (value === undefined) {
        return undefined;
      }
      const normalized: PrimitiveMap = {};
      for (const [key, entry] of Object.entries(value)) {
        const normalizedKey = key.trim();
        if (normalizedKey.length === 0) {
          throw new TypeError(`${tool}: ${field} contains an empty key`);
        }
        if (typeof entry === "string" && entry.length === 0) {
          throw new TypeError(`${tool}: ${field}.${normalizedKey} must not be an empty string`);
        }
        normalized[normalizedKey] = entry;
      }
      return normalized;
    });
}

function dateField(tool: string, field: string): ZodOutput<string> {
  return z
    .union([z.string(), z.date(), z.number()])
    .transform((value) => normalizeDate(value))
    .describe(
      `${field} date. Use YYYY-MM-DD or Bloomberg-native YYYYMMDD, never ambiguous MM/DD/YYYY.`,
    );
}

function dateTimeField(tool: string, field: string): ZodOutput<string> {
  return z
    .union([z.string(), z.date(), z.number()])
    .superRefine((value, context) => {
      if (typeof value !== "string") {
        return;
      }
      const text = value.trim();
      if (BBG_DATE_RE.test(text) || ISO_DATE_RE.test(text)) {
        context.addIssue({
          code: "custom",
          message: `${tool}: ${field} datetime requires an explicit time component; use ISO 8601 such as YYYY-MM-DDT09:30:00`,
        });
      }
    })
    .transform((value) => normalizeDateTime(value))
    .describe(`${field} datetime. Use ISO 8601 with an explicit time component.`);
}

function referenceFormat(tool: string): ZodOutput<ReferenceFormat | undefined> {
  return z
    .enum(REFERENCE_FORMATS, {
      errorMap: () => ({
        message: `${tool}: format must be one of ${REFERENCE_FORMATS.join(", ")}`,
      }),
    })
    .optional();
}

function historicalFormat(tool: string): ZodOutput<HistoricalFormat | undefined> {
  return z
    .enum(HISTORICAL_FORMATS, {
      errorMap: () => ({
        message: `${tool}: format must be one of ${HISTORICAL_FORMATS.join(", ")}`,
      }),
    })
    .optional();
}

export function createBdpSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BdpInput> {
  const tool = "xbbg_bdp";
  return z.object({
    fields: stringArray(
      tool,
      "fields",
      options.maxFields,
      options.maxStringChars,
      '["<FIELD>"]',
    ).describe("Bloomberg field mnemonics to retrieve. Use xbbg_bflds first if uncertain."),
    format: referenceFormat(tool).describe(
      "JSON output shape. Usually omit; use long_typed if downstream needs Bloomberg value types.",
    ),
    includeSecurityErrors: z
      .boolean()
      .optional()
      .describe("Include Bloomberg security errors in the response when supported."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    overrides: primitiveMap(tool, "overrides").describe(
      "Bloomberg field overrides as flat string/number/boolean values only.",
    ),
    securities: stringArray(
      tool,
      "securities",
      options.maxSecurities,
      options.maxStringChars,
      '["<TICKER> <MARKET_SECTOR>"]',
    ).describe(
      "Fully qualified Bloomberg securities supplied by the user; use /isin/<ISIN> for ISINs and /cusip/<CUSIP> for CUSIPs. Do not invent tickers.",
    ),
    validateFields: z.boolean().optional().describe("Override field validation for this request."),
  });
}

export function createBdhSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BdhInput> {
  const tool = "xbbg_bdh";
  return z
    .object({
      end: dateField(tool, "end").describe("Required end date. Use YYYY-MM-DD or YYYYMMDD."),
      fields: stringArray(
        tool,
        "fields",
        options.maxFields,
        options.maxStringChars,
        '["<FIELD>"]',
      ).describe("Bloomberg historical field mnemonics supplied by the user."),
      format: historicalFormat(tool).describe(
        "Historical JSON output shape. Use wide only when the user asks for a table by date.",
      ),
      kwargs: primitiveMap(tool, "kwargs").describe(
        "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
      ),
      overrides: primitiveMap(tool, "overrides").describe(
        "Bloomberg overrides as flat string/number/boolean values only.",
      ),
      securities: stringArray(
        tool,
        "securities",
        options.maxSecurities,
        options.maxStringChars,
        '["<TICKER> <MARKET_SECTOR>"]',
      ).describe(
        "Fully qualified Bloomberg securities supplied by the user; use /isin/<ISIN> for ISINs and /cusip/<CUSIP> for CUSIPs.",
      ),
      start: dateField(tool, "start").describe("Required start date. Use YYYY-MM-DD or YYYYMMDD."),
      validateFields: z
        .boolean()
        .optional()
        .describe("Override field validation for this request."),
    })
    .superRefine((value, ctx) => {
      if (value.start > value.end) {
        ctx.addIssue({
          code: "custom",
          message: `${tool}: start must be on or before end. Use an explicit start/end date range.`,
          path: ["start"],
        });
      }
    });
}

export function createBdsSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BdsInput> {
  const tool = "xbbg_bds";
  return z.object({
    field: nonEmptyString(tool, "field", options.maxStringChars, "<BULK_FIELD>").describe(
      "Exactly one Bloomberg bulk/table field supplied by the user.",
    ),
    format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    overrides: primitiveMap(tool, "overrides").describe(
      "Bloomberg overrides as flat string/number/boolean values only.",
    ),
    securities: stringArray(
      tool,
      "securities",
      options.maxSecurities,
      options.maxStringChars,
      '["<INDEX_TICKER> <MARKET_SECTOR>"]',
    ).describe(
      "Fully qualified Bloomberg securities supplied by the user; use /isin/<ISIN> for ISINs and /cusip/<CUSIP> for CUSIPs.",
    ),
    validateFields: z.boolean().optional().describe("Override field validation for this request."),
  });
}

export function createBdibSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BdibInput> {
  const tool = "xbbg_bdib";
  return z.object({
    end: dateTimeField(tool, "end").describe(
      "Required intraday end datetime. Use ISO 8601 with timezone when possible.",
    ),
    eventType: nonEmptyString(tool, "eventType", options.maxStringChars, "<EVENT_TYPE>")
      .optional()
      .describe("Bloomberg event type supplied by the user."),
    interval: z
      .number()
      .int(`${tool}: interval must be a positive integer number of minutes. Example: 5`)
      .positive(`${tool}: interval must be greater than zero. Example: 5`)
      .describe("Bar interval in minutes. Must be a positive integer."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    outputTz: nonEmptyString(tool, "outputTz", options.maxStringChars, "<TIMEZONE>")
      .optional()
      .describe("Optional output timezone."),
    requestTz: nonEmptyString(tool, "requestTz", options.maxStringChars, "<TIMEZONE>")
      .optional()
      .describe("Timezone for naive start/end datetimes."),
    start: dateTimeField(tool, "start").describe(
      "Required intraday start datetime. Use ISO 8601 with timezone when possible.",
    ),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "<TICKER> <MARKET_SECTOR>",
    ).describe(
      "One fully qualified Bloomberg security supplied by the user; use /isin/<ISIN> for ISINs and /cusip/<CUSIP> for CUSIPs.",
    ),
  });
}

export function createBdtickSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<BdtickInput> {
  const tool = "xbbg_bdtick";
  const includeFlag = z.boolean().optional().describe("Optional IntradayTickRequest include flag.");
  return z.object({
    end: dateTimeField(tool, "end").describe(
      "Required intraday tick end datetime. Use ISO 8601 with timezone when possible.",
    ),
    eventTypes: stringArray(
      tool,
      "eventTypes",
      options.maxFields,
      options.maxStringChars,
      '["<EVENT_TYPE>"]',
    )
      .optional()
      .describe('Bloomberg tick event types, for example ["<EVENT_TYPE>"].'),
    includeBicMicCodes: includeFlag,
    includeBloombergStandardConditionCodes: includeFlag,
    includeBrokerCodes: includeFlag,
    includeConditionCodes: includeFlag,
    includeExchangeCodes: includeFlag,
    includeNonPlottableEvents: includeFlag,
    includeRpsCodes: includeFlag,
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced IntradayTickRequest kwargs as flat string/number/boolean values only.",
    ),
    outputTz: nonEmptyString(tool, "outputTz", options.maxStringChars, "<TIMEZONE>")
      .optional()
      .describe("Optional output timezone."),
    requestTz: nonEmptyString(tool, "requestTz", options.maxStringChars, "<TIMEZONE>")
      .optional()
      .describe("Timezone for naive start/end datetimes."),
    start: dateTimeField(tool, "start").describe(
      "Required intraday tick start datetime. Use ISO 8601 with timezone when possible.",
    ),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "<TICKER> <MARKET_SECTOR>",
    ).describe(
      "One fully qualified Bloomberg security supplied by the user; use /isin/<ISIN> for ISINs and /cusip/<CUSIP> for CUSIPs.",
    ),
  });
}

export function createBqlSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BqlInput> {
  const tool = "xbbg_bql";
  return z.object({
    format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    query: nonEmptyString(tool, "query", options.maxBqlQueryChars, "<BQL_QUERY>").describe(
      "Complete BQL expression string with an explicit bounded universe; prefer BDP/BDH for simple reference or historical requests.",
    ),
  });
}

export function createBqrSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BqrInput> {
  const tool = "xbbg_bqr";
  return z.object({
    end: dateTimeField(tool, "end").describe(
      "Required BQR end datetime. Use ISO 8601 with timezone when possible.",
    ),
    eventTypes: stringArray(
      tool,
      "eventTypes",
      options.maxFields,
      options.maxStringChars,
      '["<EVENT_TYPE>"]',
    )
      .optional()
      .describe('BQR event types, for example ["<EVENT_TYPE>"].'),
    includeBrokerCodes: z
      .boolean()
      .optional()
      .describe("Include broker/dealer attribution columns. Defaults to true in @xbbg/core."),
    start: dateTimeField(tool, "start").describe(
      "Required BQR start datetime. Use ISO 8601 with timezone when possible.",
    ),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "/isin/<ISIN>@<QUOTE_SOURCE> <MARKET_SECTOR>",
    ).describe(
      "Fixed-income ticker or identifier with dealer quote source, for example /isin/<ISIN>@<QUOTE_SOURCE> <MARKET_SECTOR>.",
    ),
  });
}

export function createBsrchSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BsrchInput> {
  const tool = "xbbg_bsrch";
  return z.object({
    format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Search-grid kwargs as flat string/number/boolean values only.",
    ),
    overrides: primitiveMap(tool, "overrides").describe(
      "Search-grid overrides as flat string/number/boolean values only.",
    ),
    searchSpec: nonEmptyString(
      tool,
      "searchSpec",
      options.maxSearchSpecChars,
      "<SEARCH_SPEC>",
    ).describe(
      "Bloomberg search/grid domain or saved-search spec. Not for normal security lookup.",
    ),
  });
}

export function createBfldsSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BfldsInput> {
  const tool = "xbbg_bflds";
  return z
    .object({
      fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
        .optional()
        .describe(
          "Specific field mnemonics to inspect. Provide either fields or searchSpec, not both.",
        ),
      format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
      kwargs: primitiveMap(tool, "kwargs").describe(
        "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
      ),
      searchSpec: nonEmptyString(
        tool,
        "searchSpec",
        options.maxSearchSpecChars,
        "<FIELD_SEARCH_TEXT>",
      )
        .optional()
        .describe(
          "Field search text when the field mnemonic is unknown. Provide either searchSpec or fields, not both.",
        ),
    })
    .superRefine((value, ctx) => {
      const hasFields = value.fields !== undefined;
      const hasSearchSpec = value.searchSpec !== undefined;
      if (hasFields === hasSearchSpec) {
        ctx.addIssue({
          code: "custom",
          message: `${tool}: provide exactly one of fields or searchSpec. Example: {"fields":["<FIELD>"]}`,
          path: ["fields"],
        });
      }
    });
}

export function createBeqsSchema(options: NormalizedBloombergToolsOptions): ZodOutput<BeqsInput> {
  const tool = "xbbg_beqs";
  return z.object({
    asof: dateField(tool, "asof").optional().describe("Optional as-of date for the screen."),
    format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
    group: nonEmptyString(tool, "group", options.maxStringChars, "<BEQS_GROUP>")
      .optional()
      .describe("Bloomberg BEQS group when required by the screen."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced BEQS request kwargs as flat string/number/boolean values only.",
    ),
    overrides: primitiveMap(tool, "overrides").describe(
      "BEQS overrides as flat string/number/boolean values only.",
    ),
    screen: nonEmptyString(tool, "screen", options.maxStringChars, "<BEQS_SCREEN>").describe(
      "Existing Bloomberg BEQS screen name supplied by the user.",
    ),
    screenType: nonEmptyString(tool, "screenType", options.maxStringChars, "<SCREEN_TYPE>")
      .optional()
      .describe("Bloomberg BEQS screen type when required by the screen."),
  });
}

export function createYasSchema(options: NormalizedBloombergToolsOptions): ZodOutput<YasInput> {
  const tool = "xbbg_yas";
  return z.object({
    benchmark: nonEmptyString(tool, "benchmark", options.maxStringChars, "<BENCHMARK_TICKER>")
      .optional()
      .describe("Optional YAS benchmark supplied by the user."),
    fields: stringArray(
      tool,
      "fields",
      options.maxFields,
      options.maxStringChars,
      '["<YAS_FIELD>"]',
    ).describe("YAS field mnemonics supplied by the user."),
    price: z.number().optional().describe("Optional YAS price input."),
    settleDt: dateField(tool, "settleDt").optional().describe("Optional YAS settlement date."),
    spread: z.number().optional().describe("Optional YAS spread input."),
    tickers: stringArray(
      tool,
      "tickers",
      options.maxSecurities,
      options.maxStringChars,
      '["/isin/<ISIN> <MARKET_SECTOR>"]',
    ).describe("Fully qualified fixed-income Bloomberg securities supplied by the user."),
    yieldType: z.number().int().optional().describe("Optional YAS yield type."),
    yieldVal: z.number().optional().describe("Optional YAS yield value input."),
  });
}

export function createPreferredsSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<PreferredsInput> {
  const tool = "xbbg_preferreds";
  return z.object({
    equityTicker: nonEmptyString(
      tool,
      "equityTicker",
      options.maxStringChars,
      "<ISSUER_TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified issuer equity ticker supplied by the user."),
    fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
      .optional()
      .describe("Optional fields to include in the preferreds recipe result."),
  });
}

export function createCorporateBondsSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<CorporateBondsInput> {
  const tool = "xbbg_corporate_bonds";
  return z.object({
    activeOnly: z
      .boolean()
      .optional()
      .describe("Restrict to active bonds. Defaults to true in @xbbg/core."),
    ccy: nonEmptyString(tool, "ccy", options.maxStringChars, "<CCY>")
      .optional()
      .describe("Optional currency filter supplied by the user."),
    fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
      .optional()
      .describe("Optional fields to include in the corporate bond result."),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "<ISSUER_TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified issuer/company ticker supplied by the user."),
  });
}

export function createIndexMembersSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<IndexMembersInput> {
  const tool = "xbbg_index_members";
  return z.object({
    asof: dateField(tool, "asof").optional().describe("Optional index membership as-of date."),
    field: z
      .enum(["INDX_MWEIGHT", "INDX_MEMBERS", "INDX_MEMBERS3"])
      .optional()
      .describe("Bloomberg index members field. Omit for @xbbg/core default."),
    index: nonEmptyString(
      tool,
      "index",
      options.maxStringChars,
      "<INDEX_TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified Bloomberg index ticker supplied by the user."),
  });
}

export function createResolveIsinsSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<ResolveIsinsInput> {
  const tool = "xbbg_resolve_isins";
  return z.object({
    isins: stringArray(
      tool,
      "isins",
      options.maxSecurities,
      options.maxStringChars,
      '["<ISIN>"]',
    ).describe("Raw ISIN strings to resolve. Do not add /isin/ prefixes for this recipe."),
  });
}

export function createIssuerIsinsSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<IssuerIsinsInput> {
  const tool = "xbbg_issuer_isins";
  return z.object({
    bondIsins: stringArray(
      tool,
      "bondIsins",
      options.maxSecurities,
      options.maxStringChars,
      '["<BOND_ISIN>"]',
    ).describe("Raw bond ISIN strings for issuer-level ISIN discovery."),
  });
}

export function createEtfHoldingsSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<EtfHoldingsInput> {
  const tool = "xbbg_etf_holdings";
  return z.object({
    etfTicker: nonEmptyString(
      tool,
      "etfTicker",
      options.maxStringChars,
      "<ETF_TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified Bloomberg ETF ticker supplied by the user."),
    fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
      .optional()
      .describe("Optional fields to include in the ETF holdings recipe result."),
  });
}

interface SnapshotControlShape {
  readonly allFields: ZodOutput<boolean | undefined>;
  readonly conflate: ZodOutput<boolean | undefined>;
  readonly drain: ZodOutput<boolean | undefined>;
  readonly flushThreshold: ZodOutput<number | undefined>;
  readonly maxUpdates: ZodOutput<number>;
  readonly options: ZodOutput<string[] | undefined>;
  readonly overflowPolicy: ZodOutput<string | undefined>;
  readonly streamCapacity: ZodOutput<number | undefined>;
  readonly timeoutMs: ZodOutput<number>;
}

function snapshotControlFields(
  tool: string,
  options: NormalizedBloombergToolsOptions,
): SnapshotControlShape {
  return {
    allFields: z.boolean().optional().describe("Request all Bloomberg fields when supported."),
    conflate: z
      .boolean()
      .optional()
      .describe("Enable Bloomberg conflated streaming when supported."),
    drain: z
      .boolean()
      .optional()
      .describe(
        "Pass drain=true to unsubscribe. Defaults to false; collected output remains bounded.",
      ),
    flushThreshold: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Optional stream flush threshold."),
    maxUpdates: z
      .number()
      .int(`${tool}: maxUpdates must be a positive integer.`)
      .positive(`${tool}: maxUpdates must be greater than zero.`)
      .max(
        options.maxStreamUpdates,
        `${tool}: maxUpdates can be at most ${options.maxStreamUpdates}.`,
      )
      .describe("Required maximum number of updates to collect before unsubscribing."),
    options: stringArray(
      tool,
      "options",
      options.maxFields,
      options.maxStringChars,
      '["interval=5"]',
    )
      .optional()
      .describe("Advanced Bloomberg subscription options."),
    overflowPolicy: nonEmptyString(tool, "overflowPolicy", options.maxStringChars, "drop_oldest")
      .optional()
      .describe("Optional stream overflow policy."),
    streamCapacity: z.number().int().positive().optional().describe("Optional stream capacity."),
    timeoutMs: z
      .number()
      .int()
      .positive()
      .max(options.maxStreamWaitMs, `${tool}: timeoutMs can be at most ${options.maxStreamWaitMs}.`)
      .optional()
      .default(options.maxStreamWaitMs)
      .describe("Maximum total wait in milliseconds before unsubscribing."),
  };
}

export function createStreamSnapshotSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<StreamSnapshotInput> {
  const tool = "xbbg_stream_snapshot";
  return z.object({
    fields: stringArray(
      tool,
      "fields",
      options.maxFields,
      options.maxStringChars,
      '["<FIELD>"]',
    ).describe("Bloomberg market-data fields to observe."),
    tickers: stringArray(
      tool,
      "tickers",
      options.maxSecurities,
      options.maxStringChars,
      '["<TICKER> <MARKET_SECTOR>"]',
    ).describe("Fully qualified Bloomberg securities supplied by the user to observe."),
    ...snapshotControlFields(tool, options),
  });
}

export function createMktbarSnapshotSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<MktbarSnapshotInput> {
  const tool = "xbbg_mktbar_snapshot";
  return z.object({
    fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
      .optional()
      .describe("Optional market-bar fields. Omit for Bloomberg defaults."),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "<TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified Bloomberg security supplied by the user to observe."),
    ...snapshotControlFields(tool, options),
  });
}

export function createDepthSnapshotSchema(
  options: NormalizedBloombergToolsOptions,
): ZodOutput<DepthSnapshotInput> {
  const tool = "xbbg_depth_snapshot";
  return z.object({
    fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["<FIELD>"]')
      .optional()
      .describe("Optional market-depth fields. Omit for Bloomberg defaults."),
    ticker: nonEmptyString(
      tool,
      "ticker",
      options.maxStringChars,
      "<TICKER> <MARKET_SECTOR>",
    ).describe("One fully qualified Bloomberg security supplied by the user to observe."),
    ...snapshotControlFields(tool, options),
  });
}
