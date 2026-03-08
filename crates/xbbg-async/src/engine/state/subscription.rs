//! Subscription state with Arrow builders for real-time data.
//!
//! Extracts subscription messages directly from Bloomberg Elements
//! without JSON intermediate serialization. Uses dynamic type dispatch
//! to preserve all Bloomberg types (string, int, float, datetime, etc.).

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;

use arrow::array::{ArrayRef, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::{BlpError, Message};

use super::super::OverflowPolicy;
use super::typed_builder::{ArrowType, TypedBuilder};

pub struct SubscriptionMetrics {
    pub messages_received: Arc<AtomicU64>,
    pub dropped_batches: Arc<AtomicU64>,
    pub batches_sent: Arc<AtomicU64>,
    pub slow_consumer: Arc<AtomicBool>,
}

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
    /// Field value builders — None until type is inferred from first non-null value.
    /// This preserves Bloomberg's native types (Int32, Int64, Float64, String, Date, etc.)
    /// instead of forcing everything through Float64.
    pub field_builders: Vec<Option<TypedBuilder>>,
    /// Stream to send RecordBatches (or errors for subscription failures)
    pub stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
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
    pub metrics: Arc<SubscriptionMetrics>,
    /// Cached schema — invalidated when a field type is first inferred.
    cached_schema: Option<Arc<Schema>>,
}

impl SubscriptionState {
    /// Create a new subscription state with default overflow policy.
    pub fn new(
        topic: String,
        fields: Vec<String>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
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
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        flush_threshold: usize,
        overflow_policy: OverflowPolicy,
    ) -> Self {
        let field_builders = fields.iter().map(|_| None).collect();
        let metrics = Arc::new(SubscriptionMetrics {
            messages_received: Arc::new(AtomicU64::new(0)),
            dropped_batches: Arc::new(AtomicU64::new(0)),
            batches_sent: Arc::new(AtomicU64::new(0)),
            slow_consumer: Arc::new(AtomicBool::new(false)),
        });

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
            metrics,
            cached_schema: None,
        }
    }

    /// Process a SUBSCRIPTION_DATA message using Element API.
    ///
    /// Uses dynamic type dispatch (`get_value`) to preserve Bloomberg's native types.
    /// Field types are inferred on first non-null value and locked in for the
    /// lifetime of the subscription. String, Date, Datetime, Bool, Int, Float
    /// are all preserved — no more Float64-only extraction.
    ///
    /// Timestamps use Bloomberg SDK receive time when available (requires
    /// `setRecordSubscriptionDataReceiveTimes(true)`), falling back to
    /// `SystemTime::now()` if not enabled.
    pub fn on_message(&mut self, msg: &Message) {
        // Use Bloomberg SDK receive time if available, fallback to system time
        let timestamp = msg.time_received_us().unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_micros() as i64)
                .unwrap_or(0)
        });

        self.timestamp_builder.append_value(timestamp);
        self.topic_builder.append_value(self.topic.as_ref());

        // Extract each field value using dynamic type dispatch
        let elem = msg.elements();
        for (i, field_name) in self.field_strings.iter().enumerate() {
            if let Some(field_elem) = elem.get_by_str(field_name) {
                let value = field_elem.get_value(0);

                if let Some(builder) = &mut self.field_builders[i] {
                    // Builder exists — append value (TypedBuilder handles coercion)
                    builder.append_value(value);
                } else if let Some(ref v) = value {
                    if !matches!(v, xbbg_core::Value::Null) {
                        // First non-null value for this field — infer type and create builder
                        let arrow_type = ArrowType::from_value(v);
                        let mut builder = TypedBuilder::new(arrow_type);
                        // Backfill nulls for all previous rows
                        for _ in 0..self.pending_count {
                            builder.append_null();
                        }
                        builder.append_value(value);
                        self.field_builders[i] = Some(builder);
                        self.cached_schema = None; // Schema needs rebuild
                    }
                }
                // If value is None/Null and no builder yet: skip — backfilled on creation
            } else {
                // Field not present in this message — append null if builder exists
                if let Some(builder) = &mut self.field_builders[i] {
                    builder.append_null();
                }
            }
        }

        self.pending_count += 1;
        self.metrics
            .messages_received
            .fetch_add(1, Ordering::Relaxed);

        // Auto-flush if threshold reached
        if self.pending_count >= self.flush_threshold {
            self.flush();
        }
    }

    /// Handle DATALOSS indicator.
    pub fn on_dataloss(&mut self) {
        self.slow_consumer = true;
        self.metrics.slow_consumer.store(true, Ordering::Relaxed);
        xbbg_log::warn!(topic = %self.topic, "DATALOSS detected - slow consumer");
    }

    /// Flush pending rows as a RecordBatch.
    pub fn flush(&mut self) {
        if self.pending_count == 0 {
            return;
        }

        // Build fixed arrays
        let timestamp_array = self.timestamp_builder.finish();
        let topic_array = self.topic_builder.finish();

        // Build field arrays — use TypedBuilder where available, String nulls otherwise
        let field_arrays: Vec<ArrayRef> = self
            .field_builders
            .iter_mut()
            .map(|builder_opt| {
                if let Some(builder) = builder_opt {
                    builder.finish()
                } else {
                    // Field was never non-null in this batch — produce Utf8 column of all nulls
                    let mut sb = StringBuilder::new();
                    for _ in 0..self.pending_count {
                        sb.append_null();
                    }
                    Arc::new(sb.finish()) as ArrayRef
                }
            })
            .collect();

        // Get or build schema (cached after first build)
        let schema = self.get_or_build_schema();

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
                xbbg_log::error!(topic = %self.topic, error = %e, "failed to create RecordBatch");
            }
        }

        self.pending_count = 0;
    }

    /// Get or build the Arrow schema, caching it for reuse.
    ///
    /// The schema is invalidated whenever a new field type is inferred
    /// (when a previously-null field gets its first non-null value).
    fn get_or_build_schema(&mut self) -> Arc<Schema> {
        if let Some(ref schema) = self.cached_schema {
            return schema.clone();
        }

        let mut fields = vec![
            Field::new(
                "timestamp",
                DataType::Timestamp(TimeUnit::Microsecond, None),
                false,
            ),
            Field::new("topic", DataType::Utf8, false),
        ];

        for (i, name) in self.field_strings.iter().enumerate() {
            let dt = self.field_builders[i]
                .as_ref()
                .map(|b| b.data_type())
                .unwrap_or(DataType::Utf8); // Unknown fields default to string
            fields.push(Field::new(name.as_str(), dt, true));
        }

        let schema = Arc::new(Schema::new(fields));
        self.cached_schema = Some(schema.clone());
        schema
    }

    /// Send an error to the consumer.
    ///
    /// Used for subscription failures, session termination, etc.
    /// Uses try_send to avoid blocking the worker thread.
    pub fn fail(&self, error: BlpError) {
        let _ = self.stream.try_send(Err(error));
    }

    /// Send a batch according to the configured overflow policy.
    ///
    /// NOTE: `DropOldest` is still degraded to `DropNewest` (needs ring buffer).
    /// `Block` now works properly using `blocking_send`.
    fn send_batch(&mut self, batch: RecordBatch) {
        match self.overflow_policy {
            OverflowPolicy::Block => {
                // blocking_send is designed for sync contexts (subscription worker thread).
                // Blocks until space is available or the receiver is dropped.
                if self.stream.blocking_send(Ok(batch)).is_err() {
                    xbbg_log::warn!(topic = %self.topic, "stream closed");
                } else {
                    self.metrics.batches_sent.fetch_add(1, Ordering::Relaxed);
                }
            }
            _ => {
                // DropNewest and DropOldest both use try_send.
                // DropOldest is degraded to DropNewest — proper ring buffer not yet implemented.
                match self.stream.try_send(Ok(batch)) {
                    Ok(()) => {
                        self.metrics.batches_sent.fetch_add(1, Ordering::Relaxed);
                    }
                    Err(mpsc::error::TrySendError::Full(_)) => {
                        self.dropped_batches += 1;
                        self.metrics.dropped_batches.fetch_add(1, Ordering::Relaxed);
                        let policy_label = match self.overflow_policy {
                            OverflowPolicy::DropNewest => "DropNewest",
                            OverflowPolicy::DropOldest => "DropOldest (degraded to DropNewest)",
                            OverflowPolicy::Block => "Block",
                        };
                        xbbg_log::warn!(
                            topic = %self.topic,
                            dropped = self.dropped_batches,
                            policy = policy_label,
                            "stream full - dropping batch"
                        );
                    }
                    Err(mpsc::error::TrySendError::Closed(_)) => {
                        xbbg_log::warn!(topic = %self.topic, "stream closed");
                    }
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
