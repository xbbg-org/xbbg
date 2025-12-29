//! Generic flattener state for arbitrary Bloomberg responses.
//!
//! Flattens any JSON response into a normalized table with columns:
//! - path: JSON path (e.g., "securityData[0].fieldData.PX_LAST")
//! - type: Value type (string, number, boolean, null, array, object)
//! - value_str: String representation of value
//! - value_num: Numeric value (if applicable)

use std::sync::Arc;

use arrow::array::{Float64Builder, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema::JsonValue;
use xbbg_core::{BlpError, MessageRef};

/// State for a generic request that flattens JSON to tabular format.
pub struct GenericState {
    /// JSON path builder
    path_builder: StringBuilder,
    /// Value type builder
    type_builder: StringBuilder,
    /// String value builder
    value_str_builder: StringBuilder,
    /// Numeric value builder
    value_num_builder: Float64Builder,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl GenericState {
    /// Create a new generic state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            path_builder: StringBuilder::new(),
            type_builder: StringBuilder::new(),
            value_str_builder: StringBuilder::new(),
            value_num_builder: Float64Builder::new(),
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

    /// Process a message by flattening its JSON to rows.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        // Parse as generic JSON value
        let mut json_bytes = json_str.into_bytes();
        let Ok(value) = simd_json::from_slice::<JsonValue<'_>>(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        // Flatten the JSON recursively
        self.flatten_value("", &value);
    }

    /// Recursively flatten a JSON value into rows.
    fn flatten_value(&mut self, path: &str, value: &JsonValue<'_>) {
        match value {
            JsonValue::Null => {
                self.append_row(path, "null", None, None);
            }
            JsonValue::Bool(b) => {
                self.append_row(path, "boolean", Some(&b.to_string()), None);
            }
            JsonValue::Int(i) => {
                self.append_row(path, "number", Some(&i.to_string()), Some(*i as f64));
            }
            JsonValue::Float(f) => {
                self.append_row(path, "number", Some(&f.to_string()), Some(*f));
            }
            JsonValue::String(s) => {
                self.append_row(path, "string", Some(s.as_ref()), None);
            }
            JsonValue::Array(arr) => {
                for (i, item) in arr.iter().enumerate() {
                    let child_path = if path.is_empty() {
                        format!("[{i}]")
                    } else {
                        format!("{path}[{i}]")
                    };
                    self.flatten_value(&child_path, item);
                }
            }
            JsonValue::Object(obj) => {
                for (key, val) in obj {
                    let child_path = if path.is_empty() {
                        key.to_string()
                    } else {
                        format!("{path}.{key}")
                    };
                    self.flatten_value(&child_path, val);
                }
            }
        }
    }

    /// Append a single row to the builders.
    fn append_row(
        &mut self,
        path: &str,
        value_type: &str,
        value_str: Option<&str>,
        value_num: Option<f64>,
    ) {
        self.path_builder.append_value(path);
        self.type_builder.append_value(value_type);

        match value_str {
            Some(s) => self.value_str_builder.append_value(s),
            None => self.value_str_builder.append_null(),
        }

        match value_num {
            Some(n) => self.value_num_builder.append_value(n),
            None => self.value_num_builder.append_null(),
        }
    }

    /// Build the final RecordBatch.
    fn build_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let path_array = self.path_builder.finish();
        let type_array = self.type_builder.finish();
        let value_str_array = self.value_str_builder.finish();
        let value_num_array = self.value_num_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("path", DataType::Utf8, false),
            Field::new("type", DataType::Utf8, false),
            Field::new("value_str", DataType::Utf8, true),
            Field::new("value_num", DataType::Float64, true),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(path_array),
                Arc::new(type_array),
                Arc::new(value_str_array),
                Arc::new(value_num_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
