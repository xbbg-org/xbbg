import { z } from "zod";

import type { NormalizedBloombergToolsOptions } from "./options";

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

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/u;
const BBG_DATE_RE = /^\d{8}$/u;
const AMBIGUOUS_DATE_RE = /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}([T \D]|$)/u;
const ISO_DATE_TIME_RE =
  /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/u;

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
  if (BBG_DATE_RE.test(text)) {
    return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}T00:00:00`;
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
): z.ZodType<string> {
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
): z.ZodType<string[]> {
  return z
    .array(nonEmptyString(tool, field, maxChars, example))
    .min(1, `${tool}: ${field} must contain at least one non-empty string. Example: ${example}`)
    .max(maxItems, `${tool}: ${field} can contain at most ${maxItems} values`);
}

function primitiveMap(tool: string, field: string): z.ZodType<PrimitiveMap | undefined> {
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

function dateField(tool: string, field: string): z.ZodType<string> {
  return z
    .union([z.string(), z.date(), z.number()])
    .transform((value) => normalizeDate(value))
    .describe(
      `${field} date. Use YYYY-MM-DD or Bloomberg-native YYYYMMDD, never ambiguous MM/DD/YYYY.`,
    );
}

function dateTimeField(tool: string, field: string): z.ZodType<string> {
  return z
    .union([z.string(), z.date(), z.number()])
    .transform((value) => normalizeDateTime(value))
    .describe(`${field} datetime. Use ISO 8601, for example 2024-01-31T09:30:00-05:00.`);
}

function referenceFormat(tool: string): z.ZodType<ReferenceFormat | undefined> {
  return z
    .enum(REFERENCE_FORMATS, {
      error: `${tool}: format must be one of ${REFERENCE_FORMATS.join(", ")}`,
    })
    .optional();
}

function historicalFormat(tool: string): z.ZodType<HistoricalFormat | undefined> {
  return z
    .enum(HISTORICAL_FORMATS, {
      error: `${tool}: format must be one of ${HISTORICAL_FORMATS.join(", ")}`,
    })
    .optional();
}

export function createBdpSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BdpInput> {
  const tool = "xbbg_bdp";
  return z.object({
    fields: stringArray(
      tool,
      "fields",
      options.maxFields,
      options.maxStringChars,
      '["PX_LAST"]',
    ).describe(
      'Bloomberg field mnemonics to retrieve, for example ["PX_LAST", "NAME"]. Use xbbg_bflds first if uncertain.',
    ),
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
      '["AAPL US Equity"]',
    ).describe(
      'Fully qualified Bloomberg securities, for example ["AAPL US Equity"]; use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs. Do not invent tickers.',
    ),
    validateFields: z.boolean().optional().describe("Override field validation for this request."),
  });
}

export function createBdhSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BdhInput> {
  const tool = "xbbg_bdh";
  return z
    .object({
      end: dateField(tool, "end").describe("Required end date. Use YYYY-MM-DD or YYYYMMDD."),
      fields: stringArray(
        tool,
        "fields",
        options.maxFields,
        options.maxStringChars,
        '["PX_LAST"]',
      ).describe('Bloomberg historical field mnemonics, for example ["PX_LAST"].'),
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
        '["AAPL US Equity"]',
      ).describe(
        'Fully qualified Bloomberg securities, for example ["AAPL US Equity"]; use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs.',
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
          message: `${tool}: start must be on or before end. Example: start "2024-01-01", end "2024-01-31"`,
          path: ["start"],
        });
      }
    });
}

export function createBdsSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BdsInput> {
  const tool = "xbbg_bds";
  return z.object({
    field: nonEmptyString(tool, "field", options.maxStringChars, "INDX_MEMBERS").describe(
      "Exactly one Bloomberg bulk/table field, for example INDX_MEMBERS.",
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
      '["SPX Index"]',
    ).describe(
      'Fully qualified Bloomberg securities, for example ["SPX Index"]; use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs.',
    ),
    validateFields: z.boolean().optional().describe("Override field validation for this request."),
  });
}

export function createBdibSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BdibInput> {
  const tool = "xbbg_bdib";
  return z.object({
    end: dateTimeField(tool, "end").describe(
      "Required intraday end datetime. Use ISO 8601 with timezone when possible.",
    ),
    eventType: nonEmptyString(tool, "eventType", options.maxStringChars, "TRADE")
      .optional()
      .describe("Bloomberg event type. Usually TRADE."),
    interval: z
      .number()
      .int(`${tool}: interval must be a positive integer number of minutes. Example: 5`)
      .positive(`${tool}: interval must be greater than zero. Example: 5`)
      .describe("Bar interval in minutes. Must be a positive integer."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    outputTz: nonEmptyString(tool, "outputTz", options.maxStringChars, "America/New_York")
      .optional()
      .describe("Optional output timezone, for example America/New_York."),
    requestTz: nonEmptyString(tool, "requestTz", options.maxStringChars, "America/New_York")
      .optional()
      .describe("Timezone for naive start/end datetimes, for example America/New_York."),
    start: dateTimeField(tool, "start").describe(
      "Required intraday start datetime. Use ISO 8601 with timezone when possible.",
    ),
    ticker: nonEmptyString(tool, "ticker", options.maxStringChars, "AAPL US Equity").describe(
      "One fully qualified Bloomberg security, for example AAPL US Equity; use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs.",
    ),
  });
}

export function createBdtickSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<BdtickInput> {
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
      '["TRADE"]',
    )
      .optional()
      .describe('Bloomberg tick event types, for example ["TRADE"] or ["BID", "ASK"].'),
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
    outputTz: nonEmptyString(tool, "outputTz", options.maxStringChars, "America/New_York")
      .optional()
      .describe("Optional output timezone, for example America/New_York."),
    requestTz: nonEmptyString(tool, "requestTz", options.maxStringChars, "America/New_York")
      .optional()
      .describe("Timezone for naive start/end datetimes, for example America/New_York."),
    start: dateTimeField(tool, "start").describe(
      "Required intraday tick start datetime. Use ISO 8601 with timezone when possible.",
    ),
    ticker: nonEmptyString(tool, "ticker", options.maxStringChars, "AAPL US Equity").describe(
      "One fully qualified Bloomberg security, for example AAPL US Equity; use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs.",
    ),
  });
}

export function createBqlSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BqlInput> {
  const tool = "xbbg_bql";
  return z.object({
    format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
    kwargs: primitiveMap(tool, "kwargs").describe(
      "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
    ),
    query: nonEmptyString(
      tool,
      "query",
      options.maxBqlQueryChars,
      "get(px_last) for('AAPL US Equity')",
    ).describe(
      "Complete BQL expression string. Use get(...) for(...) with an explicit bounded universe; prefer BDP/BDH for simple reference or historical requests.",
    ),
  });
}

export function createBqrSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BqrInput> {
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
      '["BID", "ASK"]',
    )
      .optional()
      .describe('BQR event types. Usually ["BID", "ASK"].'),
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
      "/isin/US037833FB15@MSG1 Corp",
    ).describe(
      "Fixed-income ticker or identifier with dealer quote source, for example /isin/US037833FB15@MSG1 Corp.",
    ),
  });
}

export function createBsrchSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BsrchInput> {
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
      "COMDTY:NG",
    ).describe(
      "Bloomberg search/grid domain or saved-search spec. Not for normal security lookup.",
    ),
  });
}

export function createBfldsSchema(options: NormalizedBloombergToolsOptions): z.ZodType<BfldsInput> {
  const tool = "xbbg_bflds";
  return z
    .object({
      fields: stringArray(tool, "fields", options.maxFields, options.maxStringChars, '["PX_LAST"]')
        .optional()
        .describe(
          'Specific field mnemonics to inspect, for example ["PX_LAST"]. Provide either fields or searchSpec, not both.',
        ),
      format: referenceFormat(tool).describe("JSON output shape. Usually omit."),
      kwargs: primitiveMap(tool, "kwargs").describe(
        "Advanced Bloomberg request kwargs as flat string/number/boolean values only.",
      ),
      searchSpec: nonEmptyString(tool, "searchSpec", options.maxSearchSpecChars, "last price")
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
          message: `${tool}: provide exactly one of fields or searchSpec. Example: {"fields":["PX_LAST"]}`,
          path: ["fields"],
        });
      }
    });
}
