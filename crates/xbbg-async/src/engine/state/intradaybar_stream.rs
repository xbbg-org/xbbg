//! Streaming intraday bar (bdib) state with Arrow builders.
//!
//! Unlike IntradayBarState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int32Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::{BlpError, MessageRef};

/// Streaming state for an intraday bar request (bdib).
pub struct IntradayBarStreamState {
    /// Ticker for this request
    ticker: String,
    /// Stream channel for sending chunks
    stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    /// Schema (cached after first build)
    schema: Option<Arc<Schema>>,
}

impl IntradayBarStreamState {
    /// Create a new streaming intraday bar state.
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

    /// Process an IntradayBarResponse message and return a RecordBatch.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let elem = msg.elements();

        let bar_data = elem.get_element("barData")?;
        let bar_tick_data = bar_data.get_element("barTickData")?;

        let num_bars = bar_tick_data.num_values();
        if num_bars == 0 {
            return None;
        }

        // Create builders
        let mut ticker_builder = StringBuilder::new();
        let mut time_builder = TimestampMicrosecondBuilder::new();
        let mut open_builder = Float64Builder::new();
        let mut high_builder = Float64Builder::new();
        let mut low_builder = Float64Builder::new();
        let mut close_builder = Float64Builder::new();
        let mut volume_builder = Float64Builder::new();
        let mut num_events_builder = Int32Builder::new();

        for i in 0..num_bars {
            let bar_elem = bar_tick_data.get_value_as_element(i)?;

            ticker_builder.append_value(&self.ticker);

            // Time
            if let Some(time_elem) = bar_elem.get_element("time") {
                if let Ok(Some(dt)) = time_elem.get_value_as_datetime(0) {
                    time_builder.append_value(dt.timestamp_micros());
                } else {
                    time_builder.append_null();
                }
            } else {
                time_builder.append_null();
            }

            // OHLC + Volume
            Self::append_float64(&bar_elem, "open", &mut open_builder);
            Self::append_float64(&bar_elem, "high", &mut high_builder);
            Self::append_float64(&bar_elem, "low", &mut low_builder);
            Self::append_float64(&bar_elem, "close", &mut close_builder);
            Self::append_float64(&bar_elem, "volume", &mut volume_builder);

            // numEvents
            if let Some(num_events_elem) = bar_elem.get_element("numEvents") {
                if let Some(val) = num_events_elem.get_value_as_int64(0) {
                    num_events_builder.append_value(val as i32);
                } else {
                    num_events_builder.append_null();
                }
            } else {
                num_events_builder.append_null();
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
                Field::new("open", DataType::Float64, true),
                Field::new("high", DataType::Float64, true),
                Field::new("low", DataType::Float64, true),
                Field::new("close", DataType::Float64, true),
                Field::new("volume", DataType::Float64, true),
                Field::new("numEvents", DataType::Int32, true),
            ]))
        });

        let columns: Vec<Arc<dyn arrow::array::Array>> = vec![
            Arc::new(ticker_builder.finish()),
            Arc::new(time_builder.finish()),
            Arc::new(open_builder.finish()),
            Arc::new(high_builder.finish()),
            Arc::new(low_builder.finish()),
            Arc::new(close_builder.finish()),
            Arc::new(volume_builder.finish()),
            Arc::new(num_events_builder.finish()),
        ];

        RecordBatch::try_new(schema.clone(), columns).ok()
    }

    fn append_float64(elem: &xbbg_core::ElementRef, field: &str, builder: &mut Float64Builder) {
        if let Some(field_elem) = elem.get_element(field) {
            if let Some(val) = field_elem.get_value_as_float64(0) {
                builder.append_value(val);
            } else {
                builder.append_null();
            }
        } else {
            builder.append_null();
        }
    }
}
