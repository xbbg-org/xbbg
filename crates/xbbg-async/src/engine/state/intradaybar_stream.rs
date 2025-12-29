//! Streaming intraday bar (bdib) state with Arrow builders.
//!
//! Unlike IntradayBarState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int32Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, Utc};
use tokio::sync::mpsc;
use tracing::trace;

use super::json_schema;
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

    /// Process an IntradayBarResponse message using JSON bulk extraction.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return None;
        };

        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_intraday_bar(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return None;
        };

        if resp.bar_data.bar_tick_data.is_empty() {
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

        for bar in &resp.bar_data.bar_tick_data {
            ticker_builder.append_value(&self.ticker);

            // Parse time string to microseconds since epoch
            if let Some(time_str) = &bar.time {
                if let Some(micros) = parse_datetime_to_micros(time_str.as_ref()) {
                    time_builder.append_value(micros);
                } else {
                    time_builder.append_null();
                }
            } else {
                time_builder.append_null();
            }

            // OHLC + Volume
            append_opt_f64(&mut open_builder, bar.open);
            append_opt_f64(&mut high_builder, bar.high);
            append_opt_f64(&mut low_builder, bar.low);
            append_opt_f64(&mut close_builder, bar.close);
            append_opt_f64(&mut volume_builder, bar.volume);

            // numEvents
            if let Some(n) = bar.num_events {
                num_events_builder.append_value(n as i32);
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
}

/// Parse an ISO datetime string to microseconds since epoch.
fn parse_datetime_to_micros(dt_str: &str) -> Option<i64> {
    if let Ok(dt) = DateTime::parse_from_rfc3339(dt_str) {
        return Some(dt.with_timezone(&Utc).timestamp_micros());
    }
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(dt_str, "%Y-%m-%dT%H:%M:%S") {
        return Some(dt.and_utc().timestamp_micros());
    }
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(dt_str, "%Y-%m-%dT%H:%M:%S%.3f") {
        return Some(dt.and_utc().timestamp_micros());
    }
    None
}

/// Helper to append an optional f64 to a Float64Builder.
fn append_opt_f64(builder: &mut Float64Builder, value: Option<f64>) {
    match value {
        Some(v) => builder.append_value(v),
        None => builder.append_null(),
    }
}
