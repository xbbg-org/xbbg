//! Intraday bar (bdib) state with Arrow builders.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int32Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, Utc};
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema;
use xbbg_core::{BlpError, MessageRef};

/// State for an intraday bar request (bdib).
pub struct IntradayBarState {
    /// Event type (TRADE, BID, ASK, etc.)
    event_type: String,
    /// Interval in minutes
    interval: u32,
    /// Ticker builder
    ticker_builder: StringBuilder,
    /// Time builder (microseconds since epoch)
    time_builder: TimestampMicrosecondBuilder,
    /// Open price builder
    open_builder: Float64Builder,
    /// High price builder
    high_builder: Float64Builder,
    /// Low price builder
    low_builder: Float64Builder,
    /// Close price builder
    close_builder: Float64Builder,
    /// Volume builder
    volume_builder: Float64Builder,
    /// Number of events builder
    num_events_builder: Int32Builder,
    /// Ticker for this request
    ticker: String,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl IntradayBarState {
    /// Create a new intraday bar state.
    pub fn new(
        ticker: String,
        event_type: String,
        interval: u32,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        Self {
            event_type,
            interval,
            ticker_builder: StringBuilder::new(),
            time_builder: TimestampMicrosecondBuilder::new(),
            open_builder: Float64Builder::new(),
            high_builder: Float64Builder::new(),
            low_builder: Float64Builder::new(),
            close_builder: Float64Builder::new(),
            volume_builder: Float64Builder::new(),
            num_events_builder: Int32Builder::new(),
            ticker,
            reply,
        }
    }

    /// Get the event type.
    pub fn event_type(&self) -> &str {
        &self.event_type
    }

    /// Get the interval.
    pub fn interval(&self) -> u32 {
        self.interval
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

    /// Process an IntradayBarResponse message using JSON bulk extraction.
    ///
    /// Uses Bloomberg SDK's native toJson (SDK 3.25.11+) for single-FFI-call extraction,
    /// then parses with simd-json for high-performance zero-copy deserialization.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        // simd-json requires mutable bytes for in-place parsing (zero-copy)
        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_intraday_bar(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        for bar in &resp.bar_data.bar_tick_data {
            self.ticker_builder.append_value(&self.ticker);

            // Parse time string to microseconds since epoch
            if let Some(time_str) = &bar.time {
                if let Some(micros) = parse_datetime_to_micros(time_str.as_ref()) {
                    self.time_builder.append_value(micros);
                } else {
                    self.time_builder.append_null();
                }
            } else {
                self.time_builder.append_null();
            }

            // Get OHLC values (direct access from typed struct)
            append_opt_f64(&mut self.open_builder, bar.open);
            append_opt_f64(&mut self.high_builder, bar.high);
            append_opt_f64(&mut self.low_builder, bar.low);
            append_opt_f64(&mut self.close_builder, bar.close);
            append_opt_f64(&mut self.volume_builder, bar.volume);

            // Get numEvents
            if let Some(n) = bar.num_events {
                self.num_events_builder.append_value(n as i32);
            } else {
                self.num_events_builder.append_null();
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let time_array = self.time_builder.finish();
        let open_array = self.open_builder.finish();
        let high_array = self.high_builder.finish();
        let low_array = self.low_builder.finish();
        let close_array = self.close_builder.finish();
        let volume_array = self.volume_builder.finish();
        let num_events_array = self.num_events_builder.finish();

        let schema = Arc::new(Schema::new(vec![
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
        ]));

        let columns: Vec<Arc<dyn arrow::array::Array>> = vec![
            Arc::new(ticker_array),
            Arc::new(time_array),
            Arc::new(open_array),
            Arc::new(high_array),
            Arc::new(low_array),
            Arc::new(close_array),
            Arc::new(volume_array),
            Arc::new(num_events_array),
        ];

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}

/// Parse an ISO datetime string to microseconds since epoch.
fn parse_datetime_to_micros(dt_str: &str) -> Option<i64> {
    // Try RFC3339 format first
    if let Ok(dt) = DateTime::parse_from_rfc3339(dt_str) {
        return Some(dt.with_timezone(&Utc).timestamp_micros());
    }
    // Try ISO format without timezone (assume UTC)
    if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(dt_str, "%Y-%m-%dT%H:%M:%S") {
        return Some(dt.and_utc().timestamp_micros());
    }
    // Try with milliseconds
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
