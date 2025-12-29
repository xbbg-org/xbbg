//! Historical data (bdh) state with Arrow builders.

use std::collections::HashMap;
use std::sync::Arc;

use arrow::array::{Date32Builder, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema;
use super::typed_builder::{ArrowType, TypedBuilder};
use xbbg_core::{BlpError, MessageRef};

/// State for a historical data request (bdh).
pub struct HistDataState {
    /// Field names as strings
    field_strings: Vec<String>,
    /// Ticker builder
    ticker_builder: StringBuilder,
    /// Date builder (days since epoch)
    date_builder: Date32Builder,
    /// Value builders (one per field, typed based on field_types)
    field_builders: Vec<TypedBuilder>,
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

        // Create typed builders for each field
        let field_builders = fields
            .iter()
            .map(|f| {
                // Default to Float64 for historical data (prices, volumes are numeric)
                let arrow_type = arrow_types.get(f).cloned().unwrap_or(ArrowType::Float64);
                TypedBuilder::new(&arrow_type)
            })
            .collect();

        Self {
            field_strings: fields,
            ticker_builder: StringBuilder::new(),
            date_builder: Date32Builder::new(),
            field_builders,
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

    /// Process a HistoricalDataResponse message using JSON bulk extraction.
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

        let Ok(resp) = json_schema::parser::parse_histdata(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        let ticker = resp.security_data.security.as_ref();

        for row in &resp.security_data.field_data {
            self.ticker_builder.append_value(ticker);

            // Parse date string to days since epoch
            if let Some(date_str) = &row.date {
                if let Some(days) = parse_date_to_days(date_str.as_ref()) {
                    self.date_builder.append_value(days);
                } else {
                    self.date_builder.append_null();
                }
            } else {
                self.date_builder.append_null();
            }

            // Get each field value using typed builders
            for (j, field_str) in self.field_strings.iter().enumerate() {
                let value = row.fields.get(field_str.as_str());
                self.field_builders[j].append_json_value(value);
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let date_array = self.date_builder.finish();

        // Build schema with typed columns
        let mut fields = vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("date", DataType::Date32, true),
        ];
        for (i, name) in self.field_strings.iter().enumerate() {
            let data_type = self.field_builders[i].data_type();
            fields.push(Field::new(name.as_str(), data_type, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> =
            vec![Arc::new(ticker_array), Arc::new(date_array)];
        for builder in &mut self.field_builders {
            columns.push(builder.finish());
        }

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}

/// Parse a date string (YYYY-MM-DD) to days since Unix epoch.
fn parse_date_to_days(date_str: &str) -> Option<i32> {
    // Try parsing ISO date format (YYYY-MM-DD)
    let parts: Vec<&str> = date_str.split('-').collect();
    if parts.len() >= 3 {
        let year: i32 = parts[0].parse().ok()?;
        let month: u32 = parts[1].parse().ok()?;
        let day: u32 = parts[2].parse().ok()?;

        use chrono::NaiveDate;
        let date = NaiveDate::from_ymd_opt(year, month, day)?;
        let epoch = NaiveDate::from_ymd_opt(1970, 1, 1)?;
        Some(date.signed_duration_since(epoch).num_days() as i32)
    } else {
        None
    }
}
