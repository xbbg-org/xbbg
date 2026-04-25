use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::{Arc, OnceLock};

use arc_swap::ArcSwap;
use chrono::Utc;

use xbbg_ext::{ExchangeInfo, ExchangeInfoSource};

/// In-memory + disk cache for exchange metadata.
///
/// In-memory reads are lock-free (atomic pointer load) via `ArcSwap`; writers
/// publish a new snapshot via RCU. Disk is loaded lazily at most once via
/// `OnceLock`.
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
