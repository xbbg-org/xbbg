//! Shared utility functions used across recipe modules.

use arrow::array::{ArrayRef, Float64Array, Int32Array, Int64Array, LargeStringArray, StringArray};
use arrow::array::RecordBatch;

use crate::error::{RecipeError, Result};

/// Extract a value from an Arrow array at `idx` as a `String`.
///
/// Supports `StringArray`, `LargeStringArray`, `Float64Array`, `Int64Array`,
/// and `Int32Array`. Returns `None` for null values, out-of-bounds indices,
/// or unsupported array types.
pub fn array_value_as_string(array: &ArrayRef, idx: usize) -> Option<String> {
    if idx >= array.len() || array.is_null(idx) {
        return None;
    }

    if let Some(arr) = array.as_any().downcast_ref::<StringArray>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<LargeStringArray>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Float64Array>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int64Array>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int32Array>() {
        return Some(arr.value(idx).to_string());
    }

    None
}

/// Convert a `Date32` value (days since Unix epoch) to a `chrono::NaiveDate`.
pub fn date32_to_naive(days_since_epoch: i32) -> Option<chrono::NaiveDate> {
    let epoch = chrono::NaiveDate::from_ymd_opt(1970, 1, 1)?;
    epoch.checked_add_signed(chrono::Duration::days(days_since_epoch as i64))
}

/// Borrow a column from a `RecordBatch` as a `&StringArray`, returning an
/// error if the column is missing or is not `Utf8`.
pub fn as_string_col<'a>(batch: &'a RecordBatch, column: &str) -> Result<&'a StringArray> {
    batch
        .column_by_name(column)
        .ok_or_else(|| RecipeError::Other(format!("missing '{column}' column")))?
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| RecipeError::Other(format!("'{column}' column must be Utf8")))
}
