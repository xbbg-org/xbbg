//! Subscription state with Arrow builders for real-time data.
//!
//! Extracts subscription messages directly from Bloomberg Elements
//! without JSON intermediate serialization. Uses dynamic type dispatch
//! to preserve all Bloomberg types (string, int, float, datetime, etc.).

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;

use arrow::array::{ArrayRef, StringBuilder, TimestampMicrosecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::{BlpError, DataType as BlpDataType, Message, Value};

use super::super::OverflowPolicy;
use super::typed_builder::{ArrowType, TypedBuilder};

pub struct SubscriptionMetrics {
    pub messages_received: Arc<AtomicU64>,
    pub dropped_batches: Arc<AtomicU64>,
    pub batches_sent: Arc<AtomicU64>,
    pub slow_consumer: Arc<AtomicBool>,
    pub data_loss_events: Arc<AtomicU64>,
    pub last_message_us: Arc<AtomicU64>,
    pub last_data_loss_us: Arc<AtomicU64>,
}

/// State for a single subscription, owned by PumpA.
pub struct SubscriptionState {
    /// Topic string (e.g., "IBM US Equity")
    pub topic: Arc<str>,
    /// Field names as strings (for schema and lookup)
    pub field_strings: Vec<String>,
    /// Fast lookup from field name to column index.
    field_indices: HashMap<String, usize>,
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
    /// Whether at least one data message has been observed.
    has_received_data: bool,
    /// Suppress stream-closed warnings during expected shutdown paths.
    suppress_closed_warning: bool,
    /// Whether to append all top-level scalar fields Bloomberg exposes.
    capture_all_fields: bool,
}

impl SubscriptionState {
    const EVENT_METADATA_FIELDS: [&'static str; 2] =
        ["MKTDATA_EVENT_TYPE", "MKTDATA_EVENT_SUBTYPE"];

    /// Create a new subscription state with default overflow policy.
    pub fn new(
        topic: String,
        fields: Vec<String>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        flush_threshold: usize,
        capture_all_fields: bool,
    ) -> Self {
        Self::with_policy(
            topic,
            fields,
            stream,
            flush_threshold,
            OverflowPolicy::default(),
            capture_all_fields,
        )
    }

    /// Create a new subscription state with specified overflow policy.
    pub fn with_policy(
        topic: String,
        fields: Vec<String>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        flush_threshold: usize,
        overflow_policy: OverflowPolicy,
        capture_all_fields: bool,
    ) -> Self {
        let mut field_strings =
            Vec::with_capacity(fields.len() + Self::EVENT_METADATA_FIELDS.len());
        let mut field_indices =
            HashMap::with_capacity(fields.len() + Self::EVENT_METADATA_FIELDS.len());
        for field in fields {
            if !field_indices.contains_key(&field) {
                let idx = field_strings.len();
                field_indices.insert(field.clone(), idx);
                field_strings.push(field);
            }
        }
        for field in Self::EVENT_METADATA_FIELDS {
            if !field_indices.contains_key(field) {
                let idx = field_strings.len();
                let field_name = field.to_string();
                field_indices.insert(field_name.clone(), idx);
                field_strings.push(field_name);
            }
        }
        let field_builders = field_strings.iter().map(|_| None).collect();
        let metrics = Arc::new(SubscriptionMetrics {
            messages_received: Arc::new(AtomicU64::new(0)),
            dropped_batches: Arc::new(AtomicU64::new(0)),
            batches_sent: Arc::new(AtomicU64::new(0)),
            slow_consumer: Arc::new(AtomicBool::new(false)),
            data_loss_events: Arc::new(AtomicU64::new(0)),
            last_message_us: Arc::new(AtomicU64::new(0)),
            last_data_loss_us: Arc::new(AtomicU64::new(0)),
        });

        Self {
            topic: topic.into(),
            field_strings,
            field_indices,
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
            has_received_data: false,
            suppress_closed_warning: false,
            capture_all_fields,
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
    pub fn on_message(&mut self, msg: &Message) -> bool {
        // Use Bloomberg SDK receive time if available, fallback to system time
        let timestamp = msg.time_received_us().unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_micros() as i64)
                .unwrap_or(0)
        });

        self.timestamp_builder.append_value(timestamp);
        self.topic_builder.append_value(self.topic.as_ref());

        let elem = msg.elements();
        if self.capture_all_fields {
            self.append_all_fields(&elem);
        } else {
            self.append_requested_fields(&elem);
        }

        self.pending_count += 1;
        self.metrics
            .messages_received
            .fetch_add(1, Ordering::Relaxed);
        self.metrics
            .last_message_us
            .store(timestamp as u64, Ordering::Relaxed);

        let first_message = !self.has_received_data;
        self.has_received_data = true;

        // Auto-flush if threshold reached
        if self.pending_count >= self.flush_threshold {
            self.flush();
        }

        first_message
    }

    fn append_requested_fields(&mut self, elem: &xbbg_core::Element<'_>) {
        for idx in 0..self.field_strings.len() {
            let field_name = &self.field_strings[idx];
            if let Some(field_elem) = elem.get_by_str(field_name) {
                self.append_value_at(idx, field_elem.get_value(0));
            } else {
                self.append_missing_at(idx);
            }
        }
    }

    fn append_all_fields(&mut self, elem: &xbbg_core::Element<'_>) {
        let mut seen = vec![false; self.field_strings.len()];

        for child_idx in 0..elem.num_children() {
            let Some(child) = elem.get_at(child_idx) else {
                continue;
            };
            if !Self::should_capture_field(&child) {
                continue;
            }

            let field_name = child.name().as_str().to_string();
            let idx = self.ensure_field(&field_name);
            if idx >= seen.len() {
                seen.resize(self.field_strings.len(), false);
            }
            seen[idx] = true;
            self.append_value_at(idx, child.get_value(0));
        }

        for (idx, was_seen) in seen.iter().enumerate() {
            if !*was_seen {
                self.append_missing_at(idx);
            }
        }
    }

    fn should_capture_field(field: &xbbg_core::Element<'_>) -> bool {
        !matches!(
            field.datatype(),
            BlpDataType::Sequence
                | BlpDataType::Choice
                | BlpDataType::ByteArray
                | BlpDataType::CorrelationId
        )
    }

    fn ensure_field(&mut self, field_name: &str) -> usize {
        if let Some(&idx) = self.field_indices.get(field_name) {
            return idx;
        }

        let idx = self.field_strings.len();
        self.field_strings.push(field_name.to_string());
        self.field_builders.push(None);
        self.field_indices.insert(field_name.to_string(), idx);
        self.cached_schema = None;
        idx
    }

    fn append_value_at(&mut self, idx: usize, value: Option<Value<'_>>) {
        if let Some(builder) = &mut self.field_builders[idx] {
            builder.append_value(value);
            return;
        }

        if let Some(ref v) = value {
            if !matches!(v, Value::Null) {
                let arrow_type = ArrowType::from_value(v);
                let mut builder = TypedBuilder::new(arrow_type);
                for _ in 0..self.pending_count {
                    builder.append_null();
                }
                builder.append_value(value);
                self.field_builders[idx] = Some(builder);
                self.cached_schema = None;
            }
        }
    }

    fn append_missing_at(&mut self, idx: usize) {
        if let Some(builder) = &mut self.field_builders[idx] {
            builder.append_null();
        }
    }

    /// Handle DATALOSS indicator.
    pub fn on_dataloss(&mut self, timestamp_us: Option<i64>) {
        self.slow_consumer = true;
        self.metrics.slow_consumer.store(true, Ordering::Relaxed);
        self.metrics
            .data_loss_events
            .fetch_add(1, Ordering::Relaxed);
        self.metrics.last_data_loss_us.store(
            timestamp_us.unwrap_or_default().max(0) as u64,
            Ordering::Relaxed,
        );
        xbbg_log::warn!(topic = %self.topic, "DATALOSS detected - slow consumer");
    }

    pub fn clear_slow_consumer(&mut self) {
        self.slow_consumer = false;
        self.metrics.slow_consumer.store(false, Ordering::Relaxed);
    }

    pub fn mark_closing(&mut self) {
        self.suppress_closed_warning = true;
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
    /// `Block` uses `blocking_send` to apply backpressure.
    fn send_batch(&mut self, batch: RecordBatch) {
        match self.overflow_policy {
            OverflowPolicy::Block => {
                // blocking_send is designed for sync contexts (subscription worker thread).
                // Blocks until space is available or the receiver is dropped.
                if self.stream.blocking_send(Ok(batch)).is_err() {
                    if !self.suppress_closed_warning {
                        xbbg_log::warn!(topic = %self.topic, "stream closed");
                    }
                } else {
                    self.metrics.batches_sent.fetch_add(1, Ordering::Relaxed);
                }
            }
            OverflowPolicy::DropNewest => {
                // try_send: drop newest batch when buffer is full
                match self.stream.try_send(Ok(batch)) {
                    Ok(()) => {
                        self.metrics.batches_sent.fetch_add(1, Ordering::Relaxed);
                    }
                    Err(mpsc::error::TrySendError::Full(_)) => {
                        self.dropped_batches += 1;
                        self.metrics.dropped_batches.fetch_add(1, Ordering::Relaxed);
                        let policy_label = "DropNewest";
                        xbbg_log::warn!(
                            topic = %self.topic,
                            dropped = self.dropped_batches,
                            policy = policy_label,
                            "stream full - dropping batch"
                        );
                    }
                    Err(mpsc::error::TrySendError::Closed(_)) => {
                        if !self.suppress_closed_warning {
                            xbbg_log::warn!(topic = %self.topic, "stream closed");
                        }
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
