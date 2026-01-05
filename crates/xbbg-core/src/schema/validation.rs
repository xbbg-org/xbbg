//! Schema-based request validation.
//!
//! Validates request parameters against cached schemas before sending to Bloomberg.
//! Provides early error detection with helpful suggestions.

use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use super::serialize::{SerializedElement, SerializedOperation, SerializedSchema};
use super::types::BlpType;

/// Validation error with context for helpful error messages.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationError {
    /// Element name that caused the error
    pub element: String,
    /// Error kind with details
    pub kind: ValidationErrorKind,
    /// Suggested correction (if available)
    pub suggestion: Option<String>,
}

impl ValidationError {
    /// Create an unknown element error.
    pub fn unknown_element(element: impl Into<String>, available: Vec<String>) -> Self {
        Self {
            element: element.into(),
            kind: ValidationErrorKind::UnknownElement { available },
            suggestion: None,
        }
    }

    /// Create an unknown element error with suggestion.
    pub fn unknown_element_with_suggestion(
        element: impl Into<String>,
        available: Vec<String>,
        suggestion: impl Into<String>,
    ) -> Self {
        Self {
            element: element.into(),
            kind: ValidationErrorKind::UnknownElement { available },
            suggestion: Some(suggestion.into()),
        }
    }

    /// Create an invalid enum value error.
    pub fn invalid_enum(
        element: impl Into<String>,
        valid: Vec<String>,
        got: impl Into<String>,
    ) -> Self {
        Self {
            element: element.into(),
            kind: ValidationErrorKind::InvalidEnumValue {
                valid,
                got: got.into(),
            },
            suggestion: None,
        }
    }

    /// Create a type mismatch error.
    pub fn type_mismatch(
        element: impl Into<String>,
        expected: BlpType,
        found: impl Into<String>,
    ) -> Self {
        Self {
            element: element.into(),
            kind: ValidationErrorKind::TypeMismatch {
                expected,
                found: found.into(),
            },
            suggestion: None,
        }
    }

    /// Create a required missing error.
    pub fn required_missing(element: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            element: element.into(),
            kind: ValidationErrorKind::RequiredMissing {
                description: description.into(),
            },
            suggestion: None,
        }
    }

    /// Create an operation not found error.
    pub fn operation_not_found(operation: impl Into<String>, available: Vec<String>) -> Self {
        Self {
            element: operation.into(),
            kind: ValidationErrorKind::OperationNotFound { available },
            suggestion: None,
        }
    }

    /// Add a suggestion to this error.
    pub fn with_suggestion(mut self, suggestion: impl Into<String>) -> Self {
        self.suggestion = Some(suggestion.into());
        self
    }
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match &self.kind {
            ValidationErrorKind::UnknownElement { .. } => {
                write!(f, "Unknown element '{}'", self.element)?;
            }
            ValidationErrorKind::InvalidEnumValue { got, .. } => {
                write!(f, "Invalid enum value '{}' for '{}'", got, self.element)?;
            }
            ValidationErrorKind::TypeMismatch { expected, found } => {
                write!(
                    f,
                    "Type mismatch for '{}': expected {}, found {}",
                    self.element, expected, found
                )?;
            }
            ValidationErrorKind::RequiredMissing { .. } => {
                write!(f, "Required element '{}' is missing", self.element)?;
            }
            ValidationErrorKind::OperationNotFound { .. } => {
                write!(f, "Operation '{}' not found", self.element)?;
            }
        }

        if let Some(ref suggestion) = self.suggestion {
            write!(f, ". Did you mean '{}'?", suggestion)?;
        }

        Ok(())
    }
}

impl std::error::Error for ValidationError {}

/// Validation error kinds.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ValidationErrorKind {
    /// Element name not found in schema
    UnknownElement {
        /// Valid element names
        available: Vec<String>,
    },
    /// Enum value not in allowed values
    InvalidEnumValue {
        /// Valid enum values
        valid: Vec<String>,
        /// Value that was provided
        got: String,
    },
    /// Value type doesn't match expected type
    TypeMismatch {
        /// Expected Bloomberg type
        expected: BlpType,
        /// Description of found type
        found: String,
    },
    /// Required element is missing
    RequiredMissing {
        /// Element description
        description: String,
    },
    /// Operation not found in service schema
    OperationNotFound {
        /// Valid operation names
        available: Vec<String>,
    },
}

/// Request validator using cached schemas.
pub struct RequestValidator<'a> {
    schema: &'a SerializedSchema,
}

impl<'a> RequestValidator<'a> {
    /// Create a new validator for a schema.
    pub fn new(schema: &'a SerializedSchema) -> Self {
        Self { schema }
    }

    /// Get the underlying schema.
    pub fn schema(&self) -> &SerializedSchema {
        self.schema
    }

    /// Validate that an operation exists.
    pub fn validate_operation(
        &self,
        operation: &str,
    ) -> Result<&SerializedOperation, ValidationError> {
        self.schema.get_operation(operation).ok_or_else(|| {
            let available: Vec<String> = self
                .schema
                .operations
                .iter()
                .map(|o| o.name.clone())
                .collect();
            let suggestion = fuzzy_match(operation, &available);
            let mut err = ValidationError::operation_not_found(operation, available);
            if let Some(s) = suggestion {
                err = err.with_suggestion(s);
            }
            err
        })
    }

    /// Validate request element names.
    ///
    /// Returns a list of validation errors (empty if all valid).
    pub fn validate_elements(
        &self,
        operation: &str,
        element_names: &[&str],
    ) -> Vec<ValidationError> {
        let Some(op) = self.schema.get_operation(operation) else {
            return vec![ValidationError::operation_not_found(
                operation,
                self.schema
                    .operations
                    .iter()
                    .map(|o| o.name.clone())
                    .collect(),
            )];
        };

        let valid_elements: HashSet<&str> = op
            .request
            .children
            .iter()
            .map(|e| e.name.as_str())
            .collect();
        let available: Vec<String> = op.request.children.iter().map(|e| e.name.clone()).collect();

        let mut errors = Vec::new();

        for &name in element_names {
            if !valid_elements.contains(name) {
                let suggestion = fuzzy_match(name, &available);
                let mut err = ValidationError::unknown_element(name, available.clone());
                if let Some(s) = suggestion {
                    err = err.with_suggestion(s);
                }
                errors.push(err);
            }
        }

        errors
    }

    /// Validate that all required elements are present.
    pub fn validate_required(&self, operation: &str, provided: &[&str]) -> Vec<ValidationError> {
        let Some(op) = self.schema.get_operation(operation) else {
            return vec![ValidationError::operation_not_found(
                operation,
                self.schema
                    .operations
                    .iter()
                    .map(|o| o.name.clone())
                    .collect(),
            )];
        };

        let provided_set: HashSet<&str> = provided.iter().copied().collect();
        let mut errors = Vec::new();

        for elem in &op.request.children {
            if !elem.is_optional && !provided_set.contains(elem.name.as_str()) {
                errors.push(ValidationError::required_missing(
                    &elem.name,
                    &elem.description,
                ));
            }
        }

        errors
    }

    /// Validate an enum value.
    pub fn validate_enum_value(
        &self,
        operation: &str,
        element: &str,
        value: &str,
    ) -> Result<(), ValidationError> {
        let Some(valid_values) = self.get_enum_values(operation, element) else {
            // Not an enum or element not found - skip validation
            return Ok(());
        };

        if valid_values.iter().any(|v| v == value) {
            Ok(())
        } else {
            let suggestion = fuzzy_match(value, &valid_values);
            let mut err = ValidationError::invalid_enum(element, valid_values, value);
            if let Some(s) = suggestion {
                err = err.with_suggestion(s);
            }
            Err(err)
        }
    }

    /// Get valid enum values for an element.
    pub fn get_enum_values(&self, operation: &str, element: &str) -> Option<Vec<String>> {
        let op = self.schema.get_operation(operation)?;
        find_element(&op.request, element).and_then(|e| e.enum_values.clone())
    }

    /// Get element info.
    pub fn get_element(&self, operation: &str, element: &str) -> Option<&SerializedElement> {
        let op = self.schema.get_operation(operation)?;
        find_element(&op.request, element)
    }

    /// List all valid element names for an operation.
    pub fn list_valid_elements(&self, operation: &str) -> Option<Vec<String>> {
        let op = self.schema.get_operation(operation)?;
        Some(op.request.children.iter().map(|e| e.name.clone()).collect())
    }

    /// Suggest a correction for a typo.
    pub fn suggest_element(&self, operation: &str, typo: &str) -> Option<String> {
        let elements = self.list_valid_elements(operation)?;
        fuzzy_match(typo, &elements)
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

/// Simple fuzzy matching for suggestions.
///
/// Returns the best match if the edit distance is small enough.
fn fuzzy_match(input: &str, candidates: &[String]) -> Option<String> {
    let input_lower = input.to_lowercase();
    let mut best_match: Option<(usize, &str)> = None;

    for candidate in candidates {
        let candidate_lower = candidate.to_lowercase();

        // Exact match (case-insensitive)
        if input_lower == candidate_lower {
            return Some(candidate.clone());
        }

        // Calculate edit distance
        let distance = edit_distance(&input_lower, &candidate_lower);

        // Only suggest if distance is small relative to string length
        let max_distance = (input.len() / 3).max(2);
        if distance <= max_distance && (best_match.is_none() || distance < best_match.unwrap().0) {
            best_match = Some((distance, candidate));
        }
    }

    best_match.map(|(_, s)| s.to_string())
}

/// Simple Levenshtein edit distance.
#[allow(clippy::needless_range_loop)]
fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();

    let m = a.len();
    let n = b.len();

    if m == 0 {
        return n;
    }
    if n == 0 {
        return m;
    }

    let mut dp = vec![vec![0; n + 1]; m + 1];

    for (i, row) in dp.iter_mut().enumerate() {
        row[0] = i;
    }
    for j in 0..=n {
        dp[0][j] = j;
    }

    for i in 1..=m {
        for j in 1..=n {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            dp[i][j] = (dp[i - 1][j] + 1)
                .min(dp[i][j - 1] + 1)
                .min(dp[i - 1][j - 1] + cost);
        }
    }

    dp[m][n]
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
                    description: String::new(),
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
                            type_name: String::new(),
                            is_array: true,
                            is_optional: false,
                            enum_values: None,
                            children: Vec::new(),
                        },
                        SerializedElement {
                            name: "fields".to_string(),
                            description: "Fields to retrieve".to_string(),
                            data_type: "String".to_string(),
                            type_name: String::new(),
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
                            enum_values: Some(vec![
                                "DAILY".to_string(),
                                "WEEKLY".to_string(),
                                "MONTHLY".to_string(),
                                "QUARTERLY".to_string(),
                                "SEMI_ANNUALLY".to_string(),
                                "YEARLY".to_string(),
                            ]),
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

        assert!(validator.validate_operation("ReferenceDataRequest").is_ok());
        assert!(validator.validate_operation("InvalidRequest").is_err());
    }

    #[test]
    fn test_validate_elements() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        // Valid elements
        let errors = validator.validate_elements("ReferenceDataRequest", &["securities", "fields"]);
        assert!(errors.is_empty());

        // Invalid element
        let errors = validator.validate_elements("ReferenceDataRequest", &["securites"]); // typo
        assert_eq!(errors.len(), 1);
        assert!(errors[0].suggestion.is_some());
        assert_eq!(errors[0].suggestion.as_ref().unwrap(), "securities");
    }

    #[test]
    fn test_validate_required() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        // Missing required elements
        let errors = validator.validate_required("ReferenceDataRequest", &[]);
        assert_eq!(errors.len(), 2); // securities and fields

        // All required present
        let errors = validator.validate_required("ReferenceDataRequest", &["securities", "fields"]);
        assert!(errors.is_empty());
    }

    #[test]
    fn test_validate_enum() {
        let schema = create_test_schema();
        let validator = RequestValidator::new(&schema);

        // Valid enum value
        assert!(validator
            .validate_enum_value("ReferenceDataRequest", "periodicitySelection", "DAILY")
            .is_ok());

        // Invalid enum value with suggestion
        let result =
            validator.validate_enum_value("ReferenceDataRequest", "periodicitySelection", "DAILYY");
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.suggestion.is_some());
        assert_eq!(err.suggestion.as_ref().unwrap(), "DAILY");
    }

    #[test]
    fn test_fuzzy_match() {
        let candidates = vec![
            "securities".to_string(),
            "fields".to_string(),
            "periodicitySelection".to_string(),
        ];

        assert_eq!(
            fuzzy_match("securites", &candidates),
            Some("securities".to_string())
        );
        assert_eq!(
            fuzzy_match("feilds", &candidates),
            Some("fields".to_string())
        );
        assert_eq!(
            fuzzy_match("periodictySelection", &candidates),
            Some("periodicitySelection".to_string())
        );
        assert_eq!(fuzzy_match("totallyDifferent", &candidates), None);
    }

    #[test]
    fn test_edit_distance() {
        assert_eq!(edit_distance("", ""), 0);
        assert_eq!(edit_distance("abc", "abc"), 0);
        assert_eq!(edit_distance("abc", "ab"), 1);
        assert_eq!(edit_distance("abc", "abd"), 1);
        assert_eq!(edit_distance("abc", "xyz"), 3);
    }
}
