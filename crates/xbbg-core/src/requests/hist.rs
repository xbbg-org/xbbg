//! Historical data (BDH) request descriptor.

/// High-level description of a historical data request (BDH).
#[derive(Debug, Clone)]
pub struct HistoricalDataRequest {
    pub tickers: Vec<String>,
    pub fields: Vec<String>,
    /// Inclusive start date in `YYYY-MM-DD` (or Bloomberg-compatible) form.
    pub start_date: String,
    /// Inclusive end date in `YYYY-MM-DD` (or Bloomberg-compatible) form.
    pub end_date: String,
    /// Simple overrides (field -> value), e.g. periodicity, adjustments.
    pub overrides: Vec<(String, String)>,
    pub label: Option<String>,
}

impl HistoricalDataRequest {
    pub fn new<T: Into<String>, F: Into<String>>(
        tickers: impl IntoIterator<Item = T>,
        fields: impl IntoIterator<Item = F>,
        start_date: impl Into<String>,
        end_date: impl Into<String>,
    ) -> Self {
        Self {
            tickers: tickers.into_iter().map(Into::into).collect(),
            fields: fields.into_iter().map(Into::into).collect(),
            start_date: start_date.into(),
            end_date: end_date.into(),
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
            return Err("HistoricalDataRequest requires at least one ticker");
        }
        if self.fields.is_empty() {
            return Err("HistoricalDataRequest requires at least one field");
        }
        if self.start_date.is_empty() || self.end_date.is_empty() {
            return Err("HistoricalDataRequest requires non-empty start and end dates");
        }
        Ok(())
    }
}



