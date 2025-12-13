//! Streaming historical data (bdh) state with Arrow builders.
//!
//! Unlike HistDataState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Date32Builder, Float64Builder, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

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

    /// Process a HistoricalDataResponse message and return a RecordBatch.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let elem = msg.elements();

        // Get securityData
        let security_data = elem.get_element("securityData")?;

        // Historical data has a single security per message
        let ticker = security_data
            .get_element("security")
            .and_then(|e| e.get_value_as_string(0))
            .unwrap_or_default();

        // Get fieldData array
        let field_data = security_data.get_element("fieldData")?;

        let num_rows = field_data.num_values();
        if num_rows == 0 {
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

        for i in 0..num_rows {
            let row_elem = field_data.get_value_as_element(i)?;

            ticker_builder.append_value(&ticker);

            // Get date
            if let Some(date_elem) = row_elem.get_element("date") {
                if let Ok(Some(dt)) = date_elem.get_value_as_datetime(0) {
                    let days = (dt.timestamp() / 86400) as i32;
                    date_builder.append_value(days);
                } else {
                    date_builder.append_null();
                }
            } else {
                date_builder.append_null();
            }

            // Get each field value
            for (j, field_str) in self.field_strings.iter().enumerate() {
                if let Some(field_elem) = row_elem.get_element(field_str) {
                    if let Some(val) = field_elem.get_value_as_float64(0) {
                        field_builders[j].append_value(val);
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
