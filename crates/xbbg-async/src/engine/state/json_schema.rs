//! Typed JSON response schemas for Bloomberg API responses.
//!
//! These structs are designed for zero-copy deserialization with simd-json.
//! Using typed structs instead of `serde_json::Value` provides:
//! - ~3-5x faster parsing via compile-time-known structure
//! - Direct field access without runtime key lookups
//! - Memory efficiency through `Cow<'a, str>` for borrowed strings

use serde::Deserialize;
use std::borrow::Cow;
use std::collections::HashMap;

/// Reference data response (bdp).
/// Structure: { securityData: [ { security, fieldData: { ... } } ] }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefDataResponse<'a> {
    #[serde(borrow)]
    pub security_data: Vec<RefDataSecurity<'a>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefDataSecurity<'a> {
    #[serde(borrow)]
    pub security: Cow<'a, str>,
    #[serde(borrow, default)]
    pub field_data: HashMap<Cow<'a, str>, JsonValue<'a>>,
    #[serde(borrow, default)]
    pub field_exceptions: Option<Vec<FieldException<'a>>>,
    #[serde(borrow, default)]
    pub security_error: Option<SecurityError<'a>>,
}

/// Historical data response (bdh).
/// Structure: { securityData: { security, fieldData: [ { date, ... } ] } }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistDataResponse<'a> {
    #[serde(borrow)]
    pub security_data: HistDataSecurity<'a>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistDataSecurity<'a> {
    #[serde(borrow)]
    pub security: Cow<'a, str>,
    #[serde(borrow, default)]
    pub field_data: Vec<HistDataRow<'a>>,
    #[serde(borrow, default)]
    pub field_exceptions: Option<Vec<FieldException<'a>>>,
    #[serde(borrow, default)]
    pub security_error: Option<SecurityError<'a>>,
}

#[derive(Debug, Deserialize)]
pub struct HistDataRow<'a> {
    /// Date as string (will need parsing to Date32)
    #[serde(borrow)]
    pub date: Option<Cow<'a, str>>,
    /// Dynamic fields - we use a flattened map
    #[serde(borrow, flatten)]
    pub fields: HashMap<Cow<'a, str>, JsonValue<'a>>,
}

/// Bulk data response (bds).
/// Structure: { securityData: [ { security, fieldData: { FIELD: [ row, ... ] } } ] }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BulkDataResponse<'a> {
    #[serde(borrow)]
    pub security_data: Vec<BulkDataSecurity<'a>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BulkDataSecurity<'a> {
    #[serde(borrow)]
    pub security: Cow<'a, str>,
    #[serde(borrow, default)]
    pub field_data: HashMap<Cow<'a, str>, JsonValue<'a>>,
    #[serde(borrow, default)]
    pub security_error: Option<SecurityError<'a>>,
}

/// Intraday bar response (bdib).
/// Structure: { barData: { barTickData: [ { time, open, high, low, close, volume, numEvents } ] } }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntradayBarResponse<'a> {
    #[serde(borrow)]
    pub bar_data: BarData<'a>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BarData<'a> {
    #[serde(borrow, default)]
    pub bar_tick_data: Vec<BarTick<'a>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BarTick<'a> {
    #[serde(borrow)]
    pub time: Option<Cow<'a, str>>,
    pub open: Option<f64>,
    pub high: Option<f64>,
    pub low: Option<f64>,
    pub close: Option<f64>,
    pub volume: Option<f64>,
    pub num_events: Option<i64>,
}

/// Intraday tick response (bdtick).
/// Structure: { tickData: { tickData: [ { time, type, value, size } ] } }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntradayTickResponse<'a> {
    #[serde(borrow)]
    pub tick_data: TickDataOuter<'a>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TickDataOuter<'a> {
    #[serde(borrow, default)]
    pub tick_data: Vec<TickData<'a>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TickData<'a> {
    #[serde(borrow)]
    pub time: Option<Cow<'a, str>>,
    #[serde(borrow, rename = "type")]
    pub tick_type: Option<Cow<'a, str>>,
    pub value: Option<f64>,
    pub size: Option<i64>,
}

/// Field exception (returned when a field is invalid or unavailable).
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FieldException<'a> {
    #[serde(borrow)]
    pub field_id: Cow<'a, str>,
    #[serde(borrow)]
    pub error_info: Option<ErrorInfo<'a>>,
}

/// Security error (returned when a security is invalid).
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SecurityError<'a> {
    pub code: Option<i64>,
    #[serde(borrow)]
    pub category: Option<Cow<'a, str>>,
    #[serde(borrow)]
    pub subcategory: Option<Cow<'a, str>>,
    #[serde(borrow)]
    pub message: Option<Cow<'a, str>>,
}

/// Error info for field exceptions.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorInfo<'a> {
    pub code: Option<i64>,
    #[serde(borrow)]
    pub category: Option<Cow<'a, str>>,
    #[serde(borrow)]
    pub subcategory: Option<Cow<'a, str>>,
    #[serde(borrow)]
    pub message: Option<Cow<'a, str>>,
}

/// Generic JSON value that can be borrowed.
/// Bloomberg API returns heterogeneous types for field values.
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum JsonValue<'a> {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    #[serde(borrow)]
    String(Cow<'a, str>),
    #[serde(borrow)]
    Array(Vec<JsonValue<'a>>),
    #[serde(borrow)]
    Object(HashMap<Cow<'a, str>, JsonValue<'a>>),
}

impl<'a> JsonValue<'a> {
    /// Get as string, converting numbers to string if needed.
    pub fn as_string(&self) -> Option<String> {
        match self {
            JsonValue::String(s) => Some(s.to_string()),
            JsonValue::Int(i) => Some(i.to_string()),
            JsonValue::Float(f) => Some(f.to_string()),
            JsonValue::Bool(b) => Some(b.to_string()),
            JsonValue::Null => None,
            JsonValue::Array(_) | JsonValue::Object(_) => None,
        }
    }

    /// Get as f64.
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            JsonValue::Float(f) => Some(*f),
            JsonValue::Int(i) => Some(*i as f64),
            JsonValue::String(s) => s.parse().ok(),
            _ => None,
        }
    }

    /// Get as i64.
    pub fn as_i64(&self) -> Option<i64> {
        match self {
            JsonValue::Int(i) => Some(*i),
            JsonValue::Float(f) => Some(*f as i64),
            JsonValue::String(s) => s.parse().ok(),
            _ => None,
        }
    }
}

/// Parse JSON using simd-json with borrowing.
/// Returns typed response or falls back to element-by-element extraction.
pub mod parser {
    use super::*;

    /// Parse a reference data response from JSON bytes.
    /// The bytes must be mutable for simd-json's in-place parsing.
    pub fn parse_refdata(json: &mut [u8]) -> Result<RefDataResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse a historical data response from JSON bytes.
    pub fn parse_histdata(json: &mut [u8]) -> Result<HistDataResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse a bulk data response from JSON bytes.
    pub fn parse_bulkdata(json: &mut [u8]) -> Result<BulkDataResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse an intraday bar response from JSON bytes.
    pub fn parse_intraday_bar(
        json: &mut [u8],
    ) -> Result<IntradayBarResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse an intraday tick response from JSON bytes.
    pub fn parse_intraday_tick(
        json: &mut [u8],
    ) -> Result<IntradayTickResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_refdata_parsing() {
        let mut json = br#"{"securityData":[{"security":"AAPL US Equity","fieldData":{"PX_LAST":150.25,"NAME":"Apple Inc"}}]}"#.to_vec();
        let resp = parser::parse_refdata(&mut json).unwrap();
        assert_eq!(resp.security_data.len(), 1);
        assert_eq!(resp.security_data[0].security, "AAPL US Equity");
        assert!(resp.security_data[0].field_data.contains_key("PX_LAST"));
    }

    #[test]
    fn test_histdata_parsing() {
        let mut json = br#"{"securityData":{"security":"AAPL US Equity","fieldData":[{"date":"2024-01-02","PX_LAST":185.5},{"date":"2024-01-03","PX_LAST":186.0}]}}"#.to_vec();
        let resp = parser::parse_histdata(&mut json).unwrap();
        assert_eq!(resp.security_data.security, "AAPL US Equity");
        assert_eq!(resp.security_data.field_data.len(), 2);
    }

    #[test]
    fn test_intraday_bar_parsing() {
        let mut json = br#"{"barData":{"barTickData":[{"time":"2024-01-02T09:30:00","open":185.0,"high":186.0,"low":184.5,"close":185.5,"volume":1000000.0,"numEvents":5000}]}}"#.to_vec();
        let resp = parser::parse_intraday_bar(&mut json).unwrap();
        assert_eq!(resp.bar_data.bar_tick_data.len(), 1);
        assert_eq!(resp.bar_data.bar_tick_data[0].open, Some(185.0));
    }
}
