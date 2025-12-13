//! Intraday tick (bdtick) state with Arrow builders.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int64Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;

use xbbg_core::{BlpError, MessageRef};

/// State for an intraday tick request (bdtick).
pub struct IntradayTickState {
    /// Ticker for this request
    ticker: String,
    /// Ticker builder
    ticker_builder: StringBuilder,
    /// Time builder (microseconds since epoch)
    time_builder: TimestampMicrosecondBuilder,
    /// Event type builder (TRADE, BID, ASK, etc.)
    type_builder: StringBuilder,
    /// Value builder (price)
    value_builder: Float64Builder,
    /// Size builder
    size_builder: Int64Builder,
    /// Condition codes builder
    condition_codes_builder: StringBuilder,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl IntradayTickState {
    /// Create a new intraday tick state.
    pub fn new(ticker: String, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            ticker,
            ticker_builder: StringBuilder::new(),
            time_builder: TimestampMicrosecondBuilder::new(),
            type_builder: StringBuilder::new(),
            value_builder: Float64Builder::new(),
            size_builder: Int64Builder::new(),
            condition_codes_builder: StringBuilder::new(),
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

        let result = self.build_batch_inner();
        let _ = self.reply.send(result);
    }

    /// Process an IntradayTickResponse message.
    fn process_message(&mut self, msg: &MessageRef) {
        let elem = msg.elements();

        // Get tickData
        let Some(tick_data) = elem.get_element("tickData") else {
            return;
        };

        // Get tickData array (nested)
        let Some(tick_data_array) = tick_data.get_element("tickData") else {
            return;
        };

        let num_ticks = tick_data_array.num_values();
        for i in 0..num_ticks {
            let Some(tick_elem) = tick_data_array.get_value_as_element(i) else {
                continue;
            };

            self.ticker_builder.append_value(&self.ticker);

            // Get time
            if let Some(time_elem) = tick_elem.get_element("time") {
                if let Ok(Some(dt)) = time_elem.get_value_as_datetime(0) {
                    let micros = dt.timestamp_micros();
                    self.time_builder.append_value(micros);
                } else {
                    self.time_builder.append_null();
                }
            } else {
                self.time_builder.append_null();
            }

            // Get type
            if let Some(type_elem) = tick_elem.get_element("type") {
                if let Some(val) = type_elem.get_value_as_string(0) {
                    self.type_builder.append_value(&val);
                } else {
                    self.type_builder.append_null();
                }
            } else {
                self.type_builder.append_null();
            }

            // Get value (price)
            if let Some(value_elem) = tick_elem.get_element("value") {
                if let Some(val) = value_elem.get_value_as_float64(0) {
                    self.value_builder.append_value(val);
                } else {
                    self.value_builder.append_null();
                }
            } else {
                self.value_builder.append_null();
            }

            // Get size
            if let Some(size_elem) = tick_elem.get_element("size") {
                if let Some(val) = size_elem.get_value_as_int64(0) {
                    self.size_builder.append_value(val);
                } else {
                    self.size_builder.append_null();
                }
            } else {
                self.size_builder.append_null();
            }

            // Get conditionCodes
            if let Some(cc_elem) = tick_elem.get_element("conditionCodes") {
                if let Some(val) = cc_elem.get_value_as_string(0) {
                    self.condition_codes_builder.append_value(&val);
                } else {
                    self.condition_codes_builder.append_null();
                }
            } else {
                self.condition_codes_builder.append_null();
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let time_array = self.time_builder.finish();
        let type_array = self.type_builder.finish();
        let value_array = self.value_builder.finish();
        let size_array = self.size_builder.finish();
        let condition_codes_array = self.condition_codes_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new(
                "time",
                DataType::Timestamp(TimeUnit::Microsecond, None),
                true,
            ),
            Field::new("type", DataType::Utf8, true),
            Field::new("value", DataType::Float64, true),
            Field::new("size", DataType::Int64, true),
            Field::new("conditionCodes", DataType::Utf8, true),
        ]));

        let columns: Vec<Arc<dyn arrow::array::Array>> = vec![
            Arc::new(ticker_array),
            Arc::new(time_array),
            Arc::new(type_array),
            Arc::new(value_array),
            Arc::new(size_array),
            Arc::new(condition_codes_array),
        ];

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
