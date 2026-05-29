// Canonical CDX field bundles for the LangGraph CDX helpers.
//
// These mirror the field sets exported by @xbbg/core (CDX_INFO_FIELDS /
// CDX_PRICING_FIELDS / CDX_RISK_FIELDS). They are defined locally rather than
// imported from @xbbg/core because importing the core module eagerly loads its
// native addon, which requires the Bloomberg SDK runtime (libblpapi). That side
// effect breaks SDK-less environments such as unit tests and the npm publish
// validation gate. The current dependency range (@xbbg/core@^1.2.4) does not yet
// export these constants, so this list is the effective source of truth.
//
// Keep in sync with @xbbg/core's CDX field bundles. To source them from core
// directly in the future, bump the @xbbg/core dependency and load it lazily
// (e.g. via the async core-loader) so module evaluation never forces a native load.

export const CDX_INFO_FIELDS: readonly string[] = Object.freeze([
  "ROLLING_SERIES",
  "VERSION",
  "ON_THE_RUN_CURRENT_BD_INDICATOR",
  "CDS_FIRST_ACCRUAL_START_DATE",
  "NAME",
  "NUM_CURRENT_COMPANIES_CCY_TKR",
  "NUM_ORIG_COMPANIES_CRNCY_TKR",
  "PX_LAST",
]);

export const CDX_PRICING_FIELDS: readonly string[] = Object.freeze([
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

export const CDX_RISK_FIELDS: readonly string[] = Object.freeze([
  "SW_CNV_BPV",
  "SW_EQV_BPV",
  "CDS_SPREAD_MID_MODIFIED_DURATION",
  "CDS_SPREAD_MID_CONVEXITY",
  "RECOVERY_RATE_SEN",
  "CDS_RECOVERY_RT",
]);
