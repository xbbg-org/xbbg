use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::{RwLock, RwLockReadGuard, RwLockWriteGuard};

use chrono::Utc;

use xbbg_ext::{ExchangeInfo, ExchangeInfoSource};

/// In-memory + disk cache for exchange metadata.
pub struct ExchangeCache {
    cache: RwLock<HashMap<String, ExchangeInfo>>,
    cache_path: PathBuf,
    loaded: RwLock<bool>,
}

impl ExchangeCache {
    fn cache_read(&self) -> Result<RwLockReadGuard<'_, HashMap<String, ExchangeInfo>>, String> {
        self.cache
            .read()
            .map_err(|_| "exchange cache lock poisoned".to_string())
    }

    fn cache_write(&self) -> Result<RwLockWriteGuard<'_, HashMap<String, ExchangeInfo>>, String> {
        self.cache
            .write()
            .map_err(|_| "exchange cache lock poisoned".to_string())
    }

    fn loaded_read(&self) -> Result<RwLockReadGuard<'_, bool>, String> {
        self.loaded
            .read()
            .map_err(|_| "exchange cache lock poisoned".to_string())
    }

    fn loaded_write(&self) -> Result<RwLockWriteGuard<'_, bool>, String> {
        self.loaded
            .write()
            .map_err(|_| "exchange cache lock poisoned".to_string())
    }

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

    pub fn get(&self, ticker: &str) -> Result<Option<ExchangeInfo>, String> {
        self.ensure_loaded()?;
        let key = ticker.trim();
        if key.is_empty() {
            return Ok(None);
        }
        Ok(self
            .cache_read()?
            .get(key)
            .cloned()
            .map(ExchangeInfo::as_cache_hit))
    }

    pub fn put(&self, ticker: &str, mut info: ExchangeInfo) -> Result<(), String> {
        self.ensure_loaded()?;
        let key = ticker.trim();
        if key.is_empty() {
            return Ok(());
        }
        info.cached_at = Some(Utc::now());
        if info.source == ExchangeInfoSource::Fallback {
            info.source = ExchangeInfoSource::Bloomberg;
        }
        self.cache_write()?.insert(key.to_string(), info);
        Ok(())
    }

    pub fn invalidate(&self, ticker: Option<&str>) -> Result<(), String> {
        self.ensure_loaded()?;
        let mut guard = self.cache_write()?;
        match ticker {
            Some(t) if !t.trim().is_empty() => {
                guard.remove(t.trim());
            }
            _ => guard.clear(),
        }
        Ok(())
    }

    pub fn save_to_disk(&self) -> Result<(), String> {
        self.ensure_loaded()?;

        if let Some(parent) = self.cache_path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("create cache dir failed: {e}"))?;
        }

        let guard = self.cache_read()?;
        let entries: Vec<&ExchangeInfo> = guard.values().collect();

        let file = fs::File::create(&self.cache_path)
            .map_err(|e| format!("create exchange cache file failed: {e}"))?;
        let writer = BufWriter::new(file);
        serde_json::to_writer_pretty(writer, &entries)
            .map_err(|e| format!("write exchange cache JSON failed: {e}"))
    }

    fn ensure_loaded(&self) -> Result<(), String> {
        let loaded = *self.loaded_read()?;
        if loaded {
            return Ok(());
        }
        self.load_from_disk()?;
        *self.loaded_write()? = true;
        Ok(())
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

        let mut guard = self.cache_write()?;
        for mut entry in entries {
            entry.source = ExchangeInfoSource::Cache;
            guard.insert(entry.ticker.clone(), entry);
        }
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
