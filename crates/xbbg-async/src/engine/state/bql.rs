//! BQL (Bloomberg Query Language) state with Arrow builders.
//!
//! BQL responses contain structured result data that we extract directly
//! from Bloomberg Elements without JSON intermediate serialization.
//!
//! Note: BQL can return complex nested structures. We flatten them into
//! a tabular format with id column + value columns per field.

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;

use super::typed_builder::ColumnSet;
use xbbg_core::{BlpError, Message};

/// State for a BQL request.
pub struct BqlState {
    /// Column set for building the output
    columns: ColumnSet,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BqlState {
    /// Create a new BQL state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            columns: ColumnSet::new(),
            reply,
        }
    }

    /// Process a PARTIAL_RESPONSE message.
    pub fn on_partial(&mut self, msg: &Message) {
        self.process_message(msg);
    }

    /// Process the final RESPONSE message and send the result via reply channel.
    pub fn finish(mut self, msg: &Message) {
        self.process_message(msg);
        let reply = self.reply;
        let result = self.columns.finish();
        let _ = reply.send(result);
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
                self.extract_results(&results);
                return;
            }
        }

        // Structure 2: Direct results array
        if let Some(results) = root.get_by_str("results") {
            self.extract_results(&results);
            return;
        }

        // Structure 3: Flatten the entire response
        self.flatten_element("", &root);
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
