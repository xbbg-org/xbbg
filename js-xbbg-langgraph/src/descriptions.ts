import type { BloombergToolsOptions } from "./options";
const REQUIRED_TOOL_INSTRUCTIONS = [
  "# Bloomberg tool usage",
  "- Use these tools only for server-side Bloomberg data access through @xbbg/core. Never imply Bloomberg data was retrieved unless a tool call actually returned it.",
  "- Ask a clarifying question before calling a tool when any security identity, field mnemonic, date range, currency, periodicity, intraday interval, timezone, override, or universe is ambiguous.",
  "- Do not invent Bloomberg tickers, field mnemonics, overrides, or BQL functions. If the user gives a field description rather than a confident mnemonic, call xbbg_bflds first.",
  "",
  "## Security identifiers",
  "- Prefer fully qualified Bloomberg securities such as AAPL US Equity, SPX Index, or CDX IG CDSI GEN 5Y Corp when the user provides them.",
  "- For raw security identifiers, request or pass Bloomberg identifier syntax directly: /isin/{isin} for ISINs, for example /isin/US0378331005; /cusip/{cusip} for CUSIPs, for example /cusip/037833100.",
  "- Do not pass raw ISIN or CUSIP strings when the request is meant to identify a security. Do not use xbbg_bsrch as a replacement for a known ticker, ISIN, or CUSIP.",
  "- For dealer quote / BQR workflows, use xbbg_bqr with a fixed-income identifier plus a dealer quote source such as /isin/US037833FB15@MSG1 Corp. For raw intraday ticks, use xbbg_bdtick.",
  "",
  "## Core request tools",
  "- xbbg_bdp: current or reference point-in-time fields, e.g. PX_LAST, NAME, CUR_MKT_CAP. Use a small explicit securities list and a small explicit fields list. Use includeSecurityErrors only when the caller wants Bloomberg security errors in the response.",
  "- xbbg_bdh: historical daily or periodic time series. Always provide explicit start and end dates in YYYY-MM-DD or YYYYMMDD form. Ask before choosing periodicity, currency, fill behavior, adjustment overrides, or a wide output table.",
  "- xbbg_bds: Bloomberg bulk/table fields such as index members. Provide exactly one bulk field; do not use bds for ordinary multi-field reference data.",
  "- xbbg_bdib: intraday bars only. Provide one ticker, explicit ISO start/end datetimes, a positive interval in minutes, and timezone context when datetimes are naive. TRADE is the usual event type unless the user asks otherwise.",
  "- xbbg_bdtick: intraday tick data. Provide one ticker, explicit ISO start/end datetimes, and explicit eventTypes when not asking for TRADE ticks. Use includeBrokerCodes or includeConditionCodes only when those columns are needed.",
  "- xbbg_bql: BQL expressions only when the user asks for BQL or the request is naturally expressed as a bounded BQL query. Keep queries short, explicit, and scoped to the requested universe.",
  "- xbbg_bsrch: Bloomberg search-grid or saved-search workflows only, such as ExcelGetGrid-style searches. Do not use it for ordinary security lookup.",
  "- xbbg_bqr: Bloomberg Quote Request / dealer quotes. Prefer fixed-income ISIN inputs with a dealer quote source such as /isin/US037833FB15@MSG1 Corp, explicit start/end datetimes, and BID/ASK event types. includeBrokerCodes defaults to true.",
  "- xbbg_bflds: Bloomberg field metadata/search. Provide exactly one of fields or searchSpec; use searchSpec for natural-language field names and fields for known mnemonics.",
  "",
  "## BQL guidance",
  "- BQL is a complete Bloomberg Query Language expression sent as one query string; the tool does not assemble get/for/with clauses for you.",
  "- Basic shape: get(field1, field2) for(universe). Examples: get(px_last) for('AAPL US Equity') and get(px_last, volume) for(['IBM US Equity', 'AAPL US Equity']).",
  "- Use BQL for universe-oriented analytics and screens such as holdings('SPY US Equity'), members('SPX Index'), debt universes, filters with with(...), and date ranges such as with(dates=range(-5d, 0d)).",
  "- Prefer xbbg_ext_bql_builder instead of hand-writing BQL for supported workflows: preferred stocks, corporate bonds, and ETF holdings.",
  "- Do not use BQL just because the user asks for normal reference data; xbbg_bdp is simpler for current fields and xbbg_bdh is simpler for historical time series.",
  "",
  "## Output handling",
  "- Tool results are JSON envelopes with tool, rowCount, truncated, and data. Inspect rowCount and truncated before summarizing.",
  "- If a response is empty, truncated, or contains Bloomberg/security errors, say that directly. Do not fill gaps from memory or assumptions.",
] as const;

const OPTIONAL_EXTENSION_INSTRUCTIONS = [
  "",
  "## Extension helper tools",
  "- xbbg_ext_ticker: ticker hygiene before live calls. parse_ticker splits a Bloomberg ticker, normalize_tickers trims/canonicalizes lists, filter_equity_tickers keeps equity-like tickers, is_specific_contract checks futures specificity, and validate_generic_ticker rejects malformed generic futures tickers.",
  "- xbbg_ext_futures: futures contract construction and selection. Use build_futures_ticker for root/month/year/asset assembly, get_futures_months for month-code lookup, generate_candidates for generic-to-specific candidates, contract_index for generic contract rank, filter_candidates_by_cycle for HMUZ/quarterly cycles, and filter_valid_contracts to keep contracts valid for a date.",
  "- xbbg_ext_cdx: CDX ticker workflow support. Use parse_cdx_ticker to understand a CDX ticker, previous_cdx_series to roll back a series, cdx_gen_to_specific to resolve a generic CDX to a target series, and cdx_info/cdx_pricing/cdx_risk for predefined BDP field bundles. cdx_pricing and cdx_risk accept recoveryRate, which becomes the CDS_RR override.",
  "- xbbg_ext_currency: currency-planning helpers. build_fx_pair constructs the Bloomberg FX pair and conversion factor, same_currency avoids unnecessary conversion, and currencies_needing_conversion identifies which currencies differ from a target before requesting converted values.",
  "- xbbg_ext_bql_builder: safe BQL generators for common xbbg workflows. Use build_preferreds_query for preferred-stock discovery from an equity, build_corporate_bonds_query for company bond universes with optional currency/active filters, and build_etf_holdings_query for ETF constituents. Prefer these builders over hand-writing those BQL shapes.",
  "- xbbg_ext_market_session: exchange calendar/timezone support. derive_sessions turns day session times into session blocks, infer_timezone maps country codes to timezones, session_times_to_utc converts local sessions to UTC, get_market_rule gets MIC/exchange rules, default_turnover_dates and default_bqr_datetimes provide bounded defaults, and get/list_exchange_override inspect configured exchange metadata.",
  "- xbbg_ext_yas_overrides: builds flat YAS override maps for fixed-income requests. Use settleDt, yieldType, spread, yieldVal, price, and benchmark to request fields such as YAS_BOND_YLD, YAS_MOD_DUR, YAS_ZSPREAD, or YAS_BOND_PX through xbbg_bdp; this package does not expose a standalone YAS tool.",
  "- xbbg_ext_constants: static lookup/format helpers for date parsing/formatting, futures month code/name mappings, dividend type mappings, and known dividend/ETF output columns.",
  "- xbbg_ext_columns: post-processing helpers for Bloomberg-shaped tables. Use rename_dividend_columns, rename_etf_columns, or build_earning_header_rename when explaining or normalizing response column names after a request.",
  "- xbbg_ext_calculate: small numeric helper for Bloomberg workflows. calculate_level_percentages pairs observed values with levels; values and levels must have the same length.",
] as const;

const OPTIONAL_LIMIT_INSTRUCTIONS = [
  "",
  "## Request limits and inputs",
  "- Keep Bloomberg requests bounded: explicit securities, explicit fields, explicit dates, limited rows, and no broad exploratory pulls unless the user narrows the universe.",
  "- Respect configured tool limits for securities, fields, rows, string size, BQL length, and search spec length. Ask the user to narrow the request rather than exceeding them.",
  "- Use flat primitive overrides and kwargs only: string, number, or boolean values. Do not send nested objects, arrays, or inferred defaults as overrides.",
] as const;

export const BLOOMBERG_TOOL_INSTRUCTIONS = [
  ...REQUIRED_TOOL_INSTRUCTIONS,
  ...OPTIONAL_EXTENSION_INSTRUCTIONS,
  ...OPTIONAL_LIMIT_INSTRUCTIONS,
].join("\n");

export interface BloombergToolInstructionsOptions {
  readonly includeExtensionGuidance?: boolean;
  readonly includeLimitReminder?: boolean;
}

export function getBloombergToolInstructions(
  options: BloombergToolInstructionsOptions = {},
): string {
  const includeExtensionGuidance = options.includeExtensionGuidance ?? true;
  const includeLimitReminder = options.includeLimitReminder ?? true;
  const lines: string[] = [...REQUIRED_TOOL_INSTRUCTIONS];
  if (includeExtensionGuidance) {
    lines.push(...OPTIONAL_EXTENSION_INSTRUCTIONS);
  }
  if (includeLimitReminder) {
    lines.push(...OPTIONAL_LIMIT_INSTRUCTIONS);
  }
  return lines.join("\n");
}

export const BDP_DESCRIPTION =
  'Bloomberg reference data for current or point-in-time fields such as PX_LAST, NAME, or CUR_MKT_CAP. Use for a small bounded list of fully qualified securities. Use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs. Example: securities ["AAPL US Equity"], fields ["PX_LAST"].';

export const BDH_DESCRIPTION =
  'Bloomberg historical time series. Requires explicit start and end dates; ask before using if the date range or periodicity is ambiguous. Use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs. Example: securities ["AAPL US Equity"], fields ["PX_LAST"], start "2024-01-01", end "2024-01-31".';

export const BDS_DESCRIPTION =
  'Bloomberg bulk/table reference data such as index members. Requires exactly one bulk field, not a field list. Use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs. Example: securities ["SPX Index"], field "INDX_MEMBERS".';

export const BDIB_DESCRIPTION =
  'Bloomberg intraday bars. Requires one ticker plus explicit ISO start/end datetimes and a positive interval in minutes. Use /isin/{isin} for ISINs and /cusip/{cusip} for CUSIPs. Example: ticker "AAPL US Equity", start "2024-01-31T09:30:00-05:00", end "2024-01-31T16:00:00-05:00", interval 5.';

export const BDTICK_DESCRIPTION =
  'Bloomberg intraday tick data. Requires one ticker plus explicit ISO start/end datetimes. Defaults eventTypes to ["TRADE"]; use ["BID", "ASK"] for quote ticks and includeBrokerCodes/includeConditionCodes only when needed.';

export const BQL_DESCRIPTION =
  "Bloomberg Query Language expression sent as one complete query string. Use for bounded universe analytics such as get(px_last) for('AAPL US Equity'), get(px_last, volume) for(['IBM US Equity', 'AAPL US Equity']), holdings('SPY US Equity'), members('SPX Index'), filters with with(...), or dates=range(...). Prefer xbbg_bdp/xbbg_bdh for simple reference or historical requests.";

export const BSRCH_DESCRIPTION =
  'Bloomberg search/grid request. Use for saved-search or ExcelGetGrid-style Bloomberg searches, not ordinary security lookup. Example searchSpec "COMDTY:NG".';

export const BQR_DESCRIPTION =
  'Bloomberg Quote Request / dealer quotes. Use for fixed-income dealer quote ticks, preferably with an ISIN plus dealer source such as "/isin/US037833FB15@MSG1 Corp"; requires explicit ISO start/end datetimes. Defaults eventTypes to ["BID", "ASK"] and includeBrokerCodes to true.';

export const BFLDS_DESCRIPTION =
  'Bloomberg field metadata and field search. Use first when a field mnemonic is uncertain. Provide exactly one of fields or searchSpec. Example: fields ["PX_LAST"] or searchSpec "last price".';

export const EXT_TICKER_DESCRIPTION =
  "Ticker hygiene helpers: parse_ticker, normalize_tickers, filter_equity_tickers, is_specific_contract, and validate_generic_ticker.";

export const EXT_FUTURES_DESCRIPTION =
  "Futures helpers for contract construction and selection: build_futures_ticker, generate_candidates, contract_index, filter_candidates_by_cycle, filter_valid_contracts, and get_futures_months.";

export const EXT_CDX_DESCRIPTION =
  "CDX helpers for parsing, series rolling/resolution, and predefined info/pricing/risk BDP field bundles.";

export const EXT_CURRENCY_DESCRIPTION =
  "Currency planning helpers: build FX pairs, test same-currency requests, and find currencies needing conversion.";

export const EXT_BQL_BUILDER_DESCRIPTION =
  "BQL builders for preferred stocks, corporate bonds, and ETF holdings. Prefer to construct those bounded BQL shapes before xbbg_bql.";

export const EXT_MARKET_SESSION_DESCRIPTION =
  "Market session and timezone helpers for deriving sessions, UTC windows, market rules, exchange metadata, turnover defaults, and BQR datetime defaults.";

export const EXT_YAS_OVERRIDES_DESCRIPTION =
  "Build flat Bloomberg YAS override maps for fixed income fields such as YAS_BOND_YLD, YAS_MOD_DUR, YAS_ZSPREAD, or YAS_BOND_PX.";

export const EXT_CONSTANTS_DESCRIPTION =
  "Static Bloomberg helper constants for date parsing/formatting, futures months, dividend types, and ETF/dividend columns.";

export const EXT_COLUMNS_DESCRIPTION =
  "Column rename helpers for dividend, ETF, and earnings-shaped Bloomberg responses.";

export const EXT_CALCULATE_DESCRIPTION =
  "Small numeric helper operations for Bloomberg workflows, including level percentage calculations.";

export function describeConfiguredLimits(options: BloombergToolsOptions): string {
  const parts: string[] = [];
  if (options.maxSecurities !== undefined) {
    parts.push(`maxSecurities=${options.maxSecurities}`);
  }
  if (options.maxFields !== undefined) {
    parts.push(`maxFields=${options.maxFields}`);
  }
  if (options.maxRows !== undefined) {
    parts.push(`maxRows=${options.maxRows}`);
  }
  return parts.length === 0 ? "default request limits" : parts.join(", ");
}
