use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::RwLock;

use chrono::Utc;

use xbbg_ext::{ExchangeInfo, ExchangeInfoSource};

/// In-memory + disk cache for exchange metadata.
pub struct ExchangeCache {
    cache: RwLock<HashMap<String, ExchangeInfo>>,
    cache_path: PathBuf,
    loaded: RwLock<bool>,
}

impl ExchangeCache {
    pub fn new() -> Self {
        Self::with_cache_path(Self::default_cache_path())
    }

    pub fn with_cache_path(path: PathBuf) -> Self {
        Self {
            cache: RwLock::new(HashMap::new()),
            cache_path: path,
            loaded: RwLock::new(false),
        }
    }

    pub fn get(&self, ticker: &str) -> Option<ExchangeInfo> {
        self.ensure_loaded();
        let key = ticker.trim();
        if key.is_empty() {
            return None;
        }
        self.cache
            .read()
            .expect("exchange cache lock poisoned")
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
        self.cache
            .write()
            .expect("exchange cache lock poisoned")
            .insert(key.to_string(), info);
    }

    pub fn invalidate(&self, ticker: Option<&str>) {
        self.ensure_loaded();
        let mut guard = self.cache.write().expect("exchange cache lock poisoned");
        match ticker {
            Some(t) if !t.trim().is_empty() => {
                guard.remove(t.trim());
            }
            _ => guard.clear(),
        }
    }

    pub fn save_to_disk(&self) -> Result<(), String> {
        self.ensure_loaded();

        if let Some(parent) = self.cache_path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("create cache dir failed: {e}"))?;
        }

        let guard = self.cache.read().expect("exchange cache lock poisoned");
        let entries: Vec<&ExchangeInfo> = guard.values().collect();

        let file = fs::File::create(&self.cache_path)
            .map_err(|e| format!("create exchange cache file failed: {e}"))?;
        let writer = BufWriter::new(file);
        serde_json::to_writer_pretty(writer, &entries)
            .map_err(|e| format!("write exchange cache JSON failed: {e}"))
    }

    fn ensure_loaded(&self) {
        let loaded = *self.loaded.read().expect("exchange cache lock poisoned");
        if loaded {
            return;
        }
        self.load_from_disk();
        *self.loaded.write().expect("exchange cache lock poisoned") = true;
    }

    fn load_from_disk(&self) {
        if !self.cache_path.exists() {
            return;
        }
        let file = match fs::File::open(&self.cache_path) {
            Ok(f) => f,
            Err(e) => {
                xbbg_log::warn!(error = %e, path = %self.cache_path.display(), "failed to open exchange cache");
                return;
            }
        };
        let reader = BufReader::new(file);
        let entries: Vec<ExchangeInfo> = match serde_json::from_reader(reader) {
            Ok(v) => v,
            Err(e) => {
                xbbg_log::warn!(error = %e, path = %self.cache_path.display(), "failed to parse exchange cache");
                return;
            }
        };

        let mut guard = self.cache.write().expect("exchange cache lock poisoned");
        for mut entry in entries {
            entry.source = ExchangeInfoSource::Cache;
            guard.insert(entry.ticker.clone(), entry);
        }
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
