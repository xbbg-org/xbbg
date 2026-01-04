//! Reference data (bdp) state with Arrow builders.

use std::collections::HashMap;
use std::sync::Arc;

use arrow::array::{
    BooleanBuilder, Date32Builder, Float64Builder, Int64Builder, StringBuilder,
    TimestampMillisecondBuilder,
};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema;
use super::typed_builder::{ArrowType, TypedBuilder};
use xbbg_core::{BlpError, MessageRef};

/// Output format for reference data.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OutputFormat {
    /// Long format: ticker, field, value (one row per ticker-field pair)
    #[default]
    Long,
    /// Wide format: ticker, field1, field2, ... (one row per ticker)
    Wide,
}

/// Long format output mode variants.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum LongMode {
    /// All values as strings (default, backwards-compatible)
    #[default]
    String,
    /// String values with dtype column containing Arrow type name
    WithMetadata,
    /// Multi-value columns: value_f64, value_i64, value_str, value_bool, value_date, value_ts
    Typed,
}

/// State for a reference data request (bdp).
pub struct RefDataState {
    /// Field names as strings
    field_strings: Vec<String>,
    /// Field types mapping (field name -> arrow type)
    field_types: HashMap<String, ArrowType>,
    /// Output format
    format: OutputFormat,
    /// Long format mode (only used when format == Long)
    long_mode: LongMode,
    /// Ticker builder (used in all formats)
    ticker_builder: StringBuilder,
    /// Field name builder (Long format only)
    field_builder: StringBuilder,
    /// Value builder (Long String mode only)
    value_builder: StringBuilder,
    /// Dtype builder (Long WithMetadata mode only)
    dtype_builder: StringBuilder,
    /// Typed value builders (Long Typed mode only)
    value_f64_builder: Float64Builder,
    value_i64_builder: Int64Builder,
    value_str_builder: StringBuilder,
    value_bool_builder: BooleanBuilder,
    value_date_builder: Date32Builder,
    value_ts_builder: TimestampMillisecondBuilder,
    /// Typed per-field builders (Wide format with type info)
    wide_typed_builders: Vec<TypedBuilder>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl RefDataState {
    /// Create a new refdata state with Long format (default).
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self::with_format(fields, OutputFormat::Long, LongMode::String, None, reply)
    }

    /// Create a new refdata state with specified format.
    pub fn with_format(
        fields: Vec<String>,
        format: OutputFormat,
        long_mode: LongMode,
        field_types: Option<HashMap<String, String>>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        // Convert string types to ArrowType
        let arrow_types: HashMap<String, ArrowType> = field_types
            .unwrap_or_default()
            .into_iter()
            .map(|(k, v)| (k, ArrowType::parse(&v)))
            .collect();

        // Create typed builders for Wide format
        let wide_typed_builders = if format == OutputFormat::Wide {
            fields
                .iter()
                .map(|f| {
                    let arrow_type = arrow_types.get(f).cloned().unwrap_or(ArrowType::String);
                    TypedBuilder::new(&arrow_type)
                })
                .collect()
        } else {
            Vec::new()
        };

        Self {
            field_strings: fields,
            field_types: arrow_types,
            format,
            long_mode,
            ticker_builder: StringBuilder::new(),
            field_builder: StringBuilder::new(),
            value_builder: StringBuilder::new(),
            dtype_builder: StringBuilder::new(),
            value_f64_builder: Float64Builder::new(),
            value_i64_builder: Int64Builder::new(),
            value_str_builder: StringBuilder::new(),
            value_bool_builder: BooleanBuilder::new(),
            value_date_builder: Date32Builder::new(),
            value_ts_builder: TimestampMillisecondBuilder::new(),
            wide_typed_builders,
            reply,
        }
    }

    /// Process a PARTIAL_RESPONSE message.
    pub fn on_partial(&mut self, msg: &MessageRef) {
        self.process_message(msg);
    }

    /// Process the final RESPONSE message and send the result via reply channel.
    pub fn finish(mut self, msg: &MessageRef) {
        self.process_message(msg);

        // Build batch first (borrows self), then take reply
        let result = self.build_batch_inner();
        let _ = self.reply.send(result);
    }

    /// Process a ReferenceDataResponse message using JSON bulk extraction.
    ///
    /// Uses Bloomberg SDK's native toJson (SDK 3.25.11+) for single-FFI-call extraction,
    /// then parses with simd-json for high-performance zero-copy deserialization.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        // simd-json requires mutable bytes for in-place parsing (zero-copy)
        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_refdata(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        for sec in &resp.security_data {
            let ticker = sec.security.as_ref();

            match self.format {
                OutputFormat::Long => {
                    for field_str in self.field_strings.clone() {
                        self.ticker_builder.append_value(ticker);
                        self.field_builder.append_value(&field_str);

                        let value = sec.field_data.get(field_str.as_str());
                        let arrow_type = self.field_types.get(&field_str).cloned();

                        match self.long_mode {
                            LongMode::String => {
                                self.append_string_value(value);
                            }
                            LongMode::WithMetadata => {
                                self.append_string_value(value);
                                self.append_dtype(value, arrow_type.as_ref());
                            }
                            LongMode::Typed => {
                                self.append_typed_value(value, arrow_type.as_ref());
                            }
                        }
                    }
                }
                OutputFormat::Wide => {
                    self.ticker_builder.append_value(ticker);

                    for (i, field_str) in self.field_strings.iter().enumerate() {
                        let value = sec.field_data.get(field_str.as_str());
                        self.wide_typed_builders[i].append_json_value(value);
                    }
                }
            }
        }
    }

    /// Append a value as string (for String and WithMetadata modes).
    fn append_string_value(&mut self, value: Option<&json_schema::JsonValue>) {
        if let Some(v) = value.and_then(|v| v.as_string()) {
            self.value_builder.append_value(&v);
        } else {
            self.value_builder.append_null();
        }
    }

    /// Append dtype metadata (for WithMetadata mode).
    fn append_dtype(
        &mut self,
        value: Option<&json_schema::JsonValue>,
        type_hint: Option<&ArrowType>,
    ) {
        let dtype = if let Some(hint) = type_hint {
            // Use provided type hint
            match hint {
                ArrowType::Float64 => "float64",
                ArrowType::Int64 => "int64",
                ArrowType::String => "string",
                ArrowType::Bool => "bool",
                ArrowType::Date32 => "date32",
                ArrowType::Timestamp => "timestamp",
            }
        } else if let Some(v) = value {
            // Infer from JSON value
            v.infer_dtype()
        } else {
            "null"
        };
        self.dtype_builder.append_value(dtype);
    }

    /// Append a value to typed columns (for Typed mode).
    fn append_typed_value(
        &mut self,
        value: Option<&json_schema::JsonValue>,
        type_hint: Option<&ArrowType>,
    ) {
        // Determine target type: use hint if available, otherwise infer
        let target_type = type_hint.cloned().unwrap_or_else(|| {
            value
                .map(|v| ArrowType::parse(v.infer_dtype()))
                .unwrap_or(ArrowType::String)
        });

        // Append to the appropriate column based on target type, null all others
        match target_type {
            ArrowType::Float64 => {
                if let Some(v) = value.and_then(|v| v.as_f64()) {
                    self.value_f64_builder.append_value(v);
                } else {
                    self.value_f64_builder.append_null();
                }
                self.value_i64_builder.append_null();
                self.value_str_builder.append_null();
                self.value_bool_builder.append_null();
                self.value_date_builder.append_null();
                self.value_ts_builder.append_null();
            }
            ArrowType::Int64 => {
                self.value_f64_builder.append_null();
                if let Some(v) = value.and_then(|v| v.as_i64()) {
                    self.value_i64_builder.append_value(v);
                } else {
                    self.value_i64_builder.append_null();
                }
                self.value_str_builder.append_null();
                self.value_bool_builder.append_null();
                self.value_date_builder.append_null();
                self.value_ts_builder.append_null();
            }
            ArrowType::String => {
                self.value_f64_builder.append_null();
                self.value_i64_builder.append_null();
                if let Some(v) = value.and_then(|v| v.as_string()) {
                    self.value_str_builder.append_value(&v);
                } else {
                    self.value_str_builder.append_null();
                }
                self.value_bool_builder.append_null();
                self.value_date_builder.append_null();
                self.value_ts_builder.append_null();
            }
            ArrowType::Bool => {
                self.value_f64_builder.append_null();
                self.value_i64_builder.append_null();
                self.value_str_builder.append_null();
                if let Some(v) = value.and_then(|v| v.as_bool()) {
                    self.value_bool_builder.append_value(v);
                } else {
                    self.value_bool_builder.append_null();
                }
                self.value_date_builder.append_null();
                self.value_ts_builder.append_null();
            }
            ArrowType::Date32 => {
                self.value_f64_builder.append_null();
                self.value_i64_builder.append_null();
                self.value_str_builder.append_null();
                self.value_bool_builder.append_null();
                if let Some(days) = value.and_then(parse_date_to_days) {
                    self.value_date_builder.append_value(days);
                } else {
                    self.value_date_builder.append_null();
                }
                self.value_ts_builder.append_null();
            }
            ArrowType::Timestamp => {
                self.value_f64_builder.append_null();
                self.value_i64_builder.append_null();
                self.value_str_builder.append_null();
                self.value_bool_builder.append_null();
                self.value_date_builder.append_null();
                if let Some(ms) = value.and_then(parse_datetime_to_millis) {
                    self.value_ts_builder.append_value(ms);
                } else {
                    self.value_ts_builder.append_null();
                }
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        match self.format {
            OutputFormat::Long => match self.long_mode {
                LongMode::String => self.build_long_string_batch(),
                LongMode::WithMetadata => self.build_long_metadata_batch(),
                LongMode::Typed => self.build_long_typed_batch(),
            },
            OutputFormat::Wide => self.build_wide_batch(),
        }
    }

    /// Build Long format RecordBatch with string values only.
    fn build_long_string_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let field_array = self.field_builder.finish();
        let value_array = self.value_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value", DataType::Utf8, true),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(ticker_array),
                Arc::new(field_array),
                Arc::new(value_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }

    /// Build Long format RecordBatch with dtype metadata column.
    fn build_long_metadata_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let field_array = self.field_builder.finish();
        let value_array = self.value_builder.finish();
        let dtype_array = self.dtype_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value", DataType::Utf8, true),
            Field::new("dtype", DataType::Utf8, true),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(ticker_array),
                Arc::new(field_array),
                Arc::new(value_array),
                Arc::new(dtype_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }

    /// Build Long format RecordBatch with multi-value typed columns.
    fn build_long_typed_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let field_array = self.field_builder.finish();
        let value_f64_array = self.value_f64_builder.finish();
        let value_i64_array = self.value_i64_builder.finish();
        let value_str_array = self.value_str_builder.finish();
        let value_bool_array = self.value_bool_builder.finish();
        let value_date_array = self.value_date_builder.finish();
        let value_ts_array = self.value_ts_builder.finish().with_timezone("UTC");

        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value_f64", DataType::Float64, true),
            Field::new("value_i64", DataType::Int64, true),
            Field::new("value_str", DataType::Utf8, true),
            Field::new("value_bool", DataType::Boolean, true),
            Field::new("value_date", DataType::Date32, true),
            Field::new(
                "value_ts",
                DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
                true,
            ),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(ticker_array),
                Arc::new(field_array),
                Arc::new(value_f64_array),
                Arc::new(value_i64_array),
                Arc::new(value_str_array),
                Arc::new(value_bool_array),
                Arc::new(value_date_array),
                Arc::new(value_ts_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }

    /// Build Wide format RecordBatch with typed columns.
    fn build_wide_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();

        // Build schema: ticker + one typed column per field
        let mut fields = vec![Field::new("ticker", DataType::Utf8, false)];
        for (i, name) in self.field_strings.iter().enumerate() {
            let data_type = self.wide_typed_builders[i].data_type();
            fields.push(Field::new(name.as_str(), data_type, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> = vec![Arc::new(ticker_array)];
        for builder in &mut self.wide_typed_builders {
            columns.push(builder.finish());
        }

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}

/// Parse a JsonValue to days since Unix epoch (for Date32).
fn parse_date_to_days(value: &json_schema::JsonValue) -> Option<i32> {
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
fn parse_datetime_to_millis(value: &json_schema::JsonValue) -> Option<i64> {
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
