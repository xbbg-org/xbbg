//! Bulk data (bds) state with Arrow builders.
//!
//! Extracts BulkDataResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::typed_builder::ColumnSet;
use xbbg_core::{BlpError, Message};

/// State for a bulk data request (bds).
pub struct BulkDataState {
    /// Field name as string (the bulk field to extract)
    field_name: String,
    /// Column set for building the output
    columns: ColumnSet,
    /// Discovered sub-field names (populated on first row)
    subfield_names: Vec<String>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl BulkDataState {
    /// Create a new bulkdata state.
    pub fn new(field: String, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            field_name: field,
            columns: ColumnSet::new(),
            subfield_names: Vec::new(),
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
        let mut order = vec!["ticker"];
        order.extend(self.subfield_names.iter().map(|s| s.as_str()));
        let result = self.columns.finish_with_order(&order);
        let _ = reply.send(result);
    }

    /// Process a BulkDataResponse message using Element API.
    ///
    /// Bloomberg structure (for bds - similar to refdata but with array fields):
    /// ```text
    /// ReferenceDataResponse {
    ///   securityData[] {
    ///     security: "AAPL US Equity"
    ///     fieldData {
    ///       DVD_HIST[] {           // <-- bulk field is an array
    ///         Declared Date: "2024-01-15"
    ///         Amount: 0.24
    ///         ...
    ///       }
    ///     }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get securityData array
        let Some(security_data) = root.get_by_str("securityData") else {
            trace!("No securityData in message");
            return;
        };

        // Iterate through each security
        let n = security_data.len();
        for i in 0..n {
            let Some(sec) = security_data.get_element(i) else {
                continue;
            };

            // Get ticker
            let ticker = sec
                .get_by_str("security")
                .and_then(|e| e.get_str(0))
                .unwrap_or("");

            // Check for security error
            if sec.get_by_str("securityError").is_some() {
                trace!(ticker = ticker, "Security has error, skipping");
                continue;
            }

            // Get fieldData
            let Some(field_data) = sec.get_by_str("fieldData") else {
                trace!(ticker = ticker, "No fieldData for security");
                continue;
            };

            // Get the bulk field (which is an array)
            let Some(bulk_field) = field_data.get_by_str(&self.field_name) else {
                trace!(ticker = ticker, field = %self.field_name, "Bulk field not found");
                continue;
            };

            // Iterate through the array of rows
            let row_count = bulk_field.len();
            for j in 0..row_count {
                let Some(row) = bulk_field.get_element(j) else {
                    continue;
                };

                self.columns.append_str("ticker", ticker);

                // Discover sub-fields on first row
                if self.subfield_names.is_empty() {
                    let num_children = row.num_children();
                    for k in 0..num_children {
                        if let Some(child) = row.get_at(k) {
                            let name = child.name();
                            self.subfield_names.push(name.as_str().to_string());
                        }
                    }
                }

                // Extract sub-field values
                for subfield_name in &self.subfield_names.clone() {
                    if let Some(subfield_elem) = row.get_by_str(subfield_name) {
                        if let Some(value) = subfield_elem.get_value(0) {
                            self.columns.append(subfield_name, value);
                        } else {
                            self.columns.append_null(subfield_name);
                        }
                    } else {
                        self.columns.append_null(subfield_name);
                    }
                }

                self.columns.end_row();
            }
        }
    }
}
