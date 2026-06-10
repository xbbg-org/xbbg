use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::{Arc, OnceLock};

use arc_swap::ArcSwap;
use chrono::Utc;

use xbbg_ext::{ExchangeInfo, ExchangeInfoSource};

/// Days an exchange cache entry stays valid. Exchange metadata (timezones,
/// session hours) drifts rarely; a month bounds staleness without forcing
/// per-run Bloomberg lookups.
pub const EXCHANGE_CACHE_TTL_DAYS: i64 = 30;

fn is_fresh(info: &ExchangeInfo) -> bool {
    info.cached_at.is_some_and(|cached_at| {
        Utc::now().signed_duration_since(cached_at)
            <= chrono::Duration::days(EXCHANGE_CACHE_TTL_DAYS)
    })
}

/// In-memory + disk cache for exchange metadata.
///
/// In-memory reads are lock-free (atomic pointer load) via `ArcSwap`; writers
/// publish a new snapshot via RCU. Disk is loaded lazily at most once via
/// `OnceLock`.
///
/// Entries carry a 30-day TTL ([`EXCHANGE_CACHE_TTL_DAYS`]): expired entries
/// (and legacy entries without a `cached_at` stamp) are served as misses and
/// replaced by the caller's next resolution `put`; expired disk entries are
/// skipped at load. Use [`ExchangeCache::invalidate`] for manual eviction.
pub struct ExchangeCache {
    cache: ArcSwap<HashMap<String, ExchangeInfo>>,
    cache_path: PathBuf,
    loaded: OnceLock<()>,
}

impl ExchangeCache {
    pub fn new() -> Self {
        Self::with_cache_path(Self::default_cache_path())
    }

    pub fn with_cache_path(path: PathBuf) -> Self {
        Self {
            cache: ArcSwap::from_pointee(HashMap::new()),
            cache_path: path,
            loaded: OnceLock::new(),
        }
    }

    pub fn get(&self, ticker: &str) -> Option<ExchangeInfo> {
        self.ensure_loaded();
        let key = ticker.trim();
        if key.is_empty() {
            return None;
        }
        self.cache
            .load()
            .get(key)
            .filter(|info| is_fresh(info))
            .cloned()
            .map(ExchangeInfo::as_cache_hit)
    }

    pub fn put(&self, ticker: &str, mut info: ExchangeInfo) {
        self.ensure_loaded();
        let key = ticker.trim();
        if key.is_empty() {
            return;
        }
        info.cached_at = Some(Utc::now());
        if info.source == ExchangeInfoSource::Fallback {
            info.source = ExchangeInfoSource::Bloomberg;
        }
        let key = key.to_string();
        self.cache.rcu(|current| {
            let mut next = (**current).clone();
            next.insert(key.clone(), info.clone());
            Arc::new(next)
        });
    }

    pub fn invalidate(&self, ticker: Option<&str>) {
        self.ensure_loaded();
        match ticker {
            Some(t) if !t.trim().is_empty() => {
                let key = t.trim().to_string();
                self.cache.rcu(|current| {
                    let mut next = (**current).clone();
                    next.remove(&key);
                    Arc::new(next)
                });
            }
            _ => {
                self.cache.store(Arc::new(HashMap::new()));
            }
        }
    }

    pub fn save_to_disk(&self) -> Result<(), String> {
        self.ensure_loaded();

        if let Some(parent) = self.cache_path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("create cache dir failed: {e}"))?;
        }

        let snapshot = self.cache.load();
        let entries: Vec<&ExchangeInfo> = snapshot.values().collect();

        let file = fs::File::create(&self.cache_path)
            .map_err(|e| format!("create exchange cache file failed: {e}"))?;
        let writer = BufWriter::new(file);
        serde_json::to_writer_pretty(writer, &entries)
            .map_err(|e| format!("write exchange cache JSON failed: {e}"))
    }

    /// Eagerly load the on-disk cache (idempotent).
    pub fn preload(&self) -> Result<(), String> {
        self.ensure_loaded();
        Ok(())
    }

    fn ensure_loaded(&self) {
        self.loaded.get_or_init(|| {
            let _ = self.load_from_disk();
        });
    }

    fn load_from_disk(&self) -> Result<(), String> {
        if !self.cache_path.exists() {
            return Ok(());
        }
        let file = match fs::File::open(&self.cache_path) {
            Ok(f) => f,
            Err(e) => {
                xbbg_log::warn!(error = %e, path = %self.cache_path.display(), "failed to open exchange cache");
                return Ok(());
            }
        };
        let reader = BufReader::new(file);
        let entries: Vec<ExchangeInfo> = match serde_json::from_reader(reader) {
            Ok(v) => v,
            Err(e) => {
                xbbg_log::warn!(error = %e, path = %self.cache_path.display(), "failed to parse exchange cache");
                return Ok(());
            }
        };

        let pairs: Vec<(String, ExchangeInfo)> = entries
            .into_iter()
            // Drop entries that already exceeded the TTL (or predate the
            // cached_at stamp) so stale disk state never reaches the map.
            .filter(is_fresh)
            .map(|mut entry| {
                entry.source = ExchangeInfoSource::Cache;
                (entry.ticker.clone(), entry)
            })
            .collect();

        self.cache.rcu(|current| {
            let mut next = (**current).clone();
            next.extend(pairs.iter().cloned());
            Arc::new(next)
        });

        Ok(())
    }

    fn default_cache_path() -> PathBuf {
        #[cfg(windows)]
        let home = std::env::var("USERPROFILE").ok().map(PathBuf::from);
        #[cfg(not(windows))]
        let home = std::env::var("HOME").ok().map(PathBuf::from);

        home.unwrap_or_else(|| PathBuf::from("."))
            .join(".xbbg")
            .join("cache")
            .join("exchanges.json")
    }
}

impl Default for ExchangeCache {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    fn info(ticker: &str, cached_at: Option<chrono::DateTime<Utc>>) -> ExchangeInfo {
        ExchangeInfo {
            cached_at,
            source: ExchangeInfoSource::Bloomberg,
            ..ExchangeInfo::fallback(ticker)
        }
    }

    fn temp_cache_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "xbbg-exchange-cache-test-{name}-{}.json",
            std::process::id()
        ))
    }

    #[test]
    fn fresh_put_round_trips() {
        let cache = ExchangeCache::with_cache_path(temp_cache_path("fresh"));
        cache.put("AAPL US Equity", info("AAPL US Equity", None));
        let hit = cache.get("AAPL US Equity").expect("fresh entry should hit");
        assert_eq!(hit.source, ExchangeInfoSource::Cache);
        assert!(hit.cached_at.is_some(), "put must stamp cached_at");
    }

    #[test]
    fn expired_entry_is_a_miss() {
        let cache = ExchangeCache::with_cache_path(temp_cache_path("expired"));
        cache.put("AAPL US Equity", info("AAPL US Equity", None));
        // Overwrite the stamp with one beyond the TTL via the RCU path.
        cache.cache.rcu(|current| {
            let mut next = (**current).clone();
            if let Some(entry) = next.get_mut("AAPL US Equity") {
                entry.cached_at = Some(Utc::now() - Duration::days(EXCHANGE_CACHE_TTL_DAYS + 1));
            }
            Arc::new(next)
        });
        assert!(
            cache.get("AAPL US Equity").is_none(),
            "expired entry must miss"
        );
    }

    #[test]
    fn legacy_entry_without_stamp_is_a_miss() {
        let cache = ExchangeCache::with_cache_path(temp_cache_path("legacy"));
        cache.cache.rcu(|current| {
            let mut next = (**current).clone();
            next.insert("IBM US Equity".to_string(), info("IBM US Equity", None));
            Arc::new(next)
        });
        assert!(cache.get("IBM US Equity").is_none());
    }

    #[test]
    fn load_from_disk_skips_expired_entries() {
        let path = temp_cache_path("disk");
        let fresh = info("FRESH US Equity", Some(Utc::now()));
        let stale = info(
            "STALE US Equity",
            Some(Utc::now() - Duration::days(EXCHANGE_CACHE_TTL_DAYS + 1)),
        );
        let payload = serde_json::to_string(&vec![&fresh, &stale]).unwrap();
        std::fs::write(&path, payload).unwrap();

        let cache = ExchangeCache::with_cache_path(path.clone());
        assert!(cache.get("FRESH US Equity").is_some());
        assert!(cache.get("STALE US Equity").is_none());
        let _ = std::fs::remove_file(path);
    }
}
