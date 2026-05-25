import * as xbbgCore from "@xbbg/core";

interface CoreCdxFields {
  readonly CDX_INFO_FIELDS?: readonly string[];
  readonly CDX_PRICING_FIELDS?: readonly string[];
  readonly CDX_RISK_FIELDS?: readonly string[];
}

const coreCdxFields = xbbgCore as CoreCdxFields;

const FALLBACK_CDX_INFO_FIELDS = Object.freeze([
  "ROLLING_SERIES",
  "VERSION",
  "ON_THE_RUN_CURRENT_BD_INDICATOR",
  "CDS_FIRST_ACCRUAL_START_DATE",
  "NAME",
  "NUM_CURRENT_COMPANIES_CCY_TKR",
  "NUM_ORIG_COMPANIES_CRNCY_TKR",
  "PX_LAST",
]);

const FALLBACK_CDX_PRICING_FIELDS = Object.freeze([
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

const FALLBACK_CDX_RISK_FIELDS = Object.freeze([
  "SW_CNV_BPV",
  "SW_EQV_BPV",
  "CDS_SPREAD_MID_MODIFIED_DURATION",
  "CDS_SPREAD_MID_CONVEXITY",
  "RECOVERY_RATE_SEN",
  "CDS_RECOVERY_RT",
]);

export const CDX_INFO_FIELDS = Object.freeze(
  coreCdxFields.CDX_INFO_FIELDS ?? FALLBACK_CDX_INFO_FIELDS,
);

export const CDX_PRICING_FIELDS = Object.freeze(
  coreCdxFields.CDX_PRICING_FIELDS ?? FALLBACK_CDX_PRICING_FIELDS,
);

export const CDX_RISK_FIELDS = Object.freeze(
  coreCdxFields.CDX_RISK_FIELDS ?? FALLBACK_CDX_RISK_FIELDS,
);
