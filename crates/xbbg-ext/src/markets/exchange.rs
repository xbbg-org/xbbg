use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::sessions::SessionWindows;

/// Source of exchange metadata.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExchangeInfoSource {
    Override,
    Cache,
    Bloomberg,
    Inferred,
    Fallback,
}

impl ExchangeInfoSource {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Override => "override",
            Self::Cache => "cache",
            Self::Bloomberg => "bloomberg",
            Self::Inferred => "inferred",
            Self::Fallback => "fallback",
        }
    }
}

/// Canonical exchange metadata used across resolution layers.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExchangeInfo {
    pub ticker: String,
    pub mic: Option<String>,
    pub exch_code: Option<String>,
    pub timezone: String,
    pub utc_offset: Option<f64>,
    pub sessions: SessionWindows,
    pub source: ExchangeInfoSource,
    pub cached_at: Option<DateTime<Utc>>,
}

impl ExchangeInfo {
    pub fn fallback(ticker: impl Into<String>) -> Self {
        Self {
            ticker: ticker.into(),
            mic: None,
            exch_code: None,
            timezone: "UTC".to_string(),
            utc_offset: None,
            sessions: SessionWindows::default(),
            source: ExchangeInfoSource::Fallback,
            cached_at: None,
        }
    }

    pub fn with_source(mut self, source: ExchangeInfoSource) -> Self {
        self.source = source;
        self
    }

    pub fn as_cache_hit(mut self) -> Self {
        self.source = ExchangeInfoSource::Cache;
        self
    }
}

/// Partial exchange update used by runtime overrides.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct OverridePatch {
    pub timezone: Option<String>,
    pub mic: Option<String>,
    pub exch_code: Option<String>,
    pub sessions: Option<SessionWindows>,
}

impl OverridePatch {
    pub fn is_empty(&self) -> bool {
        self.timezone.is_none()
            && self.mic.is_none()
            && self.exch_code.is_none()
            && self.sessions.is_none()
    }

    pub fn apply_to(&self, info: &mut ExchangeInfo) {
        if let Some(v) = &self.timezone {
            info.timezone = v.clone();
        }
        if let Some(v) = &self.mic {
            info.mic = Some(v.clone());
        }
        if let Some(v) = &self.exch_code {
            info.exch_code = Some(v.clone());
        }
        if let Some(v) = &self.sessions {
            info.sessions = v.clone();
        }
    }
}

/// Market-level metadata used by higher-level APIs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MarketInfo {
    pub exch: Option<String>,
    pub tz: Option<String>,
    pub freq: Option<String>,
    pub is_fut: bool,
}

impl Default for MarketInfo {
    fn default() -> Self {
        Self {
            exch: None,
            tz: None,
            freq: None,
            is_fut: false,
        }
    }
}
