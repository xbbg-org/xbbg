//! Bulk / block data (BDS) helpers.
//!
//! On the wire, BDS is expressed as reference-data style requests with
//! bulk fields that return sequences. At the typed layer we just record
//! which bulk fields are requested; Arrow builders will flatten them into
//! long-format rows keyed by `(ticker, field, row_index, ...)`.

#[derive(Debug, Clone)]
pub struct BulkDataRequest {
    pub tickers: Vec<String>,
    /// Bulk / table fields (e.g. `DVD_Hist_All`).
    pub fields: Vec<String>,
    /// Simple overrides (field -> value).
    pub overrides: Vec<(String, String)>,
    pub label: Option<String>,
}

impl BulkDataRequest {
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

    pub fn validate(&self) -> Result<(), &'static str> {
        if self.tickers.is_empty() {
            return Err("BulkDataRequest requires at least one ticker");
        }
        if self.fields.is_empty() {
            return Err("BulkDataRequest requires at least one bulk field");
        }
        Ok(())
    }
}
