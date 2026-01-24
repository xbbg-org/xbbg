//! Streaming intraday tick (bdtick) state with Arrow builders.
//!
//! Unlike IntradayTickState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.
//!
//! Extracts directly from Bloomberg Elements without JSON intermediate.

use std::sync::Arc;

use arrow::array::{
    ArrayRef, Float64Builder, Int64Builder, StringBuilder, TimestampMicrosecondBuilder,
};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::{BlpError, Message};

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
    pub fn on_partial(&mut self, msg: &Message) {
        if let Some(batch) = self.process_message(msg) {
            let _ = self.stream.try_send(Ok(batch));
        }
    }

    /// Process the final RESPONSE message and close the stream.
    pub fn finish(mut self, msg: &Message) {
        if let Some(batch) = self.process_message(msg) {
            let _ = self.stream.try_send(Ok(batch));
        }
    }

    /// Fail the stream with an error.
    pub fn fail(self, error: BlpError) {
        let _ = self.stream.try_send(Err(error));
    }

    /// Process an IntradayTickResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// IntradayTickResponse {
    ///   tickData {
    ///     tickData[] {
    ///       time: 2024-01-15T09:30:00.123456
    ///       type: "TRADE"
    ///       value: 150.0
    ///       size: 100
    ///       conditionCodes: "R"
    ///     }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) -> Option<RecordBatch> {
        let root = msg.elements();

        // Get tickData (outer)
        let tick_data_outer = root.get_by_str("tickData")?;

        // Get tickData array (inner - same name as parent)
        let tick_data = tick_data_outer.get_by_str("tickData")?;
        let n = tick_data.len();
        if n == 0 {
            return None;
        }

        // Create builders
        let mut ticker_builder = StringBuilder::new();
        let mut time_builder = TimestampMicrosecondBuilder::new();
        let mut type_builder = StringBuilder::new();
        let mut value_builder = Float64Builder::new();
        let mut size_builder = Int64Builder::new();
        let mut condition_codes_builder = StringBuilder::new();

        for i in 0..n {
            let Some(tick) = tick_data.get_element(i) else {
                continue;
            };

            ticker_builder.append_value(&self.ticker);

            // Get time - native datetime extraction
            if let Some(time_elem) = tick.get_by_str("time") {
                if let Some(micros) = time_elem.get_timestamp_us(0) {
                    time_builder.append_value(micros);
                } else {
                    time_builder.append_null();
                }
            } else {
                time_builder.append_null();
            }

            // Type
            if let Some(type_elem) = tick.get_by_str("type") {
                if let Some(t) = type_elem.get_str(0) {
                    type_builder.append_value(t);
                } else {
                    type_builder.append_null();
                }
            } else {
                type_builder.append_null();
            }

            // Value
            if let Some(val_elem) = tick.get_by_str("value") {
                if let Some(v) = val_elem.get_f64(0) {
                    value_builder.append_value(v);
                } else {
                    value_builder.append_null();
                }
            } else {
                value_builder.append_null();
            }

            // Size
            if let Some(size_elem) = tick.get_by_str("size") {
                if let Some(s) = size_elem.get_i64(0) {
                    size_builder.append_value(s);
                } else if let Some(s) = size_elem.get_i32(0) {
                    size_builder.append_value(s as i64);
                } else {
                    size_builder.append_null();
                }
            } else {
                size_builder.append_null();
            }

            // Condition codes
            if let Some(cc_elem) = tick.get_by_str("conditionCodes") {
                if let Some(cc) = cc_elem.get_str(0) {
                    condition_codes_builder.append_value(cc);
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
                    DataType::Timestamp(TimeUnit::Microsecond, Some("UTC".into())),
                    true,
                ),
                Field::new("type", DataType::Utf8, true),
                Field::new("value", DataType::Float64, true),
                Field::new("size", DataType::Int64, true),
                Field::new("conditionCodes", DataType::Utf8, true),
            ]))
        });

        let columns: Vec<ArrayRef> = vec![
            Arc::new(ticker_builder.finish()),
            Arc::new(time_builder.finish().with_timezone("UTC")),
            Arc::new(type_builder.finish()),
            Arc::new(value_builder.finish()),
            Arc::new(size_builder.finish()),
            Arc::new(condition_codes_builder.finish()),
        ];

        RecordBatch::try_new(schema.clone(), columns).ok()
    }
}
