//! Canonical request preparation for worker dispatch.
//!
//! `RequestParams` stays as the public edge DTO. This module is the single
//! boundary that applies operation defaults, validates required fields, routes
//! kwargs, and classifies the request shape consumed by workers.

use std::collections::HashMap;

use crate::errors::BlpAsyncError;
use crate::request_builder::RequestBuilder;
use crate::schema::SchemaCache;
use crate::services::{ExtractorType, Operation};

use super::state::{LongMode, OutputFormat};
use super::{
    merge_raw_kwargs_into_elements, normalize_excel_grid_params, parse_operation_lossless,
    RequestParams,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PlannedOutput {
    pub format: OutputFormat,
    pub long_mode: LongMode,
}

impl PlannedOutput {
    fn from_format(format: Option<&str>) -> Self {
        match format {
            Some("semi_long" | "wide") => Self {
                format: OutputFormat::Wide,
                long_mode: LongMode::String,
            },
            Some("long_typed" | "typed") => Self {
                format: OutputFormat::Long,
                long_mode: LongMode::Typed,
            },
            Some("long_metadata" | "metadata" | "with_metadata") => Self {
                format: OutputFormat::Long,
                long_mode: LongMode::WithMetadata,
            },
            _ => Self {
                format: OutputFormat::Long,
                long_mode: LongMode::String,
            },
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RequestKind {
    RefData(PlannedOutput),
    HistData(PlannedOutput),
    BulkData,
    Generic,
    Bql,
    Bsrch,
    FieldInfo,
    IntradayBar,
    IntradayTick,
}

impl RequestKind {
    fn from_params(params: &RequestParams) -> Self {
        match params.extractor {
            ExtractorType::RefData => {
                Self::RefData(PlannedOutput::from_format(params.format.as_deref()))
            }
            ExtractorType::HistData => {
                Self::HistData(PlannedOutput::from_format(params.format.as_deref()))
            }
            ExtractorType::BulkData => Self::BulkData,
            ExtractorType::Generic => Self::Generic,
            ExtractorType::Bql => Self::Bql,
            ExtractorType::Bsrch => Self::Bsrch,
            ExtractorType::FieldInfo => Self::FieldInfo,
            ExtractorType::IntradayBar => Self::IntradayBar,
            ExtractorType::IntradayTick => Self::IntradayTick,
        }
    }
}

#[derive(Clone, Debug)]
pub struct PreparedRequest {
    params: RequestParams,
    kind: RequestKind,
}

impl PreparedRequest {
    pub fn prepare(
        mut params: RequestParams,
        schema_cache: &SchemaCache,
    ) -> Result<Self, BlpAsyncError> {
        apply_request_defaults(&mut params);
        validate_request_params(&params)?;
        route_request_params(&mut params, schema_cache);
        let kind = RequestKind::from_params(&params);
        Ok(Self { params, kind })
    }

    pub fn kind(&self) -> RequestKind {
        self.kind
    }

    pub fn params(&self) -> &RequestParams {
        &self.params
    }

    pub(crate) fn set_field_types(&mut self, field_types: HashMap<String, String>) {
        self.params.field_types = Some(field_types);
    }

    pub(crate) fn set_intraday_datetimes(&mut self, start_datetime: String, end_datetime: String) {
        self.params.start_datetime = Some(start_datetime);
        self.params.end_datetime = Some(end_datetime);
    }

    pub(crate) fn effective_operation(&self) -> &str {
        self.params.effective_operation()
    }

    pub(crate) fn is_excel_get_grid_request(&self) -> bool {
        self.params.is_excel_get_grid_request()
    }
}

pub(crate) fn apply_request_defaults(params: &mut RequestParams) {
    if !params.extractor_set && params.extractor == ExtractorType::default() {
        let operation = parse_operation_lossless(params.effective_operation());
        params.extractor = operation.default_extractor();
    }
}

pub(crate) fn validate_request_params(params: &RequestParams) -> Result<(), BlpAsyncError> {
    if params.service.is_empty() {
        return Err(BlpAsyncError::ConfigError {
            detail: "service is required".to_string(),
        });
    }

    let operation = parse_operation_lossless(&params.operation);
    if matches!(operation, Operation::RawRequest) {
        if params
            .request_operation
            .as_ref()
            .is_none_or(|operation| operation.is_empty())
        {
            return Err(BlpAsyncError::ConfigError {
                detail: "request_operation is required for RawRequest".to_string(),
            });
        }
    } else if params.operation.is_empty() {
        return Err(BlpAsyncError::ConfigError {
            detail: "operation is required".to_string(),
        });
    }

    match operation {
        Operation::ReferenceData => validate_reference_data(params),
        Operation::HistoricalData => validate_historical_data(params),
        Operation::IntradayBar => validate_intraday_bar(params),
        Operation::IntradayTick => validate_intraday_tick(params),
        Operation::FieldInfo | Operation::FieldSearch => validate_field_request(params, &operation),
        // Unknown/custom operations run in power-user mode.
        Operation::Beqs
        | Operation::PortfolioData
        | Operation::InstrumentList
        | Operation::CurveList
        | Operation::GovtList
        | Operation::BqlSendQuery
        | Operation::ExcelGetGrid
        | Operation::StudyRequest
        | Operation::RawRequest
        | Operation::Custom(_) => Ok(()),
    }
}

fn route_request_params(params: &mut RequestParams, schema_cache: &SchemaCache) {
    let kwargs = params.kwargs.take().unwrap_or_default();
    if params.is_excel_get_grid_request() {
        normalize_excel_grid_params(params, kwargs);
        return;
    }

    if params.is_raw_request() {
        merge_raw_kwargs_into_elements(params, kwargs);
        return;
    }

    let routed = RequestBuilder::route_kwargs(
        schema_cache,
        &params.service,
        &params.operation,
        kwargs,
        params.overrides.take(),
    );

    if !routed.elements.is_empty() {
        params
            .elements
            .get_or_insert_with(Vec::new)
            .extend(routed.elements);
    }

    params.overrides = if routed.overrides.is_empty() {
        None
    } else {
        Some(routed.overrides)
    };

    for warning in routed.warnings {
        xbbg_log::warn!(
            service = %params.service,
            operation = %params.operation,
            warning = %warning,
            "request parameter routing warning"
        );
    }
}

fn validate_reference_data(params: &RequestParams) -> Result<(), BlpAsyncError> {
    if !has_securities(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "securities is required for ReferenceDataRequest".to_string(),
        });
    }

    if !has_fields(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "fields is required for ReferenceDataRequest".to_string(),
        });
    }

    Ok(())
}

fn validate_historical_data(params: &RequestParams) -> Result<(), BlpAsyncError> {
    if !has_securities(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "securities is required for HistoricalDataRequest".to_string(),
        });
    }

    if !has_fields(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "fields is required for HistoricalDataRequest".to_string(),
        });
    }

    if !has_start_date(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "start_date is required for HistoricalDataRequest".to_string(),
        });
    }

    if !has_end_date(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "end_date is required for HistoricalDataRequest".to_string(),
        });
    }

    Ok(())
}

fn validate_intraday_bar(params: &RequestParams) -> Result<(), BlpAsyncError> {
    if !has_security(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "security is required for IntradayBarRequest".to_string(),
        });
    }

    if !has_event_type(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "event_type is required for IntradayBarRequest".to_string(),
        });
    }

    if params.interval.is_none() {
        return Err(BlpAsyncError::ConfigError {
            detail: "interval is required for IntradayBarRequest".to_string(),
        });
    }

    if !has_start_datetime(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "start_datetime is required for IntradayBarRequest".to_string(),
        });
    }

    if !has_end_datetime(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "end_datetime is required for IntradayBarRequest".to_string(),
        });
    }

    Ok(())
}

fn validate_intraday_tick(params: &RequestParams) -> Result<(), BlpAsyncError> {
    if !has_security(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "security is required for IntradayTickRequest".to_string(),
        });
    }

    if !has_start_datetime(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "start_datetime is required for IntradayTickRequest".to_string(),
        });
    }

    if !has_end_datetime(params) {
        return Err(BlpAsyncError::ConfigError {
            detail: "end_datetime is required for IntradayTickRequest".to_string(),
        });
    }

    Ok(())
}

fn validate_field_request(
    params: &RequestParams,
    operation: &Operation,
) -> Result<(), BlpAsyncError> {
    let has_fields = has_fields(params);

    match operation {
        Operation::FieldInfo => {
            let has_field_ids = params.field_ids.as_ref().is_some_and(|ids| !ids.is_empty());
            if !has_fields && !has_field_ids {
                return Err(BlpAsyncError::ConfigError {
                    detail: "fields is required for field metadata requests".to_string(),
                });
            }
        }
        Operation::FieldSearch => {
            let has_search_spec = params.search_spec.as_ref().is_some_and(|s| !s.is_empty());
            if !has_fields && !has_search_spec {
                return Err(BlpAsyncError::ConfigError {
                    detail: "fields is required for field metadata requests".to_string(),
                });
            }
        }
        _ => {}
    }

    Ok(())
}

fn has_securities(params: &RequestParams) -> bool {
    params
        .securities
        .as_ref()
        .is_some_and(|values| !values.is_empty())
}

fn has_security(params: &RequestParams) -> bool {
    params
        .security
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

fn has_fields(params: &RequestParams) -> bool {
    params
        .fields
        .as_ref()
        .is_some_and(|values| !values.is_empty())
}

fn has_start_date(params: &RequestParams) -> bool {
    params
        .start_date
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

fn has_end_date(params: &RequestParams) -> bool {
    params
        .end_date
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

fn has_start_datetime(params: &RequestParams) -> bool {
    params
        .start_datetime
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

fn has_end_datetime(params: &RequestParams) -> bool {
    params
        .end_datetime
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

fn has_event_type(params: &RequestParams) -> bool {
    params
        .event_type
        .as_ref()
        .is_some_and(|value| !value.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    use crate::schema::SchemaCache;
    use crate::services::{Operation, Service};

    fn empty_schema() -> SchemaCache {
        SchemaCache::new()
    }

    fn refdata_params() -> RequestParams {
        RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::ReferenceData.to_string(),
            securities: Some(vec!["AAPL US Equity".to_string()]),
            fields: Some(vec!["PX_LAST".to_string()]),
            ..Default::default()
        }
    }

    #[test]
    fn prepares_reference_data_defaults_and_preserves_flags() {
        let mut field_types = HashMap::new();
        field_types.insert("PX_LAST".to_string(), "Float64".to_string());
        let params = RequestParams {
            include_security_errors: true,
            field_types: Some(field_types.clone()),
            format: Some("long_typed".to_string()),
            validate_fields: Some(false),
            ..refdata_params()
        };

        let prepared = PreparedRequest::prepare(params, &empty_schema()).unwrap();

        assert!(matches!(
            prepared.kind(),
            RequestKind::RefData(PlannedOutput {
                format: OutputFormat::Long,
                long_mode: LongMode::Typed,
            })
        ));
        let params = prepared.params();
        assert_eq!(params.extractor, ExtractorType::RefData);
        assert!(params.include_security_errors);
        assert_eq!(params.field_types.as_ref(), Some(&field_types));
        assert_eq!(params.format.as_deref(), Some("long_typed"));
        assert_eq!(params.validate_fields, Some(false));
    }

    #[test]
    fn reference_data_requires_service_securities_and_fields() {
        let mut params = refdata_params();
        params.service.clear();
        assert!(validate_request_params(&params).is_err());

        let mut params = refdata_params();
        params.securities = None;
        assert!(validate_request_params(&params).is_err());

        let mut params = refdata_params();
        params.fields = Some(Vec::new());
        assert!(validate_request_params(&params).is_err());
    }

    #[test]
    fn prepares_historical_formats_with_current_output_semantics() {
        for (format, expected) in [
            ("long", (OutputFormat::Long, LongMode::String)),
            ("long_typed", (OutputFormat::Long, LongMode::Typed)),
            (
                "long_metadata",
                (OutputFormat::Long, LongMode::WithMetadata),
            ),
            ("wide", (OutputFormat::Wide, LongMode::String)),
            ("semi_long", (OutputFormat::Wide, LongMode::String)),
        ] {
            let params = RequestParams {
                service: Service::RefData.to_string(),
                operation: Operation::HistoricalData.to_string(),
                securities: Some(vec!["AAPL US Equity".to_string()]),
                fields: Some(vec!["PX_LAST".to_string()]),
                start_date: Some("20240101".to_string()),
                end_date: Some("20240131".to_string()),
                format: Some(format.to_string()),
                ..Default::default()
            };

            let prepared = PreparedRequest::prepare(params, &empty_schema()).unwrap();
            assert_eq!(
                prepared.kind(),
                RequestKind::HistData(PlannedOutput {
                    format: expected.0,
                    long_mode: expected.1,
                })
            );
        }
    }

    #[test]
    fn prepares_intraday_bar_and_tick_inputs() {
        let bar = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::IntradayBar.to_string(),
            security: Some("AAPL US Equity".to_string()),
            event_type: Some("TRADE".to_string()),
            interval: Some(5),
            start_datetime: Some("2024-01-01T09:30:00".to_string()),
            end_datetime: Some("2024-01-01T10:00:00".to_string()),
            request_tz: Some("NY".to_string()),
            output_tz: Some("UTC".to_string()),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(bar, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::IntradayBar);
        assert_eq!(prepared.params().request_tz.as_deref(), Some("NY"));
        assert_eq!(prepared.params().output_tz.as_deref(), Some("UTC"));

        let tick = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::IntradayTick.to_string(),
            security: Some("AAPL US Equity".to_string()),
            event_types: Some(vec!["TRADE".to_string(), "BID".to_string()]),
            start_datetime: Some("2024-01-01T09:30:00".to_string()),
            end_datetime: Some("2024-01-01T10:00:00".to_string()),
            options: Some(vec![(
                "includeConditionCodes".to_string(),
                "true".to_string(),
            )]),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(tick, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::IntradayTick);
        assert_eq!(
            prepared.params().event_types.as_ref().unwrap(),
            &["TRADE".to_string(), "BID".to_string()]
        );
        assert_eq!(
            prepared.params().options.as_ref().unwrap(),
            &[("includeConditionCodes".to_string(), "true".to_string())]
        );
    }

    #[test]
    fn prepares_field_info_and_search_alias_inputs() {
        let info = RequestParams {
            service: Service::ApiFlds.to_string(),
            operation: Operation::FieldInfo.to_string(),
            field_ids: Some(vec!["PX_LAST".to_string()]),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(info, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::FieldInfo);
        assert_eq!(
            prepared.params().field_ids.as_ref().unwrap(),
            &["PX_LAST".to_string()]
        );

        let search = RequestParams {
            service: Service::ApiFlds.to_string(),
            operation: Operation::FieldSearch.to_string(),
            search_spec: Some("price".to_string()),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(search, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::Generic);
        assert_eq!(prepared.params().search_spec.as_deref(), Some("price"));

        let invalid = RequestParams {
            service: Service::ApiFlds.to_string(),
            operation: Operation::FieldSearch.to_string(),
            ..Default::default()
        };
        assert!(PreparedRequest::prepare(invalid, &empty_schema()).is_err());
    }

    #[test]
    fn raw_request_requires_and_preserves_effective_operation() {
        let invalid = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::RawRequest.to_string(),
            ..Default::default()
        };
        assert!(PreparedRequest::prepare(invalid, &empty_schema()).is_err());

        let valid = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::RawRequest.to_string(),
            request_operation: Some(Operation::ReferenceData.to_string()),
            kwargs: Some(HashMap::from([("rawElement".to_string(), "1".to_string())])),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(valid, &empty_schema()).unwrap();
        assert_eq!(
            prepared.effective_operation(),
            Operation::ReferenceData.to_string()
        );
        assert!(matches!(prepared.kind(), RequestKind::RefData(_)));
        assert_eq!(
            prepared.params().elements.as_ref().unwrap(),
            &[("rawElement".to_string(), "1".to_string())]
        );
    }

    #[test]
    fn prepares_bql_and_excel_grid_routing() {
        let bql = RequestParams {
            service: Service::BqlSvc.to_string(),
            operation: Operation::BqlSendQuery.to_string(),
            elements: Some(vec![("expression".to_string(), "get(px_last)".to_string())]),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(bql, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::Bql);
        assert_eq!(
            prepared.params().elements.as_ref().unwrap(),
            &[("expression".to_string(), "get(px_last)".to_string())]
        );

        let grid = RequestParams {
            service: Service::ExrSvc.to_string(),
            operation: Operation::ExcelGetGrid.to_string(),
            elements: Some(vec![("Domain".to_string(), "FI".to_string())]),
            kwargs: Some(HashMap::from([("Ticker".to_string(), "IBM".to_string())])),
            ..Default::default()
        };
        let prepared = PreparedRequest::prepare(grid, &empty_schema()).unwrap();
        assert_eq!(prepared.kind(), RequestKind::Bsrch);
        assert_eq!(
            prepared.params().elements.as_ref().unwrap(),
            &[("Domain".to_string(), "FI".to_string())]
        );
        assert_eq!(
            prepared.params().overrides.as_ref().unwrap(),
            &[("Ticker".to_string(), "IBM".to_string())]
        );
    }
}
