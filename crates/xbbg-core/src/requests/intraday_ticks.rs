//! Intraday tick (BDTICK) request descriptor.

/// High-level description of an intraday tick request (BDTICK).
#[derive(Debug, Clone)]
pub struct IntradayTickRequest {
    pub tickers: Vec<String>,
    /// Start time.
    pub start: String,
    /// End time.
    pub end: String,
    /// Event types to request (e.g. TRADE, BID, ASK).
    pub event_types: Vec<String>,
    /// Misc options (include condition codes, etc.).
    pub overrides: Vec<(String, String)>,
    pub label: Option<String>,
}

impl IntradayTickRequest {
    pub fn new<T: Into<String>>(
        tickers: impl IntoIterator<Item = T>,
        start: impl Into<String>,
        end: impl Into<String>,
        event_types: impl IntoIterator<Item = T>,
    ) -> Self {
        Self {
            tickers: tickers.into_iter().map(Into::into).collect(),
            start: start.into(),
            end: end.into(),
            event_types: event_types.into_iter().map(Into::into).collect(),
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
            return Err("IntradayTickRequest requires at least one ticker");
        }
        if self.start.is_empty() || self.end.is_empty() {
            return Err("IntradayTickRequest requires non-empty start/end");
        }
        if self.event_types.is_empty() {
            return Err("IntradayTickRequest requires at least one event type");
        }
        Ok(())
    }
}



