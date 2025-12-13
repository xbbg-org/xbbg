//! Reference data (BDP/BDS) request descriptor.

/// High-level description of a reference-data style request (BDP/BDS).
///
/// This is intentionally Bloomberg-agnostic – it does not know about
/// services or operations. Execution code is responsible for turning this
/// into concrete `//blp/refdata` requests.
#[derive(Debug, Clone)]
pub struct ReferenceDataRequest {
    /// Tickers / securities to query.
    pub tickers: Vec<String>,
    /// Fields to request.
    pub fields: Vec<String>,
    /// Simple overrides (field -> value).
    pub overrides: Vec<(String, String)>,
    /// Optional label for diagnostics/tracing.
    pub label: Option<String>,
}

impl ReferenceDataRequest {
    pub fn new<T: Into<String>, F: Into<String>>(
        tickers: impl IntoIterator<Item = T>,
        fields: impl IntoIterator<Item = F>,
    ) -> Self {
        Self {
            tickers: tickers.into_iter().map(Into::into).collect(),
            fields: fields.into_iter().map(Into::into).collect(),
            overrides: Vec::new(),
            label: None,
        }
    }

    pub fn with_override(mut self, name: impl Into<String>, value: impl Into<String>) -> Self {
        self.overrides.push((name.into(), value.into()));
        self
    }

    pub fn with_label(mut self, label: impl Into<String>) -> Self {
        self.label = Some(label.into());
        self
    }

    /// Basic validation; execution code should call this before sending.
    pub fn validate(&self) -> Result<(), &'static str> {
        if self.tickers.is_empty() {
            return Err("ReferenceDataRequest requires at least one ticker");
        }
        if self.fields.is_empty() {
            return Err("ReferenceDataRequest requires at least one field");
        }
        Ok(())
    }
}
