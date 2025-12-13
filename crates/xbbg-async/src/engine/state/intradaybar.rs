//! Intraday bar (bdib) state with Arrow builders.

use std::sync::Arc;

use arrow::array::{Float64Builder, Int32Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;

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

    /// Process an IntradayBarResponse message.
    fn process_message(&mut self, msg: &MessageRef) {
        let elem = msg.elements();

        // Get barData
        let Some(bar_data) = elem.get_element("barData") else {
            return;
        };

        // Get barTickData array
        let Some(bar_tick_data) = bar_data.get_element("barTickData") else {
            return;
        };

        let num_bars = bar_tick_data.num_values();
        for i in 0..num_bars {
            let Some(bar_elem) = bar_tick_data.get_value_as_element(i) else {
                continue;
            };

            self.ticker_builder.append_value(&self.ticker);

            // Get time
            if let Some(time_elem) = bar_elem.get_element("time") {
                if let Ok(Some(dt)) = time_elem.get_value_as_datetime(0) {
                    // Convert to microseconds since epoch
                    let micros = dt.timestamp_micros();
                    self.time_builder.append_value(micros);
                } else {
                    self.time_builder.append_null();
                }
            } else {
                self.time_builder.append_null();
            }

            // Get OHLC values
            self.append_float64_value(&bar_elem, "open");
            self.append_float64_value(&bar_elem, "high");
            self.append_float64_value(&bar_elem, "low");
            self.append_float64_value(&bar_elem, "close");
            self.append_float64_value(&bar_elem, "volume");

            // Get numEvents
            if let Some(num_events_elem) = bar_elem.get_element("numEvents") {
                if let Some(val) = num_events_elem.get_value_as_int64(0) {
                    self.num_events_builder.append_value(val as i32);
                } else {
                    self.num_events_builder.append_null();
                }
            } else {
                self.num_events_builder.append_null();
            }
        }
    }

    fn append_float64_value(&mut self, elem: &xbbg_core::ElementRef, field: &str) {
        let value = elem
            .get_element(field)
            .and_then(|e| e.get_value_as_float64(0));

        let builder = match field {
            "open" => &mut self.open_builder,
            "high" => &mut self.high_builder,
            "low" => &mut self.low_builder,
            "close" => &mut self.close_builder,
            "volume" => &mut self.volume_builder,
            _ => return,
        };

        match value {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
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
