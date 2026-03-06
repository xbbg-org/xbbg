//! Field type cache and resolution.
//!
//! Provides automatic field type resolution using a hierarchy:
//! 1. Manual Override (from Python)
//! 2. Physical Cache (default: `~/.xbbg/field_cache.json`, configurable via `EngineConfig`)
//! 3. API Query (//blp/apiflds service)
//! 4. Defaults (bdp=String, bdh=Float64)

use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::{Arc, RwLock};

use arrow::array::{Array, RecordBatch, StringArray};
use arrow::datatypes::DataType;
use serde::{Deserialize, Serialize};
use xbbg_log::{debug, info, warn};

/// Bloomberg field type as returned by //blp/apiflds.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BlpFieldType {
    Boolean,
    Character,
    Date,
    DateOrTime,
    Double,
    Float,
    Int32,
    Int64,
    String,
    Time,
    // Bulk types (arrays)
    BulkFormat,
    // Unknown/other
    Unknown(String),
}

impl BlpFieldType {
    /// Parse from Bloomberg field type string.
    pub fn parse(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "boolean" | "bool" => BlpFieldType::Boolean,
            "character" | "char" => BlpFieldType::Character,
            "date" => BlpFieldType::Date,
            "dateortime" | "date_or_time" => BlpFieldType::DateOrTime,
            "double" | "real" | "price" => BlpFieldType::Double,
            "float" => BlpFieldType::Float,
            "int32" | "integer" => BlpFieldType::Int32,
            "int64" | "long" => BlpFieldType::Int64,
            "string" | "longcharacter" | "stringorreal" => BlpFieldType::String,
            "time" => BlpFieldType::Time,
            "bulkformat" | "bulk" => BlpFieldType::BulkFormat,
            other => BlpFieldType::Unknown(other.to_string()),
        }
    }

    /// Convert to Arrow DataType.
    pub fn to_arrow_type(&self) -> DataType {
        match self {
            BlpFieldType::Boolean => DataType::Boolean,
            BlpFieldType::Character => DataType::Utf8,
            BlpFieldType::Date => DataType::Date32,
            BlpFieldType::DateOrTime => DataType::Utf8, // Could be either, use string
            BlpFieldType::Double | BlpFieldType::Float => DataType::Float64,
            BlpFieldType::Int32 => DataType::Int32,
            BlpFieldType::Int64 => DataType::Int64,
            BlpFieldType::String => DataType::Utf8,
            BlpFieldType::Time => DataType::Utf8, // Time as string for now
            BlpFieldType::BulkFormat => DataType::Utf8, // Bulk data as JSON string
            BlpFieldType::Unknown(_) => DataType::Utf8,
        }
    }

    /// Convert to Arrow type string (for serialization).
    ///
    /// Matches Python's FTYPE_TO_ARROW mapping exactly.
    pub fn to_arrow_type_str(&self) -> &'static str {
        match self {
            BlpFieldType::Boolean => "bool", // Python uses "bool" not "boolean"
            BlpFieldType::Character => "string",
            BlpFieldType::Date => "date32",
            BlpFieldType::DateOrTime => "string",
            BlpFieldType::Double | BlpFieldType::Float => "float64",
            BlpFieldType::Int32 => "int64", // Python normalizes Int32 → int64
            BlpFieldType::Int64 => "int64",
            BlpFieldType::String => "string",
            BlpFieldType::Time => "timestamp", // Python maps Time → timestamp
            BlpFieldType::BulkFormat => "string",
            BlpFieldType::Unknown(_) => "string",
        }
    }
}

/// Cached field information.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FieldInfo {
    pub field_id: String,
    pub arrow_type: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub category: String,
}

/// Field type resolver with caching.
pub struct FieldTypeResolver {
    /// In-memory cache (field_id -> FieldInfo)
    cache: RwLock<HashMap<String, FieldInfo>>,
    /// Path to cache file
    cache_path: PathBuf,
    /// Whether cache has been loaded from disk
    loaded: RwLock<bool>,
}

impl FieldTypeResolver {
    /// Create a new resolver with default cache path (~/.xbbg/field_cache.json).
    pub fn new() -> Self {
        let cache_path = Self::default_cache_path();
        Self {
            cache: RwLock::new(HashMap::new()),
            cache_path,
            loaded: RwLock::new(false),
        }
    }

    /// Create a resolver with a custom cache path.
    pub fn with_cache_path(path: PathBuf) -> Self {
        Self {
            cache: RwLock::new(HashMap::new()),
            cache_path: path,
            loaded: RwLock::new(false),
        }
    }

    /// Get the default cache path.
    fn default_cache_path() -> PathBuf {
        // Use standard home directory detection
        #[cfg(windows)]
        let home = std::env::var("USERPROFILE").ok().map(PathBuf::from);
        #[cfg(not(windows))]
        let home = std::env::var("HOME").ok().map(PathBuf::from);

        match home {
            Some(h) => h.join(".xbbg").join("field_cache.json"),
            None => {
                warn!(
                    "Home directory not found (USERPROFILE/HOME not set). \
                     Field cache will use current directory. Set field_cache_path in \
                     EngineConfig to specify a persistent location."
                );
                PathBuf::from(".").join(".xbbg").join("field_cache.json")
            }
        }
    }

    /// Ensure cache is loaded from disk.
    fn ensure_loaded(&self) {
        let loaded = *self.loaded.read().unwrap();
        if !loaded {
            self.load_from_disk();
            *self.loaded.write().unwrap() = true;
        }
    }

    /// Load cache from JSON file.
    fn load_from_disk(&self) {
        if !self.cache_path.exists() {
            info!(
                path = %self.cache_path.display(),
                "No field cache file found, will build cache from API queries"
            );
            return;
        }

        let file = match fs::File::open(&self.cache_path) {
            Ok(f) => f,
            Err(e) => {
                warn!(
                    error = %e,
                    path = %self.cache_path.display(),
                    "Cannot read field cache file. Field types will be re-queried from \
                     Bloomberg on each session. Check file permissions or set \
                     field_cache_path in EngineConfig."
                );
                return;
            }
        };
        let reader = BufReader::new(file);
        let entries: Vec<FieldInfo> = match serde_json::from_reader(reader) {
            Ok(v) => v,
            Err(e) => {
                warn!(
                    error = %e,
                    path = %self.cache_path.display(),
                    "Field cache file is corrupt, ignoring. Will rebuild from API queries."
                );
                return;
            }
        };
        let mut cache = self.cache.write().unwrap();
        for info in entries {
            let key = info.field_id.to_uppercase();
            cache.insert(key, info);
        }

        info!(count = cache.len(), path = %self.cache_path.display(), "Loaded field cache");
    }

    /// Save cache to JSON file.
    pub fn save_to_disk(&self) -> Result<(), String> {
        self.ensure_loaded();

        // Ensure directory exists
        if let Some(parent) = self.cache_path.parent() {
            if let Err(e) = fs::create_dir_all(parent) {
                return Err(format!(
                    "Cannot create field cache directory '{}': {e}. \
                     Field types will not persist between sessions. \
                     Set field_cache_path in EngineConfig to a writable location.",
                    parent.display()
                ));
            }
        }

        let cache = self.cache.read().unwrap();
        if cache.is_empty() {
            debug!("Cache is empty, nothing to save");
            return Ok(());
        }

        // Collect entries
        let entries: Vec<&FieldInfo> = cache.values().collect();

        let file = fs::File::create(&self.cache_path).map_err(|e| {
            format!(
                "Cannot write field cache to '{}': {e}. \
                 Field types will not persist between sessions.",
                self.cache_path.display()
            )
        })?;
        let writer = BufWriter::new(file);

        serde_json::to_writer_pretty(writer, &entries)
            .map_err(|e| format!("Failed to serialize field cache: {e}"))?;

        info!(count = cache.len(), path = %self.cache_path.display(), "Saved field cache");
        Ok(())
    }

    /// Get field info from cache.
    pub fn get(&self, field_id: &str) -> Option<FieldInfo> {
        self.ensure_loaded();
        let cache = self.cache.read().unwrap();
        cache.get(&field_id.to_uppercase()).cloned()
    }

    /// Get Arrow type string for a field.
    pub fn get_arrow_type(&self, field_id: &str) -> Option<String> {
        self.get(field_id).map(|info| info.arrow_type)
    }

    /// Insert field info into cache.
    pub fn insert(&self, info: FieldInfo) {
        self.ensure_loaded();
        let mut cache = self.cache.write().unwrap();
        cache.insert(info.field_id.to_uppercase(), info);
    }

    /// Insert multiple field infos from a FieldInfoRequest response.
    ///
    /// Expects columns from the FieldInfo extractor:
    /// - field: Field mnemonic (e.g., "PX_LAST")
    /// - type: Arrow type string (e.g., "float64")
    /// - description: Field description
    /// - category: Category name
    pub fn insert_from_response(&self, batch: &RecordBatch) {
        self.ensure_loaded();

        let field_col = batch
            .column_by_name("field")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let type_col = batch
            .column_by_name("type")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let desc_col = batch
            .column_by_name("description")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let cat_col = batch
            .column_by_name("category")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());

        let (Some(fields), Some(types)) = (field_col, type_col) else {
            warn!("FieldInfo batch missing required columns (field, type)");
            return;
        };

        let mut cache = self.cache.write().unwrap();
        for i in 0..batch.num_rows() {
            if fields.is_null(i) || types.is_null(i) {
                continue;
            }
            let field_id = fields.value(i).to_uppercase();
            let arrow_type = types.value(i).to_string();
            let description = desc_col
                .and_then(|c| if c.is_null(i) { None } else { Some(c.value(i)) })
                .unwrap_or("")
                .to_string();
            let category = cat_col
                .and_then(|c| if c.is_null(i) { None } else { Some(c.value(i)) })
                .unwrap_or("")
                .to_string();

            debug!(field = %field_id, arrow_type = %arrow_type, "Cached field type");
            cache.insert(
                field_id.clone(),
                FieldInfo {
                    field_id,
                    arrow_type,
                    description,
                    category,
                },
            );
        }
    }

    /// Resolve field types for a list of fields.
    ///
    /// Returns a HashMap of field_id -> arrow_type_string.
    /// Uses the hierarchy: manual_overrides -> cache -> default.
    pub fn resolve_types(
        &self,
        fields: &[String],
        manual_overrides: Option<&HashMap<String, String>>,
        default_type: &str,
    ) -> HashMap<String, String> {
        self.ensure_loaded();

        let mut result = HashMap::new();
        let cache = self.cache.read().unwrap();

        for field in fields {
            let field_upper = field.to_uppercase();

            // 1. Check manual overrides
            if let Some(overrides) = manual_overrides {
                if let Some(t) = overrides.get(field).or_else(|| overrides.get(&field_upper)) {
                    result.insert(field.clone(), t.clone());
                    continue;
                }
            }

            // 2. Check cache
            if let Some(info) = cache.get(&field_upper) {
                result.insert(field.clone(), info.arrow_type.clone());
                continue;
            }

            // 3. Use default
            result.insert(field.clone(), default_type.to_string());
        }

        result
    }

    /// Get list of fields that are not in cache.
    pub fn get_uncached_fields(&self, fields: &[String]) -> Vec<String> {
        self.ensure_loaded();
        let cache = self.cache.read().unwrap();

        fields
            .iter()
            .filter(|f| !cache.contains_key(&f.to_uppercase()))
            .cloned()
            .collect()
    }

    /// Clear all cached field info.
    pub fn clear(&self) {
        let mut cache = self.cache.write().unwrap();
        cache.clear();
        info!("Cleared field cache");
    }

    /// Get cache statistics.
    pub fn stats(&self) -> (usize, PathBuf) {
        self.ensure_loaded();
        let cache = self.cache.read().unwrap();
        (cache.len(), self.cache_path.clone())
    }
}

impl Default for FieldTypeResolver {
    fn default() -> Self {
        Self::new()
    }
}

/// Global field type resolver (initialized on first access or via `init_global_resolver`).
static GLOBAL_RESOLVER: std::sync::OnceLock<Arc<FieldTypeResolver>> = std::sync::OnceLock::new();

/// Initialize the global field type resolver with an optional custom cache path.
///
/// If already initialized (e.g., from a previous `Engine::start()` call), this is a no-op
/// and the existing resolver is returned. The cache path cannot be changed after initialization.
pub fn init_global_resolver(cache_path: Option<PathBuf>) -> Arc<FieldTypeResolver> {
    GLOBAL_RESOLVER
        .get_or_init(|| {
            let resolver = match cache_path {
                Some(ref path) => {
                    info!(path = %path.display(), "Using custom field cache path");
                    FieldTypeResolver::with_cache_path(path.clone())
                }
                None => FieldTypeResolver::new(),
            };
            Arc::new(resolver)
        })
        .clone()
}

/// Get the global field type resolver.
///
/// If not yet initialized, creates one with the default cache path.
pub fn global_resolver() -> Arc<FieldTypeResolver> {
    init_global_resolver(None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_blp_field_type_parsing() {
        assert_eq!(BlpFieldType::parse("Double"), BlpFieldType::Double);
        assert_eq!(BlpFieldType::parse("REAL"), BlpFieldType::Double);
        assert_eq!(BlpFieldType::parse("Price"), BlpFieldType::Double);
        assert_eq!(BlpFieldType::parse("String"), BlpFieldType::String);
        assert_eq!(BlpFieldType::parse("Boolean"), BlpFieldType::Boolean);
        assert_eq!(BlpFieldType::parse("Date"), BlpFieldType::Date);
        assert_eq!(BlpFieldType::parse("Int64"), BlpFieldType::Int64);
    }

    #[test]
    fn test_arrow_type_conversion() {
        assert_eq!(BlpFieldType::Double.to_arrow_type(), DataType::Float64);
        assert_eq!(BlpFieldType::String.to_arrow_type(), DataType::Utf8);
        assert_eq!(BlpFieldType::Boolean.to_arrow_type(), DataType::Boolean);
        assert_eq!(BlpFieldType::Date.to_arrow_type(), DataType::Date32);
        assert_eq!(BlpFieldType::Int64.to_arrow_type(), DataType::Int64);
    }

    #[test]
    fn test_resolve_with_overrides() {
        let resolver = FieldTypeResolver::new();

        let fields = vec!["PX_LAST".to_string(), "VOLUME".to_string()];
        let mut overrides = HashMap::new();
        overrides.insert("VOLUME".to_string(), "int64".to_string());

        let resolved = resolver.resolve_types(&fields, Some(&overrides), "float64");

        assert_eq!(resolved.get("PX_LAST"), Some(&"float64".to_string()));
        assert_eq!(resolved.get("VOLUME"), Some(&"int64".to_string()));
    }
}
