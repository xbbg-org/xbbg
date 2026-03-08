use std::collections::HashMap;
use std::sync::{OnceLock, RwLock, RwLockReadGuard, RwLockWriteGuard};

use chrono::Utc;

use crate::{ExtError, Result};

use super::exchange::{ExchangeInfo, ExchangeInfoSource, OverridePatch};

static REGISTRY: OnceLock<RwLock<HashMap<String, OverridePatch>>> = OnceLock::new();

fn registry() -> &'static RwLock<HashMap<String, OverridePatch>> {
    REGISTRY.get_or_init(|| RwLock::new(HashMap::new()))
}

fn registry_read() -> Result<RwLockReadGuard<'static, HashMap<String, OverridePatch>>> {
    registry()
        .read()
        .map_err(|_| ExtError::Internal("override registry poisoned".to_string()))
}

fn registry_write() -> Result<RwLockWriteGuard<'static, HashMap<String, OverridePatch>>> {
    registry()
        .write()
        .map_err(|_| ExtError::Internal("override registry poisoned".to_string()))
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
    let mut guard = registry_write()?;
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
pub fn get_exchange_override_patch(ticker: &str) -> Result<Option<OverridePatch>> {
    let key = ticker.trim();
    if key.is_empty() {
        return Ok(None);
    }
    Ok(registry_read()?.get(key).cloned())
}

/// Get a materialized exchange override object.
pub fn get_exchange_override(ticker: &str) -> Result<Option<ExchangeInfo>> {
    let Some(patch) = get_exchange_override_patch(ticker)? else {
        return Ok(None);
    };
    let mut info =
        ExchangeInfo::fallback(ticker.to_string()).with_source(ExchangeInfoSource::Override);
    patch.apply_to(&mut info);
    info.cached_at = Some(Utc::now());
    Ok(Some(info))
}

/// Remove a single override if `ticker` is provided; clear all otherwise.
pub fn clear_exchange_override(ticker: Option<&str>) -> Result<()> {
    let mut guard = registry_write()?;
    match ticker {
        Some(t) if !t.trim().is_empty() => {
            guard.remove(t.trim());
        }
        _ => guard.clear(),
    }
    Ok(())
}

/// Return all active overrides as materialized exchange info objects.
pub fn list_exchange_overrides() -> Result<HashMap<String, ExchangeInfo>> {
    Ok(registry_read()?
        .iter()
        .map(|(ticker, patch)| {
            let mut info =
                ExchangeInfo::fallback(ticker.clone()).with_source(ExchangeInfoSource::Override);
            patch.apply_to(&mut info);
            info.cached_at = Some(Utc::now());
            (ticker.clone(), info)
        })
        .collect())
}

pub fn has_exchange_override(ticker: &str) -> Result<bool> {
    let key = ticker.trim();
    if key.is_empty() {
        return Ok(false);
    }
    Ok(registry_read()?.contains_key(key))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::markets::sessions::SessionWindows;

    #[test]
    fn test_override_lifecycle() {
        clear_exchange_override(None).unwrap();

        set_exchange_override(
            "AAPL US Equity",
            OverridePatch {
                timezone: Some("America/New_York".to_string()),
                ..OverridePatch::default()
            },
        )
        .unwrap();

        assert!(has_exchange_override("AAPL US Equity").unwrap());
        let info = get_exchange_override("AAPL US Equity").unwrap().unwrap();
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

        let info = get_exchange_override("AAPL US Equity").unwrap().unwrap();
        assert_eq!(info.timezone, "America/New_York");
        assert_eq!(
            info.sessions.day,
            Some(("09:30".to_string(), "16:00".to_string()))
        );

        clear_exchange_override(Some("AAPL US Equity")).unwrap();
        assert!(!has_exchange_override("AAPL US Equity").unwrap());
    }
}
