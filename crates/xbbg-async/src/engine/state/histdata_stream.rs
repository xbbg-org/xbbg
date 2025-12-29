//! Streaming historical data (bdh) state with Arrow builders.
//!
//! Unlike HistDataState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Date32Builder, Float64Builder, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use chrono::NaiveDate;
use tokio::sync::mpsc;
use tracing::trace;

use super::json_schema;
use xbbg_core::{BlpError, MessageRef};

/// Streaming state for a historical data request (bdh).
pub struct HistDataStreamState {
    /// Field names as strings
    field_strings: Vec<String>,
    /// Stream channel for sending chunks
    stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    /// Schema (cached after first build)
    schema: Option<Arc<Schema>>,
}

impl HistDataStreamState {
    /// Create a new streaming histdata state.
    pub fn new(fields: Vec<String>, stream: mpsc::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            field_strings: fields,
            stream,
            schema: None,
        }
    }

    /// Process a PARTIAL_RESPONSE message and yield a chunk.
    pub fn on_partial(&mut self, msg: &MessageRef) {
        if let Some(batch) = self.process_message(msg) {
            // Non-blocking send - if channel is full, drop the batch
            let _ = self.stream.try_send(Ok(batch));
        }
    }

    /// Process the final RESPONSE message and close the stream.
    pub fn finish(mut self, msg: &MessageRef) {
        if let Some(batch) = self.process_message(msg) {
            let _ = self.stream.try_send(Ok(batch));
        }
        // Stream closes automatically when self is dropped
    }

    /// Fail the stream with an error.
    pub fn fail(self, error: BlpError) {
        let _ = self.stream.try_send(Err(error));
    }

    /// Process a HistoricalDataResponse message using JSON bulk extraction.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return None;
        };

        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_histdata(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return None;
        };

        let ticker = resp.security_data.security.as_ref();

        if resp.security_data.field_data.is_empty() {
            return None;
        }

        // Create builders for this chunk
        let mut ticker_builder = StringBuilder::new();
        let mut date_builder = Date32Builder::new();
        let mut field_builders: Vec<Float64Builder> = self
            .field_strings
            .iter()
            .map(|_| Float64Builder::new())
            .collect();

        for row in &resp.security_data.field_data {
            ticker_builder.append_value(ticker);

            // Parse date string to days since epoch
            if let Some(date_str) = &row.date {
                if let Some(days) = parse_date_to_days(date_str.as_ref()) {
                    date_builder.append_value(days);
                } else {
                    date_builder.append_null();
                }
            } else {
                date_builder.append_null();
            }

            // Get each field value
            for (j, field_str) in self.field_strings.iter().enumerate() {
                if let Some(value) = row.fields.get(field_str.as_str()) {
                    if let Some(f) = value.as_f64() {
                        field_builders[j].append_value(f);
                    } else {
                        field_builders[j].append_null();
                    }
                } else {
                    field_builders[j].append_null();
                }
            }
        }

        // Build the schema if not cached
        let schema = self.schema.get_or_insert_with(|| {
            let mut fields = vec![
                Field::new("ticker", DataType::Utf8, false),
                Field::new("date", DataType::Date32, true),
            ];
            for name in &self.field_strings {
                fields.push(Field::new(name.as_str(), DataType::Float64, true));
            }
            Arc::new(Schema::new(fields))
        });

        // Build columns
        let ticker_array = ticker_builder.finish();
        let date_array = date_builder.finish();
        let field_arrays: Vec<_> = field_builders
            .iter_mut()
            .map(|b| Arc::new(b.finish()) as _)
            .collect();

        let mut columns: Vec<Arc<dyn arrow::array::Array>> =
            vec![Arc::new(ticker_array), Arc::new(date_array)];
        columns.extend(field_arrays);

        RecordBatch::try_new(schema.clone(), columns).ok()
    }
}

/// Parse a date string (YYYY-MM-DD) to days since Unix epoch.
fn parse_date_to_days(date_str: &str) -> Option<i32> {
    let parts: Vec<&str> = date_str.split('-').collect();
    if parts.len() >= 3 {
        let year: i32 = parts[0].parse().ok()?;
        let month: u32 = parts[1].parse().ok()?;
        let day: u32 = parts[2].parse().ok()?;

        let date = NaiveDate::from_ymd_opt(year, month, day)?;
        let epoch = NaiveDate::from_ymd_opt(1970, 1, 1)?;
        Some(date.signed_duration_since(epoch).num_days() as i32)
    } else {
        None
    }
}
