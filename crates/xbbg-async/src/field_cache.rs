//! Field type cache and resolution.
//!
//! Provides automatic field type resolution using a hierarchy:
//! 1. Manual Override (from Python)
//! 2. Physical Cache (~/.xbbg/field_cache.parquet)
//! 3. API Query (//blp/apiflds service)
//! 4. Defaults (bdp=String, bdh=Float64)

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, RwLock};

use arrow::array::{Array, ArrayRef, RecordBatch, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::arrow::ArrowWriter;
use tracing::{debug, info, warn};

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
    pub fn to_arrow_type_str(&self) -> &'static str {
        match self {
            BlpFieldType::Boolean => "boolean",
            BlpFieldType::Character => "string",
            BlpFieldType::Date => "date32",
            BlpFieldType::DateOrTime => "string",
            BlpFieldType::Double | BlpFieldType::Float => "float64",
            BlpFieldType::Int32 => "int32",
            BlpFieldType::Int64 => "int64",
            BlpFieldType::String => "string",
            BlpFieldType::Time => "string",
            BlpFieldType::BulkFormat => "string",
            BlpFieldType::Unknown(_) => "string",
        }
    }
}

/// Cached field information.
#[derive(Clone, Debug)]
pub struct FieldInfo {
    pub field_id: String,
    pub arrow_type: String,
    pub description: String,
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
    /// Create a new resolver with default cache path (~/.xbbg/field_cache.parquet).
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
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".xbbg")
            .join("field_cache.parquet")
    }

    /// Ensure cache is loaded from disk.
    fn ensure_loaded(&self) {
        let loaded = *self.loaded.read().unwrap();
        if !loaded {
            self.load_from_disk();
            *self.loaded.write().unwrap() = true;
        }
    }

    /// Load cache from Parquet file.
    fn load_from_disk(&self) {
        if !self.cache_path.exists() {
            debug!(path = %self.cache_path.display(), "Cache file does not exist");
            return;
        }

        let file = match fs::File::open(&self.cache_path) {
            Ok(f) => f,
            Err(e) => {
                warn!(error = %e, "Failed to open cache file");
                return;
            }
        };

        let reader = match ParquetRecordBatchReaderBuilder::try_new(file) {
            Ok(builder) => match builder.build() {
                Ok(r) => r,
                Err(e) => {
                    warn!(error = %e, "Failed to build Parquet reader");
                    return;
                }
            },
            Err(e) => {
                warn!(error = %e, "Failed to create Parquet reader");
                return;
            }
        };

        let mut cache = self.cache.write().unwrap();
        let mut count = 0;

        for batch_result in reader {
            let batch = match batch_result {
                Ok(b) => b,
                Err(e) => {
                    warn!(error = %e, "Failed to read batch");
                    continue;
                }
            };

            // Extract columns
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

            if let (Some(fields), Some(types)) = (field_col, type_col) {
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

                    cache.insert(
                        field_id.clone(),
                        FieldInfo {
                            field_id,
                            arrow_type,
                            description,
                            category,
                        },
                    );
                    count += 1;
                }
            }
        }

        info!(count = count, path = %self.cache_path.display(), "Loaded field cache");
    }

    /// Save cache to Parquet file.
    pub fn save_to_disk(&self) -> Result<(), String> {
        self.ensure_loaded();

        // Ensure directory exists
        if let Some(parent) = self.cache_path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("Failed to create cache dir: {e}"))?;
        }

        let cache = self.cache.read().unwrap();
        if cache.is_empty() {
            debug!("Cache is empty, nothing to save");
            return Ok(());
        }

        // Build arrays
        let mut fields: Vec<&str> = Vec::with_capacity(cache.len());
        let mut types: Vec<&str> = Vec::with_capacity(cache.len());
        let mut descriptions: Vec<&str> = Vec::with_capacity(cache.len());
        let mut categories: Vec<&str> = Vec::with_capacity(cache.len());

        for info in cache.values() {
            fields.push(&info.field_id);
            types.push(&info.arrow_type);
            descriptions.push(&info.description);
            categories.push(&info.category);
        }

        let schema = Arc::new(Schema::new(vec![
            Field::new("field", DataType::Utf8, false),
            Field::new("type", DataType::Utf8, false),
            Field::new("description", DataType::Utf8, true),
            Field::new("category", DataType::Utf8, true),
        ]));

        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(StringArray::from(fields)) as ArrayRef,
                Arc::new(StringArray::from(types)) as ArrayRef,
                Arc::new(StringArray::from(descriptions)) as ArrayRef,
                Arc::new(StringArray::from(categories)) as ArrayRef,
            ],
        )
        .map_err(|e| format!("Failed to create batch: {e}"))?;

        let file =
            fs::File::create(&self.cache_path).map_err(|e| format!("Failed to create file: {e}"))?;

        let mut writer = ArrowWriter::try_new(file, schema, None)
            .map_err(|e| format!("Failed to create writer: {e}"))?;

        writer
            .write(&batch)
            .map_err(|e| format!("Failed to write batch: {e}"))?;

        writer
            .close()
            .map_err(|e| format!("Failed to close writer: {e}"))?;

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

/// Global field type resolver (lazily initialized).
static GLOBAL_RESOLVER: once_cell::sync::Lazy<Arc<FieldTypeResolver>> =
    once_cell::sync::Lazy::new(|| Arc::new(FieldTypeResolver::new()));

/// Get the global field type resolver.
pub fn global_resolver() -> Arc<FieldTypeResolver> {
    GLOBAL_RESOLVER.clone()
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
