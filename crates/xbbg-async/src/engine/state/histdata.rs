//! Historical data (bdh) state with Arrow builders.

use std::sync::Arc;

use arrow::array::{Date32Builder, Float64Builder, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;

use xbbg_core::{BlpError, MessageRef};

/// State for a historical data request (bdh).
pub struct HistDataState {
    /// Field names as strings
    field_strings: Vec<String>,
    /// Ticker builder
    ticker_builder: StringBuilder,
    /// Date builder (days since epoch)
    date_builder: Date32Builder,
    /// Value builders (one per field)
    field_builders: Vec<Float64Builder>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl HistDataState {
    /// Create a new histdata state.
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        let field_builders = fields.iter().map(|_| Float64Builder::new()).collect();

        Self {
            field_strings: fields,
            ticker_builder: StringBuilder::new(),
            date_builder: Date32Builder::new(),
            field_builders,
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

    /// Process a HistoricalDataResponse message.
    fn process_message(&mut self, msg: &MessageRef) {
        let elem = msg.elements();

        // Get securityData
        let Some(security_data) = elem.get_element("securityData") else {
            return;
        };

        // Historical data has a single security per message
        let ticker = security_data
            .get_element("security")
            .and_then(|e| e.get_value_as_string(0))
            .unwrap_or_default();

        // Get fieldData array
        let Some(field_data) = security_data.get_element("fieldData") else {
            return;
        };

        let num_rows = field_data.num_values();
        for i in 0..num_rows {
            let Some(row_elem) = field_data.get_value_as_element(i) else {
                continue;
            };

            self.ticker_builder.append_value(&ticker);

            // Get date
            if let Some(date_elem) = row_elem.get_element("date") {
                if let Ok(Some(dt)) = date_elem.get_value_as_datetime(0) {
                    // Convert to days since epoch
                    let days = (dt.timestamp() / 86400) as i32;
                    self.date_builder.append_value(days);
                } else {
                    self.date_builder.append_null();
                }
            } else {
                self.date_builder.append_null();
            }

            // Get each field value
            for (j, field_str) in self.field_strings.iter().enumerate() {
                if let Some(field_elem) = row_elem.get_element(field_str) {
                    if let Some(val) = field_elem.get_value_as_float64(0) {
                        self.field_builders[j].append_value(val);
                    } else {
                        self.field_builders[j].append_null();
                    }
                } else {
                    self.field_builders[j].append_null();
                }
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let date_array = self.date_builder.finish();
        let field_arrays: Vec<_> = self
            .field_builders
            .iter_mut()
            .map(|b| Arc::new(b.finish()) as _)
            .collect();

        // Build schema
        let mut fields = vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("date", DataType::Date32, true),
        ];
        for name in &self.field_strings {
            fields.push(Field::new(name.as_str(), DataType::Float64, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> =
            vec![Arc::new(ticker_array), Arc::new(date_array)];
        columns.extend(field_arrays);

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
