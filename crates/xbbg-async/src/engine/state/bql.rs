//! BQL (Bloomberg Query Language) state with Arrow builders.
//!
//! Uses zero-copy parsing with simd-json and borrowed types.
//! Note: BQL returns double-encoded JSON (JSON string inside JSON).

use std::sync::Arc;

use arrow::array::{ArrayRef, BooleanBuilder, Float64Builder, Int64Builder, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::{trace, warn};

use super::json_schema::{
    create_empty_batch, decode_double_encoded_json, parser, wrap_batch_error, BqlResponse,
    JsonValue,
};
use xbbg_core::{BlpError, MessageRef};

/// State for a BQL request with zero-copy parsing.
pub struct BqlState {
    /// Collected JSON bytes from all messages (mutable for simd-json)
    json_bytes: Vec<Vec<u8>>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BqlState {
    /// Create a new BQL state.
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
            return create_empty_batch("id");
        }

        // BQL typically returns a single response
        // Process first response (handle double-encoding)
        let mut json_bytes = std::mem::take(&mut self.json_bytes);

        for bytes in &mut json_bytes {
            // BQL returns double-encoded JSON - first decode the outer string
            let inner_bytes = match decode_double_encoded_json(bytes) {
                Ok(inner) => inner,
                Err(e) => {
                    warn!("BQL: Failed to decode outer JSON: {}", e);
                    // Try treating it as regular JSON
                    std::mem::take(bytes)
                }
            };

            // Now parse the actual BQL response with zero-copy
            let mut inner_bytes = inner_bytes;
            match parser::parse_bql(&mut inner_bytes) {
                Ok(response) => {
                    return self.build_arrow_batch(&response);
                }
                Err(e) => {
                    warn!("BQL: Failed to parse BQL response: {}", e);
                }
            }
        }

        create_empty_batch("id")
    }

    /// Build Arrow RecordBatch from BQL response (zero-copy where possible).
    fn build_arrow_batch(&self, response: &BqlResponse<'_>) -> Result<RecordBatch, BlpError> {
        if response.results.is_empty() {
            return create_empty_batch("id");
        }

        // Get field names (sorted for deterministic output)
        let mut field_names: Vec<_> = response.results.keys().collect();
        field_names.sort();

        // All fields share the same idColumn, use first field to get row count
        let first_field = &response.results[field_names[0]];
        let num_rows = first_field.id_column.values.len();

        // Build schema and arrays
        let mut fields: Vec<Field> = Vec::new();
        let mut arrays: Vec<ArrayRef> = Vec::new();

        // Add id column first (zero-copy string extraction)
        let id_array = Self::build_string_array(&first_field.id_column.values);
        fields.push(Field::new("id", DataType::Utf8, true));
        arrays.push(Arc::new(id_array));

        // Add each field's values
        for field_name in &field_names {
            let field_result = &response.results[*field_name];

            // Main value column
            let (array, dtype) = Self::build_typed_array(
                &field_result.values_column.values,
                &field_result.values_column.col_type,
            );
            fields.push(Field::new(field_name.as_ref(), dtype, true));
            arrays.push(array);

            // Secondary columns (prefixed with field name)
            for sec_col in &field_result.secondary_columns {
                let col_name = if let Some(ref name) = sec_col.name {
                    format!("{}_{}", field_name, name)
                } else {
                    format!("{}_secondary", field_name)
                };
                let (array, dtype) = Self::build_typed_array(&sec_col.values, &sec_col.col_type);
                fields.push(Field::new(&col_name, dtype, true));
                arrays.push(array);
            }
        }

        // Verify all arrays have same length
        for (i, arr) in arrays.iter().enumerate() {
            if arr.len() != num_rows {
                warn!(
                    "BQL: Array {} has {} rows, expected {}",
                    fields[i].name(),
                    arr.len(),
                    num_rows
                );
            }
        }

        let schema = Arc::new(Schema::new(fields));
        RecordBatch::try_new(schema, arrays)
            .map_err(|e| wrap_batch_error("BQL build RecordBatch", e))
    }

    /// Build a typed Arrow array from BQL values (zero-copy for strings).
    fn build_typed_array(values: &[JsonValue<'_>], col_type: &str) -> (ArrayRef, DataType) {
        match col_type.to_uppercase().as_str() {
            "DOUBLE" | "FLOAT" => {
                let mut builder = Float64Builder::with_capacity(values.len());
                for v in values {
                    builder.append_option(v.as_f64());
                }
                (Arc::new(builder.finish()), DataType::Float64)
            }
            "INT" | "INTEGER" | "INT64" | "LONG" => {
                let mut builder = Int64Builder::with_capacity(values.len());
                for v in values {
                    builder.append_option(v.as_i64());
                }
                (Arc::new(builder.finish()), DataType::Int64)
            }
            "BOOL" | "BOOLEAN" => {
                let mut builder = BooleanBuilder::with_capacity(values.len());
                for v in values {
                    builder.append_option(v.as_bool());
                }
                (Arc::new(builder.finish()), DataType::Boolean)
            }
            _ => {
                // Default to string for STRING, DATE, and unknown types
                let array = Self::build_string_array(values);
                (Arc::new(array), DataType::Utf8)
            }
        }
    }

    /// Build a string array from JSON values (uses borrowed strings where possible).
    fn build_string_array(values: &[JsonValue<'_>]) -> StringArray {
        let strings: Vec<Option<String>> = values.iter().map(|v| v.as_string()).collect();

        StringArray::from(strings)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bql_response_parsing() {
        let mut json = br#"{
            "results": {
                "px_last": {
                    "idColumn": {"name": "ID", "type": "STRING", "values": ["AAPL US Equity", "MSFT US Equity"]},
                    "valuesColumn": {"type": "DOUBLE", "values": [150.0, 380.0]},
                    "secondaryColumns": []
                }
            }
        }"#.to_vec();

        let response = parser::parse_bql(&mut json).unwrap();
        assert!(!response.results.is_empty());
        assert!(response.results.contains_key("px_last"));
    }
}
