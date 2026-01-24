//! Serde-enabled schema types for JSON serialization.
//!
//! These types mirror Bloomberg's schema structure but are designed for
//! serialization to JSON for Python interop. They are populated from
//! xbbg_core's raw FFI schema types via the introspector module.

use serde::{Deserialize, Serialize};

/// Information about a schema element (field).
///
/// Represents a single field within a request or response definition,
/// including its type, cardinality, and valid values (for enums).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ElementInfo {
    /// Element name (e.g., "securities", "fields", "periodicitySelection")
    pub name: String,

    /// Human-readable description
    pub description: String,

    /// Bloomberg data type (e.g., "String", "Int32", "Enumeration", "Sequence")
    pub data_type: String,

    /// Type name from schema (e.g., "SecuritiesArray", "PeriodicityEnum")
    pub type_name: String,

    /// Whether this element is an array (max_values > 1)
    pub is_array: bool,

    /// Whether this element is optional (min_values == 0)
    pub is_optional: bool,

    /// Valid enum values (if this is an enumeration type)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enum_values: Option<Vec<String>>,

    /// Child elements (for complex/sequence types)
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub children: Vec<ElementInfo>,
}

impl ElementInfo {
    /// Create an empty ElementInfo (for error cases).
    pub fn empty() -> Self {
        Self {
            name: String::new(),
            description: String::new(),
            data_type: String::new(),
            type_name: String::new(),
            is_array: false,
            is_optional: false,
            enum_values: None,
            children: Vec::new(),
        }
    }

    /// Get all element names recursively (for validation).
    pub fn all_element_names(&self) -> Vec<String> {
        let mut names = vec![self.name.clone()];
        for child in &self.children {
            names.extend(child.all_element_names());
        }
        names
    }

    /// Find enum values for a nested element by name.
    pub fn find_enum_values(&self, element_name: &str) -> Option<Vec<String>> {
        if self.name == element_name {
            return self.enum_values.clone();
        }
        for child in &self.children {
            if let Some(values) = child.find_enum_values(element_name) {
                return Some(values);
            }
        }
        None
    }
}

/// Schema for a Bloomberg service operation.
///
/// Represents a single operation (e.g., ReferenceDataRequest, HistoricalDataRequest)
/// including its request and response element definitions.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OperationSchema {
    /// Operation name (e.g., "ReferenceDataRequest")
    pub name: String,

    /// Human-readable description
    pub description: String,

    /// Request element definition
    pub request: ElementInfo,

    /// Response element definitions (may have multiple)
    #[serde(default)]
    pub responses: Vec<ElementInfo>,
}

impl OperationSchema {
    /// Get all valid request element names.
    pub fn request_element_names(&self) -> Vec<String> {
        self.request.all_element_names()
    }

    /// Find enum values for a request element.
    pub fn find_request_enum_values(&self, element_name: &str) -> Option<Vec<String>> {
        self.request.find_enum_values(element_name)
    }
}

/// Complete schema for a Bloomberg service.
///
/// Contains all operations and metadata for a service like //blp/refdata.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ServiceSchema {
    /// Service URI (e.g., "//blp/refdata")
    pub service: String,

    /// Human-readable description
    pub description: String,

    /// All available operations
    pub operations: Vec<OperationSchema>,

    /// ISO timestamp when this schema was cached
    pub cached_at: String,
}

impl ServiceSchema {
    /// Create a new ServiceSchema with current timestamp.
    pub fn new(service: String, description: String, operations: Vec<OperationSchema>) -> Self {
        Self {
            service,
            description,
            operations,
            cached_at: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Get an operation by name.
    pub fn get_operation(&self, name: &str) -> Option<&OperationSchema> {
        self.operations.iter().find(|op| op.name == name)
    }

    /// List all operation names.
    pub fn operation_names(&self) -> Vec<String> {
        self.operations.iter().map(|op| op.name.clone()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_element_info_serialization() {
        let elem = ElementInfo {
            name: "securities".to_string(),
            description: "List of securities".to_string(),
            data_type: "String".to_string(),
            type_name: "SecuritiesArray".to_string(),
            is_array: true,
            is_optional: false,
            enum_values: None,
            children: vec![],
        };

        let json = serde_json::to_string(&elem).unwrap();
        assert!(json.contains("\"name\":\"securities\""));
        assert!(json.contains("\"is_array\":true"));
        // enum_values should be skipped when None
        assert!(!json.contains("enum_values"));
    }

    #[test]
    fn test_element_with_enum() {
        let elem = ElementInfo {
            name: "periodicitySelection".to_string(),
            description: "Periodicity".to_string(),
            data_type: "Enumeration".to_string(),
            type_name: "PeriodicityEnum".to_string(),
            is_array: false,
            is_optional: true,
            enum_values: Some(vec!["DAILY".to_string(), "WEEKLY".to_string()]),
            children: vec![],
        };

        let json = serde_json::to_string(&elem).unwrap();
        assert!(json.contains("\"enum_values\":[\"DAILY\",\"WEEKLY\"]"));
    }

    #[test]
    fn test_find_enum_values() {
        let child = ElementInfo {
            name: "periodicitySelection".to_string(),
            description: String::new(),
            data_type: "Enumeration".to_string(),
            type_name: String::new(),
            is_array: false,
            is_optional: true,
            enum_values: Some(vec!["DAILY".to_string(), "WEEKLY".to_string()]),
            children: vec![],
        };

        let parent = ElementInfo {
            name: "request".to_string(),
            description: String::new(),
            data_type: "Sequence".to_string(),
            type_name: String::new(),
            is_array: false,
            is_optional: false,
            enum_values: None,
            children: vec![child],
        };

        let values = parent.find_enum_values("periodicitySelection");
        assert_eq!(
            values,
            Some(vec!["DAILY".to_string(), "WEEKLY".to_string()])
        );

        let not_found = parent.find_enum_values("nonexistent");
        assert_eq!(not_found, None);
    }

    #[test]
    fn test_service_schema() {
        let op = OperationSchema {
            name: "ReferenceDataRequest".to_string(),
            description: "Get reference data".to_string(),
            request: ElementInfo::empty(),
            responses: vec![],
        };

        let schema = ServiceSchema::new(
            "//blp/refdata".to_string(),
            "Reference Data Service".to_string(),
            vec![op],
        );

        assert_eq!(schema.operation_names(), vec!["ReferenceDataRequest"]);
        assert!(schema.get_operation("ReferenceDataRequest").is_some());
        assert!(schema.get_operation("NonExistent").is_none());
    }
}
