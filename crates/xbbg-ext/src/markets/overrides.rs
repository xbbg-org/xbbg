use std::collections::HashMap;
use std::sync::{OnceLock, RwLock};

use chrono::Utc;

use crate::{ExtError, Result};

use super::exchange::{ExchangeInfo, ExchangeInfoSource, OverridePatch};

static REGISTRY: OnceLock<RwLock<HashMap<String, OverridePatch>>> = OnceLock::new();

fn registry() -> &'static RwLock<HashMap<String, OverridePatch>> {
    REGISTRY.get_or_init(|| RwLock::new(HashMap::new()))
}

fn normalize_ticker(ticker: &str) -> Result<String> {
    let normalized = ticker.trim();
    if normalized.is_empty() {
        return Err(ExtError::InvalidInput("ticker cannot be empty".to_string()));
    }
    Ok(normalized.to_string())
}

/// Set or merge a runtime override patch for a ticker.
pub fn set_exchange_override(ticker: &str, patch: OverridePatch) -> Result<()> {
    if patch.is_empty() {
        return Err(ExtError::InvalidInput(
            "override patch must include at least one field".to_string(),
        ));
    }
    let key = normalize_ticker(ticker)?;
    let mut guard = registry().write().expect("override registry poisoned");
    guard
        .entry(key)
        .and_modify(|existing| {
            if patch.timezone.is_some() {
                existing.timezone = patch.timezone.clone();
            }
            if patch.mic.is_some() {
                existing.mic = patch.mic.clone();
            }
            if patch.exch_code.is_some() {
                existing.exch_code = patch.exch_code.clone();
            }
            if patch.sessions.is_some() {
                existing.sessions = patch.sessions.clone();
            }
        })
        .or_insert(patch);
    Ok(())
}

/// Get a raw override patch for merge workflows.
pub fn get_exchange_override_patch(ticker: &str) -> Option<OverridePatch> {
    let key = ticker.trim();
    if key.is_empty() {
        return None;
    }
    registry()
        .read()
        .expect("override registry poisoned")
        .get(key)
        .cloned()
}

/// Get a materialized exchange override object.
pub fn get_exchange_override(ticker: &str) -> Option<ExchangeInfo> {
    let patch = get_exchange_override_patch(ticker)?;
    let mut info =
        ExchangeInfo::fallback(ticker.to_string()).with_source(ExchangeInfoSource::Override);
    patch.apply_to(&mut info);
    info.cached_at = Some(Utc::now());
    Some(info)
}

/// Remove a single override if `ticker` is provided; clear all otherwise.
pub fn clear_exchange_override(ticker: Option<&str>) {
    let mut guard = registry().write().expect("override registry poisoned");
    match ticker {
        Some(t) if !t.trim().is_empty() => {
            guard.remove(t.trim());
        }
        _ => guard.clear(),
    }
}

/// Return all active overrides as materialized exchange info objects.
pub fn list_exchange_overrides() -> HashMap<String, ExchangeInfo> {
    registry()
        .read()
        .expect("override registry poisoned")
        .iter()
        .map(|(ticker, patch)| {
            let mut info =
                ExchangeInfo::fallback(ticker.clone()).with_source(ExchangeInfoSource::Override);
            patch.apply_to(&mut info);
            info.cached_at = Some(Utc::now());
            (ticker.clone(), info)
        })
        .collect()
}

pub fn has_exchange_override(ticker: &str) -> bool {
    let key = ticker.trim();
    if key.is_empty() {
        return false;
    }
    registry()
        .read()
        .expect("override registry poisoned")
        .contains_key(key)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::markets::sessions::SessionWindows;

    #[test]
    fn test_override_lifecycle() {
        clear_exchange_override(None);

        set_exchange_override(
            "AAPL US Equity",
            OverridePatch {
                timezone: Some("America/New_York".to_string()),
                ..OverridePatch::default()
            },
        )
        .unwrap();

        assert!(has_exchange_override("AAPL US Equity"));
        let info = get_exchange_override("AAPL US Equity").unwrap();
        assert_eq!(info.timezone, "America/New_York");
        assert_eq!(info.source, ExchangeInfoSource::Override);

        set_exchange_override(
            "AAPL US Equity",
            OverridePatch {
                sessions: Some(SessionWindows {
                    day: Some(("09:30".to_string(), "16:00".to_string())),
                    ..SessionWindows::default()
                }),
                ..OverridePatch::default()
            },
        )
        .unwrap();

        let info = get_exchange_override("AAPL US Equity").unwrap();
        assert_eq!(info.timezone, "America/New_York");
        assert_eq!(
            info.sessions.day,
            Some(("09:30".to_string(), "16:00".to_string()))
        );

        clear_exchange_override(Some("AAPL US Equity"));
        assert!(!has_exchange_override("AAPL US Equity"));
    }
}
