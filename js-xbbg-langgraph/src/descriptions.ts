import type { BloombergToolsOptions } from "./options";

export const BLOOMBERG_TOOL_INSTRUCTIONS = [
  "Use Bloomberg tools only for server-side Bloomberg data access through @xbbg/core.",
  "Ask a clarifying question before calling a tool when the ticker, field mnemonic, date range, currency, periodicity, or intraday interval is ambiguous.",
  "Do not invent Bloomberg tickers or field mnemonics. Use xbbg_bflds first when field names are uncertain.",
  "Use xbbg_ext_ticker, xbbg_ext_futures, xbbg_ext_currency, xbbg_ext_bql_builder, and xbbg_ext_market_session to normalize inputs or reason about market conventions before live Bloomberg calls.",
  "Keep requests bounded: prefer a small number of securities, fields, rows, and a specific date range.",
  "Use xbbg_bdp for current/reference point-in-time fields; xbbg_bdh for historical time series with explicit start and end dates; xbbg_bds for one bulk/table field; xbbg_bdib for intraday bars with explicit start/end/interval; xbbg_bql only for BQL-shaped questions; xbbg_bsrch only for Bloomberg search-grid workflows.",
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
  const lines = [
    "Use Bloomberg tools only for server-side Bloomberg data access through @xbbg/core.",
    "Ask a clarifying question before calling a tool when the ticker, field mnemonic, date range, currency, periodicity, or intraday interval is ambiguous.",
    "Do not invent Bloomberg tickers or field mnemonics. Use xbbg_bflds first when field names are uncertain.",
  ];
  if (includeExtensionGuidance) {
    lines.push(
      "Use xbbg extension helper tools to normalize tickers, build field/query inputs, check currencies, and reason about market sessions before live Bloomberg calls.",
    );
  }
  if (includeLimitReminder) {
    lines.push(
      "Keep Bloomberg requests bounded and prefer explicit dates, intervals, fields, and securities.",
    );
  }
  return lines.join("\n");
}

export const BDP_DESCRIPTION =
  'Bloomberg reference data for current or point-in-time fields such as PX_LAST, NAME, or CUR_MKT_CAP. Use for a small bounded list of fully qualified securities. Example: securities ["AAPL US Equity"], fields ["PX_LAST"].';

export const BDH_DESCRIPTION =
  'Bloomberg historical time series. Requires explicit start and end dates; ask before using if the date range or periodicity is ambiguous. Example: securities ["AAPL US Equity"], fields ["PX_LAST"], start "2024-01-01", end "2024-01-31".';

export const BDS_DESCRIPTION =
  'Bloomberg bulk/table reference data such as index members. Requires exactly one bulk field, not a field list. Example: securities ["SPX Index"], field "INDX_MEMBERS".';

export const BDIB_DESCRIPTION =
  'Bloomberg intraday bars. Requires one ticker plus explicit ISO start/end datetimes and a positive interval in minutes. Example: ticker "AAPL US Equity", start "2024-01-31T09:30:00-05:00", end "2024-01-31T16:00:00-05:00", interval 5.';

export const BQL_DESCRIPTION =
  "Bloomberg Query Language. Use only when the user asks for BQL or the request is naturally expressed as BQL. Keep queries short and bounded. Example query: get(px_last) for([AAPL US Equity]).";

export const BSRCH_DESCRIPTION =
  'Bloomberg search/grid request. Use for saved-search or ExcelGetGrid-style Bloomberg searches, not ordinary security lookup. Example searchSpec "COMDTY:NG".';

export const BFLDS_DESCRIPTION =
  'Bloomberg field metadata and field search. Use first when a field mnemonic is uncertain. Provide exactly one of fields or searchSpec. Example: fields ["PX_LAST"] or searchSpec "last price".';

export const EXT_TICKER_DESCRIPTION =
  "Bloomberg ticker helpers for parsing, normalizing, validating generic tickers, and filtering equity tickers before live requests.";

export const EXT_FUTURES_DESCRIPTION =
  "Bloomberg futures helper operations for month codes, contract construction, generic ticker validation, candidate generation, and contract filtering.";

export const EXT_CDX_DESCRIPTION =
  "Bloomberg CDX helper operations for parsing CDX tickers, resolving generic series, and optional CDX info/pricing/risk lookups.";

export const EXT_CURRENCY_DESCRIPTION =
  "Currency helpers for Bloomberg workflows: build FX pairs, test same-currency requests, and find currencies needing conversion.";

export const EXT_BQL_BUILDER_DESCRIPTION =
  "BQL query builders for preferreds, corporate bonds, and ETF holdings. Use to construct bounded BQL before xbbg_bql.";

export const EXT_MARKET_SESSION_DESCRIPTION =
  "Market session and timezone helpers for deriving exchange sessions, UTC windows, market rules, and exchange metadata.";

export const EXT_YAS_OVERRIDES_DESCRIPTION =
  "Build flat Bloomberg YAS override maps for fixed income requests.";

export const EXT_CONSTANTS_DESCRIPTION =
  "Static Bloomberg helper constants for futures months, dividend types, ETF/dividend columns, and date formatting.";

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
