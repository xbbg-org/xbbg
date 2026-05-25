import { tool } from "@langchain/core/tools";
import { z } from "zod";

import { createCoreResolver, type CoreResolver } from "./core-loader";
import {
  EXT_BQL_BUILDER_DESCRIPTION,
  EXT_CALCULATE_DESCRIPTION,
  EXT_CDX_DESCRIPTION,
  EXT_COLUMNS_DESCRIPTION,
  EXT_CONSTANTS_DESCRIPTION,
  EXT_CURRENCY_DESCRIPTION,
  EXT_FUTURES_DESCRIPTION,
  EXT_MARKET_SESSION_DESCRIPTION,
  EXT_TICKER_DESCRIPTION,
  EXT_YAS_OVERRIDES_DESCRIPTION,
} from "./descriptions";
import type { BloombergToolName, BloombergToolsOptions } from "./options";
import { isToolDisabled } from "./options";
import type { BloombergTool } from "./tools";
import { stringifyToolResult, throwWithToolContext } from "./result-limits";

interface StringPair {
  readonly key: string;
  readonly value: string;
}

interface FuturesCandidate {
  readonly ticker: string;
  readonly year: number;
  readonly month: number;
}

type PrimitiveMap = Readonly<Record<string, string | number | boolean>>;

type TickerOperation =
  | "parse_ticker"
  | "normalize_tickers"
  | "filter_equity_tickers"
  | "is_specific_contract"
  | "validate_generic_ticker";

interface TickerInput {
  readonly operation: TickerOperation;
  readonly ticker?: string;
  readonly tickers?: readonly string[];
}

type FuturesOperation =
  | "build_futures_ticker"
  | "generate_candidates"
  | "contract_index"
  | "filter_candidates_by_cycle"
  | "filter_valid_contracts"
  | "get_futures_months";

interface FuturesInput {
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

type CdxOperation =
  | "parse_cdx_ticker"
  | "previous_cdx_series"
  | "cdx_gen_to_specific"
  | "cdx_info"
  | "cdx_pricing"
  | "cdx_risk";

interface CdxInput {
  readonly operation: CdxOperation;
  readonly ticker?: string;
  readonly genTicker?: string;
  readonly series?: number;
  readonly recoveryRate?: number;
}

type CurrencyOperation = "build_fx_pair" | "same_currency" | "currencies_needing_conversion";

interface CurrencyInput {
  readonly operation: CurrencyOperation;
  readonly fromCcy?: string;
  readonly toCcy?: string;
  readonly ccy1?: string;
  readonly ccy2?: string;
  readonly currencies?: readonly string[];
  readonly target?: string;
}

type BqlBuilderOperation =
  | "build_preferreds_query"
  | "build_corporate_bonds_query"
  | "build_etf_holdings_query";

interface BqlBuilderInput {
  readonly operation: BqlBuilderOperation;
  readonly ticker?: string;
  readonly equityTicker?: string;
  readonly etfTicker?: string;
  readonly ccy?: string;
  readonly extraFields?: readonly string[];
  readonly activeOnly?: boolean;
}

type MarketSessionOperation =
  | "derive_sessions"
  | "get_market_rule"
  | "infer_timezone"
  | "session_times_to_utc"
  | "default_turnover_dates"
  | "default_bqr_datetimes"
  | "get_exchange_override"
  | "list_exchange_overrides";

interface MarketSessionInput {
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

interface YasOverridesInput {
  readonly settleDt?: string;
  readonly yieldType?: number;
  readonly spread?: number;
  readonly yieldVal?: number;
  readonly price?: number;
  readonly benchmark?: string;
}

type ConstantsOperation =
  | "parse_date"
  | "fmt_date"
  | "get_month_code"
  | "get_month_name"
  | "get_futures_months"
  | "get_dvd_type"
  | "get_dvd_types"
  | "get_dvd_cols"
  | "get_etf_cols";

interface ConstantsInput {
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

type ColumnsOperation =
  | "rename_dividend_columns"
  | "rename_etf_columns"
  | "build_earning_header_rename";

interface ColumnsInput {
  readonly operation: ColumnsOperation;
  readonly columns?: readonly string[];
  readonly headerRow?: readonly StringPair[];
  readonly dataColumns?: readonly string[];
}

interface CalculateInput {
  readonly operation: "calculate_level_percentages";
  readonly values: readonly (number | null)[];
  readonly levels: readonly (number | null)[];
}

const CDX_INFO_FIELDS = Object.freeze([
  "ROLLING_SERIES",
  "VERSION",
  "ON_THE_RUN_CURRENT_BD_INDICATOR",
  "CDS_FIRST_ACCRUAL_START_DATE",
  "NAME",
  "NUM_CURRENT_COMPANIES_CCY_TKR",
  "NUM_ORIG_COMPANIES_CRNCY_TKR",
  "PX_LAST",
]);

const CDX_PRICING_FIELDS = Object.freeze([
  "PX_LAST",
  "PX_BID",
  "PX_ASK",
  "UPFRONT_LAST",
  "UPFRONT_BID",
  "UPFRONT_ASK",
  "CDS_FLAT_SPREAD",
  "UPFRONT_FEE",
  "PV_CDS_PREMIUM_LEG",
  "PV_CDS_DEFAULT_LEG",
]);

const CDX_RISK_FIELDS = Object.freeze([
  "SW_CNV_BPV",
  "SW_EQV_BPV",
  "CDS_SPREAD_MID_MODIFIED_DURATION",
  "CDS_SPREAD_MID_CONVEXITY",
  "RECOVERY_RATE_SEN",
  "CDS_RECOVERY_RT",
]);

const stringPairSchema = z.object({
  key: z.string().trim().min(1).describe("String pair key."),
  value: z.string().trim().min(1).describe("String pair value."),
});

const futuresCandidateSchema = z.object({
  month: z.number().int().min(1).max(12).describe("Contract month number, 1-12."),
  ticker: z.string().trim().min(1).describe("Specific Bloomberg futures ticker."),
  year: z.number().int().min(1900).describe("Contract year."),
});

function nonEmptyString(description: string): z.ZodPipe<z.ZodString, z.ZodString> {
  return z.string().trim().pipe(z.string().min(1).describe(description));
}

function stringArray(description: string): z.ZodArray<z.ZodPipe<z.ZodString, z.ZodString>> {
  return z.array(nonEmptyString(description)).min(1).describe(description);
}

function optionalString(description: string): z.ZodOptional<z.ZodPipe<z.ZodString, z.ZodString>> {
  return nonEmptyString(description).optional();
}
function asRecord(value: object): Record<string, unknown> {
  return value as unknown as Record<string, unknown>;
}

function requireString(
  toolName: BloombergToolName,
  input: Record<string, unknown>,
  field: string,
): string {
  const value = input[field];
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new TypeError(`${toolName}: ${field} is required and must be a non-empty string`);
  }
  return value.trim();
}

function requireNumber(
  toolName: BloombergToolName,
  input: Record<string, unknown>,
  field: string,
): number {
  const value = input[field];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${toolName}: ${field} is required and must be a finite number`);
  }
  return value;
}

function requireInteger(
  toolName: BloombergToolName,
  input: Record<string, unknown>,
  field: string,
): number {
  const value = requireNumber(toolName, input, field);
  if (!Number.isInteger(value)) {
    throw new TypeError(`${toolName}: ${field} must be an integer`);
  }
  return value;
}
function requireYearString(
  toolName: BloombergToolName,
  input: Record<string, unknown>,
  field: string,
): string {
  const value = input[field];
  if (typeof value === "number" && Number.isInteger(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  throw new TypeError(`${toolName}: ${field} is required and must be a year string or integer`);
}

function requireStringArray(
  toolName: BloombergToolName,
  input: Record<string, unknown>,
  field: string,
): readonly string[] {
  const value = input[field];
  if (!Array.isArray(value) || value.length === 0) {
    throw new TypeError(`${toolName}: ${field} is required and must be a non-empty string array`);
  }
  return value.map((entry) => {
    if (typeof entry !== "string" || entry.trim().length === 0) {
      throw new TypeError(`${toolName}: ${field} entries must be non-empty strings`);
    }
    return entry.trim();
  });
}

function resultString(resolver: CoreResolver, name: BloombergToolName, value: unknown): string {
  return stringifyToolResult(
    name,
    value,
    resolver.options.maxRows,
    resolver.options.maxStringChars,
  );
}

function recoveryOverrides(recoveryRate: number | undefined): PrimitiveMap | undefined {
  return recoveryRate === undefined ? undefined : { CDS_RR: recoveryRate };
}

function enabledTool(
  resolver: CoreResolver,
  name: BloombergToolName,
  creator: (resolver: CoreResolver) => BloombergTool,
): BloombergTool[] {
  return isToolDisabled(resolver.options, name) ? [] : [creator(resolver)];
}

function tickerSchema(): z.ZodType<TickerInput> {
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
    ticker: optionalString("One Bloomberg ticker for parse/contract validation operations."),
    tickers: stringArray("Bloomberg tickers to normalize or filter.").optional(),
  });
}

function futuresSchema(): z.ZodType<FuturesInput> {
  return z.object({
    asset: optionalString("Bloomberg asset class suffix, for example Comdty."),
    candidates: z
      .array(futuresCandidateSchema)
      .min(1)
      .optional()
      .describe("Candidate futures contracts."),
    contracts: z
      .array(stringPairSchema)
      .min(1)
      .optional()
      .describe("Contract pairs for validity filtering."),
    count: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Maximum number of futures candidates to generate."),
    cycle: optionalString("Futures cycle code to filter candidates by."),
    day: z.number().int().min(1).max(31).optional().describe("Day number for contract filtering."),
    freq: optionalString("Futures frequency/cycle hint."),
    genTicker: optionalString("Generic Bloomberg futures ticker."),
    month: z.number().int().min(1).max(12).optional().describe("Month number, 1-12."),
    monthCode: optionalString("Bloomberg futures month code, for example H."),
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
    prefix: optionalString("Futures ticker root prefix."),
    year: z
      .union([z.string().trim().min(1), z.number().int()])
      .optional()
      .describe("Contract year."),
  });
}

function cdxSchema(): z.ZodType<CdxInput> {
  return z.object({
    genTicker: optionalString("Generic CDX ticker."),
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
    ticker: optionalString("CDX ticker."),
  });
}

function currencySchema(): z.ZodType<CurrencyInput> {
  return z.object({
    ccy1: optionalString("First ISO currency code."),
    ccy2: optionalString("Second ISO currency code."),
    currencies: stringArray("ISO currency codes.").optional(),
    fromCcy: optionalString("Source ISO currency code."),
    operation: z
      .enum(["build_fx_pair", "same_currency", "currencies_needing_conversion"])
      .describe("Currency helper operation to run."),
    target: optionalString("Target ISO currency code."),
    toCcy: optionalString("Destination ISO currency code."),
  });
}

function bqlBuilderSchema(): z.ZodType<BqlBuilderInput> {
  return z.object({
    activeOnly: z.boolean().optional().describe("Restrict corporate bond query to active bonds."),
    ccy: optionalString("Currency filter for corporate bond query."),
    equityTicker: optionalString("Equity ticker for preferreds query."),
    etfTicker: optionalString("ETF ticker for holdings query."),
    extraFields: stringArray("Extra BQL fields to include.").optional(),
    operation: z
      .enum(["build_preferreds_query", "build_corporate_bonds_query", "build_etf_holdings_query"])
      .describe("BQL builder operation to run."),
    ticker: optionalString("Ticker for corporate bond query."),
  });
}

function marketSessionSchema(): z.ZodType<MarketSessionInput> {
  return z.object({
    countryIso: optionalString("ISO country code for timezone inference."),
    date: optionalString("Date for UTC session conversion, YYYY-MM-DD or YYYYMMDD."),
    dayEnd: optionalString("Exchange day end time, for example 16:00."),
    dayStart: optionalString("Exchange day start time, for example 09:30."),
    endDate: optionalString("Optional end date."),
    endDatetime: optionalString("Optional end datetime."),
    endTime: optionalString("Session end time, for example 16:00."),
    exchCode: optionalString("Bloomberg exchange code."),
    exchangeTz: optionalString("IANA exchange timezone."),
    mic: optionalString("Market Identifier Code."),
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
    startDate: optionalString("Optional start date."),
    startDatetime: optionalString("Optional start datetime."),
    startTime: optionalString("Session start time, for example 09:30."),
    ticker: optionalString("Ticker for exchange override lookup."),
  });
}

function yasOverridesSchema(): z.ZodType<YasOverridesInput> {
  return z.object({
    benchmark: optionalString("Optional YAS benchmark."),
    price: z.number().optional().describe("YAS price override."),
    settleDt: optionalString("YAS settlement date."),
    spread: z.number().optional().describe("YAS spread override."),
    yieldType: z.number().int().optional().describe("YAS yield type override."),
    yieldVal: z.number().optional().describe("YAS yield value override."),
  });
}

function constantsSchema(): z.ZodType<ConstantsInput> {
  return z.object({
    code: optionalString("Month code."),
    dateStr: optionalString("Date string to parse."),
    day: z.number().int().min(1).max(31).optional().describe("Day number."),
    dvdType: optionalString("Dividend type code or label."),
    fmt: optionalString("Date output format."),
    month: z.number().int().min(1).max(12).optional().describe("Month number."),
    monthName: optionalString("Month name."),
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

function columnsSchema(): z.ZodType<ColumnsInput> {
  return z.object({
    columns: stringArray("Column names to rename.").optional(),
    dataColumns: stringArray("Earnings data column names.").optional(),
    headerRow: z
      .array(stringPairSchema)
      .min(1)
      .optional()
      .describe("Earnings header row key/value pairs."),
    operation: z
      .enum(["rename_dividend_columns", "rename_etf_columns", "build_earning_header_rename"])
      .describe("Column helper operation to run."),
  });
}

function calculateSchema(): z.ZodType<CalculateInput> {
  return z.object({
    levels: z.array(z.number().nullable()).min(1).describe("Reference level values."),
    operation: z
      .literal("calculate_level_percentages")
      .describe("Numeric helper operation to run."),
    values: z.array(z.number().nullable()).min(1).describe("Observed values."),
  });
}

function extTickerWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_ticker" satisfies BloombergToolName;
  return tool(
    async (input: TickerInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "parse_ticker":
            return resultString(
              resolver,
              name,
              core.ext.parseTicker(requireString(name, args, "ticker")),
            );
          case "normalize_tickers":
            return resultString(
              resolver,
              name,
              core.ext.normalizeTickers(requireStringArray(name, args, "tickers")),
            );
          case "filter_equity_tickers":
            return resultString(
              resolver,
              name,
              core.ext.filterEquityTickers(requireStringArray(name, args, "tickers")),
            );
          case "is_specific_contract":
            return resultString(
              resolver,
              name,
              core.ext.isSpecificContract(requireString(name, args, "ticker")),
            );
          case "validate_generic_ticker": {
            const ticker = requireString(name, args, "ticker");
            core.ext.validateGenericTicker(ticker);
            return resultString(resolver, name, { ticker, valid: true });
          }
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_TICKER_DESCRIPTION, name, schema: tickerSchema() },
  );
}

function extFuturesWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_futures" satisfies BloombergToolName;
  return tool(
    async (input: FuturesInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "build_futures_ticker":
            return resultString(
              resolver,
              name,
              core.ext.buildFuturesTicker(
                requireString(name, args, "prefix"),
                requireString(name, args, "monthCode"),
                requireYearString(name, args, "year"),
                requireString(name, args, "asset"),
              ),
            );
          case "generate_candidates":
            return resultString(
              resolver,
              name,
              core.ext.generateFuturesCandidates(
                requireString(name, args, "genTicker"),
                requireInteger(name, args, "year"),
                requireInteger(name, args, "month"),
                requireInteger(name, args, "day"),
                input.freq,
                input.count,
              ),
            );
          case "contract_index":
            return resultString(
              resolver,
              name,
              core.ext.contractIndex(requireString(name, args, "genTicker")),
            );
          case "filter_candidates_by_cycle":
            if (input.candidates === undefined) {
              throw new TypeError(`${name}: candidates is required`);
            }
            return resultString(
              resolver,
              name,
              core.ext.filterCandidatesByCycle(
                input.candidates,
                requireString(name, args, "cycle"),
              ),
            );
          case "filter_valid_contracts":
            if (input.contracts === undefined) {
              throw new TypeError(`${name}: contracts is required`);
            }
            return resultString(
              resolver,
              name,
              core.ext.filterValidContracts(
                input.contracts,
                requireInteger(name, args, "year"),
                requireInteger(name, args, "month"),
                requireInteger(name, args, "day"),
              ),
            );
          case "get_futures_months":
            return resultString(resolver, name, core.ext.getFuturesMonths());
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_FUTURES_DESCRIPTION, name, schema: futuresSchema() },
  );
}

function extCdxWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_cdx" satisfies BloombergToolName;
  return tool(
    async (input: CdxInput): Promise<string> => {
      try {
        const args = asRecord(input);
        if (
          input.operation === "cdx_info" ||
          input.operation === "cdx_pricing" ||
          input.operation === "cdx_risk"
        ) {
          const engine = await resolver.getEngine();
          const ticker = requireString(name, args, "ticker");
          const fields =
            input.operation === "cdx_info"
              ? CDX_INFO_FIELDS
              : input.operation === "cdx_pricing"
                ? CDX_PRICING_FIELDS
                : CDX_RISK_FIELDS;
          const result = await engine.bdp([ticker], fields, {
            backend: "json",
            overrides: recoveryOverrides(input.recoveryRate),
          });
          return resultString(resolver, name, result);
        }
        const core = await resolver.getCore();
        switch (input.operation) {
          case "parse_cdx_ticker":
            return resultString(
              resolver,
              name,
              core.ext.parseCdxTicker(requireString(name, args, "ticker")),
            );
          case "previous_cdx_series":
            return resultString(
              resolver,
              name,
              core.ext.previousCdxSeries(requireString(name, args, "ticker")),
            );
          case "cdx_gen_to_specific":
            return resultString(
              resolver,
              name,
              core.ext.cdxGenToSpecific(
                requireString(name, args, "genTicker"),
                requireInteger(name, args, "series"),
              ),
            );
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_CDX_DESCRIPTION, name, schema: cdxSchema() },
  );
}

function extCurrencyWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_currency" satisfies BloombergToolName;
  return tool(
    async (input: CurrencyInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "build_fx_pair":
            return resultString(
              resolver,
              name,
              core.ext.buildFxPair(
                requireString(name, args, "fromCcy"),
                requireString(name, args, "toCcy"),
              ),
            );
          case "same_currency":
            return resultString(
              resolver,
              name,
              core.ext.sameCurrency(
                requireString(name, args, "ccy1"),
                requireString(name, args, "ccy2"),
              ),
            );
          case "currencies_needing_conversion":
            return resultString(
              resolver,
              name,
              core.ext.currenciesNeedingConversion(
                requireStringArray(name, args, "currencies"),
                requireString(name, args, "target"),
              ),
            );
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_CURRENCY_DESCRIPTION, name, schema: currencySchema() },
  );
}

function extBqlBuilderWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_bql_builder" satisfies BloombergToolName;
  return tool(
    async (input: BqlBuilderInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "build_preferreds_query":
            return resultString(
              resolver,
              name,
              core.ext.buildPreferredsQuery(
                requireString(name, args, "equityTicker"),
                input.extraFields,
              ),
            );
          case "build_corporate_bonds_query":
            return resultString(
              resolver,
              name,
              core.ext.buildCorporateBondsQuery(
                requireString(name, args, "ticker"),
                input.ccy,
                input.extraFields,
                input.activeOnly,
              ),
            );
          case "build_etf_holdings_query":
            return resultString(
              resolver,
              name,
              core.ext.buildEtfHoldingsQuery(
                requireString(name, args, "etfTicker"),
                input.extraFields,
              ),
            );
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_BQL_BUILDER_DESCRIPTION, name, schema: bqlBuilderSchema() },
  );
}

function extMarketSessionWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_market_session" satisfies BloombergToolName;
  return tool(
    async (input: MarketSessionInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "derive_sessions":
            return resultString(
              resolver,
              name,
              core.ext.deriveSessions(
                requireString(name, args, "dayStart"),
                requireString(name, args, "dayEnd"),
                input.mic,
                input.exchCode,
              ),
            );
          case "get_market_rule":
            return resultString(resolver, name, core.ext.getMarketRule(input.mic, input.exchCode));
          case "infer_timezone":
            return resultString(
              resolver,
              name,
              core.ext.inferTimezone(requireString(name, args, "countryIso")),
            );
          case "session_times_to_utc":
            return resultString(
              resolver,
              name,
              core.ext.sessionTimesToUtc(
                requireString(name, args, "startTime"),
                requireString(name, args, "endTime"),
                requireString(name, args, "exchangeTz"),
                requireString(name, args, "date"),
              ),
            );
          case "default_turnover_dates":
            return resultString(
              resolver,
              name,
              core.ext.defaultTurnoverDates(input.startDate, input.endDate),
            );
          case "default_bqr_datetimes":
            return resultString(
              resolver,
              name,
              core.ext.defaultBqrDatetimes(input.startDatetime, input.endDatetime),
            );
          case "get_exchange_override":
            return resultString(
              resolver,
              name,
              core.ext.getExchangeOverride(requireString(name, args, "ticker")),
            );
          case "list_exchange_overrides":
            return resultString(resolver, name, core.ext.listExchangeOverrides());
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_MARKET_SESSION_DESCRIPTION, name, schema: marketSessionSchema() },
  );
}

function extYasOverridesWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_yas_overrides" satisfies BloombergToolName;
  return tool(
    async (input: YasOverridesInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        return resultString(
          resolver,
          name,
          core.ext.buildYasOverrides(
            input.settleDt,
            input.yieldType,
            input.spread,
            input.yieldVal,
            input.price,
            input.benchmark,
          ),
        );
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_YAS_OVERRIDES_DESCRIPTION, name, schema: yasOverridesSchema() },
  );
}

function extConstantsWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_constants" satisfies BloombergToolName;
  return tool(
    async (input: ConstantsInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "parse_date":
            return resultString(
              resolver,
              name,
              core.ext.parseDate(requireString(name, args, "dateStr")),
            );
          case "fmt_date":
            return resultString(
              resolver,
              name,
              core.ext.fmtDate(
                requireInteger(name, args, "year"),
                requireInteger(name, args, "month"),
                requireInteger(name, args, "day"),
                input.fmt,
              ),
            );
          case "get_month_code":
            return resultString(
              resolver,
              name,
              core.ext.getMonthCode(requireString(name, args, "monthName")),
            );
          case "get_month_name":
            return resultString(
              resolver,
              name,
              core.ext.getMonthName(requireString(name, args, "code")),
            );
          case "get_futures_months":
            return resultString(resolver, name, core.ext.getFuturesMonths());
          case "get_dvd_type":
            return resultString(
              resolver,
              name,
              core.ext.getDvdType(requireString(name, args, "dvdType")),
            );
          case "get_dvd_types":
            return resultString(resolver, name, core.ext.getDvdTypes());
          case "get_dvd_cols":
            return resultString(resolver, name, core.ext.getDvdCols());
          case "get_etf_cols":
            return resultString(resolver, name, core.ext.getEtfCols());
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_CONSTANTS_DESCRIPTION, name, schema: constantsSchema() },
  );
}

function extColumnsWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_columns" satisfies BloombergToolName;
  return tool(
    async (input: ColumnsInput): Promise<string> => {
      try {
        const core = await resolver.getCore();
        const args = asRecord(input);
        switch (input.operation) {
          case "rename_dividend_columns":
            return resultString(
              resolver,
              name,
              core.ext.renameDividendColumns(requireStringArray(name, args, "columns")),
            );
          case "rename_etf_columns":
            return resultString(
              resolver,
              name,
              core.ext.renameEtfColumns(requireStringArray(name, args, "columns")),
            );
          case "build_earning_header_rename":
            if (input.headerRow === undefined) {
              throw new TypeError(`${name}: headerRow is required`);
            }
            return resultString(
              resolver,
              name,
              core.ext.buildEarningHeaderRename(
                input.headerRow,
                requireStringArray(name, args, "dataColumns"),
              ),
            );
        }
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_COLUMNS_DESCRIPTION, name, schema: columnsSchema() },
  );
}

function extCalculateWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_ext_calculate" satisfies BloombergToolName;
  return tool(
    async (input: CalculateInput): Promise<string> => {
      try {
        if (input.values.length !== input.levels.length) {
          throw new TypeError(`${name}: values and levels must have the same length`);
        }
        const core = await resolver.getCore();
        return resultString(
          resolver,
          name,
          core.ext.calculateLevelPercentages(input.values, input.levels),
        );
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    { description: EXT_CALCULATE_DESCRIPTION, name, schema: calculateSchema() },
  );
}

export function createExtTickerTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extTickerWithResolver(createCoreResolver(options));
}

export function createExtFuturesTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extFuturesWithResolver(createCoreResolver(options));
}

export function createExtCdxTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extCdxWithResolver(createCoreResolver(options));
}

export function createExtCurrencyTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extCurrencyWithResolver(createCoreResolver(options));
}

export function createExtBqlBuilderTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extBqlBuilderWithResolver(createCoreResolver(options));
}

export function createExtMarketSessionTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extMarketSessionWithResolver(createCoreResolver(options));
}

export function createExtYasOverridesTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extYasOverridesWithResolver(createCoreResolver(options));
}

export function createExtConstantsTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extConstantsWithResolver(createCoreResolver(options));
}

export function createExtColumnsTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extColumnsWithResolver(createCoreResolver(options));
}

export function createExtCalculateTool(options: BloombergToolsOptions = {}): BloombergTool {
  return extCalculateWithResolver(createCoreResolver(options));
}

export function createBloombergExtToolsForResolver(resolver: CoreResolver): BloombergTool[] {
  return [
    ...enabledTool(resolver, "xbbg_ext_ticker", extTickerWithResolver),
    ...enabledTool(resolver, "xbbg_ext_futures", extFuturesWithResolver),
    ...enabledTool(resolver, "xbbg_ext_cdx", extCdxWithResolver),
    ...enabledTool(resolver, "xbbg_ext_currency", extCurrencyWithResolver),
    ...enabledTool(resolver, "xbbg_ext_bql_builder", extBqlBuilderWithResolver),
    ...enabledTool(resolver, "xbbg_ext_market_session", extMarketSessionWithResolver),
    ...enabledTool(resolver, "xbbg_ext_yas_overrides", extYasOverridesWithResolver),
    ...enabledTool(resolver, "xbbg_ext_constants", extConstantsWithResolver),
    ...enabledTool(resolver, "xbbg_ext_columns", extColumnsWithResolver),
    ...enabledTool(resolver, "xbbg_ext_calculate", extCalculateWithResolver),
  ];
}

export function createBloombergExtTools(options: BloombergToolsOptions = {}): BloombergTool[] {
  return createBloombergExtToolsForResolver(createCoreResolver(options));
}
