//! JSON to Arrow state for generic JSON responses.
//!
//! Parses JSON responses into Arrow RecordBatch using schema inference.
//! This is a middle ground between:
//! - raw_json.rs: Returns JSON strings (slow, parsed in Python)
//! - Typed handlers: Fully optimized for specific response types
//!
//! Use this for operations where we don't have a typed handler yet.

use std::io::Cursor;
use std::sync::Arc;

use arrow::datatypes::Schema;
use arrow::json::ReaderBuilder;
use arrow::record_batch::RecordBatch;
use serde_json::Value;
use tokio::sync::oneshot;
use tracing::{trace, warn};

use xbbg_core::{BlpError, MessageRef};

/// State for a JSON-to-Arrow request that parses JSON into Arrow columns.
pub struct JsonArrowState {
    /// Collected JSON values from all messages
    values: Vec<Value>,
    /// Optional path to extract data from (e.g., "securityData", "results")
    extract_path: Option<String>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl JsonArrowState {
    /// Create a new JSON-to-Arrow state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            values: Vec::new(),
            extract_path: None,
            reply,
        }
    }

    /// Create with a specific extraction path.
    ///
    /// The path specifies which field to extract from the JSON response.
    /// For example, "securityData" will extract the securityData array from BEQS responses.
    pub fn with_extract_path(
        extract_path: impl Into<String>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        Self {
            values: Vec::new(),
            extract_path: Some(extract_path.into()),
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

    /// Process a message by parsing its JSON and collecting values.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        // Parse JSON
        let parsed: Value = match serde_json::from_str(&json_str) {
            Ok(v) => v,
            Err(e) => {
                warn!("Failed to parse JSON: {}", e);
                return;
            }
        };

        // Extract data based on path or collect raw
        let extracted = if let Some(ref path) = self.extract_path {
            self.extract_at_path(&parsed, path)
        } else {
            self.extract_auto(&parsed)
        };

        self.values.extend(extracted);
    }

    /// Extract values at a specific path.
    fn extract_at_path(&self, value: &Value, path: &str) -> Vec<Value> {
        // Navigate to the path
        let parts: Vec<&str> = path.split('.').collect();
        let mut current = value;

        for part in parts {
            match current {
                Value::Object(obj) => {
                    if let Some(v) = obj.get(part) {
                        current = v;
                    } else {
                        return vec![];
                    }
                }
                _ => return vec![],
            }
        }

        // Return array items or single value
        match current {
            Value::Array(arr) => arr.clone(),
            other => vec![other.clone()],
        }
    }

    /// Auto-extract data from common Bloomberg response structures.
    fn extract_auto(&self, value: &Value) -> Vec<Value> {
        if let Value::Object(obj) = value {
            // Common Bloomberg response patterns
            let common_keys = [
                "securityData",
                "results",
                "data",
                "fieldData",
                "tickData",
                "barData",
            ];

            for key in common_keys {
                if let Some(v) = obj.get(key) {
                    return match v {
                        Value::Array(arr) => arr.clone(),
                        Value::Object(inner) => {
                            // Try nested extraction (e.g., tickData.tickData)
                            if let Some(Value::Array(arr)) = inner.get(key) {
                                return arr.clone();
                            }
                            // Return inner object's array values
                            for inner_val in inner.values() {
                                if let Value::Array(arr) = inner_val {
                                    return arr.clone();
                                }
                            }
                            vec![v.clone()]
                        }
                        _ => vec![v.clone()],
                    };
                }
            }
        }

        // Fallback: wrap in array if not already
        match value {
            Value::Array(arr) => arr.clone(),
            other => vec![other.clone()],
        }
    }

    /// Build the final RecordBatch from collected JSON values.
    fn build_batch(&mut self) -> Result<RecordBatch, BlpError> {
        if self.values.is_empty() {
            // Return empty batch with no columns
            let schema = Arc::new(Schema::empty());
            return RecordBatch::try_new(schema, vec![]).map_err(|e| BlpError::Internal {
                detail: format!("build empty RecordBatch: {e}"),
            });
        }

        // Flatten nested structures for better Arrow conversion
        let flattened = self.flatten_values();

        // Convert to NDJSON format for arrow-json reader
        let ndjson: String = flattened
            .iter()
            .filter_map(|v| serde_json::to_string(v).ok())
            .collect::<Vec<_>>()
            .join("\n");

        if ndjson.is_empty() {
            let schema = Arc::new(Schema::empty());
            return RecordBatch::try_new(schema, vec![]).map_err(|e| BlpError::Internal {
                detail: format!("build empty RecordBatch: {e}"),
            });
        }

        // Use arrow-json to infer schema and build batch
        let cursor = Cursor::new(ndjson.as_bytes());
        let reader = ReaderBuilder::new(Arc::new(Schema::empty()))
            .with_batch_size(flattened.len())
            .build(cursor)
            .map_err(|e| BlpError::Internal {
                detail: format!("create JSON reader: {e}"),
            })?;

        // Read all batches and concatenate
        let mut batches = Vec::new();
        for batch_result in reader {
            let batch = batch_result.map_err(|e| BlpError::Internal {
                detail: format!("read JSON batch: {e}"),
            })?;
            batches.push(batch);
        }

        if batches.is_empty() {
            let schema = Arc::new(Schema::empty());
            return RecordBatch::try_new(schema, vec![]).map_err(|e| BlpError::Internal {
                detail: format!("build empty RecordBatch: {e}"),
            });
        }

        // Concatenate all batches
        if batches.len() == 1 {
            Ok(batches.remove(0))
        } else {
            arrow::compute::concat_batches(&batches[0].schema(), &batches).map_err(|e| {
                BlpError::Internal {
                    detail: format!("concat batches: {e}"),
                }
            })
        }
    }

    /// Flatten nested objects for better Arrow conversion.
    fn flatten_values(&self) -> Vec<Value> {
        self.values
            .iter()
            .map(|v| self.flatten_value(v, ""))
            .collect()
    }

    /// Flatten a single value, prefixing nested keys.
    fn flatten_value(&self, value: &Value, _prefix: &str) -> Value {
        match value {
            Value::Object(obj) => {
                let mut flat = serde_json::Map::new();

                for (key, val) in obj {
                    match val {
                        // Flatten nested objects one level
                        Value::Object(inner) => {
                            for (inner_key, inner_val) in inner {
                                let flat_key = format!("{}_{}", key, inner_key);
                                // Convert complex types to strings
                                let flat_val = match inner_val {
                                    Value::Array(_) | Value::Object(_) => {
                                        Value::String(inner_val.to_string())
                                    }
                                    other => other.clone(),
                                };
                                flat.insert(flat_key, flat_val);
                            }
                        }
                        // Convert arrays to strings
                        Value::Array(_) => {
                            flat.insert(key.clone(), Value::String(val.to_string()));
                        }
                        // Keep primitives as-is
                        other => {
                            flat.insert(key.clone(), other.clone());
                        }
                    }
                }

                Value::Object(flat)
            }
            other => other.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_at_path() {
        let (tx, _rx) = oneshot::channel();
        let state = JsonArrowState::with_extract_path("securityData", tx);

        let json: Value =
            serde_json::from_str(r#"{"securityData": [{"security": "AAPL", "value": 150.0}]}"#)
                .unwrap();

        let extracted = state.extract_at_path(&json, "securityData");
        assert_eq!(extracted.len(), 1);
    }

    #[test]
    fn test_flatten_value() {
        let (tx, _rx) = oneshot::channel();
        let state = JsonArrowState::new(tx);

        let json: Value = serde_json::from_str(
            r#"{"security": "AAPL", "fieldData": {"PX_LAST": 150.0, "VOLUME": 1000000}}"#,
        )
        .unwrap();

        let flattened = state.flatten_value(&json, "");

        if let Value::Object(obj) = flattened {
            assert!(obj.contains_key("security"));
            assert!(obj.contains_key("fieldData_PX_LAST"));
            assert!(obj.contains_key("fieldData_VOLUME"));
        } else {
            panic!("Expected object");
        }
    }
}
