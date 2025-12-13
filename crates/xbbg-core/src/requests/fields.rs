//! Field search / info request descriptors.

/// Request to search for fields (e.g. via `FieldSearchRequest`).
#[derive(Debug, Clone)]
pub struct FieldSearchRequest {
    /// Free-text search pattern, e.g. "PX_LAST".
    pub search: String,
    /// Optional filters (category, datatype, etc.), represented generically.
    pub filters: Vec<(String, String)>,
}

impl FieldSearchRequest {
    pub fn new(search: impl Into<String>) -> Self {
        Self {
            search: search.into(),
            filters: Vec::new(),
        }
    }

    pub fn with_filter(mut self, name: impl Into<String>, value: impl Into<String>) -> Self {
        self.filters.push((name.into(), value.into()));
        self
    }

    pub fn validate(&self) -> Result<(), &'static str> {
        if self.search.is_empty() {
            return Err("FieldSearchRequest requires a non-empty search string");
        }
        Ok(())
    }
}

/// Request to fetch detailed information for a set of fields.
#[derive(Debug, Clone)]
pub struct FieldInfoRequest {
    pub field_ids: Vec<String>,
}

impl FieldInfoRequest {
    pub fn new<F: Into<String>>(field_ids: impl IntoIterator<Item = F>) -> Self {
        Self {
            field_ids: field_ids.into_iter().map(Into::into).collect(),
        }
    }

    pub fn validate(&self) -> Result<(), &'static str> {
        if self.field_ids.is_empty() {
            return Err("FieldInfoRequest requires at least one field id");
        }
        Ok(())
    }
}
