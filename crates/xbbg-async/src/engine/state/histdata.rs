//! Historical data (bdh) state with Arrow builders.
//!
//! Extracts HistoricalDataResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use std::collections::HashMap;

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use xbbg_log::trace;

use super::refdata::{LongMode, OutputFormat};
use super::typed_builder::{ArrowType, ColumnSet};
use super::value_utils::{append_long_value_row, append_wide_row};
use xbbg_core::{BlpError, Message, Value};

/// State for a historical data request (bdh).
pub struct HistDataState {
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

impl HistDataState {
    /// Create a new histdata state with Long format (default).
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self::with_format(fields, OutputFormat::Long, LongMode::String, None, reply)
    }

    /// Create a new histdata state with optional field type overrides (defaults to Long format).
    pub fn with_types(
        fields: Vec<String>,
        field_types: Option<HashMap<String, String>>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        Self::with_format(
            fields,
            OutputFormat::Long,
            LongMode::String,
            field_types,
            reply,
        )
    }

    /// Create a new histdata state with specified format.
    pub fn with_format(
        fields: Vec<String>,
        format: OutputFormat,
        long_mode: LongMode,
        field_types: Option<HashMap<String, String>>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        // Convert string types to ArrowType, defaulting to Float64 for historical data
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
                    .finish_with_order(&["ticker", "date", "field", "value"]),
                LongMode::WithMetadata => self
                    .columns
                    .finish_with_order(&["ticker", "date", "field", "value", "dtype"]),
                LongMode::Typed => self.columns.finish_with_order(&[
                    "ticker",
                    "date",
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
                let mut order = vec!["ticker", "date"];
                order.extend(self.field_names.iter().map(|s| s.as_str()));
                self.columns.finish_with_order(&order)
            }
        };
        if let Ok(ref batch) = result {
            xbbg_log::debug!(
                rows = batch.num_rows(),
                cols = batch.num_columns(),
                "histdata finish"
            );
        }
        let _ = reply.send(result);
    }

    /// Process a HistoricalDataResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// HistoricalDataResponse {
    ///   securityData {
    ///     security: "AAPL US Equity"
    ///     fieldData[] {
    ///       date: 2024-01-15
    ///       PX_LAST: 150.0
    ///       VOLUME: 1000000
    ///       ...
    ///     }
    ///     fieldExceptions[]? { ... }
    ///     securityError? { ... }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get securityData (note: singular in HistoricalDataResponse)
        let Some(security_data) = root.get_by_str("securityData") else {
            trace!("No securityData in message");
            return;
        };

        // Get ticker
        let ticker = security_data
            .get_by_str("security")
            .and_then(|e| e.get_str(0))
            .unwrap_or("");

        // Check for security error
        if security_data.get_by_str("securityError").is_some() {
            trace!(ticker = ticker, "Security has error, skipping");
            return;
        }

        // Get fieldData array
        let Some(field_data) = security_data.get_by_str("fieldData") else {
            trace!(ticker = ticker, "No fieldData for security");
            return;
        };

        // Iterate through each row (each date)
        let n = field_data.len();
        for i in 0..n {
            let Some(row) = field_data.get_element(i) else {
                continue;
            };

            // Get date value for this row
            let date_value = row.get_by_str("date").and_then(|e| e.get_value(0));

            match self.format {
                OutputFormat::Long => {
                    self.process_long_format(ticker, &date_value, &row);
                }
                OutputFormat::Wide => {
                    self.process_wide_format(ticker, &date_value, &row);
                }
            }
        }
    }

    /// Process row in long format (one row per field).
    fn process_long_format(
        &mut self,
        ticker: &str,
        date_value: &Option<Value>,
        row: &xbbg_core::Element,
    ) {
        let field_names = self.field_names.clone();
        for field_name in field_names {
            // Get the field value
            let value = row.get_by_str(&field_name).and_then(|e| e.get_value(0));
            let dtype = value.as_ref().map(|v| self.get_dtype(&field_name, v));

            append_long_value_row(
                &mut self.columns,
                self.long_mode,
                &field_name,
                &value,
                dtype,
                |columns| {
                    columns.append_str("ticker", ticker);
                    if let Some(date_value) = date_value {
                        columns.append("date", date_value.clone());
                    } else {
                        columns.append_null("date");
                    }
                },
            );
        }
    }

    /// Process row in wide format (one row per date with all fields as columns).
    fn process_wide_format(
        &mut self,
        ticker: &str,
        date_value: &Option<Value>,
        row: &xbbg_core::Element,
    ) {
        let field_names = self.field_names.clone();
        append_wide_row(
            &mut self.columns,
            &field_names,
            |columns| {
                columns.append_str("ticker", ticker);
                if let Some(date_value) = date_value {
                    columns.append("date", date_value.clone());
                } else {
                    columns.append_null("date");
                }
            },
            |field_name| row.get_by_str(field_name).and_then(|e| e.get_value(0)),
        );
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
}
