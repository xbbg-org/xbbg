//! BSRCH (Bloomberg Search) state with Arrow builders.
//!
//! Extracts BSRCH responses directly from Bloomberg Elements.
//!
//! BSRCH response structure:
//! ```text
//! BeqsData {
//!   numOfFields: 3
//!   fieldDisplayUnits[]
//!   results[] {
//!     resultsRow[] {
//!       col1, col2, col3, ...
//!     }
//!   }
//! }
//! ```

use std::sync::Arc;

use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use xbbg_log::trace;

use super::typed_builder::ColumnSet;
use xbbg_core::{BlpError, Message};

/// State for a BSRCH request.
pub struct BsrchState {
    /// Column set for building the output
    columns: ColumnSet,
    /// Discovered column names
    column_names: Vec<String>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BsrchState {
    /// Create a new BSRCH state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            columns: ColumnSet::new(),
            column_names: Vec::new(),
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
        let result = if self.columns.column_count() == 0 {
            // Return empty batch with ticker column
            let schema = Arc::new(Schema::new(vec![Field::new(
                "ticker",
                DataType::Utf8,
                true,
            )]));
            RecordBatch::try_new(
                schema,
                vec![Arc::new(arrow::array::StringArray::from(
                    Vec::<Option<&str>>::new(),
                ))],
            )
            .map_err(|e| BlpError::Internal {
                detail: format!("build empty RecordBatch: {e}"),
            })
        } else if !self.column_names.is_empty() {
            let order: Vec<&str> = self.column_names.iter().map(|s| s.as_str()).collect();
            self.columns.finish_with_order(&order)
        } else {
            self.columns.finish()
        };
        let _ = reply.send(result);
    }

    /// Process a BSRCH response message using Element API.
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Try to find BeqsData or similar response structure
        // We check in order of preference and work with whichever we find
        let beqs_data_opt = root
            .get_by_str("BeqsData")
            .or_else(|| root.get_by_str("beqsData"));

        // Helper to get the actual data element to work with
        let get_field_units = || {
            beqs_data_opt
                .as_ref()
                .and_then(|d| d.get_by_str("fieldDisplayUnits"))
                .or_else(|| root.get_by_str("fieldDisplayUnits"))
        };

        let get_results = || {
            beqs_data_opt
                .as_ref()
                .and_then(|d| d.get_by_str("results"))
                .or_else(|| root.get_by_str("results"))
        };

        // Try to get column names from fieldDisplayUnits or similar
        if self.column_names.is_empty() {
            if let Some(field_units) = get_field_units() {
                let n = field_units.len();
                for i in 0..n {
                    if let Some(unit) = field_units.get_element(i) {
                        // Try to get the field name
                        let name = unit
                            .get_by_str("field")
                            .or_else(|| unit.get_by_str("fieldId"))
                            .and_then(|e| e.get_str(0))
                            .unwrap_or_else(|| format!("col{}", i).leak());
                        self.column_names.push(name.to_string());
                    }
                }
            }
        }

        // Get results array
        let Some(results) = get_results() else {
            trace!("No results in BSRCH response");
            return;
        };

        // Iterate through results
        let n = results.len();
        for i in 0..n {
            let Some(result) = results.get_element(i) else {
                continue;
            };

            // Get resultsRow (may be nested) - use helper closure to avoid clone
            let row_opt = result.get_by_str("resultsRow");

            // Helper function to process a row element
            let process_row = |row: &xbbg_core::Element<'_>,
                               column_names: &mut Vec<String>,
                               columns: &mut ColumnSet| {
                // If we don't have column names yet, discover them
                if column_names.is_empty() {
                    let num_children = row.num_children();
                    for j in 0..num_children {
                        if let Some(child) = row.get_at(j) {
                            column_names.push(child.name().as_str().to_string());
                        }
                    }
                }

                // Extract values
                if !column_names.is_empty() {
                    for col_name in column_names.clone().iter() {
                        if let Some(col_elem) = row.get_by_str(col_name) {
                            if let Some(value) = col_elem.get_value(0) {
                                columns.append(col_name, value);
                            } else {
                                columns.append_null(col_name);
                            }
                        } else {
                            columns.append_null(col_name);
                        }
                    }
                } else {
                    // Fallback: iterate all children
                    let num_children = row.num_children();
                    for j in 0..num_children {
                        if let Some(child) = row.get_at(j) {
                            let name = child.name();
                            if let Some(value) = child.get_value(0) {
                                columns.append(name.as_str(), value);
                            } else {
                                columns.append_null(name.as_str());
                            }
                        }
                    }
                }

                columns.end_row();
            };

            // Process either the nested resultsRow or the result itself
            if let Some(ref row) = row_opt {
                process_row(row, &mut self.column_names, &mut self.columns);
            } else {
                process_row(&result, &mut self.column_names, &mut self.columns);
            }
        }
    }
}
