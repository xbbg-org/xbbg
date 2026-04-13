use std::borrow::Cow;
use std::collections::HashMap;

use super::refdata::LongMode;
use super::typed_builder::{ArrowType, ColumnSet};
use xbbg_core::Value;

/// Compute the common Arrow type for the "value" column from field type hints.
///
/// If all fields resolve to the same numeric type family, returns that type
/// (promoting mixed int/float to Float64). If any field is non-numeric or no
/// hints are provided, falls back to String.
pub(crate) fn common_value_type(field_types: &HashMap<String, ArrowType>) -> ArrowType {
    if field_types.is_empty() {
        return ArrowType::String;
    }

    let mut has_float = false;
    let mut has_int = false;

    for arrow_type in field_types.values() {
        match arrow_type {
            ArrowType::Float64 => has_float = true,
            ArrowType::Int64 | ArrowType::Int32 => has_int = true,
            // Any non-numeric type → fall back to string
            _ => return ArrowType::String,
        }
    }

    if has_float || has_int {
        ArrowType::Float64
    } else {
        ArrowType::String
    }
}

pub(crate) fn append_long_value_row<F>(
    columns: &mut ColumnSet,
    long_mode: LongMode,
    field_name: &str,
    value: Option<Value<'_>>,
    dtype: Option<&str>,
    prefix: F,
) where
    F: FnOnce(&mut ColumnSet),
{
    prefix(columns);
    columns.append_str("field", field_name);

    match long_mode {
        LongMode::String => {
            if let Some(value) = value {
                columns.append("value", value);
            } else {
                columns.append_null("value");
            }
        }
        LongMode::WithMetadata => {
            if let Some(ref value) = value {
                let value_str = value_to_string(value);
                columns.append_str("value", value_str.as_ref());
                columns.append_str("dtype", dtype.unwrap_or("null"));
            } else {
                columns.append_null("value");
                columns.append_str("dtype", "null");
            }
        }
        LongMode::Typed => append_typed_value(columns, value.as_ref()),
    }

    columns.end_row();
}

pub(crate) fn append_typed_value(columns: &mut ColumnSet, value: Option<&Value<'_>>) {
    match value {
        Some(Value::Float64(v)) => {
            columns.append("value_f64", Value::Float64(*v));
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::Int64(v)) => {
            columns.append_null("value_f64");
            columns.append("value_i64", Value::Int64(*v));
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::Int32(v)) => {
            columns.append_null("value_f64");
            columns.append("value_i64", Value::Int64(*v as i64));
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::String(s)) | Some(Value::Enum(s)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_str("value_str", s);
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::Bool(b)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append("value_bool", Value::Bool(*b));
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::Date32(d)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append("value_date", Value::Date32(*d));
            columns.append_null("value_ts");
        }
        Some(Value::TimestampMicros(ts)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append("value_ts", Value::TimestampMicros(*ts));
        }
        Some(Value::Datetime(dt)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append("value_ts", Value::TimestampMicros(dt.to_micros()));
        }
        Some(Value::Time64Micros(t)) => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append("value_ts", Value::TimestampMicros(*t));
        }
        Some(Value::Byte(b)) => {
            columns.append_null("value_f64");
            columns.append("value_i64", Value::Int64(*b as i64));
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
        Some(Value::Null) | None => {
            columns.append_null("value_f64");
            columns.append_null("value_i64");
            columns.append_null("value_str");
            columns.append_null("value_bool");
            columns.append_null("value_date");
            columns.append_null("value_ts");
        }
    }
}

pub(crate) fn append_wide_row<'a, F, G>(
    columns: &mut ColumnSet,
    field_names: &[String],
    prefix: F,
    mut lookup: G,
) where
    F: FnOnce(&mut ColumnSet),
    G: FnMut(&str) -> Option<Value<'a>>,
{
    prefix(columns);

    for field_name in field_names {
        if let Some(value) = lookup(field_name) {
            columns.append(field_name, value);
        } else {
            columns.append_null(field_name);
        }
    }

    columns.end_row();
}

pub(crate) fn format_date32(days: i32) -> String {
    use chrono::{DateTime, Duration, Utc};

    let epoch = DateTime::<Utc>::UNIX_EPOCH.date_naive();
    let date = epoch + Duration::days(days as i64);
    date.format("%Y-%m-%d").to_string()
}

pub(crate) fn format_time64_micros(micros: i64) -> String {
    let total_secs = micros / 1_000_000;
    let frac_us = (micros % 1_000_000).unsigned_abs();
    let h = total_secs / 3600;
    let m = (total_secs % 3600) / 60;
    let s = total_secs % 60;
    format!("{:02}:{:02}:{:02}.{:06}", h, m, s, frac_us)
}

pub(crate) fn format_timestamp_micros(micros: i64) -> String {
    use chrono::DateTime;

    let secs = micros / 1_000_000;
    let nanos = ((micros % 1_000_000) * 1000) as u32;
    if let Some(dt) = DateTime::from_timestamp(secs, nanos) {
        dt.format("%Y-%m-%dT%H:%M:%S%.6fZ").to_string()
    } else {
        format!("{micros}us")
    }
}

pub(crate) fn value_to_string<'a>(value: &'a Value<'a>) -> Cow<'a, str> {
    match value {
        Value::Null => Cow::Borrowed(""),
        Value::Bool(b) => Cow::Owned(b.to_string()),
        Value::Int32(i) => Cow::Owned(i.to_string()),
        Value::Int64(i) => Cow::Owned(i.to_string()),
        Value::Float64(f) => Cow::Owned(f.to_string()),
        Value::String(s) | Value::Enum(s) => Cow::Borrowed(s),
        Value::Date32(days) => Cow::Owned(format_date32(*days)),
        Value::TimestampMicros(micros) => Cow::Owned(format_timestamp_micros(*micros)),
        Value::Datetime(dt) => Cow::Owned(format_timestamp_micros(dt.to_micros())),
        Value::Time64Micros(micros) => Cow::Owned(format_time64_micros(*micros)),
        Value::Byte(b) => Cow::Owned(b.to_string()),
    }
}
