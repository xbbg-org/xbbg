//! Streaming intraday tick (bdtick) state with Arrow builders.
//!
//! Unlike IntradayTickState, this state yields chunks immediately via a channel
//! instead of accumulating all data until the final response.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int64Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, Utc};
use tokio::sync::mpsc;
use tracing::trace;

use super::json_schema;
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

    /// Process an IntradayTickResponse message using JSON bulk extraction.
    fn process_message(&mut self, msg: &MessageRef) -> Option<RecordBatch> {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return None;
        };

        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_intraday_tick(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return None;
        };

        if resp.tick_data.tick_data.is_empty() {
            return None;
        }

        // Create builders
        let mut ticker_builder = StringBuilder::new();
        let mut time_builder = TimestampMicrosecondBuilder::new();
        let mut type_builder = StringBuilder::new();
        let mut value_builder = Float64Builder::new();
        let mut size_builder = Int64Builder::new();
        let mut condition_codes_builder = StringBuilder::new();

        for tick in &resp.tick_data.tick_data {
            ticker_builder.append_value(&self.ticker);

            // Parse time string to microseconds since epoch
            if let Some(time_str) = &tick.time {
                if let Some(micros) = parse_datetime_to_micros(time_str.as_ref()) {
                    time_builder.append_value(micros);
                } else {
                    time_builder.append_null();
                }
            } else {
                time_builder.append_null();
            }

            // Type
            if let Some(t) = &tick.tick_type {
                type_builder.append_value(t.as_ref());
            } else {
                type_builder.append_null();
            }

            // Value
            if let Some(v) = tick.value {
                value_builder.append_value(v);
            } else {
                value_builder.append_null();
            }

            // Size
            if let Some(s) = tick.size {
                size_builder.append_value(s);
            } else {
                size_builder.append_null();
            }

            // Condition codes (not in base schema, append null)
            condition_codes_builder.append_null();
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
