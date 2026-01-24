//! Historical data (bdh) state with Arrow builders.
//!
//! Extracts HistoricalDataResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use std::collections::HashMap;

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use xbbg_core::{BlpError, Message};

/// State for a historical data request (bdh).
pub struct HistDataState {
    /// Field names as strings
    field_names: Vec<String>,
    /// Column set for building the output
    columns: ColumnSet,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl HistDataState {
    /// Create a new histdata state with default Float64 types for all fields.
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self::with_types(fields, None, reply)
    }

    /// Create a new histdata state with optional field type overrides.
    pub fn with_types(
        fields: Vec<String>,
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
        columns.set_type_hint("ticker", ArrowType::String);
        columns.set_type_hint("date", ArrowType::Date32);

        // Set hints for fields, defaulting to Float64 for historical data
        for field in &fields {
            let arrow_type = arrow_types
                .get(field)
                .copied()
                .unwrap_or(ArrowType::Float64);
            columns.set_type_hint(field, arrow_type);
        }

        Self {
            field_names: fields,
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
        let mut order = vec!["ticker", "date"];
        order.extend(self.field_names.iter().map(|s| s.as_str()));
        let result = self.columns.finish_with_order(&order);
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

            self.columns.append_str("ticker", ticker);

            // Get date
            if let Some(date_elem) = row.get_by_str("date") {
                if let Some(date_value) = date_elem.get_value(0) {
                    self.columns.append("date", date_value);
                } else {
                    self.columns.append_null("date");
                }
            } else {
                self.columns.append_null("date");
            }

            // Get each field value
            for field_name in &self.field_names.clone() {
                if let Some(field_elem) = row.get_by_str(field_name) {
                    if let Some(value) = field_elem.get_value(0) {
                        self.columns.append(field_name, value);
                    } else {
                        self.columns.append_null(field_name);
                    }
                } else {
                    self.columns.append_null(field_name);
                }
            }

            self.columns.end_row();
        }
    }
}
