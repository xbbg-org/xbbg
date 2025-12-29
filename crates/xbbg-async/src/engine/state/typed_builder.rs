//! Typed Arrow array builders for dynamic schema support.
//!
//! This module provides a unified interface for building Arrow arrays
//! with types determined at runtime from field_types configuration.

use std::sync::Arc;

use arrow::array::{
    ArrayRef, BooleanBuilder, Date32Builder, Float64Builder, Int64Builder, StringBuilder,
    TimestampMillisecondBuilder,
};
use arrow::datatypes::{DataType, Field, TimeUnit};

use super::json_schema::JsonValue;

/// Arrow type identifier strings (matching Python field_types values).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ArrowType {
    Float64,
    Int64,
    String,
    Bool,
    Date32,
    Timestamp,
}

impl ArrowType {
    /// Parse from type string (e.g., "float64", "int64", "string").
    pub fn parse(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "float64" | "float" | "double" | "f64" => ArrowType::Float64,
            "int64" | "int" | "integer" | "i64" => ArrowType::Int64,
            "bool" | "boolean" => ArrowType::Bool,
            "date32" | "date" => ArrowType::Date32,
            "timestamp" | "datetime" => ArrowType::Timestamp,
            _ => ArrowType::String, // Default to string
        }
    }

    /// Get the Arrow DataType for this type.
    pub fn to_arrow_datatype(&self) -> DataType {
        match self {
            ArrowType::Float64 => DataType::Float64,
            ArrowType::Int64 => DataType::Int64,
            ArrowType::String => DataType::Utf8,
            ArrowType::Bool => DataType::Boolean,
            ArrowType::Date32 => DataType::Date32,
            ArrowType::Timestamp => DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
        }
    }
}

/// A builder that can hold different Arrow array builder types.
pub enum TypedBuilder {
    Float64(Float64Builder),
    Int64(Int64Builder),
    String(StringBuilder),
    Bool(BooleanBuilder),
    Date32(Date32Builder),
    Timestamp(TimestampMillisecondBuilder),
}

impl TypedBuilder {
    /// Create a new builder from an ArrowType.
    pub fn new(arrow_type: &ArrowType) -> Self {
        match arrow_type {
            ArrowType::Float64 => TypedBuilder::Float64(Float64Builder::new()),
            ArrowType::Int64 => TypedBuilder::Int64(Int64Builder::new()),
            ArrowType::String => TypedBuilder::String(StringBuilder::new()),
            ArrowType::Bool => TypedBuilder::Bool(BooleanBuilder::new()),
            ArrowType::Date32 => TypedBuilder::Date32(Date32Builder::new()),
            ArrowType::Timestamp => TypedBuilder::Timestamp(TimestampMillisecondBuilder::new()),
        }
    }

    /// Create a new builder from a type string.
    pub fn from_type_str(type_str: &str) -> Self {
        Self::new(&ArrowType::parse(type_str))
    }

    /// Append a value from a JsonValue, converting as needed.
    pub fn append_json_value(&mut self, value: Option<&JsonValue>) {
        match self {
            TypedBuilder::Float64(b) => {
                if let Some(v) = value.and_then(|v| v.as_f64()) {
                    b.append_value(v);
                } else {
                    b.append_null();
                }
            }
            TypedBuilder::Int64(b) => {
                if let Some(v) = value.and_then(|v| v.as_i64()) {
                    b.append_value(v);
                } else {
                    b.append_null();
                }
            }
            TypedBuilder::String(b) => {
                if let Some(v) = value.and_then(|v| v.as_string()) {
                    b.append_value(&v);
                } else {
                    b.append_null();
                }
            }
            TypedBuilder::Bool(b) => {
                if let Some(v) = value.and_then(|v| match v {
                    JsonValue::Bool(b) => Some(*b),
                    JsonValue::String(s) => s.parse().ok(),
                    JsonValue::Int(i) => Some(*i != 0),
                    _ => None,
                }) {
                    b.append_value(v);
                } else {
                    b.append_null();
                }
            }
            TypedBuilder::Date32(b) => {
                // Parse date string to days since epoch
                if let Some(days) = value.and_then(|v| parse_date_to_days(v)) {
                    b.append_value(days);
                } else {
                    b.append_null();
                }
            }
            TypedBuilder::Timestamp(b) => {
                // Parse datetime string to milliseconds since epoch
                if let Some(ms) = value.and_then(|v| parse_datetime_to_millis(v)) {
                    b.append_value(ms);
                } else {
                    b.append_null();
                }
            }
        }
    }

    /// Append a null value.
    pub fn append_null(&mut self) {
        match self {
            TypedBuilder::Float64(b) => b.append_null(),
            TypedBuilder::Int64(b) => b.append_null(),
            TypedBuilder::String(b) => b.append_null(),
            TypedBuilder::Bool(b) => b.append_null(),
            TypedBuilder::Date32(b) => b.append_null(),
            TypedBuilder::Timestamp(b) => b.append_null(),
        }
    }

    /// Finish building and return the array.
    pub fn finish(&mut self) -> ArrayRef {
        match self {
            TypedBuilder::Float64(b) => Arc::new(b.finish()),
            TypedBuilder::Int64(b) => Arc::new(b.finish()),
            TypedBuilder::String(b) => Arc::new(b.finish()),
            TypedBuilder::Bool(b) => Arc::new(b.finish()),
            TypedBuilder::Date32(b) => Arc::new(b.finish()),
            TypedBuilder::Timestamp(b) => Arc::new(b.finish().with_timezone("UTC")),
        }
    }

    /// Get the Arrow DataType for this builder.
    pub fn data_type(&self) -> DataType {
        match self {
            TypedBuilder::Float64(_) => DataType::Float64,
            TypedBuilder::Int64(_) => DataType::Int64,
            TypedBuilder::String(_) => DataType::Utf8,
            TypedBuilder::Bool(_) => DataType::Boolean,
            TypedBuilder::Date32(_) => DataType::Date32,
            TypedBuilder::Timestamp(_) => {
                DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into()))
            }
        }
    }
}

/// Parse a JsonValue to days since Unix epoch (for Date32).
fn parse_date_to_days(value: &JsonValue) -> Option<i32> {
    let s = value.as_string()?;

    // Try common date formats
    // Bloomberg typically uses YYYY-MM-DD
    if let Ok(date) = chrono::NaiveDate::parse_from_str(&s, "%Y-%m-%d") {
        let epoch = chrono::NaiveDate::from_ymd_opt(1970, 1, 1)?;
        return Some((date - epoch).num_days() as i32);
    }

    // Try YYYYMMDD format
    if let Ok(date) = chrono::NaiveDate::parse_from_str(&s, "%Y%m%d") {
        let epoch = chrono::NaiveDate::from_ymd_opt(1970, 1, 1)?;
        return Some((date - epoch).num_days() as i32);
    }

    None
}

/// Parse a JsonValue to milliseconds since Unix epoch (for Timestamp).
fn parse_datetime_to_millis(value: &JsonValue) -> Option<i64> {
    let s = value.as_string()?;

    // Try ISO 8601 format
    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(&s) {
        return Some(dt.timestamp_millis());
    }

    // Try common Bloomberg datetime formats
    // "2024-01-15T10:30:00.000"
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(&s, "%Y-%m-%dT%H:%M:%S%.f") {
        return Some(dt.and_utc().timestamp_millis());
    }

    // "2024-01-15 10:30:00"
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(&s, "%Y-%m-%d %H:%M:%S") {
        return Some(dt.and_utc().timestamp_millis());
    }

    // Date only (midnight)
    if let Some(days) = parse_date_to_days(value) {
        return Some(days as i64 * 86_400_000);
    }

    None
}

/// Create an Arrow Field from a field name and ArrowType.
pub fn create_field(name: &str, arrow_type: &ArrowType, nullable: bool) -> Field {
    Field::new(name, arrow_type.to_arrow_datatype(), nullable)
}
