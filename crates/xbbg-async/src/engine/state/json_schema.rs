//! Typed JSON response schemas for Bloomberg API responses.
//!
//! These structs are designed for zero-copy deserialization with simd-json.
//! Using typed structs instead of `serde_json::Value` provides:
//! - ~3-5x faster parsing via compile-time-known structure
//! - Direct field access without runtime key lookups
//! - Memory efficiency through `Cow<'a, str>` for borrowed strings
//!
//! ## Double-Encoded JSON Handling
//!
//! Some Bloomberg responses (BQL, sometimes BSRCH) return double-encoded JSON:
//! the outer JSON is a string containing the actual JSON response. Use
//! [`decode_double_encoded_json`] to handle this case before parsing.

use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::Arc;

use arrow::array::{ArrayRef, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use serde::Deserialize;
use simd_json::prelude::ValueAsScalar;
use xbbg_core::BlpError;

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

/// Field info response (from //blp/apiflds FieldInfoRequest).
/// Structure: { fieldData: [ { fieldInfo: { id, mnemonic, description, datatype, ftype, ... } } ] }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FieldInfoResponse<'a> {
    #[serde(borrow, default)]
    pub field_data: Vec<FieldDataItem<'a>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FieldDataItem<'a> {
    #[serde(borrow)]
    pub field_info: FieldInfoData<'a>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FieldInfoData<'a> {
    /// Field ID (e.g., "DS002")
    #[serde(borrow, default)]
    pub id: Option<Cow<'a, str>>,
    /// Field mnemonic (e.g., "PX_LAST")
    #[serde(borrow, default)]
    pub mnemonic: Option<Cow<'a, str>>,
    /// Field description
    #[serde(borrow, default)]
    pub description: Option<Cow<'a, str>>,
    /// Data type (e.g., "Double", "String", "Date")
    #[serde(borrow, default)]
    pub datatype: Option<Cow<'a, str>>,
    /// Field type (e.g., "Price", "Character")
    #[serde(borrow, default)]
    pub ftype: Option<Cow<'a, str>>,
    /// Category names
    #[serde(borrow, default)]
    pub category_name: Option<Vec<Cow<'a, str>>>,
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

    /// Get as bool.
    ///
    /// Handles Bloomberg's encoding where boolean fields are returned as:
    /// - 89 = 'Y' (ASCII) = true
    /// - 78 = 'N' (ASCII) = false
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            JsonValue::Bool(b) => Some(*b),
            JsonValue::Int(i) => match *i {
                89 => Some(true),  // 'Y' ASCII
                78 => Some(false), // 'N' ASCII
                _ => Some(*i != 0),
            },
            JsonValue::String(s) => s.parse().ok(),
            _ => None,
        }
    }

    /// Check if this value is a Bloomberg boolean (78='N' or 89='Y').
    pub fn is_bloomberg_bool(&self) -> bool {
        matches!(self, JsonValue::Int(78 | 89))
    }

    /// Infer the Arrow dtype from the JSON value type.
    pub fn infer_dtype(&self) -> &'static str {
        match self {
            JsonValue::Null => "null",
            JsonValue::Bool(_) => "bool",
            JsonValue::Int(78 | 89) => "bool", // Bloomberg Y/N encoding
            JsonValue::Int(_) => "int64",
            JsonValue::Float(_) => "float64",
            JsonValue::String(s) => {
                // Try to detect date/timestamp strings
                let s = s.as_ref();
                let bytes = s.as_bytes();

                // Check for date pattern: YYYY-MM-DD (exactly 10 chars)
                let is_date_prefix = s.len() >= 10
                    && bytes.get(4) == Some(&b'-')
                    && bytes.get(7) == Some(&b'-')
                    && bytes[0..4].iter().all(|b| b.is_ascii_digit())
                    && bytes[5..7].iter().all(|b| b.is_ascii_digit())
                    && bytes[8..10].iter().all(|b| b.is_ascii_digit());

                if is_date_prefix {
                    if s.len() == 10 {
                        // Pure date: YYYY-MM-DD
                        "date32"
                    } else if s.len() > 10 && bytes.get(10) == Some(&b'T') {
                        // ISO timestamp: YYYY-MM-DDTHH:MM:SS...
                        "timestamp"
                    } else {
                        "string"
                    }
                } else {
                    "string"
                }
            }
            JsonValue::Array(_) => "string", // Arrays become strings
            JsonValue::Object(_) => "string", // Objects become strings
        }
    }
}

/// BQL (Bloomberg Query Language) response.
/// Structure: { results: { field1: { idColumn, valuesColumn, secondaryColumns }, ... } }
/// Note: BQL returns double-encoded JSON (JSON string inside JSON).
#[derive(Debug, Deserialize)]
pub struct BqlResponse<'a> {
    #[serde(borrow, default)]
    pub results: HashMap<Cow<'a, str>, BqlFieldResult<'a>>,
}

/// BQL field result with id column, values column, and optional secondary columns.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BqlFieldResult<'a> {
    #[serde(borrow)]
    pub id_column: BqlColumn<'a>,
    #[serde(borrow)]
    pub values_column: BqlColumn<'a>,
    #[serde(borrow, default)]
    pub secondary_columns: Vec<BqlColumn<'a>>,
}

/// BQL column with name, type, and values.
#[derive(Debug, Deserialize)]
pub struct BqlColumn<'a> {
    #[serde(borrow, default)]
    pub name: Option<Cow<'a, str>>,
    #[serde(borrow, rename = "type")]
    pub col_type: Cow<'a, str>,
    #[serde(borrow)]
    pub values: Vec<JsonValue<'a>>,
}

/// BSRCH (Bloomberg Search) response.
/// Structure: { NumOfFields, NumOfRecords, ColumnTitles, DataRecords, ReachMax, Error, SequenceNumber }
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct BsrchResponse<'a> {
    #[serde(default)]
    pub num_of_fields: i64,
    #[serde(default)]
    pub num_of_records: i64,
    #[serde(borrow, default)]
    pub column_titles: Vec<Cow<'a, str>>,
    #[serde(borrow, default)]
    pub data_records: Vec<BsrchRecord<'a>>,
    #[serde(default)]
    pub reach_max: bool,
    #[serde(borrow, default)]
    pub error: Cow<'a, str>,
    #[serde(default)]
    pub sequence_number: i64,
}

/// BSRCH data record with field values.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct BsrchRecord<'a> {
    #[serde(borrow, default)]
    pub data_fields: Vec<JsonValue<'a>>,
}

// =============================================================================
// Shared Utilities
// =============================================================================

/// Decode double-encoded JSON (JSON string containing JSON).
///
/// Some Bloomberg responses (BQL, sometimes BSRCH) return the actual JSON
/// wrapped in an outer JSON string. This function extracts the inner JSON.
///
/// # Arguments
/// * `bytes` - Mutable JSON bytes (simd-json modifies in-place)
///
/// # Returns
/// * `Ok(Vec<u8>)` - The inner JSON bytes (either extracted or original if not double-encoded)
/// * `Err` - If the outer JSON parsing fails
pub fn decode_double_encoded_json(bytes: &mut [u8]) -> Result<Vec<u8>, simd_json::Error> {
    // Parse as a JSON value
    let value: simd_json::OwnedValue = simd_json::from_slice(bytes)?;

    // Extract the inner string if double-encoded
    if let Some(inner_str) = value.as_str() {
        Ok(inner_str.as_bytes().to_vec())
    } else {
        // Not a string, return as-is
        Ok(bytes.to_vec())
    }
}

/// Wrap an Arrow error in a BlpError with context.
///
/// # Arguments
/// * `context` - Description of what operation failed (e.g., "BQL build RecordBatch")
/// * `error` - The Arrow error
pub fn wrap_batch_error(context: &str, error: arrow::error::ArrowError) -> BlpError {
    BlpError::Internal {
        detail: format!("{}: {}", context, error),
    }
}

/// Create an empty RecordBatch with a single string column.
///
/// # Arguments
/// * `column_name` - Name for the column (e.g., "id", "ticker")
pub fn create_empty_batch(column_name: &str) -> Result<RecordBatch, BlpError> {
    let schema = Arc::new(Schema::new(vec![Field::new(
        column_name,
        DataType::Utf8,
        true,
    )]));
    let array: ArrayRef = Arc::new(StringArray::from(Vec::<Option<String>>::new()));
    RecordBatch::try_new(schema, vec![array])
        .map_err(|e| wrap_batch_error("create empty batch", e))
}

// =============================================================================
// Parsers
// =============================================================================

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

    /// Parse a field info response from JSON bytes.
    pub fn parse_field_info(json: &mut [u8]) -> Result<FieldInfoResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse a BQL response from JSON bytes.
    /// Note: BQL returns double-encoded JSON, so caller must first decode the outer string.
    pub fn parse_bql(json: &mut [u8]) -> Result<BqlResponse<'_>, simd_json::Error> {
        simd_json::from_slice(json)
    }

    /// Parse a BSRCH response from JSON bytes.
    pub fn parse_bsrch(json: &mut [u8]) -> Result<BsrchResponse<'_>, simd_json::Error> {
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
