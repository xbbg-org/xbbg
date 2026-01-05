//! Bloomberg type definitions with Arrow mapping.
//!
//! This module provides type mappings between Bloomberg's internal data types
//! and Arrow data types for schema-driven validation and building.

use arrow::datatypes::{DataType as ArrowDataType, TimeUnit};
use serde::{Deserialize, Serialize};

/// Bloomberg data type enumeration.
///
/// Maps to Bloomberg's internal datatype IDs as returned by schema introspection.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BlpType {
    Bool,
    Char,
    Byte,
    Int32,
    Int64,
    Float32,
    Float64,
    String,
    ByteArray,
    Date,
    Time,
    Decimal,
    Datetime,
    Enumeration,
    Sequence,
    Choice,
    CorrelationId,
    Unknown,
}

impl BlpType {
    /// Convert from Bloomberg datatype ID (from schema introspection).
    ///
    /// These IDs match the values in blpapi_DataType_t.
    pub fn from_datatype_id(id: i32) -> Self {
        match id {
            1 => BlpType::Bool,
            2 => BlpType::Char,
            3 => BlpType::Byte,
            4 => BlpType::Int32,
            5 => BlpType::Int64,
            6 => BlpType::Float32,
            7 => BlpType::Float64,
            8 => BlpType::String,
            9 => BlpType::ByteArray,
            10 => BlpType::Date,
            11 => BlpType::Time,
            12 => BlpType::Decimal,
            13 => BlpType::Datetime,
            14 => BlpType::Enumeration,
            15 => BlpType::Sequence,
            16 => BlpType::Choice,
            17 => BlpType::CorrelationId,
            _ => BlpType::Unknown,
        }
    }

    /// Convert to Bloomberg datatype ID.
    pub fn to_datatype_id(self) -> i32 {
        match self {
            BlpType::Bool => 1,
            BlpType::Char => 2,
            BlpType::Byte => 3,
            BlpType::Int32 => 4,
            BlpType::Int64 => 5,
            BlpType::Float32 => 6,
            BlpType::Float64 => 7,
            BlpType::String => 8,
            BlpType::ByteArray => 9,
            BlpType::Date => 10,
            BlpType::Time => 11,
            BlpType::Decimal => 12,
            BlpType::Datetime => 13,
            BlpType::Enumeration => 14,
            BlpType::Sequence => 15,
            BlpType::Choice => 16,
            BlpType::CorrelationId => 17,
            BlpType::Unknown => -1,
        }
    }

    /// Parse from datatype name string (from cached JSON schemas).
    pub fn from_datatype_name(name: &str) -> Self {
        match name {
            "Bool" => BlpType::Bool,
            "Char" => BlpType::Char,
            "Byte" => BlpType::Byte,
            "Int32" => BlpType::Int32,
            "Int64" => BlpType::Int64,
            "Float32" => BlpType::Float32,
            "Float64" => BlpType::Float64,
            "String" => BlpType::String,
            "ByteArray" => BlpType::ByteArray,
            "Date" => BlpType::Date,
            "Time" => BlpType::Time,
            "Decimal" => BlpType::Decimal,
            "Datetime" => BlpType::Datetime,
            "Enumeration" => BlpType::Enumeration,
            "Sequence" => BlpType::Sequence,
            "Choice" => BlpType::Choice,
            "CorrelationId" => BlpType::CorrelationId,
            _ => BlpType::Unknown,
        }
    }

    /// Convert to Arrow DataType.
    ///
    /// Complex types (Sequence, Choice) map to Utf8 (JSON string representation).
    pub fn to_arrow(self) -> ArrowDataType {
        match self {
            BlpType::Bool => ArrowDataType::Boolean,
            BlpType::Char => ArrowDataType::Utf8,
            BlpType::Byte => ArrowDataType::Int8,
            BlpType::Int32 => ArrowDataType::Int32,
            BlpType::Int64 => ArrowDataType::Int64,
            BlpType::Float32 => ArrowDataType::Float32,
            BlpType::Float64 => ArrowDataType::Float64,
            BlpType::String => ArrowDataType::Utf8,
            BlpType::ByteArray => ArrowDataType::Binary,
            BlpType::Date => ArrowDataType::Date32,
            BlpType::Time => ArrowDataType::Time64(TimeUnit::Nanosecond),
            BlpType::Decimal => ArrowDataType::Float64, // Decimal as f64
            BlpType::Datetime => {
                ArrowDataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into()))
            }
            BlpType::Enumeration => ArrowDataType::Utf8,
            BlpType::Sequence => ArrowDataType::Utf8, // JSON representation
            BlpType::Choice => ArrowDataType::Utf8,   // JSON representation
            BlpType::CorrelationId => ArrowDataType::Int64,
            BlpType::Unknown => ArrowDataType::Utf8,
        }
    }

    /// Check if this is a primitive (non-complex) type.
    pub fn is_primitive(self) -> bool {
        !matches!(self, BlpType::Sequence | BlpType::Choice)
    }

    /// Check if this type can be validated against a JSON value.
    pub fn is_validatable(self) -> bool {
        !matches!(self, BlpType::Unknown | BlpType::CorrelationId)
    }

    /// Get the expected JSON value type for validation.
    pub fn expected_json_type(self) -> &'static str {
        match self {
            BlpType::Bool => "boolean",
            BlpType::Char | BlpType::String | BlpType::Enumeration => "string",
            BlpType::Byte | BlpType::Int32 | BlpType::Int64 => "integer",
            BlpType::Float32 | BlpType::Float64 | BlpType::Decimal => "number",
            BlpType::Date | BlpType::Time | BlpType::Datetime => "string (ISO format)",
            BlpType::ByteArray => "string (base64)",
            BlpType::Sequence => "object",
            BlpType::Choice => "object",
            BlpType::CorrelationId => "integer",
            BlpType::Unknown => "any",
        }
    }
}

impl std::fmt::Display for BlpType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let name = match self {
            BlpType::Bool => "Bool",
            BlpType::Char => "Char",
            BlpType::Byte => "Byte",
            BlpType::Int32 => "Int32",
            BlpType::Int64 => "Int64",
            BlpType::Float32 => "Float32",
            BlpType::Float64 => "Float64",
            BlpType::String => "String",
            BlpType::ByteArray => "ByteArray",
            BlpType::Date => "Date",
            BlpType::Time => "Time",
            BlpType::Decimal => "Decimal",
            BlpType::Datetime => "Datetime",
            BlpType::Enumeration => "Enumeration",
            BlpType::Sequence => "Sequence",
            BlpType::Choice => "Choice",
            BlpType::CorrelationId => "CorrelationId",
            BlpType::Unknown => "Unknown",
        };
        write!(f, "{}", name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_from_datatype_id() {
        assert_eq!(BlpType::from_datatype_id(1), BlpType::Bool);
        assert_eq!(BlpType::from_datatype_id(8), BlpType::String);
        assert_eq!(BlpType::from_datatype_id(14), BlpType::Enumeration);
        assert_eq!(BlpType::from_datatype_id(15), BlpType::Sequence);
        assert_eq!(BlpType::from_datatype_id(999), BlpType::Unknown);
    }

    #[test]
    fn test_roundtrip() {
        for id in 1..=17 {
            let blp_type = BlpType::from_datatype_id(id);
            assert_eq!(blp_type.to_datatype_id(), id);
        }
    }

    #[test]
    fn test_to_arrow() {
        assert_eq!(BlpType::Bool.to_arrow(), ArrowDataType::Boolean);
        assert_eq!(BlpType::Int64.to_arrow(), ArrowDataType::Int64);
        assert_eq!(BlpType::String.to_arrow(), ArrowDataType::Utf8);
        assert_eq!(BlpType::Date.to_arrow(), ArrowDataType::Date32);
    }

    #[test]
    fn test_is_primitive() {
        assert!(BlpType::Bool.is_primitive());
        assert!(BlpType::String.is_primitive());
        assert!(!BlpType::Sequence.is_primitive());
        assert!(!BlpType::Choice.is_primitive());
    }
}
