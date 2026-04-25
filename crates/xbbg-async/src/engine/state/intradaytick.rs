//! Intraday tick (bdtick) state with Arrow builders.
//!
//! Extracts IntradayTickResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use arrow::record_batch::RecordBatch;
use std::collections::HashSet;
use tokio::sync::oneshot;
use xbbg_log::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use super::value_utils::{arrow_type_for_element, should_emit_scalar_field};
use xbbg_core::{BlpError, Element, Message};

const CORE_OUTPUT_COLUMNS: [&str; 5] = ["ticker", "time", "type", "value", "size"];
const TICKER_COLUMN: &str = "ticker";

/// State for an intraday tick request (bdtick).
pub struct IntradayTickState {
    /// Ticker for this request.
    ticker: String,
    /// Output columns in stable order. Starts with core columns, then first-seen tick fields.
    column_order: Vec<String>,
    /// Membership set for O(1) duplicate checks while preserving `column_order`.
    column_name_set: HashSet<String>,
    /// Column set for building the output.
    columns: ColumnSet,
    /// Reply channel.
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

        Self {
            ticker,
            column_order: CORE_OUTPUT_COLUMNS
                .iter()
                .map(|name| (*name).to_string())
                .collect(),
            column_name_set: CORE_OUTPUT_COLUMNS
                .iter()
                .map(|name| (*name).to_string())
                .collect(),
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
        let order: Vec<_> = self.column_order.iter().map(String::as_str).collect();
        let result = self.columns.finish_with_order(&order);
        if let Ok(ref batch) = result {
            xbbg_log::debug!(rows = batch.num_rows(), "intradaytick finish");
        }
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
    ///       conditionCodes: "..."  # optional request-dependent fields
    ///     }
    ///     eidData[] { ... }          # response metadata, not per-tick data
    ///   }
    /// }
    /// ```
    ///
    /// Extra scalar children under `tickData.tickData[]` are appended as typed
    /// columns. Metadata outside the tick array is intentionally ignored.
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        let Some(tick_data_outer) = root.get_by_str("tickData") else {
            trace!("No tickData in message");
            return;
        };

        let Some(tick_data) = tick_data_outer.get_by_str("tickData") else {
            trace!("No inner tickData array in message");
            return;
        };

        let n = tick_data.len();
        for i in 0..n {
            let Some(tick) = tick_data.get_element(i) else {
                continue;
            };

            self.discover_tick_fields(&tick);

            let columns = &mut self.columns;
            columns.append_str(TICKER_COLUMN, &self.ticker);
            for field_name in self
                .column_order
                .iter()
                .filter(|name| name.as_str() != TICKER_COLUMN)
            {
                Self::append_field(columns, &tick, field_name);
            }
            columns.end_row();
        }
    }

    fn discover_tick_fields(&mut self, tick: &Element<'_>) {
        for child in tick.children() {
            if !should_emit_scalar_field(&child) {
                continue;
            }

            let name = child.name().as_str().to_string();
            if name == TICKER_COLUMN || !self.column_name_set.insert(name.clone()) {
                continue;
            }

            self.columns
                .set_type_hint(&name, arrow_type_for_element(&child));
            self.column_order.push(name);
        }
    }

    /// Helper to append a field value or null.
    fn append_field(columns: &mut ColumnSet, element: &Element<'_>, field_name: &str) {
        if let Some(field_elem) = element.get_by_str(field_name) {
            if let Some(value) = field_elem.get_value(0) {
                columns.append(field_name, value);
            } else {
                columns.append_null(field_name);
            }
        } else {
            columns.append_null(field_name);
        }
    }
}
