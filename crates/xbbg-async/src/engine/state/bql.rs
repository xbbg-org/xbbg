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
use std::{collections::HashSet, sync::Arc};
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
                if !results.is_empty() {
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
    /// Bloomberg BQL JSON response structure:
    /// ```json
    /// {
    ///   "clientContext": { "clientRequestId": "...", ... },
    ///   "responseExceptions": null | [{ "message", "messageCategory",
    ///       "messageSubcategory", "nodeName", "type" }],
    ///   "results": null | {
    ///     "field_name": {
    ///       "idColumn": { "name": "ID", "type": "STRING", "values": [...] },
    ///       "valuesColumn": { "name": "VALUE", "type": "DOUBLE"|..., "values": [...] },
    ///       "secondaryColumns": [{ "name": "DATE"|"CURRENCY", "values": [...] }],
    ///       "responseExceptions": [],
    ///       "partialErrorMap": { "errorIterator": null | [...] }
    ///     }
    ///   }
    /// }
    /// ```
    fn parse_bql_json(&self, json_str: &str) -> Result<RecordBatch, BlpError> {
        let json: JsonValue = serde_json::from_str(json_str).map_err(|e| BlpError::Internal {
            detail: format!("Failed to parse BQL JSON: {}", e),
        })?;

        let request_id = json
            .get("clientContext")
            .and_then(|c| c.get("clientRequestId"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        // Collect top-level responseExceptions (syntax errors, invalid fields, etc.)
        let top_exceptions = Self::extract_exception_messages(&json);

        // Route on results: object → parse fields, null/missing → empty or error.
        let results_obj = match json.get("results") {
            Some(JsonValue::Object(obj)) if !obj.is_empty() => obj,
            Some(JsonValue::Object(_)) | Some(JsonValue::Null) | None => {
                // No results. If there were exceptions, report them as the error.
                if !top_exceptions.is_empty() {
                    return Err(BlpError::RequestFailure {
                        service: "//blp/bqlsvc".into(),
                        operation: Some("sendQuery".into()),
                        cid: None,
                        label: None,
                        request_id,
                        source: Some(top_exceptions.join("; ").into()),
                    });
                }
                return Self::empty_batch();
            }
            Some(other) => {
                return Err(BlpError::Internal {
                    detail: format!("BQL 'results' has unexpected type: {other}"),
                });
            }
        };

        // Results present — log any partial exceptions as warnings but continue.
        if !top_exceptions.is_empty() {
            xbbg_log::warn!(
                exceptions = top_exceptions.join("; ").as_str(),
                "BQL response has partial exceptions but results are present"
            );
        }

        // Collect field names and determine row count from first field
        let field_names: Vec<&String> = results_obj.keys().collect();
        let mut id_values: Vec<String> = Vec::new();
        type FieldCol<'a> = (String, Vec<Option<&'a JsonValue>>, Option<&'a str>);
        let mut field_columns: Vec<FieldCol<'_>> = Vec::new();
        let mut emitted_column_names = HashSet::new();

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

            // Extract secondaryColumns (e.g. DATE, CURRENCY) — time-series and
            // multi-axis BQL queries return per-field auxiliary dimensions here.
            // Emit each distinct column once, placed before the primary value
            // column so the natural column order is ticker, DATE, <field>.
            if let Some(JsonValue::Array(sec_cols)) = field_data.get("secondaryColumns") {
                for sec_col in sec_cols {
                    let Some(col_name) = sec_col.get("name").and_then(|n| n.as_str()) else {
                        continue;
                    };
                    let Some(JsonValue::Array(col_vals)) = sec_col.get("values") else {
                        continue;
                    };
                    let col_name_lower = col_name.to_lowercase();
                    if !emitted_column_names.insert(col_name_lower.clone()) {
                        continue;
                    }
                    let mut sec_values: Vec<Option<&JsonValue>> = col_vals
                        .iter()
                        .map(|v| if v.is_null() { None } else { Some(v) })
                        .collect();
                    sec_values.resize(id_values.len(), None);
                    let sec_type = sec_col.get("type").and_then(|t| t.as_str());
                    field_columns.push((col_name_lower, sec_values, sec_type));
                }
            }

            // Extract valuesColumn values and type hint
            let mut values: Vec<Option<&JsonValue>> = Vec::new();
            let mut val_type: Option<&str> = None;
            if let Some(val_col) = field_data.get("valuesColumn") {
                val_type = val_col.get("type").and_then(|t| t.as_str());
                if let Some(vals) = val_col.get("values") {
                    if let Some(arr) = vals.as_array() {
                        values = arr
                            .iter()
                            .map(|v| if v.is_null() { None } else { Some(v) })
                            .collect();
                    }
                }
            }

            values.resize(id_values.len(), None);

            // Warn about per-field partial errors
            let field_exceptions = Self::extract_exception_messages(field_data);
            if !field_exceptions.is_empty() {
                xbbg_log::warn!(
                    field = field_name.as_str(),
                    exceptions = field_exceptions.join("; ").as_str(),
                    "BQL field has partial errors"
                );
            }

            emitted_column_names.insert(field_name.to_string());
            field_columns.push((field_name.to_string(), values, val_type));
        }

        // Build Arrow arrays
        // Use "ticker" for the id column to avoid conflicts with user-requested "id" field
        let mut id_builder = StringBuilder::new();
        for v in &id_values {
            id_builder.append_value(v);
        }

        let mut fields = vec![Field::new("ticker", DataType::Utf8, true)];
        let mut arrays: Vec<ArrayRef> = vec![Arc::new(id_builder.finish())];

        for (name, values, type_hint) in &field_columns {
            let is_numeric = match type_hint {
                Some(t)
                    if t.eq_ignore_ascii_case("DOUBLE")
                        || t.eq_ignore_ascii_case("FLOAT")
                        || t.eq_ignore_ascii_case("INT32")
                        || t.eq_ignore_ascii_case("INT64")
                        || t.eq_ignore_ascii_case("INTEGER") =>
                {
                    true
                }
                Some(t)
                    if t.eq_ignore_ascii_case("STRING")
                        || t.eq_ignore_ascii_case("DATE")
                        || t.eq_ignore_ascii_case("DATETIME") =>
                {
                    false
                }
                _ => values
                    .iter()
                    .filter_map(|v| v.as_ref())
                    .all(|v| matches!(v, JsonValue::Number(_))),
            };

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
                fields.push(Field::new(name.as_str(), DataType::Float64, true));
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
                fields.push(Field::new(name.as_str(), DataType::Utf8, true));
                arrays.push(Arc::new(builder.finish()));
            }
        }

        let schema = Arc::new(Schema::new(fields));
        RecordBatch::try_new(schema, arrays).map_err(|e| BlpError::Internal {
            detail: format!("Failed to create RecordBatch: {}", e),
        })
    }

    /// Extract human-readable messages from a `responseExceptions` array.
    /// Works for both the top-level response and per-field exception arrays.
    fn extract_exception_messages(json: &JsonValue) -> Vec<String> {
        let Some(JsonValue::Array(exceptions)) = json.get("responseExceptions") else {
            return Vec::new();
        };
        exceptions
            .iter()
            .filter_map(|e| {
                e.get("message").and_then(|m| m.as_str()).map(|msg| {
                    if let Some(node) = e.get("nodeName").and_then(|n| n.as_str()) {
                        format!("{msg} (in {node})")
                    } else {
                        msg.to_string()
                    }
                })
            })
            .collect()
    }

    /// Return an empty single-column batch (no results).
    fn empty_batch() -> Result<RecordBatch, BlpError> {
        let schema = Schema::new(vec![Field::new("ticker", DataType::Utf8, true)]);
        RecordBatch::try_new(
            Arc::new(schema),
            vec![Arc::new(StringArray::from(Vec::<&str>::new()))],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("Failed to create empty batch: {}", e),
        })
    }

    /// Extract results from a BQL results element (legacy Element-API fallback).
    /// Note: secondaryColumns (DATE, CURRENCY) are only available in the JSON
    /// path — this path does not support them.
    fn extract_results(&mut self, results: &xbbg_core::Element) {
        xbbg_log::warn!(
            "BQL response routed to Element-API path — secondaryColumns will be missing"
        );
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

#[cfg(test)]
mod tests {
    use super::*;
    use arrow::array::{Float64Array, StringArray};

    fn make_state() -> BqlState {
        let (tx, _rx) = oneshot::channel();
        BqlState::new(tx)
    }

    #[test]
    fn parse_bql_json_extracts_secondary_columns() {
        let json = r#"{
            "clientContext": { "clientRequestId": "abc" },
            "responseExceptions": null,
            "results": {
                "px_last": {
                    "idColumn": {
                        "name": "ID",
                        "type": "STRING",
                        "values": ["AAPL US Equity", "AAPL US Equity", "AAPL US Equity"]
                    },
                    "valuesColumn": {
                        "name": "VALUE",
                        "type": "DOUBLE",
                        "values": [150.1, 151.2, 152.3]
                    },
                    "secondaryColumns": [
                        {
                            "name": "DATE",
                            "type": "DATE",
                            "values": ["2026-04-10", "2026-04-11", "2026-04-14"]
                        },
                        {
                            "name": "CURRENCY",
                            "type": "STRING",
                            "values": ["USD", "USD", "USD"]
                        }
                    ],
                    "responseExceptions": [],
                    "partialErrorMap": { "errorIterator": null }
                }
            }
        }"#;

        let batch = make_state().parse_bql_json(json).expect("parse ok");
        let schema = batch.schema();
        let names: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();
        assert_eq!(names, vec!["ticker", "date", "currency", "px_last"]);
        assert_eq!(batch.num_rows(), 3);

        let dates = batch
            .column(1)
            .as_any()
            .downcast_ref::<StringArray>()
            .expect("date column is utf8");
        assert_eq!(dates.value(0), "2026-04-10");
        assert_eq!(dates.value(2), "2026-04-14");

        let px = batch
            .column(3)
            .as_any()
            .downcast_ref::<Float64Array>()
            .expect("px_last column is f64");
        assert_eq!(px.value(0), 150.1);
    }

    #[test]
    fn parse_bql_json_dedupes_secondary_columns_across_fields() {
        let json = r#"{
            "results": {
                "px_last": {
                    "idColumn": { "values": ["T"] },
                    "valuesColumn": { "values": [1.0] },
                    "secondaryColumns": [
                        { "name": "DATE", "values": ["2026-04-10"] }
                    ]
                },
                "px_open": {
                    "idColumn": { "values": ["T"] },
                    "valuesColumn": { "values": [0.9] },
                    "secondaryColumns": [
                        { "name": "DATE", "values": ["2026-04-10"] }
                    ]
                }
            }
        }"#;

        let batch = make_state().parse_bql_json(json).expect("parse ok");
        let schema = batch.schema();
        let names: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();
        // DATE should appear exactly once, primary fields follow in insertion order
        let date_count = names.iter().filter(|n| **n == "date").count();
        assert_eq!(date_count, 1);
        assert!(names.contains(&"px_last"));
        assert!(names.contains(&"px_open"));
    }

    #[test]
    fn parse_bql_json_mismatched_field_lengths_truncates() {
        let json = r#"{
            "results": {
                "field_a": {
                    "idColumn": { "values": ["X", "Y"] },
                    "valuesColumn": { "type": "DOUBLE", "values": [1.0, 2.0] }
                },
                "field_b": {
                    "idColumn": { "values": ["X", "Y", "Z", "W"] },
                    "valuesColumn": { "type": "DOUBLE", "values": [10.0, 20.0, 30.0, 40.0] }
                }
            }
        }"#;

        let batch = make_state().parse_bql_json(json).expect("parse ok");
        assert_eq!(batch.num_rows(), 2);
        assert_eq!(batch.num_columns(), 3);
        let col_b = batch
            .column(2)
            .as_any()
            .downcast_ref::<Float64Array>()
            .expect("field_b is f64");
        assert_eq!(col_b.value(0), 10.0);
        assert_eq!(col_b.value(1), 20.0);
    }

    #[test]
    fn parse_bql_json_uses_type_hint_over_value_sniffing() {
        let json = r#"{
            "results": {
                "sector": {
                    "idColumn": { "values": ["AAPL"] },
                    "valuesColumn": { "type": "STRING", "values": ["Technology"] }
                }
            }
        }"#;

        let batch = make_state().parse_bql_json(json).expect("parse ok");
        let col = batch
            .column(1)
            .as_any()
            .downcast_ref::<StringArray>()
            .expect("sector is utf8 via type hint");
        assert_eq!(col.value(0), "Technology");
    }
}
