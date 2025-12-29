//! Intraday tick (bdtick) state with Arrow builders.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int64Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, Utc};
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema;
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

    /// Process an IntradayTickResponse message using JSON bulk extraction.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_intraday_tick(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        for tick in &resp.tick_data.tick_data {
            self.ticker_builder.append_value(&self.ticker);

            // Parse time string to microseconds
            if let Some(time_str) = &tick.time {
                if let Some(micros) = parse_datetime_to_micros(time_str.as_ref()) {
                    self.time_builder.append_value(micros);
                } else {
                    self.time_builder.append_null();
                }
            } else {
                self.time_builder.append_null();
            }

            // Type
            if let Some(t) = &tick.tick_type {
                self.type_builder.append_value(t.as_ref());
            } else {
                self.type_builder.append_null();
            }

            // Value
            if let Some(v) = tick.value {
                self.value_builder.append_value(v);
            } else {
                self.value_builder.append_null();
            }

            // Size
            if let Some(s) = tick.size {
                self.size_builder.append_value(s);
            } else {
                self.size_builder.append_null();
            }

            // Condition codes (not in base schema, append null)
            self.condition_codes_builder.append_null();
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
