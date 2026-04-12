//! Reference data (bdp) state with Arrow builders.
//!
//! Extracts ReferenceDataResponse messages directly from Bloomberg Elements
//! without JSON intermediate serialization.

use std::collections::HashMap;

use arrow::record_batch::RecordBatch;
use tokio::sync::oneshot;
use xbbg_log::trace;

use super::typed_builder::{ArrowType, ColumnSet};
use super::value_utils::{append_long_value_row, append_wide_row};
use xbbg_core::{BlpError, Element, Message, Value};

/// Output format for reference data.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OutputFormat {
    /// Long format: ticker, field, value (one row per ticker-field pair)
    #[default]
    Long,
    /// Wide format: ticker, field1, field2, ... (one row per ticker)
    Wide,
}

/// Long format output mode variants.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum LongMode {
    /// All values as strings (default, backwards-compatible)
    #[default]
    String,
    /// String values with dtype column containing Arrow type name
    WithMetadata,
    /// Multi-value columns: value_f64, value_i64, value_str, value_bool, value_date, value_ts
    Typed,
}

/// State for a reference data request (bdp).
pub struct RefDataState {
    /// Field names as strings
    field_names: Vec<String>,
    /// Field type hints (field name -> arrow type)
    field_types: HashMap<String, ArrowType>,
    /// Output format
    format: OutputFormat,
    /// Long format mode (only used when format == Long)
    long_mode: LongMode,
    /// Include security error rows in output.
    include_security_errors: bool,
    /// Security identifiers that returned securityError.
    failed_securities: Vec<String>,
    /// Column set for building the output
    columns: ColumnSet,
    /// Reply channel
    pub reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
}

impl RefDataState {
    /// Create a new refdata state with Long format (default).
    pub fn new(fields: Vec<String>, reply: oneshot::Sender<Result<RecordBatch, BlpError>>) -> Self {
        Self::with_format(
            fields,
            OutputFormat::Long,
            LongMode::String,
            None,
            false,
            reply,
        )
    }

    /// Create a new refdata state with specified format.
    pub fn with_format(
        fields: Vec<String>,
        format: OutputFormat,
        long_mode: LongMode,
        field_types: Option<HashMap<String, String>>,
        include_security_errors: bool,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Self {
        // Convert string types to ArrowType
        let arrow_types: HashMap<String, ArrowType> = field_types
            .unwrap_or_default()
            .into_iter()
            .map(|(k, v)| (k, ArrowType::parse(&v)))
            .collect();

        // Create column set with type hints
        let mut columns = ColumnSet::new();
        for (name, arrow_type) in &arrow_types {
            columns.set_type_hint(name, *arrow_type);
        }

        // Set type hint for the "value" column based on common field type.
        // If all fields are numeric, the value column will be Float64 instead
        // of Utf8, preserving native types from the Bloomberg response.
        if long_mode == LongMode::String {
            use super::value_utils::common_value_type;
            let common_type = common_value_type(&arrow_types);
            columns.set_type_hint("value", common_type);
        }

        Self {
            field_names: fields,
            field_types: arrow_types,
            format,
            long_mode,
            include_security_errors,
            failed_securities: Vec::new(),
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

        if !self.failed_securities.is_empty() {
            xbbg_log::warn!(
                count = self.failed_securities.len(),
                tickers = ?self.failed_securities,
                "ReferenceData completed with security failures"
            );
        }

        if self.columns.row_count() == 0 && !self.failed_securities.is_empty() {
            let detail = format!(
                "All securities failed: {}",
                self.failed_securities.join(", ")
            );
            let _ = self.reply.send(Err(BlpError::RequestFailure {
                service: "//blp/refdata".to_string(),
                operation: Some("ReferenceDataRequest".to_string()),
                cid: None,
                label: Some(detail),
                request_id: None,
                source: None,
            }));
            return;
        }

        let reply = self.reply;
        let result = match self.format {
            OutputFormat::Long => match self.long_mode {
                LongMode::String => self
                    .columns
                    .finish_with_order(&["ticker", "field", "value"]),
                LongMode::WithMetadata => self
                    .columns
                    .finish_with_order(&["ticker", "field", "value", "dtype"]),
                LongMode::Typed => self.columns.finish_with_order(&[
                    "ticker",
                    "field",
                    "value_f64",
                    "value_i64",
                    "value_str",
                    "value_bool",
                    "value_date",
                    "value_ts",
                ]),
            },
            OutputFormat::Wide => {
                let mut order = vec!["ticker"];
                order.extend(self.field_names.iter().map(|s| s.as_str()));
                self.columns.finish_with_order(&order)
            }
        };
        if let Ok(ref batch) = result {
            xbbg_log::debug!(
                rows = batch.num_rows(),
                cols = batch.num_columns(),
                "refdata finish"
            );
        }
        let _ = reply.send(result);
    }

    /// Process a ReferenceDataResponse message using Element API.
    ///
    /// Bloomberg structure:
    /// ```text
    /// ReferenceDataResponse {
    ///   securityData[] {
    ///     security: "AAPL US Equity"
    ///     fieldData {
    ///       PX_LAST: 150.0
    ///       NAME: "Apple Inc"
    ///       ...
    ///     }
    ///     fieldExceptions[]? { ... }
    ///     securityError? { ... }
    ///   }
    /// }
    /// ```
    fn process_message(&mut self, msg: &Message) {
        let root = msg.elements();

        // Get securityData array
        let Some(security_data) = root.get_by_str("securityData") else {
            trace!("No securityData in message");
            return;
        };

        // Iterate through each security
        let n = security_data.len();
        for i in 0..n {
            let Some(sec) = security_data.get_element(i) else {
                continue;
            };

            // Get ticker
            let ticker = sec
                .get_by_str("security")
                .and_then(|e| e.get_str(0))
                .unwrap_or("");

            // Check for security error
            if let Some(security_error) = sec.get_by_str("securityError") {
                let category = security_error
                    .get_by_str("category")
                    .and_then(|e| e.get_str(0))
                    .unwrap_or("");
                let code = security_error
                    .get_by_str("code")
                    .and_then(|e| e.get_i32(0))
                    .unwrap_or_default();
                let message = security_error
                    .get_by_str("message")
                    .and_then(|e| e.get_str(0))
                    .unwrap_or("");

                xbbg_log::warn!(
                    ticker = ticker,
                    category = category,
                    code = code,
                    message = message,
                    "ReferenceData securityError; skipping security"
                );

                self.failed_securities.push(ticker.to_string());

                if self.include_security_errors {
                    let subcategory = security_error
                        .get_by_str("subcategory")
                        .and_then(|e| e.get_str(0))
                        .unwrap_or("");
                    self.append_security_error_row(ticker, code, category, subcategory, message);
                }
                continue;
            }

            if let Some(field_exceptions) = sec.get_by_str("fieldExceptions") {
                let n = field_exceptions.len();
                if n > 0 {
                    // Collect field names and error messages for diagnostics
                    let mut details: Vec<String> = Vec::with_capacity(n);
                    for j in 0..n {
                        if let Some(exc) = field_exceptions.get_element(j) {
                            let field_id = exc
                                .get_by_str("fieldId")
                                .and_then(|e| e.get_str(0))
                                .unwrap_or("?");
                            let err_info = exc.get_by_str("errorInfo");
                            let message = err_info
                                .as_ref()
                                .and_then(|e| e.get_by_str("message"))
                                .and_then(|e| e.get_str(0))
                                .unwrap_or("");
                            details.push(format!("{field_id}: {message}"));
                        }
                    }
                    xbbg_log::debug!(
                        ticker = ticker,
                        count = n,
                        fields = details.join(", ").as_str(),
                        "ReferenceData fieldExceptions"
                    );
                }
            }

            // Get fieldData
            let Some(field_data) = sec.get_by_str("fieldData") else {
                trace!(ticker = ticker, "No fieldData for security");
                continue;
            };

            match self.format {
                OutputFormat::Long => {
                    self.process_long_format(ticker, &field_data);
                }
                OutputFormat::Wide => {
                    self.process_wide_format(ticker, &field_data);
                }
            }
        }
    }

    fn append_security_error_row(
        &mut self,
        ticker: &str,
        code: i32,
        category: &str,
        subcategory: &str,
        message: &str,
    ) {
        let detail =
            format!("code={code} category={category} subcategory={subcategory} message={message}");
        let value = Some(Value::String(detail.as_str()));
        append_long_value_row(
            &mut self.columns,
            self.long_mode,
            "__SECURITY_ERROR__",
            value,
            Some("string"),
            |columns| columns.append_str("ticker", ticker),
        );
    }

    /// Process security in long format (one row per field).
    fn process_long_format(&mut self, ticker: &str, field_data: &Element) {
        let long_mode = self.long_mode;
        let field_names = &self.field_names;
        let field_types = &self.field_types;
        let columns = &mut self.columns;

        for field_name in field_names {
            // Get the field element
            let value = field_data
                .get_by_str(field_name)
                .and_then(|e| e.get_value(0));
            let dtype = value
                .as_ref()
                .map(|v| dtype_from_hints(field_types, field_name, v));

            append_long_value_row(columns, long_mode, field_name, value, dtype, |columns| {
                columns.append_str("ticker", ticker)
            });
        }
    }

    /// Process security in wide format (one row per ticker).
    fn process_wide_format(&mut self, ticker: &str, field_data: &Element) {
        let field_names = &self.field_names;
        append_wide_row(
            &mut self.columns,
            field_names,
            |columns| columns.append_str("ticker", ticker),
            |field_name| {
                field_data
                    .get_by_str(field_name)
                    .and_then(|e| e.get_value(0))
            },
        );
    }
}

fn dtype_from_hints(
    field_types: &HashMap<String, ArrowType>,
    field_name: &str,
    value: &Value<'_>,
) -> &'static str {
    // Use type hint if available
    if let Some(hint) = field_types.get(field_name) {
        return hint.type_name();
    }
    // Otherwise infer from value
    ArrowType::from_value(value).type_name()
}
