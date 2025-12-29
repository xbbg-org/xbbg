//! Bulk data (bds) state with Arrow builders.

use std::borrow::Cow;
use std::sync::Arc;

use arrow::array::StringBuilder;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema::{self, JsonValue};
use xbbg_core::{BlpError, MessageRef};

/// State for a bulk data request (bds).
pub struct BulkDataState {
    /// Field name as string
    field_string: String,
    /// Ticker builder
    ticker_builder: StringBuilder,
    /// Discovered sub-field names (populated on first row)
    subfield_names: Vec<String>,
    /// Sub-field builders (one per sub-field, dynamic)
    subfield_builders: Vec<StringBuilder>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BulkDataState {
    /// Create a new bulkdata state.
    pub fn new(field: String, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            field_string: field,
            ticker_builder: StringBuilder::new(),
            subfield_names: Vec::new(),
            subfield_builders: Vec::new(),
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

    /// Process a BulkDataResponse message using JSON bulk extraction.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_bulkdata(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        for sec in &resp.security_data {
            let ticker = sec.security.as_ref();

            // Get the bulk field array from fieldData
            let Some(bulk_value) = sec.field_data.get(self.field_string.as_str()) else {
                continue;
            };

            // bulk_value should be an array of objects
            let JsonValue::Array(rows) = bulk_value else {
                continue;
            };

            for row in rows {
                let JsonValue::Object(row_obj) = row else {
                    continue;
                };

                self.ticker_builder.append_value(ticker);

                // Discover sub-fields on first row
                if self.subfield_names.is_empty() {
                    for key in row_obj.keys() {
                        self.subfield_names.push(key.to_string());
                        self.subfield_builders.push(StringBuilder::new());
                    }
                }

                // Extract sub-field values
                for (k, subfield_name) in self.subfield_names.iter().enumerate() {
                    if let Some(value) = row_obj.get(&Cow::Borrowed(subfield_name.as_str())) {
                        if let Some(s) = value.as_string() {
                            self.subfield_builders[k].append_value(&s);
                        } else {
                            self.subfield_builders[k].append_null();
                        }
                    } else {
                        self.subfield_builders[k].append_null();
                    }
                }
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();

        // Build schema
        let mut fields = vec![Field::new("ticker", DataType::Utf8, false)];
        for name in &self.subfield_names {
            fields.push(Field::new(name.as_str(), DataType::Utf8, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> = vec![Arc::new(ticker_array)];
        for builder in &mut self.subfield_builders {
            columns.push(Arc::new(builder.finish()));
        }

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
