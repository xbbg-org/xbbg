//! Schema-based request validation.
//!
//! Validates request parameters against cached schemas before sending to Bloomberg.
//! This provides early error detection and better error messages.

use std::collections::HashSet;

use xbbg_core::schema::{SerializedElement, SerializedSchema};

/// Validation result with detailed error information.
#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub valid: bool,
    pub errors: Vec<ValidationError>,
    pub warnings: Vec<ValidationWarning>,
}

impl ValidationResult {
    pub fn ok() -> Self {
        Self {
            valid: true,
            errors: Vec::new(),
            warnings: Vec::new(),
        }
    }

    pub fn with_error(error: ValidationError) -> Self {
        Self {
            valid: false,
            errors: vec![error],
            warnings: Vec::new(),
        }
    }

    pub fn add_error(&mut self, error: ValidationError) {
        self.valid = false;
        self.errors.push(error);
    }

    pub fn add_warning(&mut self, warning: ValidationWarning) {
        self.warnings.push(warning);
    }
}

/// Validation error.
#[derive(Debug, Clone)]
pub enum ValidationError {
    /// Operation not found in service schema
    OperationNotFound { operation: String, available: Vec<String> },
    /// Required element is missing
    RequiredElementMissing { element: String, description: String },
    /// Unknown element name
    UnknownElement { element: String, available: Vec<String> },
    /// Type mismatch
    TypeMismatch { element: String, expected: String, found: String },
}

/// Validation warning (non-fatal).
#[derive(Debug, Clone)]
pub enum ValidationWarning {
    /// Deprecated element
    DeprecatedElement { element: String },
    /// Unknown element (when in lenient mode)
    UnknownElement { element: String },
}

/// Request parameter validator using cached schemas.
pub struct RequestValidator<'a> {
    schema: &'a SerializedSchema,
}

impl<'a> RequestValidator<'a> {
    pub fn new(schema: &'a SerializedSchema) -> Self {
        Self { schema }
    }

    /// Validate that an operation exists in the schema.
    pub fn validate_operation(&self, operation: &str) -> ValidationResult {
        if self.schema.get_operation(operation).is_some() {
            ValidationResult::ok()
        } else {
            ValidationResult::with_error(ValidationError::OperationNotFound {
                operation: operation.to_string(),
                available: self.schema.operations.iter().map(|o| o.name.clone()).collect(),
            })
        }
    }

    /// Validate request element names against the schema.
    pub fn validate_elements(
        &self,
        operation: &str,
        elements: &[&str],
    ) -> ValidationResult {
        let Some(op) = self.schema.get_operation(operation) else {
            return ValidationResult::with_error(ValidationError::OperationNotFound {
                operation: operation.to_string(),
                available: self.schema.operations.iter().map(|o| o.name.clone()).collect(),
            });
        };

        let mut result = ValidationResult::ok();
        let valid_elements: HashSet<_> = op.request.children.iter().map(|e| e.name.as_str()).collect();

        for elem in elements {
            if !valid_elements.contains(*elem) {
                result.add_warning(ValidationWarning::UnknownElement {
                    element: elem.to_string(),
                });
            }
        }

        result
    }

    /// Validate that all required elements are present.
    pub fn validate_required(
        &self,
        operation: &str,
        provided: &[&str],
    ) -> ValidationResult {
        let Some(op) = self.schema.get_operation(operation) else {
            return ValidationResult::with_error(ValidationError::OperationNotFound {
                operation: operation.to_string(),
                available: self.schema.operations.iter().map(|o| o.name.clone()).collect(),
            });
        };

        let mut result = ValidationResult::ok();
        let provided_set: HashSet<_> = provided.iter().copied().collect();

        for elem in &op.request.children {
            if !elem.is_optional && !provided_set.contains(elem.name.as_str()) {
                result.add_error(ValidationError::RequiredElementMissing {
                    element: elem.name.clone(),
                    description: elem.description.clone(),
                });
            }
        }

        result
    }

    /// Get valid enum values for an element.
    pub fn get_enum_values(&self, operation: &str, element: &str) -> Option<Vec<String>> {
        let op = self.schema.get_operation(operation)?;
        find_element(&op.request, element).and_then(|e| e.enum_values.clone())
    }

    /// Get element info.
    pub fn get_element_info(&self, operation: &str, element: &str) -> Option<ElementInfo> {
        let op = self.schema.get_operation(operation)?;
        find_element(&op.request, element).map(|e| ElementInfo {
            name: e.name.clone(),
            description: e.description.clone(),
            data_type: e.data_type.clone(),
            type_name: e.type_name.clone(),
            is_array: e.is_array,
            is_optional: e.is_optional,
            enum_values: e.enum_values.clone(),
        })
    }

    /// List all valid element names for an operation.
    pub fn list_valid_elements(&self, operation: &str) -> Option<Vec<String>> {
        let op = self.schema.get_operation(operation)?;
        Some(op.request.children.iter().map(|e| e.name.clone()).collect())
    }
}

/// Find an element in a schema tree by name (recursive).
fn find_element<'a>(parent: &'a SerializedElement, name: &str) -> Option<&'a SerializedElement> {
    if parent.name == name {
        return Some(parent);
    }
    for child in &parent.children {
        if let Some(found) = find_element(child, name) {
            return Some(found);
        }
    }
    None
}

/// Element information for IDE/autocomplete.
#[derive(Debug, Clone)]
pub struct ElementInfo {
    pub name: String,
    pub description: String,
    pub data_type: String,
    pub type_name: String,
    pub is_array: bool,
    pub is_optional: bool,
    pub enum_values: Option<Vec<String>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_schema() -> SerializedSchema {
        SerializedSchema {
            service: "//blp/refdata".to_string(),
            description: "Reference Data".to_string(),
            operations: vec![SerializedOperation {
                name: "ReferenceDataRequest".to_string(),
                description: "Get reference data".to_string(),
                request: SerializedElement {
                    name: "ReferenceDataRequest".to_string(),
                    description: "".to_string(),
                    data_type: "Sequence".to_string(),
                    type_name: "ReferenceDataRequest".to_string(),
                    is_array: false,
                    is_optional: false,
                    enum_values: None,
                    children: vec![
                        SerializedElement {
                            name: "securities".to_string(),
                            description: "Securities to query".to_string(),
                            data_type: "String".to_string(),
                            type_name: "".to_string(),
                            is_array: true,
                            is_optional: false,
                            enum_values: None,
                            children: Vec::new(),
                        },
                        SerializedElement {
                            name: "fields".to_string(),
                            description: "Fields to retrieve".to_string(),
                            data_type: "String".to_string(),
                            type_name: "".to_string(),
                            is_array: true,
                            is_optional: false,
                            enum_values: None,
                            children: Vec::new(),
                        },
                        SerializedElement {
                            name: "periodicitySelection".to_string(),
                            description: "Periodicity".to_string(),
                            data_type: "Enumeration".to_string(),
                            type_name: "PeriodicitySelection".to_string(),
                            is_array: false,
                            is_optional: true,
                            enum_values: Some(vec!["DAILY".to_string(), "WEEKLY".to_string(), "MONTHLY".to_string()]),
                            children: Vec::new(),
                        },
                    ],
                },
                responses: Vec::new(),
            }],
            cached_at: "2024-01-01T00:00:00Z".to_string(),
        }
    }

    #[test]
    fn test_validate_operation() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        let result = validator.validate_operation("ReferenceDataRequest");
        assert!(result.valid);

        let result = validator.validate_operation("InvalidRequest");
        assert!(!result.valid);
        assert!(matches!(
            &result.errors[0],
            ValidationError::OperationNotFound { .. }
        ));
    }

    #[test]
    fn test_validate_required() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        // Missing both required elements
        let result = validator.validate_required("ReferenceDataRequest", &[]);
        assert!(!result.valid);
        assert_eq!(result.errors.len(), 2);

        // All required elements present
        let result = validator.validate_required("ReferenceDataRequest", &["securities", "fields"]);
        assert!(result.valid);
    }

    #[test]
    fn test_get_enum_values() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        let values = validator.get_enum_values("ReferenceDataRequest", "periodicitySelection");
        assert!(values.is_some());
        let values = values.unwrap();
        assert!(values.contains(&"DAILY".to_string()));
        assert!(values.contains(&"WEEKLY".to_string()));
    }
}
