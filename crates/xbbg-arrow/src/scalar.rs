//! Scalar conversion helpers for xbbg Arrow carrier data.

use std::sync::Arc;

use arrow_array::{
    Array, ArrayRef, BooleanArray, Date32Array, Float32Array, Float64Array, Int32Array, Int64Array,
    StringArray, Time64MicrosecondArray, TimestampMicrosecondArray, TimestampMillisecondArray,
    UInt32Array, UInt64Array,
};
use arrow_schema::{DataType, Field, TimeUnit};
use chrono::NaiveDate;

/// Scalar values used by xbbg's native carrier operations.
#[derive(Clone, Debug, PartialEq)]
pub enum CellValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Date(NaiveDate),
    Text(String),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum InferredKind {
    Bool,
    Int,
    Float,
    Date,
    Text,
}

fn merge_kind(current: Option<InferredKind>, value: &CellValue) -> Option<InferredKind> {
    let next = match value {
        CellValue::Null => return current,
        CellValue::Bool(_) => InferredKind::Bool,
        CellValue::Int(_) => InferredKind::Int,
        CellValue::Float(_) => InferredKind::Float,
        CellValue::Date(_) => InferredKind::Date,
        CellValue::Text(_) => InferredKind::Text,
    };
    Some(match (current, next) {
        (None, kind) => kind,
        (Some(InferredKind::Text), _) | (_, InferredKind::Text) => InferredKind::Text,
        (Some(InferredKind::Date), InferredKind::Date) => InferredKind::Date,
        (Some(InferredKind::Date), _) | (_, InferredKind::Date) => InferredKind::Text,
        (
            Some(InferredKind::Float),
            InferredKind::Int | InferredKind::Bool | InferredKind::Float,
        )
        | (Some(InferredKind::Int | InferredKind::Bool), InferredKind::Float) => {
            InferredKind::Float
        }
        (Some(InferredKind::Int), InferredKind::Bool | InferredKind::Int)
        | (Some(InferredKind::Bool), InferredKind::Int) => InferredKind::Int,
        (Some(InferredKind::Bool), InferredKind::Bool) => InferredKind::Bool,
    })
}

/// Convert a carrier scalar to a string representation, preserving nulls.
pub fn cell_to_string(value: &CellValue) -> Option<String> {
    match value {
        CellValue::Null => None,
        CellValue::Bool(v) => Some(v.to_string()),
        CellValue::Int(v) => Some(v.to_string()),
        CellValue::Float(v) => Some(v.to_string()),
        CellValue::Date(v) => Some(v.to_string()),
        CellValue::Text(v) => Some(v.clone()),
    }
}

/// Build an Arrow array from xbbg carrier scalar values, inferring a narrow type.
pub fn build_array(name: &str, cells: &[CellValue]) -> (Field, ArrayRef) {
    let kind = cells
        .iter()
        .fold(None, merge_kind)
        .unwrap_or(InferredKind::Text);
    match kind {
        InferredKind::Bool => {
            let values: Vec<Option<bool>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(*v),
                    CellValue::Int(v) => Some(*v != 0),
                    CellValue::Float(v) => Some(*v != 0.0),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Boolean, true),
                Arc::new(BooleanArray::from(values)),
            )
        }
        InferredKind::Int => {
            let values: Vec<Option<i64>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(i64::from(*v)),
                    CellValue::Int(v) => Some(*v),
                    CellValue::Float(v) => Some(*v as i64),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Int64, true),
                Arc::new(Int64Array::from(values)),
            )
        }
        InferredKind::Float => {
            let values: Vec<Option<f64>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(if *v { 1.0 } else { 0.0 }),
                    CellValue::Int(v) => Some(*v as f64),
                    CellValue::Float(v) => Some(*v),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Float64, true),
                Arc::new(Float64Array::from(values)),
            )
        }
        InferredKind::Date => {
            let epoch = NaiveDate::from_ymd_opt(1970, 1, 1).expect("valid epoch date");
            let values: Vec<Option<i32>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Date(v) => Some(v.signed_duration_since(epoch).num_days() as i32),
                    _ => None,
                })
                .collect();
            (
                Field::new(name, DataType::Date32, true),
                Arc::new(Date32Array::from(values)),
            )
        }
        InferredKind::Text => {
            let values: Vec<Option<String>> = cells.iter().map(cell_to_string).collect();
            (
                Field::new(name, DataType::Utf8, true),
                Arc::new(StringArray::from(values)),
            )
        }
    }
}

/// Convert date32 days from Unix epoch to a [`NaiveDate`].
pub fn date_from_days(days: i32) -> Option<NaiveDate> {
    NaiveDate::from_ymd_opt(1970, 1, 1)?.checked_add_signed(chrono::Duration::days(days as i64))
}

/// Convert an Arrow scalar at `row` to xbbg's carrier scalar representation.
pub fn cell_from_array(array: &dyn Array, row: usize) -> CellValue {
    if array.is_null(row) {
        return CellValue::Null;
    }
    match array.data_type() {
        DataType::Boolean => CellValue::Bool(
            array
                .as_any()
                .downcast_ref::<BooleanArray>()
                .expect("BooleanArray")
                .value(row),
        ),
        DataType::Int32 => CellValue::Int(i64::from(
            array
                .as_any()
                .downcast_ref::<Int32Array>()
                .expect("Int32Array")
                .value(row),
        )),
        DataType::Int64 => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<Int64Array>()
                .expect("Int64Array")
                .value(row),
        ),
        DataType::UInt32 => CellValue::Int(i64::from(
            array
                .as_any()
                .downcast_ref::<UInt32Array>()
                .expect("UInt32Array")
                .value(row),
        )),
        DataType::UInt64 => CellValue::Text(
            array
                .as_any()
                .downcast_ref::<UInt64Array>()
                .expect("UInt64Array")
                .value(row)
                .to_string(),
        ),
        DataType::Float32 => CellValue::Float(
            array
                .as_any()
                .downcast_ref::<Float32Array>()
                .expect("Float32Array")
                .value(row) as f64,
        ),
        DataType::Float64 => CellValue::Float(
            array
                .as_any()
                .downcast_ref::<Float64Array>()
                .expect("Float64Array")
                .value(row),
        ),
        DataType::Utf8 => CellValue::Text(
            array
                .as_any()
                .downcast_ref::<StringArray>()
                .expect("StringArray")
                .value(row)
                .to_string(),
        ),
        DataType::Date32 => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        )
        .map(CellValue::Date)
        .unwrap_or(CellValue::Null),
        DataType::Time64(TimeUnit::Microsecond) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<Time64MicrosecondArray>()
                .expect("Time64MicrosecondArray")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Microsecond, _) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<TimestampMicrosecondArray>()
                .expect("TimestampMicrosecondArray")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Millisecond, _) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<TimestampMillisecondArray>()
                .expect("TimestampMillisecondArray")
                .value(row),
        ),
        _ => CellValue::Text(format!("{array:?}")),
    }
}

/// Whether a carrier scalar should count as a present value.
pub fn cell_has_value(cell: &CellValue) -> bool {
    match cell {
        CellValue::Null => false,
        CellValue::Text(text) => !text.is_empty(),
        _ => true,
    }
}

/// Parse a carrier scalar as a date when possible.
pub fn date_from_cell(cell: &CellValue) -> Option<NaiveDate> {
    match cell {
        CellValue::Date(value) => Some(*value),
        CellValue::Text(value) if value.len() >= 10 => {
            NaiveDate::parse_from_str(&value[..10], "%Y-%m-%d").ok()
        }
        CellValue::Text(value) if value.len() == 8 => {
            NaiveDate::parse_from_str(value, "%Y%m%d").ok()
        }
        _ => None,
    }
}

/// Parse an Arrow scalar at `row` as a date when possible.
pub fn date_from_array(array: &dyn Array, row: usize) -> Option<NaiveDate> {
    if array.is_null(row) {
        return None;
    }
    match array.data_type() {
        DataType::Date32 => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        ),
        _ => date_from_cell(&cell_from_array(array, row)),
    }
}

/// Compare an Arrow scalar at `row` with a carrier scalar.
pub fn cell_matches(array: &dyn Array, row: usize, needle: &CellValue) -> bool {
    if array.is_null(row) {
        return matches!(needle, CellValue::Null);
    }
    match (array.data_type(), needle) {
        (DataType::Boolean, CellValue::Bool(expected)) => {
            array
                .as_any()
                .downcast_ref::<BooleanArray>()
                .expect("BooleanArray")
                .value(row)
                == *expected
        }
        (DataType::Int64, CellValue::Int(expected)) => {
            array
                .as_any()
                .downcast_ref::<Int64Array>()
                .expect("Int64Array")
                .value(row)
                == *expected
        }
        (DataType::Int32, CellValue::Int(expected)) => {
            i64::from(
                array
                    .as_any()
                    .downcast_ref::<Int32Array>()
                    .expect("Int32Array")
                    .value(row),
            ) == *expected
        }
        (DataType::Float64, CellValue::Float(expected)) => {
            array
                .as_any()
                .downcast_ref::<Float64Array>()
                .expect("Float64Array")
                .value(row)
                == *expected
        }
        (DataType::Time64(TimeUnit::Microsecond), CellValue::Int(expected)) => {
            array
                .as_any()
                .downcast_ref::<Time64MicrosecondArray>()
                .expect("Time64MicrosecondArray")
                .value(row)
                == *expected
        }
        (DataType::Date32, CellValue::Date(expected)) => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        )
        .map(|value| value == *expected)
        .unwrap_or(false),
        (DataType::Utf8, CellValue::Text(expected)) => {
            array
                .as_any()
                .downcast_ref::<StringArray>()
                .expect("StringArray")
                .value(row)
                == expected
        }
        _ => false,
    }
}
