//! Raw JSON state for debugging and custom parsing.
//!
//! Returns the raw JSON response as a single-column table:
//! - json: The complete JSON string from each message

use std::sync::Arc;

use arrow::array::StringBuilder;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use xbbg_core::{BlpError, MessageRef};

/// State for a raw JSON request that preserves the original JSON.
pub struct RawJsonState {
    /// JSON string builder (one row per message)
    json_builder: StringBuilder,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl RawJsonState {
    /// Create a new raw JSON state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            json_builder: StringBuilder::new(),
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

        let result = self.build_batch();
        let _ = self.reply.send(result);
    }

    /// Process a message by appending its JSON to the builder.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        self.json_builder.append_value(&json_str);
    }

    /// Build the final RecordBatch.
    fn build_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let json_array = self.json_builder.finish();

        let schema = Arc::new(Schema::new(vec![Field::new("json", DataType::Utf8, false)]));

        RecordBatch::try_new(schema, vec![Arc::new(json_array)]).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
