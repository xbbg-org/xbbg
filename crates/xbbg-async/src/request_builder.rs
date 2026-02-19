//! Schema-driven request routing utilities.
//!
//! Ports Python `_aroute_kwargs()` routing behavior to Rust:
//! - schema-known names -> request elements
//! - UPPERCASE / Mixed_Case_Field -> Bloomberg field overrides
//! - unknown with schema -> warning + pass-through element
//! - unknown without schema -> pass-through element

use std::collections::{HashMap, HashSet};

use serde_json::Value;

use crate::schema::SchemaCache;

/// Routed request parameters after kwargs classification.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RoutedParams {
    /// Schema-recognized (or pass-through) request elements.
    pub elements: Vec<(String, String)>,
    /// Bloomberg field overrides (`fieldId`/`value` pairs).
    pub overrides: Vec<(String, String)>,
    /// Non-fatal routing warnings.
    pub warnings: Vec<String>,
}

/// Request routing helper.
#[derive(Debug, Default)]
pub struct RequestBuilder;

impl RequestBuilder {
    /// Route kwargs into request elements vs Bloomberg field overrides.
    ///
    /// This mirrors Python `_aroute_kwargs()` behavior, using only a synchronous
    /// schema cache read (no async introspection).
    pub fn route_kwargs(
        schema_cache: &SchemaCache,
        service: &str,
        operation: &str,
        mut kwargs: HashMap<String, String>,
        explicit_overrides: Option<Vec<(String, String)>>,
    ) -> RoutedParams {
        let valid_elements = valid_elements_from_cache(schema_cache, service, operation);

        let mut routed = RoutedParams::default();

        // Handle explicit overrides first (matches Python behavior).
        if let Some(raw_overrides) = kwargs.remove("overrides") {
            routed.overrides.extend(parse_raw_overrides(&raw_overrides));
        }

        if let Some(overrides) = explicit_overrides {
            routed.overrides.extend(overrides);
        }

        // HashMap iteration order is not stable. Sort keys for deterministic routing.
        let mut keys: Vec<String> = kwargs.keys().cloned().collect();
        keys.sort();

        for key in keys {
            let Some(value) = kwargs.remove(&key) else {
                continue;
            };

            if valid_elements.contains(&key) {
                routed.elements.push((key, value));
            } else if is_field_override_name(&key) {
                routed.overrides.push((key, value));
            } else if !valid_elements.is_empty() {
                let warning = format_unknown_parameter_warning(&key, operation, &valid_elements);
                routed.warnings.push(warning);
                routed.elements.push((key, value));
            } else {
                routed.elements.push((key, value));
            }
        }

        routed
    }
}

fn valid_elements_from_cache(
    schema_cache: &SchemaCache,
    service: &str,
    operation: &str,
) -> HashSet<String> {
    schema_cache
        .get(service)
        .and_then(|schema| {
            schema
                .get_operation(operation)
                .map(|op| op.request_element_names())
        })
        .map(|elements| elements.into_iter().collect())
        .unwrap_or_default()
}

fn parse_raw_overrides(raw: &str) -> Vec<(String, String)> {
    if let Ok(map) = serde_json::from_str::<serde_json::Map<String, Value>>(raw) {
        return map
            .into_iter()
            .map(|(k, v)| (k, json_value_to_string(v)))
            .collect();
    }

    if let Ok(list) = serde_json::from_str::<Vec<(String, Value)>>(raw) {
        return list
            .into_iter()
            .map(|(k, v)| (k, json_value_to_string(v)))
            .collect();
    }

    Vec::new()
}

fn json_value_to_string(value: Value) -> String {
    match value {
        Value::String(s) => s,
        other => other.to_string(),
    }
}

fn is_field_override_name(key: &str) -> bool {
    is_all_uppercase(key)
        || (key.chars().count() > 2
            && key.chars().next().is_some_and(char::is_uppercase)
            && key.contains('_'))
}

fn is_all_uppercase(value: &str) -> bool {
    let mut has_uppercase_letter = false;

    for ch in value.chars() {
        if ch.is_lowercase() {
            return false;
        }
        if ch.is_uppercase() {
            has_uppercase_letter = true;
        }
    }

    has_uppercase_letter
}

fn format_unknown_parameter_warning(
    key: &str,
    operation: &str,
    valid_elements: &HashSet<String>,
) -> String {
    let mut valid: Vec<&str> = valid_elements.iter().map(String::as_str).collect();
    valid.sort_unstable();

    let preview = if valid.len() > 10 {
        format!("{:?}...", &valid[..10])
    } else {
        format!("{:?}", valid)
    };

    format!(
        "Unknown parameter '{}' for {} - passing to Bloomberg. Valid elements: {}",
        key, operation, preview
    )
}

#[cfg(test)]
mod tests {
    use tempfile::TempDir;

    use super::*;
    use crate::engine::{ExtractorType, RequestParams};
    use crate::schema::{ElementInfo, OperationSchema, ServiceSchema};
    use crate::services::Operation;

    fn test_cache_with_operation(
        service: &str,
        operation: &str,
        valid_elements: &[&str],
    ) -> SchemaCache {
        let temp_dir = TempDir::new().unwrap();
        let cache = SchemaCache::with_cache_dir(temp_dir.path().to_path_buf());

        let request = ElementInfo {
            name: "request".to_string(),
            description: String::new(),
            data_type: "Sequence".to_string(),
            type_name: "Request".to_string(),
            is_array: false,
            is_optional: false,
            enum_values: None,
            children: valid_elements
                .iter()
                .map(|name| ElementInfo {
                    name: (*name).to_string(),
                    description: String::new(),
                    data_type: "String".to_string(),
                    type_name: String::new(),
                    is_array: false,
                    is_optional: true,
                    enum_values: None,
                    children: vec![],
                })
                .collect(),
        };

        let schema = ServiceSchema::new(
            service.to_string(),
            "test".to_string(),
            vec![OperationSchema {
                name: operation.to_string(),
                description: "test".to_string(),
                request,
                responses: vec![],
            }],
        );

        cache.insert(service, schema);
        cache
    }

    fn collect_kwargs(entries: &[(&str, &str)]) -> HashMap<String, String> {
        entries
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect()
    }

    fn empty_test_cache() -> SchemaCache {
        let temp_dir = TempDir::new().unwrap();
        SchemaCache::with_cache_dir(temp_dir.path().to_path_buf())
    }

    #[test]
    fn route_kwargs_splits_elements_and_overrides() {
        let cache = test_cache_with_operation(
            "//blp/refdata",
            "ReferenceDataRequest",
            &["securities", "periodicitySelection"],
        );

        let kwargs = collect_kwargs(&[
            ("securities", "AAPL US Equity"),
            ("periodicitySelection", "DAILY"),
            ("CRNCY", "USD"),
        ]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert!(routed
            .elements
            .contains(&("securities".to_string(), "AAPL US Equity".to_string())));
        assert!(routed
            .elements
            .contains(&("periodicitySelection".to_string(), "DAILY".to_string())));
        assert!(routed
            .overrides
            .contains(&("CRNCY".to_string(), "USD".to_string())));
        assert!(routed.warnings.is_empty());
    }

    #[test]
    fn route_kwargs_merges_explicit_overrides() {
        let cache =
            test_cache_with_operation("//blp/refdata", "ReferenceDataRequest", &["securities"]);

        let kwargs = collect_kwargs(&[("securities", "AAPL US Equity"), ("PX_LAST", "123")]);

        let explicit_overrides = vec![("EQY_FUND_CRNCY".to_string(), "USD".to_string())];

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            Some(explicit_overrides),
        );

        assert!(routed
            .overrides
            .contains(&("EQY_FUND_CRNCY".to_string(), "USD".to_string())));
        assert!(routed
            .overrides
            .contains(&("PX_LAST".to_string(), "123".to_string())));
    }

    #[test]
    fn route_kwargs_handles_raw_overrides_dict_string() {
        let cache =
            test_cache_with_operation("//blp/refdata", "ReferenceDataRequest", &["securities"]);

        let kwargs = collect_kwargs(&[
            ("securities", "AAPL US Equity"),
            (
                "overrides",
                r#"{"CRNCY":"USD","BEST_FPERIOD_OVERRIDE":"1FY"}"#,
            ),
        ]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert!(routed
            .overrides
            .contains(&("CRNCY".to_string(), "USD".to_string())));
        assert!(routed
            .overrides
            .contains(&("BEST_FPERIOD_OVERRIDE".to_string(), "1FY".to_string())));
    }

    #[test]
    fn route_kwargs_detects_mixed_case_field_override() {
        let cache = empty_test_cache();
        let kwargs = collect_kwargs(&[("Eqy_Fund_Year", "2026")]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert_eq!(routed.overrides.len(), 1);
        assert_eq!(
            routed.overrides[0],
            ("Eqy_Fund_Year".to_string(), "2026".to_string())
        );
    }

    #[test]
    fn route_kwargs_warns_on_unknown_param_when_schema_available() {
        let cache =
            test_cache_with_operation("//blp/refdata", "ReferenceDataRequest", &["securities"]);

        let kwargs = collect_kwargs(&[("mystery_param", "value")]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert_eq!(routed.warnings.len(), 1);
        assert!(routed.warnings[0].contains("mystery_param"));
        assert!(routed.warnings[0].contains("ReferenceDataRequest"));
        assert!(routed
            .elements
            .contains(&("mystery_param".to_string(), "value".to_string())));
    }

    #[test]
    fn route_kwargs_passes_unknown_without_warning_when_schema_missing() {
        let cache = empty_test_cache();
        let kwargs = collect_kwargs(&[("mystery_param", "value")]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert!(routed.warnings.is_empty());
        assert!(routed
            .elements
            .contains(&("mystery_param".to_string(), "value".to_string())));
    }

    #[test]
    fn route_kwargs_prefers_schema_element_over_uppercase_rule() {
        let cache =
            test_cache_with_operation("//blp/refdata", "ReferenceDataRequest", &["PX_LAST"]);

        let kwargs = collect_kwargs(&[("PX_LAST", "yes")]);

        let routed = RequestBuilder::route_kwargs(
            &cache,
            "//blp/refdata",
            "ReferenceDataRequest",
            kwargs,
            None,
        );

        assert!(routed
            .elements
            .contains(&("PX_LAST".to_string(), "yes".to_string())));
        assert!(routed.overrides.is_empty());
    }

    fn base_params(operation: Operation) -> RequestParams {
        RequestParams {
            service: "//blp/refdata".to_string(),
            operation: operation.to_string(),
            ..Default::default()
        }
    }

    #[test]
    fn request_builder_with_defaults_uses_operation_default_extractor() {
        let params = RequestParams {
            service: "//blp/refdata".to_string(),
            operation: Operation::HistoricalData.to_string(),
            extractor: ExtractorType::RefData,
            extractor_set: false,
            ..Default::default()
        };

        let resolved = params.with_defaults();
        assert_eq!(resolved.extractor, ExtractorType::HistData);
    }

    #[test]
    fn request_builder_with_defaults_keeps_explicit_extractor() {
        let params = RequestParams {
            service: "//blp/refdata".to_string(),
            operation: Operation::ReferenceData.to_string(),
            extractor: ExtractorType::BulkData,
            extractor_set: true,
            ..Default::default()
        };

        let resolved = params.with_defaults();
        assert_eq!(resolved.extractor, ExtractorType::BulkData);
    }

    #[test]
    fn request_builder_validate_reference_data_pass_and_fail() {
        let params = base_params(Operation::ReferenceData);
        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("securities is required for ReferenceDataRequest"));

        let mut params = base_params(Operation::ReferenceData);
        params.securities = Some(vec!["AAPL US Equity".to_string()]);
        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("fields is required for ReferenceDataRequest"));

        params.fields = Some(vec!["PX_LAST".to_string()]);
        assert!(params.validate().is_ok());
    }

    #[test]
    fn request_builder_validate_historical_data_pass_and_fail() {
        let mut params = base_params(Operation::HistoricalData);
        params.securities = Some(vec!["AAPL US Equity".to_string()]);
        params.fields = Some(vec!["PX_LAST".to_string()]);

        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("start_date is required for HistoricalDataRequest"));

        params.start_date = Some("20240101".to_string());
        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("end_date is required for HistoricalDataRequest"));

        params.end_date = Some("20240131".to_string());
        assert!(params.validate().is_ok());
    }

    #[test]
    fn request_builder_validate_intraday_bar_pass_and_fail() {
        let mut params = base_params(Operation::IntradayBar);
        params.security = Some("AAPL US Equity".to_string());
        params.event_type = Some("TRADE".to_string());
        params.start_datetime = Some("2024-01-01T09:30:00".to_string());
        params.end_datetime = Some("2024-01-01T16:00:00".to_string());

        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("interval is required for IntradayBarRequest"));

        params.interval = Some(1);
        assert!(params.validate().is_ok());
    }

    #[test]
    fn request_builder_validate_intraday_tick_pass_and_fail() {
        let mut params = base_params(Operation::IntradayTick);
        params.security = Some("AAPL US Equity".to_string());
        params.end_datetime = Some("2024-01-01T16:00:00".to_string());

        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("start_datetime is required for IntradayTickRequest"));

        params.start_datetime = Some("2024-01-01T09:30:00".to_string());
        assert!(params.validate().is_ok());
    }

    #[test]
    fn request_builder_validate_field_metadata_requests_pass_and_fail() {
        let mut field_info = base_params(Operation::FieldInfo);
        let err = field_info.validate().unwrap_err().to_string();
        assert!(err.contains("fields is required for field metadata requests"));

        field_info.field_ids = Some(vec!["PX_LAST".to_string()]);
        assert!(field_info.validate().is_ok());

        let mut field_search = base_params(Operation::FieldSearch);
        let err = field_search.validate().unwrap_err().to_string();
        assert!(err.contains("fields is required for field metadata requests"));

        field_search.search_spec = Some("last price".to_string());
        assert!(field_search.validate().is_ok());
    }

    #[test]
    fn request_builder_validate_custom_operation_skips_validation() {
        let params = RequestParams {
            service: "//blp/custom".to_string(),
            operation: "CustomRequest".to_string(),
            ..Default::default()
        };

        assert!(params.validate().is_ok());
    }
}
