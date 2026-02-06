//! Intraday bar (bdib) state with Arrow builders.
//!
//! Extracts IntradayBarResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use xbbg_log::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use xbbg_core::{BlpError, Message};

/// State for an intraday bar request (bdib).
pub struct IntradayBarState {
    /// Event type (TRADE, BID, ASK, etc.)
    event_type: String,
    /// Interval in minutes
    interval: u32,
    /// Ticker for this request
    ticker: String,
    /// Column set for building the output
    columns: ColumnSet,
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
        let mut columns = ColumnSet::new();
        columns.set_type_hint("ticker", ArrowType::String);
        columns.set_type_hint("time", ArrowType::TimestampMicros);
        columns.set_type_hint("open", ArrowType::Float64);
        columns.set_type_hint("high", ArrowType::Float64);
        columns.set_type_hint("low", ArrowType::Float64);
        columns.set_type_hint("close", ArrowType::Float64);
        columns.set_type_hint("volume", ArrowType::Float64);
        columns.set_type_hint("numEvents", ArrowType::Int32);

        Self {
            event_type,
            interval,
            ticker,
            columns,
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
            "open",
            "high",
            "low",
            "close",
            "volume",
            "numEvents",
        ]);
        let _ = reply.send(result);
    }

    /// Process an IntradayBarResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// IntradayBarResponse {
    ///   barData {
    ///     barTickData[] {
    ///       time: 2024-01-15T09:30:00
    ///       open: 150.0
    ///       high: 151.0
    ///       low: 149.5
    ///       close: 150.5
    ///       volume: 1000000
    ///       numEvents: 500
    ///     }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get barData
        let Some(bar_data) = root.get_by_str("barData") else {
            trace!("No barData in message");
            return;
        };

        // Get barTickData array
        let Some(bar_tick_data) = bar_data.get_by_str("barTickData") else {
            trace!("No barTickData in message");
            return;
        };

        // Iterate through each bar
        let n = bar_tick_data.len();
        for i in 0..n {
            let Some(bar) = bar_tick_data.get_element(i) else {
                continue;
            };

            self.columns.append_str("ticker", &self.ticker);

            // Get time (as timestamp)
            if let Some(time_elem) = bar.get_by_str("time") {
                if let Some(value) = time_elem.get_value(0) {
                    self.columns.append("time", value);
                } else {
                    self.columns.append_null("time");
                }
            } else {
                self.columns.append_null("time");
            }

            // Get OHLC values
            self.append_field(&bar, "open");
            self.append_field(&bar, "high");
            self.append_field(&bar, "low");
            self.append_field(&bar, "close");
            self.append_field(&bar, "volume");
            self.append_field(&bar, "numEvents");

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
