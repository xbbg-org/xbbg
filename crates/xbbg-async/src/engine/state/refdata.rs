//! Reference data (bdp) state with Arrow builders.
//!
//! Extracts ReferenceDataResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use std::collections::HashMap;

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use xbbg_core::{BlpError, Element, Message, Value};

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
    field_names: Vec<String>,
    /// Field type hints (field name -> arrow type)
    field_types: HashMap<String, ArrowType>,
    /// Output format
    format: OutputFormat,
    /// Long format mode (only used when format == Long)
    long_mode: LongMode,
    /// Column set for building the output
    columns: ColumnSet,
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

        // Create column set with type hints
        let mut columns = ColumnSet::new();
        for (name, arrow_type) in &arrow_types {
            columns.set_type_hint(name, *arrow_type);
        }

        Self {
            field_names: fields,
            field_types: arrow_types,
            format,
            long_mode,
            columns,
            reply,
        }
    }

    /// Process a PARTIAL_RESPONSE message.
    pub fn on_partial(&mut self, msg: &Message) {
        self.process_message(msg);
    }

    /// Process the final RESPONSE message and send the result via reply channel.
    pub fn finish(mut self, msg: &Message) {
        self.process_message(msg);
        let reply = self.reply;
        let result = match self.format {
            OutputFormat::Long => match self.long_mode {
                LongMode::String => self
                    .columns
                    .finish_with_order(&["ticker", "field", "value"]),
                LongMode::WithMetadata => self
                    .columns
                    .finish_with_order(&["ticker", "field", "value", "dtype"]),
                LongMode::Typed => self.columns.finish_with_order(&[
                    "ticker",
                    "field",
                    "value_f64",
                    "value_i64",
                    "value_str",
                    "value_bool",
                    "value_date",
                    "value_ts",
                ]),
            },
            OutputFormat::Wide => {
                let mut order = vec!["ticker"];
                order.extend(self.field_names.iter().map(|s| s.as_str()));
                self.columns.finish_with_order(&order)
            }
        };
        let _ = reply.send(result);
    }

    /// Process a ReferenceDataResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// ReferenceDataResponse {
    ///   securityData[] {
    ///     security: "AAPL US Equity"
    ///     fieldData {
    ///       PX_LAST: 150.0
    ///       NAME: "Apple Inc"
    ///       ...
    ///     }
    ///     fieldExceptions[]? { ... }
    ///     securityError? { ... }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get securityData array
        let Some(security_data) = root.get_by_str("securityData") else {
            trace!("No securityData in message");
            return;
        };

        // Iterate through each security
        let n = security_data.len();
        for i in 0..n {
            let Some(sec) = security_data.get_element(i) else {
                continue;
            };

            // Get ticker
            let ticker = sec
                .get_by_str("security")
                .and_then(|e| e.get_str(0))
                .unwrap_or("");

            // Check for security error
            if sec.get_by_str("securityError").is_some() {
                trace!(ticker = ticker, "Security has error, skipping");
                continue;
            }

            // Get fieldData
            let Some(field_data) = sec.get_by_str("fieldData") else {
                trace!(ticker = ticker, "No fieldData for security");
                continue;
            };

            match self.format {
                OutputFormat::Long => {
                    self.process_long_format(ticker, &field_data);
                }
                OutputFormat::Wide => {
                    self.process_wide_format(ticker, &field_data);
                }
            }
        }
    }

    /// Process security in long format (one row per field).
    fn process_long_format(&mut self, ticker: &str, field_data: &Element) {
        for field_name in &self.field_names.clone() {
            // Get the field element
            let value = field_data
                .get_by_str(field_name)
                .and_then(|e| e.get_value(0));

            match self.long_mode {
                LongMode::String => {
                    self.columns.append_str("ticker", ticker);
                    self.columns.append_str("field", field_name);
                    if let Some(v) = &value {
                        self.columns.append_str("value", &value_to_string(v));
                    } else {
                        self.columns.append_null("value");
                    }
                }
                LongMode::WithMetadata => {
                    self.columns.append_str("ticker", ticker);
                    self.columns.append_str("field", field_name);
                    if let Some(v) = &value {
                        self.columns.append_str("value", &value_to_string(v));
                        let dtype = self.get_dtype(field_name, v);
                        self.columns.append_str("dtype", dtype);
                    } else {
                        self.columns.append_null("value");
                        self.columns.append_str("dtype", "null");
                    }
                }
                LongMode::Typed => {
                    self.columns.append_str("ticker", ticker);
                    self.columns.append_str("field", field_name);
                    self.append_typed_value(&value);
                }
            }
            self.columns.end_row();
        }
    }

    /// Process security in wide format (one row per ticker).
    fn process_wide_format(&mut self, ticker: &str, field_data: &Element) {
        self.columns.append_str("ticker", ticker);

        for field_name in &self.field_names.clone() {
            let value = field_data
                .get_by_str(field_name)
                .and_then(|e| e.get_value(0));

            if let Some(v) = value {
                self.columns.append(field_name, v);
            } else {
                self.columns.append_null(field_name);
            }
        }
        self.columns.end_row();
    }

    /// Get dtype string for a value.
    fn get_dtype(&self, field_name: &str, value: &Value) -> &'static str {
        // Use type hint if available
        if let Some(hint) = self.field_types.get(field_name) {
            return hint.type_name();
        }
        // Otherwise infer from value
        ArrowType::from_value(value).type_name()
    }

    /// Append typed value to multi-value columns (for Typed mode).
    fn append_typed_value(&mut self, value: &Option<Value>) {
        match value {
            Some(Value::Float64(v)) => {
                self.columns.append("value_f64", Value::Float64(*v));
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::Int64(v)) => {
                self.columns.append_null("value_f64");
                self.columns.append("value_i64", Value::Int64(*v));
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::Int32(v)) => {
                self.columns.append_null("value_f64");
                self.columns.append("value_i64", Value::Int64(*v as i64));
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::String(s)) | Some(Value::Enum(s)) => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_str("value_str", s);
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::Bool(b)) => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append("value_bool", Value::Bool(*b));
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::Date32(d)) => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append("value_date", Value::Date32(*d));
                self.columns.append_null("value_ts");
            }
            Some(Value::TimestampMicros(ts)) => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append("value_ts", Value::TimestampMicros(*ts));
            }
            Some(Value::Datetime(dt)) => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns
                    .append("value_ts", Value::TimestampMicros(dt.to_micros()));
            }
            Some(Value::Byte(b)) => {
                self.columns.append_null("value_f64");
                self.columns.append("value_i64", Value::Int64(*b as i64));
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
            Some(Value::Null) | None => {
                self.columns.append_null("value_f64");
                self.columns.append_null("value_i64");
                self.columns.append_null("value_str");
                self.columns.append_null("value_bool");
                self.columns.append_null("value_date");
                self.columns.append_null("value_ts");
            }
        }
    }
}

/// Convert a Value to its string representation.
fn value_to_string(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::Bool(b) => b.to_string(),
        Value::Int32(i) => i.to_string(),
        Value::Int64(i) => i.to_string(),
        Value::Float64(f) => f.to_string(),
        Value::String(s) | Value::Enum(s) => s.to_string(),
        Value::Date32(days) => {
            use chrono::{Duration, NaiveDate};
            let epoch = NaiveDate::from_ymd_opt(1970, 1, 1).unwrap();
            let date = epoch + Duration::days(*days as i64);
            date.format("%Y-%m-%d").to_string()
        }
        Value::TimestampMicros(micros) => {
            use chrono::DateTime;
            let secs = micros / 1_000_000;
            let nanos = ((micros % 1_000_000) * 1000) as u32;
            if let Some(dt) = DateTime::from_timestamp(secs, nanos) {
                dt.format("%Y-%m-%dT%H:%M:%S%.6fZ").to_string()
            } else {
                format!("{}us", micros)
            }
        }
        Value::Datetime(dt) => {
            use chrono::DateTime;
            let micros = dt.to_micros();
            let secs = micros / 1_000_000;
            let nanos = ((micros % 1_000_000) * 1000) as u32;
            if let Some(dt) = DateTime::from_timestamp(secs, nanos) {
                dt.format("%Y-%m-%dT%H:%M:%S%.6fZ").to_string()
            } else {
                format!("{}us", micros)
            }
        }
        Value::Byte(b) => b.to_string(),
    }
}
