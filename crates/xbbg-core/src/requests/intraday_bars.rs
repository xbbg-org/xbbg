//! Intraday bar (BDIB) request descriptor.

/// High-level description of an intraday bar request (BDIB).
#[derive(Debug, Clone)]
pub struct IntradayBarRequest {
    pub tickers: Vec<String>,
    /// Start time in a Bloomberg-compatible string (e.g. `YYYY-MM-DDTHH:MM:SS`).
    pub start: String,
    /// End time.
    pub end: String,
    /// Bar interval in minutes or seconds, depending on options.
    pub interval: u32,
    /// If true, interval is interpreted as seconds instead of minutes.
    pub interval_has_seconds: bool,
    /// Event type (e.g. TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK).
    pub event_type: String,
    /// Misc options (e.g. gapFillInitialBar, adjustment flags).
    pub overrides: Vec<(String, String)>,
    pub label: Option<String>,
}

impl IntradayBarRequest {
    pub fn new<T: Into<String>>(
        tickers: impl IntoIterator<Item = T>,
        start: impl Into<String>,
        end: impl Into<String>,
        interval: u32,
    ) -> Self {
        Self {
            tickers: tickers.into_iter().map(Into::into).collect(),
            start: start.into(),
            end: end.into(),
            interval,
            interval_has_seconds: false,
            event_type: "TRADE".to_string(),
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
            return Err("IntradayBarRequest requires at least one ticker");
        }
        if self.start.is_empty() || self.end.is_empty() {
            return Err("IntradayBarRequest requires non-empty start/end");
        }
        if self.interval == 0 {
            return Err("IntradayBarRequest requires a non-zero interval");
        }
        Ok(())
    }
}



