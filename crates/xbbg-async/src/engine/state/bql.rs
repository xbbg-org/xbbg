//! BQL (Bloomberg Query Language) state with Arrow builders.
//!
//! BQL responses contain structured result data that we extract directly
//! from Bloomberg Elements without JSON intermediate serialization.
//!
//! Note: BQL can return complex nested structures. We flatten them into
//! a tabular format with id column + value columns per field.

use arrow::array::{ArrayRef, Float64Builder, StringArray, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use serde_json::Value as JsonValue;
use std::sync::Arc;
use tokio::sync::oneshot;

use super::typed_builder::ColumnSet;
use xbbg_core::{BlpError, Message};

/// State for a BQL request.
pub struct BqlState {
    /// Column set for building the output
    columns: ColumnSet,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    /// Accumulated JSON string (for JSON-encoded responses)
    json_buffer: Option<String>,
}

impl BqlState {
    /// Create a new BQL state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            columns: ColumnSet::new(),
            reply,
            json_buffer: None,
        }
    }

    /// Process a PARTIAL_RESPONSE message.
    pub fn on_partial(&mut self, msg: &Message) {
        self.process_message(msg);
    }

    /// Process the final RESPONSE message and send the result via reply channel.
    pub fn finish(mut self, msg: &Message) {
        self.process_message(msg);

        // If we accumulated JSON, try to parse it
        let result = if let Some(json_str) = self.json_buffer.take() {
            self.parse_bql_json(&json_str)
        } else {
            self.columns.finish()
        };

        if let Ok(ref batch) = result {
            xbbg_log::debug!(
                rows = batch.num_rows(),
                cols = batch.num_columns(),
                "bql finish"
            );
        }
        let _ = self.reply.send(result);
    }

    /// Process a BQL response message using Element API.
    ///
    /// BQL response structure:
    /// ```text
    /// beqlData {
    ///   results[] {
    ///     ... varies by query
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Try different BQL response structures
        // Structure 1: beqlData -> results
        if let Some(beql_data) = root.get_by_str("beqlData") {
            if let Some(results) = beql_data.get_by_str("results") {
                // Check if first result is a JSON string
                if results.len() > 0 {
                    if let Some(first) = results.get_element(0) {
                        if let Some(xbbg_core::Value::String(s)) = first.get_value(0) {
                            // This is a JSON-encoded response
                            if s.starts_with('{') {
                                self.json_buffer = Some(s.to_string());
                                return;
                            }
                        }
                    }
                }
                self.extract_results(&results);
                return;
            }

            // Check for direct JSON string in beqlData
            if let Some(xbbg_core::Value::String(s)) = beql_data.get_value(0) {
                if s.starts_with('{') {
                    self.json_buffer = Some(s.to_string());
                    return;
                }
            }
        }

        // Structure 2: Direct results array
        if let Some(results) = root.get_by_str("results") {
            self.extract_results(&results);
            return;
        }

        // Structure 3: Check if root contains a JSON string value
        if let Some(xbbg_core::Value::String(s)) = root.get_value(0) {
            if s.starts_with('{') {
                self.json_buffer = Some(s.to_string());
                return;
            }
        }

        // Structure 4: Flatten the entire response (fallback)
        self.flatten_element("", &root);
    }

    /// Parse BQL JSON response into a proper table.
    ///
    /// BQL JSON structure:
    /// ```json
    /// {
    ///   "results": {
    ///     "field_name": {
    ///       "idColumn": { "values": ["ticker1", "ticker2", ...] },
    ///       "valuesColumn": { "values": [value1, value2, ...] }
    ///     },
    ///     ...
    ///   }
    /// }
    /// ```
    fn parse_bql_json(&self, json_str: &str) -> Result<RecordBatch, BlpError> {
        let json: JsonValue = serde_json::from_str(json_str).map_err(|e| BlpError::Internal {
            detail: format!("Failed to parse BQL JSON: {}", e),
        })?;

        let results = json.get("results").ok_or_else(|| BlpError::Internal {
            detail: "BQL JSON missing 'results' field".into(),
        })?;

        let results_obj = results.as_object().ok_or_else(|| BlpError::Internal {
            detail: "BQL 'results' is not an object".into(),
        })?;

        if results_obj.is_empty() {
            // Return empty batch
            let schema = Schema::new(vec![Field::new("ticker", DataType::Utf8, true)]);
            return RecordBatch::try_new(
                Arc::new(schema),
                vec![Arc::new(StringArray::from(Vec::<&str>::new()))],
            )
            .map_err(|e| BlpError::Internal {
                detail: format!("Failed to create empty batch: {}", e),
            });
        }

        // Collect field names and determine row count from first field
        let field_names: Vec<&String> = results_obj.keys().collect();
        let mut id_values: Vec<String> = Vec::new();
        let mut field_columns: Vec<(&str, Vec<Option<JsonValue>>)> = Vec::new();

        for field_name in &field_names {
            let field_data = &results_obj[*field_name];

            // Extract idColumn values (only need to do this once)
            if id_values.is_empty() {
                if let Some(id_col) = field_data.get("idColumn") {
                    if let Some(values) = id_col.get("values") {
                        if let Some(arr) = values.as_array() {
                            id_values = arr
                                .iter()
                                .map(|v| match v {
                                    JsonValue::String(s) => s.clone(),
                                    JsonValue::Null => String::new(),
                                    other => other.to_string(),
                                })
                                .collect();
                        }
                    }
                }
            }

            // Extract valuesColumn values
            let mut values: Vec<Option<JsonValue>> = Vec::new();
            if let Some(val_col) = field_data.get("valuesColumn") {
                if let Some(vals) = val_col.get("values") {
                    if let Some(arr) = vals.as_array() {
                        values = arr
                            .iter()
                            .map(|v| if v.is_null() { None } else { Some(v.clone()) })
                            .collect();
                    }
                }
            }

            // Pad values to match id_values length if needed
            while values.len() < id_values.len() {
                values.push(None);
            }

            field_columns.push((field_name.as_str(), values));
        }

        // Build Arrow arrays
        // Use "ticker" for the id column to avoid conflicts with user-requested "id" field
        let mut id_builder = StringBuilder::new();
        for v in &id_values {
            id_builder.append_value(v);
        }

        let mut fields = vec![Field::new("ticker", DataType::Utf8, true)];
        let mut arrays: Vec<ArrayRef> = vec![Arc::new(id_builder.finish())];

        // Value columns - detect type from first non-null value
        for (name, values) in &field_columns {
            // Detect if numeric
            let is_numeric = values
                .iter()
                .any(|v| matches!(v, Some(JsonValue::Number(_))));

            if is_numeric {
                let mut builder = Float64Builder::new();
                for v in values {
                    match v {
                        Some(JsonValue::Number(n)) => {
                            builder.append_value(n.as_f64().unwrap_or(f64::NAN));
                        }
                        Some(JsonValue::String(s)) => {
                            // Try to parse string as number
                            if let Ok(f) = s.parse::<f64>() {
                                builder.append_value(f);
                            } else {
                                builder.append_null();
                            }
                        }
                        _ => builder.append_null(),
                    }
                }
                fields.push(Field::new(*name, DataType::Float64, true));
                arrays.push(Arc::new(builder.finish()));
            } else {
                let mut builder = StringBuilder::new();
                for v in values {
                    match v {
                        Some(JsonValue::String(s)) => builder.append_value(s),
                        Some(JsonValue::Null) | None => builder.append_null(),
                        Some(other) => builder.append_value(other.to_string()),
                    }
                }
                fields.push(Field::new(*name, DataType::Utf8, true));
                arrays.push(Arc::new(builder.finish()));
            }
        }

        let schema = Arc::new(Schema::new(fields));
        RecordBatch::try_new(schema, arrays).map_err(|e| BlpError::Internal {
            detail: format!("Failed to create RecordBatch: {}", e),
        })
    }

    /// Extract results from a BQL results element.
    fn extract_results(&mut self, results: &xbbg_core::Element) {
        let n = results.len();
        for i in 0..n {
            if let Some(row) = results.get_element(i) {
                // Each result row - extract all fields
                let num_children = row.num_children();
                for j in 0..num_children {
                    if let Some(child) = row.get_at(j) {
                        let name = child.name();
                        let name_str = name.as_str();
                        if let Some(value) = child.get_value(0) {
                            self.columns.append(name_str, value);
                        } else {
                            self.columns.append_null(name_str);
                        }
                    }
                }
                self.columns.end_row();
            }
        }
    }

    /// Flatten an element into path-value pairs (fallback for complex structures).
    fn flatten_element(&mut self, path: &str, element: &xbbg_core::Element) {
        let datatype = element.datatype();

        // For complex types, recurse into children
        if datatype.is_complex() {
            // If it's an array/sequence with values
            if element.is_array() {
                let n = element.len();
                for i in 0..n {
                    if let Some(child) = element.get_element(i) {
                        let child_path = if path.is_empty() {
                            format!("[{i}]")
                        } else {
                            format!("{path}[{i}]")
                        };
                        self.flatten_element(&child_path, &child);
                    }
                }
            } else {
                // Iterate named children
                let n = element.num_children();
                for i in 0..n {
                    if let Some(child) = element.get_at(i) {
                        let name = child.name();
                        let child_path = if path.is_empty() {
                            name.as_str().to_string()
                        } else {
                            format!("{}.{}", path, name.as_str())
                        };
                        self.flatten_element(&child_path, &child);
                    }
                }
            }
        } else {
            // Leaf value - add to columns
            if let Some(value) = element.get_value(0) {
                self.columns.append_str("path", path);

                // Convert value to string for generic representation
                let value_str = match &value {
                    xbbg_core::Value::String(s) | xbbg_core::Value::Enum(s) => s.to_string(),
                    xbbg_core::Value::Float64(f) => f.to_string(),
                    xbbg_core::Value::Int64(i) => i.to_string(),
                    xbbg_core::Value::Int32(i) => i.to_string(),
                    xbbg_core::Value::Bool(b) => b.to_string(),
                    xbbg_core::Value::Null => String::new(),
                    _ => format!("{:?}", value),
                };
                self.columns.append_str("value", &value_str);
                self.columns.end_row();
            }
        }
    }
}
