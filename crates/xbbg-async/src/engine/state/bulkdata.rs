//! Bulk data (bds) state with Arrow builders.

use std::sync::Arc;

use arrow::array::StringBuilder;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;

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

    /// Process a BulkDataResponse message.
    fn process_message(&mut self, msg: &MessageRef) {
        let elem = msg.elements();

        // Get securityData array
        let Some(security_data) = elem.get_element("securityData") else {
            return;
        };

        let num_securities = security_data.num_values();
        for i in 0..num_securities {
            let Some(sec_elem) = security_data.get_value_as_element(i) else {
                continue;
            };

            // Get security name
            let ticker = sec_elem
                .get_element("security")
                .and_then(|e| e.get_value_as_string(0))
                .unwrap_or_default();

            // Get fieldData
            let Some(field_data) = sec_elem.get_element("fieldData") else {
                continue;
            };

            // Get the bulk field (array of rows)
            let Some(bulk_array) = field_data.get_element(&self.field_string) else {
                continue;
            };

            let num_rows = bulk_array.num_values();
            for j in 0..num_rows {
                let Some(row_elem) = bulk_array.get_value_as_element(j) else {
                    continue;
                };

                self.ticker_builder.append_value(&ticker);

                // Discover sub-fields on first row
                if self.subfield_names.is_empty() {
                    let num_elements = row_elem.num_elements();
                    for k in 0..num_elements {
                        if let Some(sub_elem) = row_elem.get_element_at(k) {
                            if let Some(name) = sub_elem.name_string() {
                                self.subfield_names.push(name);
                                self.subfield_builders.push(StringBuilder::new());
                            }
                        }
                    }
                }

                // Extract sub-field values
                for (k, subfield_name) in self.subfield_names.iter().enumerate() {
                    if let Some(sub_elem) = row_elem.get_element(subfield_name) {
                        let value = sub_elem.get_value_as_string(0).unwrap_or_default();
                        self.subfield_builders[k].append_value(&value);
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
