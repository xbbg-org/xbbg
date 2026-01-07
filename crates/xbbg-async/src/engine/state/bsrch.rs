//! BSRCH (Bloomberg Search) state with Arrow builders.
//!
//! Uses zero-copy parsing with simd-json and borrowed types.
//! BSRCH responses have this structure:
//! ```json
//! {
//!     "NumOfFields": 3,
//!     "NumOfRecords": 10,
//!     "ColumnTitles": ["Ticker", "Name", "Price"],
//!     "DataRecords": [
//!         {"DataFields": ["AAPL US Equity", "Apple Inc", "150.00"]},
//!         ...
//!     ],
//!     "ReachMax": false,
//!     "Error": "",
//!     "SequenceNumber": 0
//! }
//! ```

use simd_json::prelude::ValueAsScalar;
use std::sync::Arc;

use arrow::array::{ArrayRef, StringBuilder, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::{trace, warn};

use super::json_schema::{parser, JsonValue};
use xbbg_core::{BlpError, MessageRef};

/// State for a BSRCH request with zero-copy parsing.
pub struct BsrchState {
    /// Collected JSON bytes from all messages (mutable for simd-json)
    json_bytes: Vec<Vec<u8>>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BsrchState {
    /// Create a new BSRCH state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            json_bytes: Vec::new(),
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

        let result = self.build_batch();
        let _ = self.reply.send(result);
    }

    /// Process a message by collecting its JSON bytes.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };
        self.json_bytes.push(json_str.into_bytes());
    }

    /// Build the final RecordBatch from collected JSON.
    fn build_batch(&mut self) -> Result<RecordBatch, BlpError> {
        if self.json_bytes.is_empty() {
            return Self::empty_batch();
        }

        // Collect all responses (handle pagination)
        let mut all_titles: Vec<String> = Vec::new();
        let mut all_records: Vec<Vec<String>> = Vec::new(); // Pre-converted to strings

        let json_bytes = std::mem::take(&mut self.json_bytes);

        for mut bytes in json_bytes {
            // BSRCH might return double-encoded JSON in some cases
            let inner_bytes = match Self::decode_outer_json(&mut bytes) {
                Ok(inner) => inner,
                Err(e) => {
                    warn!("BSRCH: Failed to decode outer JSON: {}", e);
                    // Try treating it as regular JSON
                    bytes
                }
            };

            // Parse with zero-copy
            let mut inner_bytes = inner_bytes;
            match parser::parse_bsrch(&mut inner_bytes) {
                Ok(response) => {
                    // Check for errors
                    if !response.error.is_empty() {
                        warn!("BSRCH returned error: {}", response.error);
                    }

                    // Use first response's titles (they should all be the same)
                    if all_titles.is_empty() && !response.column_titles.is_empty() {
                        all_titles = response
                            .column_titles
                            .iter()
                            .map(|s| s.to_string())
                            .collect();
                    }

                    // Convert records to owned strings for later use
                    for record in &response.data_records {
                        let row: Vec<String> = record
                            .data_fields
                            .iter()
                            .map(|v| Self::json_value_to_string(v))
                            .collect();
                        all_records.push(row);
                    }
                }
                Err(e) => {
                    warn!("BSRCH: Failed to parse response: {}", e);
                }
            }
        }

        if all_titles.is_empty() || all_records.is_empty() {
            return Self::empty_batch();
        }

        // Build Arrow columns
        self.build_arrow_batch(&all_titles, &all_records)
    }

    /// Decode the outer JSON string (for double-encoding case).
    fn decode_outer_json(bytes: &mut [u8]) -> Result<Vec<u8>, simd_json::Error> {
        // Parse as a JSON value
        let value: simd_json::OwnedValue = simd_json::from_slice(bytes)?;

        // Extract the inner string if double-encoded
        if let Some(inner_str) = value.as_str() {
            Ok(inner_str.as_bytes().to_vec())
        } else {
            // Not a string, return as-is
            Ok(bytes.to_vec())
        }
    }

    /// Convert a JsonValue to a string representation.
    fn json_value_to_string(value: &JsonValue<'_>) -> String {
        match value {
            JsonValue::String(s) => s.to_string(),
            JsonValue::Int(i) => i.to_string(),
            JsonValue::Float(f) => f.to_string(),
            JsonValue::Bool(b) => b.to_string(),
            JsonValue::Null => String::new(),
            JsonValue::Array(arr) => {
                // Join array elements
                let parts: Vec<String> = arr.iter().map(Self::json_value_to_string).collect();
                parts.join(", ")
            }
            JsonValue::Object(obj) => {
                // Convert object to JSON-like string
                let parts: Vec<String> = obj
                    .iter()
                    .map(|(k, v)| format!("{}: {}", k, Self::json_value_to_string(v)))
                    .collect();
                format!("{{{}}}", parts.join(", "))
            }
        }
    }

    /// Build Arrow RecordBatch from BSRCH results.
    fn build_arrow_batch(
        &self,
        titles: &[String],
        records: &[Vec<String>],
    ) -> Result<RecordBatch, BlpError> {
        let num_cols = titles.len();
        let num_rows = records.len();

        // Pre-allocate column builders (all strings)
        let mut builders: Vec<StringBuilder> = (0..num_cols)
            .map(|_| StringBuilder::with_capacity(num_rows, num_rows * 32))
            .collect();

        // Fill in the data
        for record in records {
            for (col_idx, builder) in builders.iter_mut().enumerate() {
                if let Some(value) = record.get(col_idx) {
                    if value.is_empty() {
                        builder.append_null();
                    } else {
                        builder.append_value(value);
                    }
                } else {
                    builder.append_null();
                }
            }
        }

        // Build schema and arrays
        let fields: Vec<Field> = titles
            .iter()
            .map(|name| Field::new(name, DataType::Utf8, true))
            .collect();

        let arrays: Vec<ArrayRef> = builders
            .into_iter()
            .map(|mut b| Arc::new(b.finish()) as ArrayRef)
            .collect();

        let schema = Arc::new(Schema::new(fields));
        RecordBatch::try_new(schema, arrays).map_err(|e| BlpError::Internal {
            detail: format!("BSRCH build RecordBatch: {e}"),
        })
    }

    /// Create an empty RecordBatch.
    fn empty_batch() -> Result<RecordBatch, BlpError> {
        let schema = Arc::new(Schema::new(vec![Field::new("ticker", DataType::Utf8, true)]));
        let ticker_array: ArrayRef = Arc::new(StringArray::from(Vec::<Option<String>>::new()));
        RecordBatch::try_new(schema, vec![ticker_array]).map_err(|e| BlpError::Internal {
            detail: format!("BSRCH empty batch: {e}"),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bsrch_response_parsing() {
        let mut json = br#"{
            "NumOfFields": 3,
            "NumOfRecords": 2,
            "ColumnTitles": ["Ticker", "Name", "Price"],
            "DataRecords": [
                {"DataFields": ["AAPL US Equity", "Apple Inc", "150.00"]},
                {"DataFields": ["MSFT US Equity", "Microsoft Corp", "380.00"]}
            ],
            "ReachMax": false,
            "Error": "",
            "SequenceNumber": 0
        }"#
        .to_vec();

        let response = parser::parse_bsrch(&mut json).unwrap();
        assert_eq!(response.num_of_fields, 3);
        assert_eq!(response.num_of_records, 2);
        assert_eq!(response.column_titles.len(), 3);
        assert_eq!(response.data_records.len(), 2);
    }
}
