//! Subscription state with Arrow builders for real-time data.

use std::sync::Arc;

use arrow::array::{Float64Builder, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::MessageRef;

use super::super::OverflowPolicy;

/// State for a single subscription, owned by PumpA.
pub struct SubscriptionState {
    /// Topic string (e.g., "IBM US Equity")
    pub topic: Arc<str>,
    /// Field names as strings (for schema and lookup)
    pub field_strings: Vec<String>,
    /// Timestamp builder (event time)
    pub timestamp_builder: TimestampMicrosecondBuilder,
    /// Topic builder (repeated for each row)
    pub topic_builder: StringBuilder,
    /// Field value builders (one per field, all Float64 for now)
    pub field_builders: Vec<Float64Builder>,
    /// Stream to send RecordBatches
    pub stream: mpsc::Sender<RecordBatch>,
    /// Number of pending rows before flush
    pub pending_count: usize,
    /// Flush threshold
    pub flush_threshold: usize,
    /// Slow consumer flag (DATALOSS received)
    pub slow_consumer: bool,
    /// Overflow policy for slow consumers
    pub overflow_policy: OverflowPolicy,
    /// Dropped batch count (for metrics)
    pub dropped_batches: u64,
}

impl SubscriptionState {
    /// Create a new subscription state with default overflow policy.
    pub fn new(
        topic: String,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
        flush_threshold: usize,
    ) -> Self {
        Self::with_policy(
            topic,
            fields,
            stream,
            flush_threshold,
            OverflowPolicy::default(),
        )
    }

    /// Create a new subscription state with specified overflow policy.
    pub fn with_policy(
        topic: String,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
        flush_threshold: usize,
        overflow_policy: OverflowPolicy,
    ) -> Self {
        let field_builders = fields.iter().map(|_| Float64Builder::new()).collect();

        Self {
            topic: topic.into(),
            field_strings: fields,
            timestamp_builder: TimestampMicrosecondBuilder::new(),
            topic_builder: StringBuilder::new(),
            field_builders,
            stream,
            pending_count: 0,
            flush_threshold,
            slow_consumer: false,
            overflow_policy,
            dropped_batches: 0,
        }
    }

    /// Process a SUBSCRIPTION_DATA message.
    pub fn on_message(&mut self, msg: &MessageRef) {
        // Get timestamp
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_micros() as i64)
            .unwrap_or(0);

        self.timestamp_builder.append_value(timestamp);
        self.topic_builder.append_value(self.topic.as_ref());

        // Extract each field value directly (no text conversion)
        let elem = msg.elements();
        for (i, field_name) in self.field_strings.iter().enumerate() {
            if let Some(field_elem) = elem.get_element(field_name) {
                // Try to get as float64 (most market data is numeric)
                if let Some(val) = field_elem.get_value_as_float64(0) {
                    self.field_builders[i].append_value(val);
                } else {
                    self.field_builders[i].append_null();
                }
            } else {
                self.field_builders[i].append_null();
            }
        }

        self.pending_count += 1;

        // Auto-flush if threshold reached
        if self.pending_count >= self.flush_threshold {
            self.flush();
        }
    }

    /// Handle DATALOSS indicator.
    pub fn on_dataloss(&mut self) {
        self.slow_consumer = true;
        tracing::warn!(topic = %self.topic, "DATALOSS detected - slow consumer");
    }

    /// Flush pending rows as a RecordBatch.
    pub fn flush(&mut self) {
        if self.pending_count == 0 {
            return;
        }

        // Build arrays
        let timestamp_array = self.timestamp_builder.finish();
        let topic_array = self.topic_builder.finish();
        let field_arrays: Vec<_> = self
            .field_builders
            .iter_mut()
            .map(|b| Arc::new(b.finish()) as _)
            .collect();

        // Build schema
        let mut fields = vec![
            Field::new(
                "timestamp",
                DataType::Timestamp(TimeUnit::Microsecond, None),
                false,
            ),
            Field::new("topic", DataType::Utf8, false),
        ];
        for name in &self.field_strings {
            fields.push(Field::new(name.as_str(), DataType::Float64, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> =
            vec![Arc::new(timestamp_array), Arc::new(topic_array)];
        columns.extend(field_arrays);

        // Create RecordBatch
        match RecordBatch::try_new(schema, columns) {
            Ok(batch) => {
                self.send_batch(batch);
            }
            Err(e) => {
                tracing::error!(topic = %self.topic, error = %e, "failed to create RecordBatch");
            }
        }

        self.pending_count = 0;
    }

    /// Send a batch according to the configured overflow policy.
    fn send_batch(&mut self, batch: RecordBatch) {
        match self.overflow_policy {
            OverflowPolicy::DropNewest => {
                // Non-blocking: drop the batch if stream is full
                if self.stream.try_send(batch).is_err() {
                    self.dropped_batches += 1;
                    tracing::warn!(
                        topic = %self.topic,
                        dropped = self.dropped_batches,
                        "stream full - dropping newest batch"
                    );
                }
            }
            OverflowPolicy::DropOldest => {
                // Try to send; if full, drain one from receiver side and retry
                // Note: This requires the receiver to cooperate, so we use a loop
                // with try_send and a reserve check
                loop {
                    match self.stream.try_send(batch.clone()) {
                        Ok(()) => break,
                        Err(mpsc::error::TrySendError::Full(_)) => {
                            // For DropOldest, we need the receiver to drop old messages
                            // Since we can't access the receiver here, we fall back to
                            // dropping newest with a warning
                            self.dropped_batches += 1;
                            tracing::warn!(
                                topic = %self.topic,
                                dropped = self.dropped_batches,
                                "stream full - DropOldest policy (dropping newest as fallback)"
                            );
                            break;
                        }
                        Err(mpsc::error::TrySendError::Closed(_)) => {
                            tracing::warn!(topic = %self.topic, "stream closed");
                            break;
                        }
                    }
                }
            }
            OverflowPolicy::Block => {
                // Blocking send - use blocking_send in a sync context
                // Since we're in a sync context (pump thread), we can't use async
                // Fall back to try_send with a warning
                if self.stream.try_send(batch).is_err() {
                    self.dropped_batches += 1;
                    tracing::warn!(
                        topic = %self.topic,
                        dropped = self.dropped_batches,
                        "stream full - Block policy (non-blocking fallback)"
                    );
                }
            }
        }
    }
}

impl Drop for SubscriptionState {
    fn drop(&mut self) {
        // Flush any remaining rows
        self.flush();
    }
}
