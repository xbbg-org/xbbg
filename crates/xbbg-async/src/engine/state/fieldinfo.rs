//! FieldInfo extractor state for //blp/apiflds FieldInfoRequest responses.
//!
//! Produces a clean table with columns:
//! - field: Field mnemonic (e.g., "PX_LAST")
//! - type: Arrow type string (e.g., "float64", "string", "date32")
//! - description: Field description
//! - category: Category name

use std::sync::Arc;

use arrow::array::StringBuilder;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema::parser;
use crate::field_cache::BlpFieldType;
use xbbg_core::{BlpError, MessageRef};

/// State for a FieldInfoRequest that extracts field metadata.
pub struct FieldInfoState {
    /// Field mnemonic builder
    field_builder: StringBuilder,
    /// Arrow type builder
    type_builder: StringBuilder,
    /// Description builder
    description_builder: StringBuilder,
    /// Category builder
    category_builder: StringBuilder,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl FieldInfoState {
    /// Create a new FieldInfo state.
    pub fn new(reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self {
            field_builder: StringBuilder::new(),
            type_builder: StringBuilder::new(),
            description_builder: StringBuilder::new(),
            category_builder: StringBuilder::new(),
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

    /// Process a message by extracting field info.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        let mut json_bytes = json_str.into_bytes();
        let Ok(response) = parser::parse_field_info(&mut json_bytes) else {
            trace!("FieldInfo JSON parsing failed, message skipped");
            return;
        };

        for item in &response.field_data {
            let info = &item.field_info;

            // Get field mnemonic
            let field = info
                .mnemonic
                .as_ref()
                .or(info.id.as_ref())
                .map(|s| s.as_ref())
                .unwrap_or("");

            if field.is_empty() {
                continue;
            }

            // Get type - prefer datatype over ftype
            let type_str = info
                .datatype
                .as_ref()
                .or(info.ftype.as_ref())
                .map(|s| s.as_ref())
                .unwrap_or("String");

            // Convert to Arrow type
            let blp_type = BlpFieldType::parse(type_str);
            let arrow_type = blp_type.to_arrow_type_str();

            // Get description
            let description = info.description.as_ref().map(|s| s.as_ref()).unwrap_or("");

            // Get category (first one if multiple)
            let category = info
                .category_name
                .as_ref()
                .and_then(|cats| cats.first())
                .map(|s| s.as_ref())
                .unwrap_or("");

            self.field_builder.append_value(field);
            self.type_builder.append_value(arrow_type);
            self.description_builder.append_value(description);
            self.category_builder.append_value(category);
        }
    }

    /// Build the final RecordBatch.
    fn build_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let field_array = self.field_builder.finish();
        let type_array = self.type_builder.finish();
        let description_array = self.description_builder.finish();
        let category_array = self.category_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("field", DataType::Utf8, false),
            Field::new("type", DataType::Utf8, false),
            Field::new("description", DataType::Utf8, true),
            Field::new("category", DataType::Utf8, true),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(field_array),
                Arc::new(type_array),
                Arc::new(description_array),
                Arc::new(category_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
