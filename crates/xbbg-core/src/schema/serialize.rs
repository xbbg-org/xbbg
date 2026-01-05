//! Schema serialization for caching and IDE stub generation.
//!
//! This module provides serializable representations of Bloomberg service schemas
//! that can be cached to disk as JSON and used for schema-driven request building.

use serde::{Deserialize, Serialize};

use super::{DataType, Operation, SchemaElementDefinition};
use crate::service::Service;

/// Serializable representation of a Bloomberg service schema.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedSchema {
    /// Service URI (e.g., "//blp/refdata")
    pub service: String,
    /// Service description
    pub description: String,
    /// List of operations
    pub operations: Vec<SerializedOperation>,
    /// ISO8601 timestamp when this schema was cached
    pub cached_at: String,
}

/// Serializable representation of a service operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedOperation {
    /// Operation name (e.g., "ReferenceDataRequest")
    pub name: String,
    /// Operation description
    pub description: String,
    /// Request schema
    pub request: SerializedElement,
    /// Response schemas (some operations have multiple response types)
    pub responses: Vec<SerializedElement>,
}

/// Serializable representation of a schema element.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedElement {
    /// Element name
    pub name: String,
    /// Element description
    pub description: String,
    /// Data type name (e.g., "String", "Int32", "Sequence")
    pub data_type: String,
    /// Type name from schema (e.g., "PeriodicitySelectionType")
    pub type_name: String,
    /// Whether this element can appear multiple times
    pub is_array: bool,
    /// Whether this element is optional
    pub is_optional: bool,
    /// Enumeration values (if this is an enum type)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enum_values: Option<Vec<String>>,
    /// Child elements (for complex types)
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub children: Vec<SerializedElement>,
}

impl SerializedElement {
    /// Create a SerializedElement from a SchemaElementDefinition.
    pub fn from_definition(def: &SchemaElementDefinition, max_depth: usize) -> Self {
        let data_type = def.data_type();
        let is_enum = def.is_enumeration();

        let enum_values = if is_enum {
            let values = def.enumeration_values();
            if values.is_empty() {
                None
            } else {
                Some(values)
            }
        } else {
            None
        };

        let children = if max_depth > 0 {
            (0..def.num_children())
                .filter_map(|i| def.child_at(i).ok())
                .map(|child| Self::from_definition(&child, max_depth - 1))
                .collect()
        } else {
            Vec::new()
        };

        Self {
            name: def.name().to_string(),
            description: def.description().to_string(),
            data_type: data_type_to_string(data_type),
            type_name: def.type_name(),
            is_array: def.is_array(),
            is_optional: def.is_optional(),
            enum_values,
            children,
        }
    }
}

impl SerializedOperation {
    /// Create a SerializedOperation from an Operation.
    pub fn from_operation(op: &Operation) -> Self {
        let request = op
            .request_definition()
            .map(|def| SerializedElement::from_definition(&def, 3))
            .unwrap_or_else(|_| SerializedElement {
                name: String::new(),
                description: String::new(),
                data_type: "Unknown".to_string(),
                type_name: String::new(),
                is_array: false,
                is_optional: false,
                enum_values: None,
                children: Vec::new(),
            });

        // Get response definitions (works for most services except refdata)
        let responses: Vec<SerializedElement> = (0..op.num_response_definitions())
            .filter_map(|i| op.response_definition(i).ok())
            .map(|def| SerializedElement::from_definition(&def, 3))
            .collect();

        Self {
            name: op.name().to_string(),
            description: op.description().to_string(),
            request,
            responses,
        }
    }
}

impl SerializedSchema {
    /// Create a SerializedSchema from a Service.
    pub fn from_service(service: &Service) -> Self {
        let operations: Vec<SerializedOperation> = service
            .operation_names()
            .iter()
            .filter_map(|name| service.get_operation(name).ok())
            .map(|op| SerializedOperation::from_operation(&op))
            .collect();

        Self {
            service: service.name().to_string(),
            description: service.description().to_string(),
            operations,
            cached_at: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Serialize to JSON string.
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }

    /// Deserialize from JSON string.
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }

    /// Get an operation by name.
    pub fn get_operation(&self, name: &str) -> Option<&SerializedOperation> {
        self.operations.iter().find(|op| op.name == name)
    }
}

/// Convert DataType enum to string.
fn data_type_to_string(dt: DataType) -> String {
    match dt {
        DataType::Bool => "Bool",
        DataType::Char => "Char",
        DataType::Byte => "Byte",
        DataType::Int32 => "Int32",
        DataType::Int64 => "Int64",
        DataType::Float32 => "Float32",
        DataType::Float64 => "Float64",
        DataType::String => "String",
        DataType::Date => "Date",
        DataType::Time => "Time",
        DataType::Decimal => "Decimal",
        DataType::Datetime => "Datetime",
        DataType::Enumeration => "Enumeration",
        DataType::ByteArray => "ByteArray",
        DataType::Name => "Name",
        DataType::Sequence => "Sequence",
        DataType::Choice => "Choice",
        DataType::CorrelationId => "CorrelationId",
        DataType::Unknown(v) => return format!("Unknown({})", v),
    }
    .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_serialized_element_roundtrip() {
        let elem = SerializedElement {
            name: "test".to_string(),
            description: "A test element".to_string(),
            data_type: "String".to_string(),
            type_name: "TestType".to_string(),
            is_array: false,
            is_optional: true,
            enum_values: Some(vec!["A".to_string(), "B".to_string()]),
            children: Vec::new(),
        };

        let json = serde_json::to_string(&elem).unwrap();
        let parsed: SerializedElement = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.name, "test");
        assert_eq!(parsed.enum_values, Some(vec!["A".to_string(), "B".to_string()]));
    }
}
