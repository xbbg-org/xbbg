//! Reference data (bdp) state with Arrow builders.

use std::sync::Arc;

use arrow::array::StringBuilder;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use tracing::trace;

use super::json_schema;
use xbbg_core::{BlpError, MessageRef};

/// Output format for reference data.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OutputFormat {
    /// Long format: ticker, field, value (one row per ticker-field pair)
    #[default]
    Long,
    /// Wide format: ticker, field1, field2, ... (one row per ticker)
    Wide,
}

/// State for a reference data request (bdp).
pub struct RefDataState {
    /// Field names as strings
    field_strings: Vec<String>,
    /// Output format
    format: OutputFormat,
    /// Ticker builder (used in both formats)
    ticker_builder: StringBuilder,
    /// Field name builder (Long format only)
    field_builder: StringBuilder,
    /// Value builder (Long format only)
    value_builder: StringBuilder,
    /// Per-field builders (Wide format only)
    wide_field_builders: Vec<StringBuilder>,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl RefDataState {
    /// Create a new refdata state with Long format (default).
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self::with_format(fields, OutputFormat::Long, reply)
    }

    /// Create a new refdata state with specified format.
    pub fn with_format(
        fields: Vec<String>,
        format: OutputFormat,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        let wide_field_builders = if format == OutputFormat::Wide {
            fields.iter().map(|_| StringBuilder::new()).collect()
        } else {
            Vec::new()
        };

        Self {
            field_strings: fields,
            format,
            ticker_builder: StringBuilder::new(),
            field_builder: StringBuilder::new(),
            value_builder: StringBuilder::new(),
            wide_field_builders,
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

        // Build batch first (borrows self), then take reply
        let result = self.build_batch_inner();
        let _ = self.reply.send(result);
    }

    /// Process a ReferenceDataResponse message using JSON bulk extraction.
    ///
    /// Uses Bloomberg SDK's native toJson (SDK 3.25.11+) for single-FFI-call extraction,
    /// then parses with simd-json for high-performance zero-copy deserialization.
    fn process_message(&mut self, msg: &MessageRef) {
        let Some(json_str) = msg.to_json() else {
            trace!("toJson not available, message skipped");
            return;
        };

        // simd-json requires mutable bytes for in-place parsing (zero-copy)
        let mut json_bytes = json_str.into_bytes();

        let Ok(resp) = json_schema::parser::parse_refdata(&mut json_bytes) else {
            trace!("JSON parsing failed, message skipped");
            return;
        };

        for sec in &resp.security_data {
            let ticker = sec.security.as_ref();

            match self.format {
                OutputFormat::Long => {
                    for field_str in self.field_strings.clone() {
                        self.ticker_builder.append_value(ticker);
                        self.field_builder.append_value(&field_str);

                        if let Some(value) = sec.field_data.get(field_str.as_str()) {
                            if let Some(s) = value.as_string() {
                                self.value_builder.append_value(&s);
                            } else {
                                self.value_builder.append_null();
                            }
                        } else {
                            self.value_builder.append_null();
                        }
                    }
                }
                OutputFormat::Wide => {
                    self.ticker_builder.append_value(ticker);

                    for (i, field_str) in self.field_strings.iter().enumerate() {
                        if let Some(value) = sec.field_data.get(field_str.as_str()) {
                            if let Some(s) = value.as_string() {
                                self.wide_field_builders[i].append_value(&s);
                            } else {
                                self.wide_field_builders[i].append_null();
                            }
                        } else {
                            self.wide_field_builders[i].append_null();
                        }
                    }
                }
            }
        }
    }

    /// Build the final RecordBatch.
    fn build_batch_inner(&mut self) -> Result<RecordBatch, BlpError> {
        match self.format {
            OutputFormat::Long => self.build_long_batch(),
            OutputFormat::Wide => self.build_wide_batch(),
        }
    }

    /// Build Long format RecordBatch.
    fn build_long_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();
        let field_array = self.field_builder.finish();
        let value_array = self.value_builder.finish();

        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value", DataType::Utf8, true),
        ]));

        RecordBatch::try_new(
            schema,
            vec![
                Arc::new(ticker_array),
                Arc::new(field_array),
                Arc::new(value_array),
            ],
        )
        .map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }

    /// Build Wide format RecordBatch.
    fn build_wide_batch(&mut self) -> Result<RecordBatch, BlpError> {
        let ticker_array = self.ticker_builder.finish();

        // Build schema: ticker + one column per field
        let mut fields = vec![Field::new("ticker", DataType::Utf8, false)];
        for name in &self.field_strings {
            fields.push(Field::new(name.as_str(), DataType::Utf8, true));
        }
        let schema = Arc::new(Schema::new(fields));

        // Build columns
        let mut columns: Vec<Arc<dyn arrow::array::Array>> = vec![Arc::new(ticker_array)];
        for builder in &mut self.wide_field_builders {
            columns.push(Arc::new(builder.finish()));
        }

        RecordBatch::try_new(schema, columns).map_err(|e| BlpError::Internal {
            detail: format!("build RecordBatch: {e}"),
        })
    }
}
