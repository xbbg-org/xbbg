use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::Arc;

use super::refdata::LongMode;
use super::typed_builder::{ArrowType, ColumnSet, TypedBuilder};
use arrow::array::{ArrayRef, Date32Builder, StringBuilder};
use arrow::datatypes::{Field, Schema};
use arrow::record_batch::RecordBatch;
use xbbg_core::{BlpError, DataType as BlpDataType, Element, Name, Value};

pub(crate) fn should_emit_scalar_field(element: &Element<'_>) -> bool {
    !element.is_array()
        && !matches!(
            element.datatype(),
            BlpDataType::Sequence
                | BlpDataType::Choice
                | BlpDataType::ByteArray
                | BlpDataType::CorrelationId
        )
}

pub(crate) fn arrow_type_for_element(element: &Element<'_>) -> ArrowType {
    match element.datatype() {
        BlpDataType::Bool => ArrowType::Bool,
        BlpDataType::Char | BlpDataType::Byte | BlpDataType::Int32 => ArrowType::Int32,
        BlpDataType::Int64 => ArrowType::Int64,
        BlpDataType::Float32 | BlpDataType::Float64 | BlpDataType::Decimal => ArrowType::Float64,
        BlpDataType::String | BlpDataType::Enumeration => ArrowType::String,
        BlpDataType::Date => ArrowType::Date32,
        BlpDataType::Time => ArrowType::Time64Micros,
        BlpDataType::Datetime => ArrowType::TimestampMicros,
        BlpDataType::Sequence
        | BlpDataType::Choice
        | BlpDataType::ByteArray
        | BlpDataType::CorrelationId => ArrowType::String,
    }
}

#[inline(always)]
pub(crate) fn get_value_cached_datatype<'a>(
    element: &Element<'a>,
    cached_datatype: &mut Option<BlpDataType>,
) -> Option<Value<'a>> {
    if let Some(cached) = *cached_datatype {
        if let Some(value) = get_value_for_datatype(element, cached, 0) {
            return Some(value);
        }

        let datatype = element.datatype();
        if datatype != cached {
            xbbg_log::debug!(
                cached = ?cached,
                actual = ?datatype,
                "Bloomberg element datatype changed; refreshing extractor cache"
            );
        }
        *cached_datatype = Some(datatype);
        return get_value_for_datatype(element, datatype, 0);
    }

    let datatype = element.datatype();
    *cached_datatype = Some(datatype);
    get_value_for_datatype(element, datatype, 0)
}

#[inline(always)]
fn get_value_for_datatype<'a>(
    element: &Element<'a>,
    datatype: BlpDataType,
    index: usize,
) -> Option<Value<'a>> {
    match datatype {
        BlpDataType::Bool => element.get_bool(index).map(Value::Bool),
        BlpDataType::Char | BlpDataType::Byte => {
            if let Some(value) = element.get_bool(index) {
                return Some(Value::Bool(value));
            }
            element.get_i32(index).map(|value| Value::Byte(value as u8))
        }
        BlpDataType::Int32 => element.get_i32(index).map(Value::Int32),
        BlpDataType::Int64 => element.get_i64(index).map(Value::Int64),
        BlpDataType::Float32 | BlpDataType::Float64 | BlpDataType::Decimal => {
            element.get_f64(index).map(Value::Float64)
        }
        BlpDataType::String => element.get_str(index).map(Value::String),
        BlpDataType::Date => element.get_datetime(index).map(|dt| {
            let micros = dt.to_micros();
            Value::Date32((micros / 86_400_000_000) as i32)
        }),
        BlpDataType::Time => element
            .get_datetime(index)
            .map(|dt| Value::Time64Micros(dt.to_time_micros())),
        BlpDataType::Datetime => element.get_datetime(index).map(|dt| {
            if dt.has_date_parts() {
                Value::TimestampMicros(dt.to_micros())
            } else {
                Value::Time64Micros(dt.to_time_micros())
            }
        }),
        BlpDataType::Enumeration => element.get_str(index).map(Value::Enum),
        BlpDataType::Sequence
        | BlpDataType::Choice
        | BlpDataType::ByteArray
        | BlpDataType::CorrelationId => Some(Value::Null),
    }
}
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

pub(crate) struct LongStringColumns {
    ticker: StringBuilder,
    date: Option<Date32Builder>,
    field: StringBuilder,
    value: TypedBuilder,
    row_count: usize,
}

impl LongStringColumns {
    pub(crate) fn refdata(value_type: ArrowType) -> Self {
        Self::new(value_type, false)
    }

    pub(crate) fn histdata(value_type: ArrowType) -> Self {
        Self::new(value_type, true)
    }

    fn new(value_type: ArrowType, include_date: bool) -> Self {
        Self {
            ticker: StringBuilder::new(),
            date: include_date.then(Date32Builder::new),
            field: StringBuilder::new(),
            value: TypedBuilder::new(value_type),
            row_count: 0,
        }
    }

    pub(crate) fn row_count(&self) -> usize {
        self.row_count
    }

    pub(crate) fn append_refdata_row(
        &mut self,
        ticker: &str,
        field_name: &str,
        value: Option<Value<'_>>,
    ) {
        self.ticker.append_value(ticker);
        self.field.append_value(field_name);
        self.append_value(value);
        self.row_count += 1;
    }

    pub(crate) fn append_histdata_row(
        &mut self,
        ticker: &str,
        date_value: Option<Value<'_>>,
        field_name: &str,
        value: Option<Value<'_>>,
    ) {
        self.ticker.append_value(ticker);
        if let Some(date) = self.date.as_mut() {
            append_date32_value(date, date_value);
        }
        self.field.append_value(field_name);
        self.append_value(value);
        self.row_count += 1;
    }

    fn append_value(&mut self, value: Option<Value<'_>>) {
        match value {
            Some(value) => self.value.append_value(Some(value)),
            None => self.value.append_null(),
        }
    }

    pub(crate) fn finish_refdata(mut self) -> Result<RecordBatch, BlpError> {
        let fields = vec![
            Field::new("ticker", ArrowType::String.to_arrow_datatype(), true),
            Field::new("field", ArrowType::String.to_arrow_datatype(), true),
            Field::new("value", self.value.data_type(), true),
        ];
        let arrays: Vec<ArrayRef> = vec![
            Arc::new(self.ticker.finish()),
            Arc::new(self.field.finish()),
            self.value.finish(),
        ];
        RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).map_err(|e| {
            BlpError::Internal {
                detail: format!("build long ReferenceData RecordBatch: {e}"),
            }
        })
    }

    pub(crate) fn finish_histdata(mut self) -> Result<RecordBatch, BlpError> {
        let Some(mut date) = self.date.take() else {
            return Err(BlpError::Internal {
                detail: "histdata long columns missing date builder".to_string(),
            });
        };
        let fields = vec![
            Field::new("ticker", ArrowType::String.to_arrow_datatype(), true),
            Field::new("date", ArrowType::Date32.to_arrow_datatype(), true),
            Field::new("field", ArrowType::String.to_arrow_datatype(), true),
            Field::new("value", self.value.data_type(), true),
        ];
        let arrays: Vec<ArrayRef> = vec![
            Arc::new(self.ticker.finish()),
            Arc::new(date.finish()),
            Arc::new(self.field.finish()),
            self.value.finish(),
        ];
        RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).map_err(|e| {
            BlpError::Internal {
                detail: format!("build long HistoricalData RecordBatch: {e}"),
            }
        })
    }
}

fn append_date32_value(builder: &mut Date32Builder, value: Option<Value<'_>>) {
    match value {
        Some(Value::Date32(days)) => builder.append_value(days),
        Some(Value::TimestampMicros(micros)) => {
            builder.append_value((micros / 86_400_000_000) as i32)
        }
        _ => builder.append_null(),
    }
}

struct WideFieldColumn {
    name: String,
    type_hint: Option<ArrowType>,
    builder: Option<TypedBuilder>,
}

pub(crate) struct WideColumns {
    ticker: StringBuilder,
    date: Option<Date32Builder>,
    fields: Vec<WideFieldColumn>,
    row_count: usize,
}

impl WideColumns {
    pub(crate) fn refdata(
        field_names: &[String],
        field_types: &HashMap<String, ArrowType>,
    ) -> Self {
        Self::new(field_names, field_types, false)
    }

    pub(crate) fn histdata(
        field_names: &[String],
        field_types: &HashMap<String, ArrowType>,
    ) -> Self {
        Self::new(field_names, field_types, true)
    }

    fn new(
        field_names: &[String],
        field_types: &HashMap<String, ArrowType>,
        include_date: bool,
    ) -> Self {
        Self {
            ticker: StringBuilder::new(),
            date: include_date.then(Date32Builder::new),
            fields: field_names
                .iter()
                .map(|name| WideFieldColumn {
                    name: name.clone(),
                    type_hint: field_types.get(name).copied(),
                    builder: None,
                })
                .collect(),
            row_count: 0,
        }
    }

    pub(crate) fn append_refdata_row<'a, F>(
        &mut self,
        ticker: &str,
        field_lookup_names: &[Name],
        field_datatypes: &mut [Option<BlpDataType>],
        lookup: F,
    ) where
        F: FnMut(&Name, &mut Option<BlpDataType>) -> Option<Value<'a>>,
    {
        self.ticker.append_value(ticker);
        self.append_field_values(field_lookup_names, field_datatypes, lookup);
        self.row_count += 1;
    }

    pub(crate) fn append_histdata_row<'a, F>(
        &mut self,
        ticker: &str,
        date_value: Option<Value<'_>>,
        field_lookup_names: &[Name],
        field_datatypes: &mut [Option<BlpDataType>],
        lookup: F,
    ) where
        F: FnMut(&Name, &mut Option<BlpDataType>) -> Option<Value<'a>>,
    {
        self.ticker.append_value(ticker);
        if let Some(date) = self.date.as_mut() {
            append_date32_value(date, date_value);
        }
        self.append_field_values(field_lookup_names, field_datatypes, lookup);
        self.row_count += 1;
    }

    fn append_field_values<'a, F>(
        &mut self,
        field_lookup_names: &[Name],
        field_datatypes: &mut [Option<BlpDataType>],
        mut lookup: F,
    ) where
        F: FnMut(&Name, &mut Option<BlpDataType>) -> Option<Value<'a>>,
    {
        for index in 0..self.fields.len() {
            let value = match (
                field_lookup_names.get(index),
                field_datatypes.get_mut(index),
            ) {
                (Some(field_lookup_name), Some(field_datatype)) => {
                    lookup(field_lookup_name, field_datatype)
                }
                _ => None,
            };
            self.append_field_value(index, value);
        }
    }

    fn append_field_value(&mut self, index: usize, value: Option<Value<'_>>) {
        let Some(column) = self.fields.get_mut(index) else {
            return;
        };

        if let Some(builder) = column.builder.as_mut() {
            match value {
                Some(value) => builder.append_value(Some(value)),
                None => builder.append_null(),
            }
            return;
        }

        if let Some(value) = value {
            let arrow_type = column
                .type_hint
                .unwrap_or_else(|| ArrowType::from_value(&value));
            let mut builder = TypedBuilder::new(arrow_type);
            for _ in 0..self.row_count {
                builder.append_null();
            }
            builder.append_value(Some(value));
            column.builder = Some(builder);
        }
    }

    pub(crate) fn finish_refdata(self) -> Result<RecordBatch, BlpError> {
        self.finish(false)
    }

    pub(crate) fn finish_histdata(self) -> Result<RecordBatch, BlpError> {
        self.finish(true)
    }

    fn finish(mut self, include_date: bool) -> Result<RecordBatch, BlpError> {
        let mut arrow_fields =
            Vec::with_capacity(self.fields.len() + if include_date { 2 } else { 1 });
        let mut arrays: Vec<ArrayRef> = Vec::with_capacity(arrow_fields.capacity());

        arrow_fields.push(Field::new(
            "ticker",
            ArrowType::String.to_arrow_datatype(),
            true,
        ));
        arrays.push(Arc::new(self.ticker.finish()));

        if include_date {
            let Some(mut date) = self.date.take() else {
                return Err(BlpError::Internal {
                    detail: "wide HistoricalData columns missing date builder".to_string(),
                });
            };
            arrow_fields.push(Field::new(
                "date",
                ArrowType::Date32.to_arrow_datatype(),
                true,
            ));
            arrays.push(Arc::new(date.finish()));
        }

        for mut column in self.fields {
            let mut builder = column.builder.take().unwrap_or_else(|| {
                let mut builder = TypedBuilder::new(column.type_hint.unwrap_or(ArrowType::String));
                for _ in 0..self.row_count {
                    builder.append_null();
                }
                builder
            });
            arrow_fields.push(Field::new(&column.name, builder.data_type(), true));
            arrays.push(builder.finish());
        }

        RecordBatch::try_new(Arc::new(Schema::new(arrow_fields)), arrays).map_err(|e| {
            BlpError::Internal {
                detail: format!("build wide RecordBatch: {e}"),
            }
        })
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

fn civil_from_days(days: i64) -> (i32, u32, u32) {
    // Howard Hinnant's civil-from-days algorithm. `days` is relative to
    // 1970-01-01, matching Arrow Date32 and Bloomberg date extraction.
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    let year = y + i64::from(month <= 2);

    (year as i32, month as u32, day as u32)
}

fn push_padded_u64(out: &mut String, value: u64, width: usize) {
    let mut buffer = itoa::Buffer::new();
    let digits = buffer.format(value);
    for _ in digits.len()..width {
        out.push('0');
    }
    out.push_str(digits);
}

fn push_padded_i64(out: &mut String, value: i64, width: usize) {
    if value < 0 {
        out.push('-');
        push_padded_u64(out, value.unsigned_abs(), width);
    } else {
        push_padded_u64(out, value as u64, width);
    }
}

fn push_date(out: &mut String, days: i64) {
    let (year, month, day) = civil_from_days(days);
    push_padded_i64(out, year as i64, 4);
    out.push('-');
    push_padded_u64(out, month as u64, 2);
    out.push('-');
    push_padded_u64(out, day as u64, 2);
}

pub(crate) fn format_date32(days: i32) -> String {
    let mut out = String::with_capacity(10);
    push_date(&mut out, days as i64);
    out
}

pub(crate) fn format_time64_micros(micros: i64) -> String {
    let total_secs = micros / 1_000_000;
    let frac_us = (micros % 1_000_000).unsigned_abs();
    let h = total_secs / 3600;
    let m = (total_secs % 3600) / 60;
    let s = total_secs % 60;

    let mut out = String::with_capacity(15);
    push_padded_i64(&mut out, h, 2);
    out.push(':');
    push_padded_i64(&mut out, m, 2);
    out.push(':');
    push_padded_i64(&mut out, s, 2);
    out.push('.');
    push_padded_u64(&mut out, frac_us, 6);
    out
}

pub(crate) fn format_timestamp_micros(micros: i64) -> String {
    if micros < 0 {
        return format_timestamp_micros_fallback(micros);
    }

    let secs = micros / 1_000_000;
    let frac_us = (micros % 1_000_000) as u64;
    let days = secs / 86_400;
    let seconds_of_day = secs % 86_400;
    let h = seconds_of_day / 3_600;
    let m = (seconds_of_day % 3_600) / 60;
    let s = seconds_of_day % 60;

    let mut out = String::with_capacity(27);
    push_date(&mut out, days);
    out.push('T');
    push_padded_i64(&mut out, h, 2);
    out.push(':');
    push_padded_i64(&mut out, m, 2);
    out.push(':');
    push_padded_i64(&mut out, s, 2);
    out.push('.');
    push_padded_u64(&mut out, frac_us, 6);
    out.push('Z');
    out
}

fn format_timestamp_micros_fallback(micros: i64) -> String {
    use chrono::DateTime;

    let secs = micros / 1_000_000;
    let nanos = ((micros % 1_000_000) * 1000) as u32;
    if let Some(dt) = DateTime::from_timestamp(secs, nanos) {
        dt.format("%Y-%m-%dT%H:%M:%S%.6fZ").to_string()
    } else {
        let mut buffer = itoa::Buffer::new();
        let mut out = String::with_capacity(24);
        out.push_str(buffer.format(micros));
        out.push_str("us");
        out
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

#[cfg(test)]
mod tests {
    use super::*;
    use arrow::array::{Array, Date32Array, Float64Array, StringArray};

    #[test]
    fn date_time_formatters_match_expected_strings() {
        assert_eq!(format_date32(0), "1970-01-01");
        assert_eq!(format_date32(1), "1970-01-02");
        assert_eq!(format_timestamp_micros(0), "1970-01-01T00:00:00.000000Z");
        assert_eq!(
            format_timestamp_micros(1_714_639_234_567_890),
            "2024-05-02T08:40:34.567890Z"
        );
        assert_eq!(format_time64_micros(37_234_005_006), "10:20:34.005006");
    }

    #[test]
    fn long_string_columns_refdata_preserve_order_and_nulls() {
        let mut columns = LongStringColumns::refdata(ArrowType::String);
        columns.append_refdata_row("IBM US Equity", "PX_LAST", Some(Value::Float64(123.45)));
        columns.append_refdata_row("IBM US Equity", "BAD_FIELD", None);

        let batch = columns.finish_refdata().unwrap();
        assert_eq!(batch.num_rows(), 2);
        assert_eq!(batch.num_columns(), 3);
        assert_eq!(batch.schema().field(0).name(), "ticker");
        assert_eq!(batch.schema().field(1).name(), "field");
        assert_eq!(batch.schema().field(2).name(), "value");

        let tickers = batch
            .column(0)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();
        let fields = batch
            .column(1)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();
        let values = batch
            .column(2)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();

        assert_eq!(tickers.value(0), "IBM US Equity");
        assert_eq!(fields.value(0), "PX_LAST");
        assert_eq!(values.value(0), "123.45");
        assert_eq!(fields.value(1), "BAD_FIELD");
        assert!(values.is_null(1));
    }

    #[test]
    fn long_string_columns_histdata_preserve_date_and_typed_value() {
        let mut columns = LongStringColumns::histdata(ArrowType::Float64);
        columns.append_histdata_row(
            "IBM US Equity",
            Some(Value::Date32(20_000)),
            "PX_LAST",
            Some(Value::Float64(123.45)),
        );
        columns.append_histdata_row("IBM US Equity", Some(Value::Date32(20_001)), "VOLUME", None);

        let batch = columns.finish_histdata().unwrap();
        assert_eq!(batch.num_rows(), 2);
        assert_eq!(batch.num_columns(), 4);
        assert_eq!(batch.schema().field(0).name(), "ticker");
        assert_eq!(batch.schema().field(1).name(), "date");
        assert_eq!(batch.schema().field(2).name(), "field");
        assert_eq!(batch.schema().field(3).name(), "value");

        let dates = batch
            .column(1)
            .as_any()
            .downcast_ref::<Date32Array>()
            .unwrap();
        let fields = batch
            .column(2)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();
        let values = batch
            .column(3)
            .as_any()
            .downcast_ref::<Float64Array>()
            .unwrap();

        assert_eq!(dates.value(0), 20_000);
        assert_eq!(fields.value(0), "PX_LAST");
        assert_eq!(values.value(0), 123.45);
        assert_eq!(dates.value(1), 20_001);
        assert_eq!(fields.value(1), "VOLUME");
        assert!(values.is_null(1));
    }
}
