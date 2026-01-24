//! Intraday tick (bdtick) state with Arrow builders.
//!
//! Extracts IntradayTickResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use xbbg_core::{BlpError, Message};

/// State for an intraday tick request (bdtick).
pub struct IntradayTickState {
    /// Ticker for this request
    ticker: String,
    /// Column set for building the output
    columns: ColumnSet,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl IntradayTickState {
    /// Create a new intraday tick state.
    pub fn new(ticker: String, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        let mut columns = ColumnSet::new();
        columns.set_type_hint("ticker", ArrowType::String);
        columns.set_type_hint("time", ArrowType::TimestampMicros);
        columns.set_type_hint("type", ArrowType::String);
        columns.set_type_hint("value", ArrowType::Float64);
        columns.set_type_hint("size", ArrowType::Int64);
        columns.set_type_hint("conditionCodes", ArrowType::String);

        Self {
            ticker,
            columns,
            reply,
        }
    }

    /// Process a PARTIAL_RESPONSE message.
    pub fn on_partial(&mut self, msg: &Message) {
        self.process_message(msg);
    }

    /// Process the final RESPONSE message and send the result via reply channel.
    pub fn finish(mut self, msg: &Message) {
        self.process_message(msg);
        let reply = self.reply;
        let result = self.columns.finish_with_order(&[
            "ticker",
            "time",
            "type",
            "value",
            "size",
            "conditionCodes",
        ]);
        let _ = reply.send(result);
    }

    /// Process an IntradayTickResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// IntradayTickResponse {
    ///   tickData {
    ///     tickData[] {
    ///       time: 2024-01-15T09:30:00.123
    ///       type: "TRADE"
    ///       value: 150.0
    ///       size: 100
    ///       conditionCodes: "R"
    ///     }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get tickData (outer)
        let Some(tick_data_outer) = root.get_by_str("tickData") else {
            trace!("No tickData in message");
            return;
        };

        // Get tickData[] (inner array)
        let Some(tick_data) = tick_data_outer.get_by_str("tickData") else {
            trace!("No inner tickData array in message");
            return;
        };

        // Iterate through each tick
        let n = tick_data.len();
        for i in 0..n {
            let Some(tick) = tick_data.get_element(i) else {
                continue;
            };

            self.columns.append_str("ticker", &self.ticker);

            // Get time
            self.append_field(&tick, "time");

            // Get type
            self.append_field(&tick, "type");

            // Get value
            self.append_field(&tick, "value");

            // Get size
            self.append_field(&tick, "size");

            // Get condition codes (may not always be present)
            self.append_field(&tick, "conditionCodes");

            self.columns.end_row();
        }
    }

    /// Helper to append a field value or null.
    fn append_field(&mut self, element: &xbbg_core::Element, field_name: &str) {
        if let Some(field_elem) = element.get_by_str(field_name) {
            if let Some(value) = field_elem.get_value(0) {
                self.columns.append(field_name, value);
            } else {
                self.columns.append_null(field_name);
            }
        } else {
            self.columns.append_null(field_name);
        }
    }
}
