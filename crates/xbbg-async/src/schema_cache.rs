//! Schema cache for Bloomberg service introspection.
//!
//! Caches service schemas to disk for:
//! 1. Faster startup (no re-introspection on every session)
//! 2. IDE stub generation (Python reads cached JSON)
//! 3. Schema-driven request validation
//!
//! Cache location: ~/.xbbg/schemas/<service_name>.json

use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter};
use std::path::PathBuf;
use std::sync::{Arc, RwLock};

use tracing::{debug, info, warn};
use xbbg_core::schema::{RequestValidator, SerializedOperation, SerializedSchema};
use xbbg_core::{BlpError, Service};

/// Schema cache manager.
///
/// Handles loading/saving service schemas from disk and memory caching.
/// Schemas are loaded once and kept in memory for the lifetime of the cache.
///
/// # Performance
///
/// - **First access**: Loads from disk (or introspects if not cached)
/// - **Subsequent access**: Pure in-memory lookup
/// - **Validation**: In-memory only, no disk I/O
pub struct SchemaCache {
    /// In-memory cache (service_uri -> schema)
    /// Using Arc for efficient sharing with validators
    cache: RwLock<HashMap<String, Arc<SerializedSchema>>>,
    /// Base directory for cache files
    cache_dir: PathBuf,
}

impl SchemaCache {
    /// Create a new schema cache with default directory (~/.xbbg/schemas/).
    pub fn new() -> Self {
        Self::with_cache_dir(Self::default_cache_dir())
    }

    /// Create a schema cache with a custom directory.
    pub fn with_cache_dir(cache_dir: PathBuf) -> Self {
        Self {
            cache: RwLock::new(HashMap::new()),
            cache_dir,
        }
    }

    /// Get the default cache directory.
    fn default_cache_dir() -> PathBuf {
        #[cfg(windows)]
        let home = std::env::var("USERPROFILE").ok().map(PathBuf::from);
        #[cfg(not(windows))]
        let home = std::env::var("HOME").ok().map(PathBuf::from);

        home.unwrap_or_else(|| PathBuf::from("."))
            .join(".xbbg")
            .join("schemas")
    }

    /// Get the cache file path for a service.
    fn cache_path(&self, service_uri: &str) -> PathBuf {
        // Convert service URI to filename: "//blp/refdata" -> "refdata.json"
        let name = service_uri
            .trim_start_matches("//blp/")
            .trim_start_matches("//")
            .replace('/', "_");
        self.cache_dir.join(format!("{name}.json"))
    }

    /// Get a cached schema for a service.
    ///
    /// First checks in-memory cache, then disk cache.
    /// Returns an Arc for efficient sharing.
    pub fn get(&self, service_uri: &str) -> Option<Arc<SerializedSchema>> {
        // Check in-memory cache first
        {
            let cache = self.cache.read().unwrap();
            if let Some(schema) = cache.get(service_uri) {
                debug!(service = service_uri, "Schema cache hit (memory)");
                return Some(Arc::clone(schema));
            }
        }

        // Try loading from disk
        let path = self.cache_path(service_uri);
        if !path.exists() {
            debug!(service = service_uri, "Schema cache miss");
            return None;
        }

        let file = match fs::File::open(&path) {
            Ok(f) => f,
            Err(e) => {
                warn!(error = %e, path = %path.display(), "Failed to open schema cache");
                return None;
            }
        };

        let reader = BufReader::new(file);
        let schema: SerializedSchema = match serde_json::from_reader(reader) {
            Ok(s) => s,
            Err(e) => {
                warn!(error = %e, path = %path.display(), "Failed to parse schema cache");
                return None;
            }
        };

        info!(service = service_uri, path = %path.display(), "Loaded schema from disk cache");

        let schema = Arc::new(schema);

        // Store in memory cache
        {
            let mut cache = self.cache.write().unwrap();
            cache.insert(service_uri.to_string(), Arc::clone(&schema));
        }

        Some(schema)
    }

    /// Store a schema in cache (memory and disk).
    pub fn put(&self, schema: &SerializedSchema) -> Result<(), String> {
        let service_uri = &schema.service;

        // Ensure directory exists
        fs::create_dir_all(&self.cache_dir)
            .map_err(|e| format!("Failed to create cache dir: {e}"))?;

        // Write to disk
        let path = self.cache_path(service_uri);
        let file =
            fs::File::create(&path).map_err(|e| format!("Failed to create cache file: {e}"))?;
        let writer = BufWriter::new(file);

        serde_json::to_writer_pretty(writer, schema)
            .map_err(|e| format!("Failed to write schema JSON: {e}"))?;

        info!(service = service_uri, path = %path.display(), "Saved schema to disk cache");

        // Update memory cache
        {
            let mut cache = self.cache.write().unwrap();
            cache.insert(service_uri.to_string(), Arc::new(schema.clone()));
        }

        Ok(())
    }

    /// Get or introspect a schema for a service.
    ///
    /// If cached, returns the cached schema. Otherwise, introspects the service
    /// and caches the result.
    pub fn get_or_introspect(&self, service: &Service) -> Result<Arc<SerializedSchema>, String> {
        let service_uri = service.name();

        // Check cache first
        if let Some(schema) = self.get(service_uri) {
            return Ok(schema);
        }

        // Introspect from live service
        info!(service = service_uri, "Introspecting service schema");
        let schema = SerializedSchema::from_service(service);

        // Cache it
        self.put(&schema)?;

        // Return the Arc version from cache
        self.get(service_uri)
            .ok_or_else(|| "Schema not found after caching".to_string())
    }

    // ========== Validation Methods ==========

    /// Validate request elements against cached schema.
    ///
    /// Returns Ok(()) if valid, or Err with validation errors.
    /// If no schema is cached for the service, returns Ok(()) (validation skipped).
    pub fn validate_request(
        &self,
        service_uri: &str,
        operation: &str,
        element_names: &[&str],
    ) -> Result<(), BlpError> {
        let Some(schema) = self.get(service_uri) else {
            // No schema cached, skip validation
            debug!(
                service = service_uri,
                "No schema cached, skipping validation"
            );
            return Ok(());
        };

        let validator = RequestValidator::new(&schema);

        // Validate operation exists
        if let Err(err) = validator.validate_operation(operation) {
            return Err(BlpError::Validation {
                message: err.to_string(),
                errors: vec![err],
            });
        }

        // Validate element names
        let errors = validator.validate_elements(operation, element_names);
        if !errors.is_empty() {
            let message = errors
                .iter()
                .map(|e| e.to_string())
                .collect::<Vec<_>>()
                .join("; ");
            return Err(BlpError::Validation { message, errors });
        }

        Ok(())
    }

    /// Validate an enum value against cached schema.
    ///
    /// Returns Ok(()) if valid or if validation cannot be performed.
    pub fn validate_enum(
        &self,
        service_uri: &str,
        operation: &str,
        element: &str,
        value: &str,
    ) -> Result<(), BlpError> {
        let Some(schema) = self.get(service_uri) else {
            return Ok(());
        };

        let validator = RequestValidator::new(&schema);

        if let Err(err) = validator.validate_enum_value(operation, element, value) {
            return Err(BlpError::Validation {
                message: err.to_string(),
                errors: vec![err],
            });
        }

        Ok(())
    }

    /// Get valid enum values for an element.
    pub fn get_enum_values(
        &self,
        service_uri: &str,
        operation: &str,
        element: &str,
    ) -> Option<Vec<String>> {
        let schema = self.get(service_uri)?;
        let validator = RequestValidator::new(&schema);
        validator.get_enum_values(operation, element)
    }

    /// Get valid element names for an operation.
    pub fn get_valid_elements(&self, service_uri: &str, operation: &str) -> Option<Vec<String>> {
        let schema = self.get(service_uri)?;
        let validator = RequestValidator::new(&schema);
        validator.list_valid_elements(operation)
    }

    /// Suggest a correction for a potentially misspelled element.
    pub fn suggest_element(
        &self,
        service_uri: &str,
        operation: &str,
        typo: &str,
    ) -> Option<String> {
        let schema = self.get(service_uri)?;
        let validator = RequestValidator::new(&schema);
        validator.suggest_element(operation, typo)
    }

    /// Preload schemas for common services.
    ///
    /// Call this at engine startup for faster first requests.
    pub fn preload_from_disk(&self) {
        for service in ["//blp/refdata", "//blp/apiflds", "//blp/instruments"] {
            if self.get(service).is_some() {
                debug!(service, "Preloaded schema from disk");
            }
        }
    }

    /// Get an operation schema by name.
    pub fn get_operation(
        &self,
        service_uri: &str,
        operation_name: &str,
    ) -> Option<SerializedOperation> {
        self.get(service_uri)
            .and_then(|schema| schema.get_operation(operation_name).cloned())
    }

    /// Invalidate (remove) a cached schema.
    pub fn invalidate(&self, service_uri: &str) {
        // Remove from memory
        {
            let mut cache = self.cache.write().unwrap();
            cache.remove(service_uri);
        }

        // Remove from disk
        let path = self.cache_path(service_uri);
        if path.exists() {
            if let Err(e) = fs::remove_file(&path) {
                warn!(error = %e, path = %path.display(), "Failed to remove cache file");
            } else {
                info!(service = service_uri, "Invalidated schema cache");
            }
        }
    }

    /// Clear all cached schemas.
    pub fn clear(&self) {
        // Clear memory
        {
            let mut cache = self.cache.write().unwrap();
            cache.clear();
        }

        // Clear disk
        if self.cache_dir.exists() {
            if let Ok(entries) = fs::read_dir(&self.cache_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.extension().is_some_and(|ext| ext == "json") {
                        let _ = fs::remove_file(&path);
                    }
                }
            }
        }

        info!("Cleared all schema caches");
    }

    /// List all cached service URIs.
    pub fn list_cached(&self) -> Vec<String> {
        if !self.cache_dir.exists() {
            return Vec::new();
        }

        let mut services = Vec::new();
        if let Ok(entries) = fs::read_dir(&self.cache_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().is_some_and(|ext| ext == "json") {
                    if let Some(name) = path.file_stem().and_then(|s| s.to_str()) {
                        services.push(format!("//blp/{name}"));
                    }
                }
            }
        }
        services
    }

    /// Get cache statistics.
    pub fn stats(&self) -> SchemaCacheStats {
        let cache = self.cache.read().unwrap();
        let memory_count = cache.len();

        let mut disk_count = 0;
        let mut total_size = 0;

        if self.cache_dir.exists() {
            if let Ok(entries) = fs::read_dir(&self.cache_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.extension().is_some_and(|ext| ext == "json") {
                        disk_count += 1;
                        if let Ok(meta) = path.metadata() {
                            total_size += meta.len();
                        }
                    }
                }
            }
        }

        SchemaCacheStats {
            memory_count,
            disk_count,
            total_size_bytes: total_size,
            cache_dir: self.cache_dir.clone(),
        }
    }
}

impl Default for SchemaCache {
    fn default() -> Self {
        Self::new()
    }
}

/// Schema cache statistics.
#[derive(Debug, Clone)]
pub struct SchemaCacheStats {
    /// Number of schemas in memory cache
    pub memory_count: usize,
    /// Number of schemas on disk
    pub disk_count: usize,
    /// Total size of disk cache in bytes
    pub total_size_bytes: u64,
    /// Cache directory path
    pub cache_dir: PathBuf,
}

/// Global schema cache (lazily initialized).
static GLOBAL_SCHEMA_CACHE: once_cell::sync::Lazy<std::sync::Arc<SchemaCache>> =
    once_cell::sync::Lazy::new(|| std::sync::Arc::new(SchemaCache::new()));

/// Get the global schema cache.
pub fn global_schema_cache() -> std::sync::Arc<SchemaCache> {
    GLOBAL_SCHEMA_CACHE.clone()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn create_test_schema() -> SerializedSchema {
        SerializedSchema {
            service: "//blp/refdata".to_string(),
            description: "Reference Data Service".to_string(),
            operations: vec![],
            cached_at: "2024-01-01T00:00:00Z".to_string(),
        }
    }

    #[test]
    fn test_cache_path() {
        let cache = SchemaCache::with_cache_dir(PathBuf::from("/tmp/test"));

        assert_eq!(
            cache.cache_path("//blp/refdata"),
            PathBuf::from("/tmp/test/refdata.json")
        );
        assert_eq!(
            cache.cache_path("//blp/instruments"),
            PathBuf::from("/tmp/test/instruments.json")
        );
    }

    #[test]
    fn test_put_and_get() {
        let temp_dir = TempDir::new().unwrap();
        let cache = SchemaCache::with_cache_dir(temp_dir.path().to_path_buf());

        let schema = create_test_schema();
        cache.put(&schema).unwrap();

        // Should get from memory
        let retrieved = cache.get("//blp/refdata").unwrap();
        assert_eq!(retrieved.service, schema.service);

        // Clear memory, should still get from disk
        cache.cache.write().unwrap().clear();
        let retrieved = cache.get("//blp/refdata").unwrap();
        assert_eq!(retrieved.service, schema.service);
    }

    #[test]
    fn test_invalidate() {
        let temp_dir = TempDir::new().unwrap();
        let cache = SchemaCache::with_cache_dir(temp_dir.path().to_path_buf());

        let schema = create_test_schema();
        cache.put(&schema).unwrap();

        assert!(cache.get("//blp/refdata").is_some());

        cache.invalidate("//blp/refdata");

        assert!(cache.get("//blp/refdata").is_none());
    }

    #[test]
    fn test_list_cached() {
        let temp_dir = TempDir::new().unwrap();
        let cache = SchemaCache::with_cache_dir(temp_dir.path().to_path_buf());

        let mut schema = create_test_schema();
        cache.put(&schema).unwrap();

        schema.service = "//blp/instruments".to_string();
        cache.put(&schema).unwrap();

        let cached = cache.list_cached();
        assert_eq!(cached.len(), 2);
        assert!(cached.contains(&"//blp/refdata".to_string()));
        assert!(cached.contains(&"//blp/instruments".to_string()));
    }
}
