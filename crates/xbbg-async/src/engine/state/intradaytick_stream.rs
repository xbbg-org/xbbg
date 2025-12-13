//! Streaming intraday tick (bdtick) state with Arrow builders.
//!
//! Unlike IntradayTickState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int64Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::{BlpError, MessageRef};

/// Streaming state for an intraday tick request (bdtick).
pub struct IntradayTickStreamState {
    /// Ticker for this request
    ticker: String,
    /// Stream channel for sending chunks
    stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    /// Schema (cached after first build)
    schema: Option<Arc<Schema>>,
}

impl IntradayTickStreamState {
    /// Create a new streaming intraday tick state.
    pub fn new(ticker: String, stream: mpsc::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            ticker,
            stream,
            schema: None,
        }
    }

    /// Process a PARTIAL_RESPONSE message and yield a chunk.
    pub fn on_partial(&mut self, msg: &MessageRef) {
        if let Some(batch) = self.process_message(msg) {
            let _ = self.stream.try_send(Ok(batch));
        }
    }

    /// Process the final RESPONSE message and close the stream.
    pub fn finish(mut self, msg: &MessageRef) {
        if let Some(batch) = self.process_message(msg) {
            let _ = self.stream.try_send(Ok(batch));
        }
    }

    /// Fail the stream with an error.
    pub fn fail(self, error: BlpError) {
        let _ = self.stream.try_send(Err(error));
    }

    /// Process an IntradayTickResponse message and return a RecordBatch.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let elem = msg.elements();

        let tick_data = elem.get_element("tickData")?;
        let tick_data_array = tick_data.get_element("tickData")?;

        let num_ticks = tick_data_array.num_values();
        if num_ticks == 0 {
            return None;
        }

        // Create builders
        let mut ticker_builder = StringBuilder::new();
        let mut time_builder = TimestampMicrosecondBuilder::new();
        let mut type_builder = StringBuilder::new();
        let mut value_builder = Float64Builder::new();
        let mut size_builder = Int64Builder::new();
        let mut condition_codes_builder = StringBuilder::new();

        for i in 0..num_ticks {
            let tick_elem = tick_data_array.get_value_as_element(i)?;

            ticker_builder.append_value(&self.ticker);

            // Time
            if let Some(time_elem) = tick_elem.get_element("time") {
                if let Ok(Some(dt)) = time_elem.get_value_as_datetime(0) {
                    time_builder.append_value(dt.timestamp_micros());
                } else {
                    time_builder.append_null();
                }
            } else {
                time_builder.append_null();
            }

            // Type
            if let Some(type_elem) = tick_elem.get_element("type") {
                if let Some(val) = type_elem.get_value_as_string(0) {
                    type_builder.append_value(&val);
                } else {
                    type_builder.append_null();
                }
            } else {
                type_builder.append_null();
            }

            // Value
            if let Some(value_elem) = tick_elem.get_element("value") {
                if let Some(val) = value_elem.get_value_as_float64(0) {
                    value_builder.append_value(val);
                } else {
                    value_builder.append_null();
                }
            } else {
                value_builder.append_null();
            }

            // Size
            if let Some(size_elem) = tick_elem.get_element("size") {
                if let Some(val) = size_elem.get_value_as_int64(0) {
                    size_builder.append_value(val);
                } else {
                    size_builder.append_null();
                }
            } else {
                size_builder.append_null();
            }

            // Condition codes
            if let Some(cc_elem) = tick_elem.get_element("conditionCodes") {
                if let Some(val) = cc_elem.get_value_as_string(0) {
                    condition_codes_builder.append_value(&val);
                } else {
                    condition_codes_builder.append_null();
                }
            } else {
                condition_codes_builder.append_null();
            }
        }

        // Build schema if not cached
        let schema = self.schema.get_or_insert_with(|| {
            Arc::new(Schema::new(vec![
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
            ]))
        });

        let columns: Vec<Arc<dyn arrow::array::Array>> = vec![
            Arc::new(ticker_builder.finish()),
            Arc::new(time_builder.finish()),
            Arc::new(type_builder.finish()),
            Arc::new(value_builder.finish()),
            Arc::new(size_builder.finish()),
            Arc::new(condition_codes_builder.finish()),
        ];

        RecordBatch::try_new(schema.clone(), columns).ok()
    }
}
