//! Fixed income utilities for Bloomberg YAS (Yield & Spread Analysis).
//!
//! Provides the [YieldType] enum for Bloomberg YAS_YLD_FLAG override values
//! and the [build_yas_overrides] helper to construct YAS override tuples.

use std::fmt;
use std::str::FromStr;

use crate::error::ExtError;

/// Bloomberg YAS yield type flags for the YAS_YLD_FLAG override.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum YieldType {
    /// Yield to Maturity - assumes bond held to maturity.
    YTM = 1,
    /// Yield to Call - assumes bond called at first call date.
    YTC = 2,
    /// Yield to Refunding - assumes bond refunded at first refunding date.
    YTR = 3,
    /// Yield to Next Put - yield to next put date.
    YTP = 4,
    /// Yield to Worst - worst of next put, call, or maturity.
    YTW = 5,
    /// Yield to Worst Refunding - worst of maturity, refunding, or next put.
    YTWR = 6,
    /// Euro Yield to Worst - Euro worst of maturity, next call, or put.
    EYTW = 7,
    /// Euro Yield to Worst Refunding - Euro worst of YTWR.
    EYTWR = 8,
    /// Yield to Average Life - yield to average life at maturity.
    YTAL = 9,
}

impl YieldType {
    /// Parse a yield type from a string (case-insensitive).
    pub fn parse(s: &str) -> Result<Self, ExtError> {
        let upper = s.trim().to_uppercase();
        match upper.as_str() {
            "YTM" => Ok(Self::YTM),
            "YTC" => Ok(Self::YTC),
            "YTR" => Ok(Self::YTR),
            "YTP" => Ok(Self::YTP),
            "YTW" => Ok(Self::YTW),
            "YTWR" => Ok(Self::YTWR),
            "EYTW" => Ok(Self::EYTW),
            "EYTWR" => Ok(Self::EYTWR),
            "YTAL" => Ok(Self::YTAL),
            "YIELD TO MATURITY" => Ok(Self::YTM),
            "YIELD TO CALL" => Ok(Self::YTC),
            "YIELD TO REFUNDING" => Ok(Self::YTR),
            "YIELD TO PUT" | "YIELD TO NEXT PUT" => Ok(Self::YTP),
            "YIELD TO WORST" => Ok(Self::YTW),
            "YIELD TO WORST REFUNDING" => Ok(Self::YTWR),
            "EURO YIELD TO WORST" => Ok(Self::EYTW),
            "EURO YIELD TO WORST REFUNDING" => Ok(Self::EYTWR),
            "YIELD TO AVERAGE LIFE" => Ok(Self::YTAL),
            _ => Err(ExtError::UnknownYieldType(s.to_string())),
        }
    }

    /// Human-readable description of the yield type.
    pub fn description(&self) -> &'static str {
        match self {
            Self::YTM => "Yield to Maturity - assumes bond held to maturity",
            Self::YTC => "Yield to Call - assumes bond called at first call date",
            Self::YTR => "Yield to Refunding - assumes bond refunded at first refunding date",
            Self::YTP => "Yield to Next Put - yield to next put date",
            Self::YTW => "Yield to Worst - worst of next put, call, or maturity",
            Self::YTWR => "Yield to Worst Refunding - worst of maturity, refunding, or next put",
            Self::EYTW => "Euro Yield to Worst - Euro worst of maturity, next call, or put",
            Self::EYTWR => "Euro Yield to Worst Refunding - Euro worst of YTWR",
            Self::YTAL => "Yield to Average Life - yield to average life at maturity",
        }
    }

    /// Returns the Bloomberg integer flag value (1-9).
    pub fn as_flag_value(&self) -> u8 {
        *self as u8
    }
}

impl fmt::Display for YieldType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::YTM => write!(f, "YTM"),
            Self::YTC => write!(f, "YTC"),
            Self::YTR => write!(f, "YTR"),
            Self::YTP => write!(f, "YTP"),
            Self::YTW => write!(f, "YTW"),
            Self::YTWR => write!(f, "YTWR"),
            Self::EYTW => write!(f, "EYTW"),
            Self::EYTWR => write!(f, "EYTWR"),
            Self::YTAL => write!(f, "YTAL"),
        }
    }
}

impl FromStr for YieldType {
    type Err = ExtError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::parse(s)
    }
}

impl TryFrom<u8> for YieldType {
    type Error = ExtError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::YTM),
            2 => Ok(Self::YTC),
            3 => Ok(Self::YTR),
            4 => Ok(Self::YTP),
            5 => Ok(Self::YTW),
            6 => Ok(Self::YTWR),
            7 => Ok(Self::EYTW),
            8 => Ok(Self::EYTWR),
            9 => Ok(Self::YTAL),
            _ => Err(ExtError::UnknownYieldType(value.to_string())),
        }
    }
}

/// Build Bloomberg YAS (Yield & Spread Analysis) override tuples.
///
/// Returns a Vec of Bloomberg override key-value pairs.
/// Only includes entries for parameters that are Some.
pub fn build_yas_overrides(
    settle_dt: Option<&str>,
    yield_type: Option<YieldType>,
    spread: Option<f64>,
    yield_val: Option<f64>,
    price: Option<f64>,
    benchmark: Option<&str>,
) -> Vec<(String, String)> {
    let mut overrides = Vec::new();

    if let Some(dt) = settle_dt {
        overrides.push(("YAS_SETTLE_DT".to_string(), dt.to_string()));
    }
    if let Some(yt) = yield_type {
        overrides.push(("YAS_YLD_FLAG".to_string(), yt.as_flag_value().to_string()));
    }
    if let Some(s) = spread {
        overrides.push(("YAS_YLD_SPREAD".to_string(), s.to_string()));
    }
    if let Some(y) = yield_val {
        overrides.push(("YAS_BOND_YLD".to_string(), y.to_string()));
    }
    if let Some(p) = price {
        overrides.push(("YAS_BOND_PX".to_string(), p.to_string()));
    }
    if let Some(b) = benchmark {
        overrides.push(("YAS_BNCHMRK_BOND".to_string(), b.to_string()));
    }

    overrides
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_short_names() {
        assert_eq!(YieldType::parse("YTM").unwrap(), YieldType::YTM);
        assert_eq!(YieldType::parse("YTC").unwrap(), YieldType::YTC);
        assert_eq!(YieldType::parse("YTR").unwrap(), YieldType::YTR);
        assert_eq!(YieldType::parse("YTP").unwrap(), YieldType::YTP);
        assert_eq!(YieldType::parse("YTW").unwrap(), YieldType::YTW);
        assert_eq!(YieldType::parse("YTWR").unwrap(), YieldType::YTWR);
        assert_eq!(YieldType::parse("EYTW").unwrap(), YieldType::EYTW);
        assert_eq!(YieldType::parse("EYTWR").unwrap(), YieldType::EYTWR);
        assert_eq!(YieldType::parse("YTAL").unwrap(), YieldType::YTAL);
    }

    #[test]
    fn parse_full_names() {
        assert_eq!(YieldType::parse("yield to maturity").unwrap(), YieldType::YTM);
        assert_eq!(YieldType::parse("yield to call").unwrap(), YieldType::YTC);
        assert_eq!(YieldType::parse("yield to refunding").unwrap(), YieldType::YTR);
        assert_eq!(YieldType::parse("yield to put").unwrap(), YieldType::YTP);
        assert_eq!(YieldType::parse("yield to next put").unwrap(), YieldType::YTP);
        assert_eq!(YieldType::parse("yield to worst").unwrap(), YieldType::YTW);
        assert_eq!(YieldType::parse("yield to worst refunding").unwrap(), YieldType::YTWR);
        assert_eq!(YieldType::parse("euro yield to worst").unwrap(), YieldType::EYTW);
        assert_eq!(YieldType::parse("euro yield to worst refunding").unwrap(), YieldType::EYTWR);
        assert_eq!(YieldType::parse("yield to average life").unwrap(), YieldType::YTAL);
    }

    #[test]
    fn parse_case_insensitive() {
        assert_eq!(YieldType::parse("ytm").unwrap(), YieldType::YTM);
        assert_eq!(YieldType::parse("Ytm").unwrap(), YieldType::YTM);
        assert_eq!(YieldType::parse("  YTM  ").unwrap(), YieldType::YTM);
    }

    #[test]
    fn parse_invalid() {
        assert!(YieldType::parse("INVALID").is_err());
        assert!(YieldType::parse("").is_err());
    }

    #[test]
    fn flag_values() {
        assert_eq!(YieldType::YTM.as_flag_value(), 1);
        assert_eq!(YieldType::YTC.as_flag_value(), 2);
        assert_eq!(YieldType::YTR.as_flag_value(), 3);
        assert_eq!(YieldType::YTP.as_flag_value(), 4);
        assert_eq!(YieldType::YTW.as_flag_value(), 5);
        assert_eq!(YieldType::YTWR.as_flag_value(), 6);
        assert_eq!(YieldType::EYTW.as_flag_value(), 7);
        assert_eq!(YieldType::EYTWR.as_flag_value(), 8);
        assert_eq!(YieldType::YTAL.as_flag_value(), 9);
    }

    #[test]
    fn descriptions() {
        assert!(YieldType::YTM.description().contains("Maturity"));
        assert!(YieldType::YTC.description().contains("Call"));
        assert!(YieldType::YTW.description().contains("Worst"));
    }

    #[test]
    fn display_short_name() {
        assert_eq!(YieldType::YTM.to_string(), "YTM");
        assert_eq!(YieldType::EYTWR.to_string(), "EYTWR");
    }

    #[test]
    fn from_str_roundtrip() {
        for yt in [
            YieldType::YTM, YieldType::YTC, YieldType::YTR,
            YieldType::YTP, YieldType::YTW, YieldType::YTWR,
            YieldType::EYTW, YieldType::EYTWR, YieldType::YTAL,
        ] {
            let s = yt.to_string();
            assert_eq!(YieldType::from_str(&s).unwrap(), yt);
        }
    }

    #[test]
    fn try_from_u8() {
        assert_eq!(YieldType::try_from(1u8).unwrap(), YieldType::YTM);
        assert_eq!(YieldType::try_from(9u8).unwrap(), YieldType::YTAL);
        assert!(YieldType::try_from(0u8).is_err());
        assert!(YieldType::try_from(10u8).is_err());
    }

    #[test]
    fn build_yas_basic() {
        let ov = build_yas_overrides(Some("20240115"), Some(YieldType::YTM), None, None, None, None);
        assert_eq!(ov.len(), 2);
        assert!(ov.contains(&("YAS_SETTLE_DT".to_string(), "20240115".to_string())));
        assert!(ov.contains(&("YAS_YLD_FLAG".to_string(), "1".to_string())));
    }

    #[test]
    fn build_yas_price() {
        let ov = build_yas_overrides(None, None, None, None, Some(99.5), None);
        assert_eq!(ov.len(), 1);
        assert_eq!(ov[0].0, "YAS_BOND_PX");
        assert_eq!(ov[0].1, "99.5");
    }

    #[test]
    fn build_yas_empty() {
        let ov = build_yas_overrides(None, None, None, None, None, None);
        assert!(ov.is_empty());
    }

    #[test]
    fn build_yas_all() {
        let ov = build_yas_overrides(
            Some("20240115"), Some(YieldType::YTW),
            Some(50.0), Some(5.25), Some(99.5), Some("US912810SV17 Govt"),
        );
        assert_eq!(ov.len(), 6);
    }
}
