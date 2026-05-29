import * as z from "zod";

import type { NormalizedBloombergToolsOptions } from "./options";

export interface StringPair {
  readonly key: string;
  readonly value: string;
}

export interface FuturesCandidate {
  readonly ticker: string;
  readonly year: number;
  readonly month: number;
}

export type PrimitiveMap = Readonly<Record<string, string | number | boolean>>;

export type TickerOperation =
  | "parse_ticker"
  | "normalize_tickers"
  | "filter_equity_tickers"
  | "is_specific_contract"
  | "validate_generic_ticker";

export interface TickerInput {
  readonly operation: TickerOperation;
  readonly ticker?: string;
  readonly tickers?: readonly string[];
}

export type FuturesOperation =
  | "build_futures_ticker"
  | "generate_candidates"
  | "contract_index"
  | "filter_candidates_by_cycle"
  | "filter_valid_contracts"
  | "get_futures_months";

export interface FuturesInput {
  readonly operation: FuturesOperation;
  readonly prefix?: string;
  readonly monthCode?: string;
  readonly year?: string | number;
  readonly asset?: string;
  readonly genTicker?: string;
  readonly month?: number;
  readonly day?: number;
  readonly freq?: string;
  readonly count?: number;
  readonly candidates?: readonly FuturesCandidate[];
  readonly cycle?: string;
  readonly contracts?: readonly StringPair[];
}

export type CdxOperation =
  | "parse_cdx_ticker"
  | "previous_cdx_series"
  | "cdx_gen_to_specific"
  | "cdx_info"
  | "cdx_pricing"
  | "cdx_risk";

export interface CdxInput {
  readonly operation: CdxOperation;
  readonly ticker?: string;
  readonly genTicker?: string;
  readonly series?: number;
  readonly recoveryRate?: number;
}

export type CurrencyOperation = "build_fx_pair" | "same_currency" | "currencies_needing_conversion";

export interface CurrencyInput {
  readonly operation: CurrencyOperation;
  readonly fromCcy?: string;
  readonly toCcy?: string;
  readonly ccy1?: string;
  readonly ccy2?: string;
  readonly currencies?: readonly string[];
  readonly target?: string;
}

export type BqlBuilderOperation =
  | "build_preferreds_query"
  | "build_corporate_bonds_query"
  | "build_etf_holdings_query";

export interface BqlBuilderInput {
  readonly operation: BqlBuilderOperation;
  readonly ticker?: string;
  readonly equityTicker?: string;
  readonly etfTicker?: string;
  readonly ccy?: string;
  readonly extraFields?: readonly string[];
  readonly activeOnly?: boolean;
}

export type MarketSessionOperation =
  | "derive_sessions"
  | "get_market_rule"
  | "infer_timezone"
  | "session_times_to_utc"
  | "default_turnover_dates"
  | "default_bqr_datetimes"
  | "get_exchange_override"
  | "list_exchange_overrides";

export interface MarketSessionInput {
  readonly operation: MarketSessionOperation;
  readonly dayStart?: string;
  readonly dayEnd?: string;
  readonly mic?: string;
  readonly exchCode?: string;
  readonly countryIso?: string;
  readonly startTime?: string;
  readonly endTime?: string;
  readonly exchangeTz?: string;
  readonly date?: string;
  readonly startDate?: string;
  readonly endDate?: string;
  readonly startDatetime?: string;
  readonly endDatetime?: string;
  readonly ticker?: string;
}

export interface YasOverridesInput {
  readonly settleDt?: string;
  readonly yieldType?: number;
  readonly spread?: number;
  readonly yieldVal?: number;
  readonly price?: number;
  readonly benchmark?: string;
}

export type ConstantsOperation =
  | "parse_date"
  | "fmt_date"
  | "get_month_code"
  | "get_month_name"
  | "get_futures_months"
  | "get_dvd_type"
  | "get_dvd_types"
  | "get_dvd_cols"
  | "get_etf_cols";

export interface ConstantsInput {
  readonly operation: ConstantsOperation;
  readonly dateStr?: string;
  readonly year?: number;
  readonly month?: number;
  readonly day?: number;
  readonly fmt?: string;
  readonly monthName?: string;
  readonly code?: string;
  readonly dvdType?: string;
}

export type ColumnsOperation =
  | "rename_dividend_columns"
  | "rename_etf_columns"
  | "build_earning_header_rename";

export interface ColumnsInput {
  readonly operation: ColumnsOperation;
  readonly columns?: readonly string[];
  readonly headerRow?: readonly StringPair[];
  readonly dataColumns?: readonly string[];
}

export interface CalculateInput {
  readonly operation: "calculate_level_percentages";
  readonly values: readonly (number | null)[];
  readonly levels: readonly (number | null)[];
}

const stringPairSchema = z.object({
  key: z.string().trim().min(1).describe("String pair key."),
  value: z.string().trim().min(1).describe("String pair value."),
});

const futuresCandidateSchema = z.object({
  month: z.number().int().min(1).max(12).describe("Contract month number, 1-12."),
  ticker: z.string().trim().min(1).describe("Specific Bloomberg futures ticker."),
  year: z.number().int().min(1900).describe("Contract year."),
});

function nonEmptyString(
  options: NormalizedBloombergToolsOptions,
  description: string,
): z.ZodPipe<z.ZodString, z.ZodString> {
  return z
    .string()
    .trim()
    .pipe(z.string().min(1).max(options.maxStringChars).describe(description));
}

function stringArray(
  options: NormalizedBloombergToolsOptions,
  description: string,
  maxItems = options.maxFields,
): z.ZodArray<z.ZodPipe<z.ZodString, z.ZodString>> {
  return z.array(nonEmptyString(options, description)).min(1).max(maxItems).describe(description);
}

function optionalString(
  options: NormalizedBloombergToolsOptions,
  description: string,
): z.ZodOptional<z.ZodPipe<z.ZodString, z.ZodString>> {
  return nonEmptyString(options, description).optional();
}
export function tickerSchema(options: NormalizedBloombergToolsOptions): z.ZodType<TickerInput> {
  return z.object({
    operation: z
      .enum([
        "parse_ticker",
        "normalize_tickers",
        "filter_equity_tickers",
        "is_specific_contract",
        "validate_generic_ticker",
      ])
      .describe("Ticker helper operation to run."),
    ticker: optionalString(
      options,
      "One Bloomberg ticker for parse/contract validation operations.",
    ),
    tickers: stringArray(
      options,
      "Bloomberg tickers to normalize or filter.",
      options.maxSecurities,
    ).optional(),
  });
}

export function futuresSchema(options: NormalizedBloombergToolsOptions): z.ZodType<FuturesInput> {
  return z.object({
    asset: optionalString(options, "Bloomberg asset class suffix, for example Comdty."),
    candidates: z
      .array(futuresCandidateSchema)
      .min(1)
      .max(options.maxFields)
      .optional()
      .describe("Candidate futures contracts."),
    contracts: z
      .array(stringPairSchema)
      .min(1)
      .max(options.maxFields)
      .optional()
      .describe("Contract pairs for validity filtering."),
    count: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Maximum number of futures candidates to generate."),
    cycle: optionalString(options, "Futures cycle code to filter candidates by."),
    day: z.number().int().min(1).max(31).optional().describe("Day number for contract filtering."),
    freq: optionalString(options, "Futures frequency/cycle hint."),
    genTicker: optionalString(options, "Generic Bloomberg futures ticker."),
    month: z.number().int().min(1).max(12).optional().describe("Month number, 1-12."),
    monthCode: optionalString(options, "Bloomberg futures month code, for example H."),
    operation: z
      .enum([
        "build_futures_ticker",
        "generate_candidates",
        "contract_index",
        "filter_candidates_by_cycle",
        "filter_valid_contracts",
        "get_futures_months",
      ])
      .describe("Futures helper operation to run."),
    prefix: optionalString(options, "Futures ticker root prefix."),
    year: z
      .union([z.string().trim().min(1), z.number().int()])
      .optional()
      .describe("Contract year."),
  });
}

export function cdxSchema(options: NormalizedBloombergToolsOptions): z.ZodType<CdxInput> {
  return z.object({
    genTicker: optionalString(options, "Generic CDX ticker."),
    operation: z
      .enum([
        "parse_cdx_ticker",
        "previous_cdx_series",
        "cdx_gen_to_specific",
        "cdx_info",
        "cdx_pricing",
        "cdx_risk",
      ])
      .describe("CDX helper operation to run."),
    recoveryRate: z
      .number()
      .optional()
      .describe("Optional recovery rate override for pricing/risk lookups."),
    series: z.number().int().positive().optional().describe("Specific CDX series number."),
    ticker: optionalString(options, "CDX ticker."),
  });
}

export function currencySchema(options: NormalizedBloombergToolsOptions): z.ZodType<CurrencyInput> {
  return z.object({
    ccy1: optionalString(options, "First ISO currency code."),
    ccy2: optionalString(options, "Second ISO currency code."),
    currencies: stringArray(options, "ISO currency codes.").optional(),
    fromCcy: optionalString(options, "Source ISO currency code."),
    operation: z
      .enum(["build_fx_pair", "same_currency", "currencies_needing_conversion"])
      .describe("Currency helper operation to run."),
    target: optionalString(options, "Target ISO currency code."),
    toCcy: optionalString(options, "Destination ISO currency code."),
  });
}

export function bqlBuilderSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<BqlBuilderInput> {
  return z.object({
    activeOnly: z.boolean().optional().describe("Restrict corporate bond query to active bonds."),
    ccy: optionalString(options, "Currency filter for corporate bond query."),
    equityTicker: optionalString(options, "Equity ticker for preferreds query."),
    etfTicker: optionalString(options, "ETF ticker for holdings query."),
    extraFields: stringArray(options, "Extra BQL fields to include.").optional(),
    operation: z
      .enum(["build_preferreds_query", "build_corporate_bonds_query", "build_etf_holdings_query"])
      .describe("BQL builder operation to run."),
    ticker: optionalString(options, "Ticker for corporate bond query."),
  });
}

export function marketSessionSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<MarketSessionInput> {
  return z.object({
    countryIso: optionalString(options, "ISO country code for timezone inference."),
    date: optionalString(options, "Date for UTC session conversion, YYYY-MM-DD or YYYYMMDD."),
    dayEnd: optionalString(options, "Exchange day end time, for example 16:00."),
    dayStart: optionalString(options, "Exchange day start time, for example 09:30."),
    endDate: optionalString(options, "Optional end date."),
    endDatetime: optionalString(options, "Optional end datetime."),
    endTime: optionalString(options, "Session end time, for example 16:00."),
    exchCode: optionalString(options, "Bloomberg exchange code."),
    exchangeTz: optionalString(options, "IANA exchange timezone."),
    mic: optionalString(options, "Market Identifier Code."),
    operation: z
      .enum([
        "derive_sessions",
        "get_market_rule",
        "infer_timezone",
        "session_times_to_utc",
        "default_turnover_dates",
        "default_bqr_datetimes",
        "get_exchange_override",
        "list_exchange_overrides",
      ])
      .describe("Market session helper operation to run."),
    startDate: optionalString(options, "Optional start date."),
    startDatetime: optionalString(options, "Optional start datetime."),
    startTime: optionalString(options, "Session start time, for example 09:30."),
    ticker: optionalString(options, "Ticker for exchange override lookup."),
  });
}

export function yasOverridesSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<YasOverridesInput> {
  return z.object({
    benchmark: optionalString(options, "Optional YAS benchmark."),
    price: z.number().optional().describe("YAS price override."),
    settleDt: optionalString(options, "YAS settlement date."),
    spread: z.number().optional().describe("YAS spread override."),
    yieldType: z.number().int().optional().describe("YAS yield type override."),
    yieldVal: z.number().optional().describe("YAS yield value override."),
  });
}

export function constantsSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<ConstantsInput> {
  return z.object({
    code: optionalString(options, "Month code."),
    dateStr: optionalString(options, "Date string to parse."),
    day: z.number().int().min(1).max(31).optional().describe("Day number."),
    dvdType: optionalString(options, "Dividend type code or label."),
    fmt: optionalString(options, "Date output format."),
    month: z.number().int().min(1).max(12).optional().describe("Month number."),
    monthName: optionalString(options, "Month name."),
    operation: z
      .enum([
        "parse_date",
        "fmt_date",
        "get_month_code",
        "get_month_name",
        "get_futures_months",
        "get_dvd_type",
        "get_dvd_types",
        "get_dvd_cols",
        "get_etf_cols",
      ])
      .describe("Constants helper operation to run."),
    year: z.number().int().min(1).optional().describe("Year number."),
  });
}

export function columnsSchema(options: NormalizedBloombergToolsOptions): z.ZodType<ColumnsInput> {
  return z.object({
    columns: stringArray(options, "Column names to rename.").optional(),
    dataColumns: stringArray(options, "Earnings data column names.").optional(),
    headerRow: z
      .array(stringPairSchema)
      .min(1)
      .max(options.maxFields)
      .optional()
      .describe("Earnings header row key/value pairs."),
    operation: z
      .enum(["rename_dividend_columns", "rename_etf_columns", "build_earning_header_rename"])
      .describe("Column helper operation to run."),
  });
}

export function calculateSchema(
  options: NormalizedBloombergToolsOptions,
): z.ZodType<CalculateInput> {
  return z.object({
    levels: z
      .array(z.number().nullable())
      .min(1)
      .max(options.maxFields)
      .describe("Reference level values."),
    operation: z
      .literal("calculate_level_percentages")
      .describe("Numeric helper operation to run."),
    values: z
      .array(z.number().nullable())
      .min(1)
      .max(options.maxFields)
      .describe("Observed values."),
  });
}
