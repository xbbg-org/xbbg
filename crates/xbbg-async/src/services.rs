//! Bloomberg service definitions and request parameters.
//!
//! Canonical enums for Bloomberg services, operations, and output formats.
//! All enums include a Custom(String) variant for forward compatibility.

use std::convert::Infallible;
use std::fmt;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::engine::ExtractorType;

/// Bloomberg service URIs.
///
/// Standard Bloomberg API services with URIs from the Bloomberg C++ SDK.
/// Use [Service::Custom] for services not listed here.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Service {
    /// Reference data service (//blp/refdata) for bdp, bdh, bds, bdib, bdtick, beqs, bport.
    RefData,
    /// Real-time market data subscriptions (//blp/mktdata).
    MktData,
    /// Field metadata service (//blp/apiflds) for field info and search.
    ApiFlds,
    /// Instruments service (//blp/instruments) for security lookup.
    Instruments,
    /// Bloomberg Query Language service (//blp/bqlsvc).
    BqlSvc,
    /// Excel/Search service (//blp/exrsvc) for Bloomberg searches.
    ExrSvc,
    /// Technical Analysis service (//blp/tasvc) for study calculations.
    TaSvc,
    /// Real-time VWAP subscription service (//blp/mktvwap).
    MktVwap,
    /// Real-time streaming OHLC bars (//blp/mktbar).
    MktBar,
    /// Level 2 market depth / order book data (//blp/mktdepthdata). Requires B-PIPE.
    MktDepth,
    /// Option chains and futures chains (//blp/mktlist). Requires B-PIPE.
    MktList,
    /// Custom service URI not listed above.
    Custom(String),
}

impl Service {
    /// Returns the Bloomberg service URI string.
    pub fn as_str(&self) -> &str {
        match self {
            Self::RefData => "//blp/refdata",
            Self::MktData => "//blp/mktdata",
            Self::ApiFlds => "//blp/apiflds",
            Self::Instruments => "//blp/instruments",
            Self::BqlSvc => "//blp/bqlsvc",
            Self::ExrSvc => "//blp/exrsvc",
            Self::TaSvc => "//blp/tasvc",
            Self::MktVwap => "//blp/mktvwap",
            Self::MktBar => "//blp/mktbar",
            Self::MktDepth => "//blp/mktdepthdata",
            Self::MktList => "//blp/mktlist",
            Self::Custom(s) => s.as_str(),
        }
    }
}

impl fmt::Display for Service {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for Service {
    type Err = Infallible;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let svc = match s {
            "//blp/refdata" => Self::RefData,
            "//blp/mktdata" => Self::MktData,
            "//blp/apiflds" => Self::ApiFlds,
            "//blp/instruments" => Self::Instruments,
            "//blp/bqlsvc" => Self::BqlSvc,
            "//blp/exrsvc" => Self::ExrSvc,
            "//blp/tasvc" => Self::TaSvc,
            "//blp/mktvwap" => Self::MktVwap,
            "//blp/mktbar" => Self::MktBar,
            "//blp/mktdepthdata" => Self::MktDepth,
            "//blp/mktlist" => Self::MktList,
            other => Self::Custom(other.to_string()),
        };
        Ok(svc)
    }
}

impl Serialize for Service {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(self.as_str())
    }
}

impl<'de> Deserialize<'de> for Service {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        Ok(Self::from_str(&s).unwrap()) // Infallible
    }
}

/// Bloomberg request operation names.
///
/// Standard Bloomberg API operation types from the Bloomberg C++ SDK.
/// Use [Operation::Custom] for operations not listed here.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Operation {
    /// Single point-in-time data (ReferenceDataRequest).
    ReferenceData,
    /// Historical time series data (HistoricalDataRequest).
    HistoricalData,
    /// Intraday OHLCV bars (IntradayBarRequest).
    IntradayBar,
    /// Intraday tick data (IntradayTickRequest).
    IntradayTick,
    /// Get field metadata (FieldInfoRequest).
    FieldInfo,
    /// Search for fields by keyword (FieldSearchRequest).
    FieldSearch,
    /// Bloomberg Equity Screening (BeqsRequest).
    Beqs,
    /// Portfolio data request (PortfolioDataRequest).
    PortfolioData,
    /// Security lookup by name (instrumentListRequest).
    InstrumentList,
    /// List yield curves (curveListRequest).
    CurveList,
    /// List government securities (govtListRequest).
    GovtList,
    /// Bloomberg Query Language query (sendQuery).
    BqlSendQuery,
    /// Bloomberg Search/Excel grid request (ExcelGetGridRequest).
    ExcelGetGrid,
    /// Technical analysis study request (studyRequest).
    StudyRequest,
    /// Raw session.sendRequest() call (no operation name needed).
    RawRequest,
    /// Custom operation name not listed above.
    Custom(String),
}

impl Operation {
    /// Returns the Bloomberg operation name string.
    pub fn as_str(&self) -> &str {
        match self {
            Self::ReferenceData => "ReferenceDataRequest",
            Self::HistoricalData => "HistoricalDataRequest",
            Self::IntradayBar => "IntradayBarRequest",
            Self::IntradayTick => "IntradayTickRequest",
            Self::FieldInfo => "FieldInfoRequest",
            Self::FieldSearch => "FieldSearchRequest",
            Self::Beqs => "BeqsRequest",
            Self::PortfolioData => "PortfolioDataRequest",
            Self::InstrumentList => "instrumentListRequest",
            Self::CurveList => "curveListRequest",
            Self::GovtList => "govtListRequest",
            Self::BqlSendQuery => "sendQuery",
            Self::ExcelGetGrid => "ExcelGetGridRequest",
            Self::StudyRequest => "studyRequest",
            Self::RawRequest => "",
            Self::Custom(s) => s.as_str(),
        }
    }

    /// Returns the default extractor for this operation.
    pub fn default_extractor(&self) -> ExtractorType {
        match self {
            Self::ReferenceData => ExtractorType::RefData,
            Self::HistoricalData => ExtractorType::HistData,
            Self::IntradayBar => ExtractorType::IntradayBar,
            Self::IntradayTick => ExtractorType::IntradayTick,
            Self::FieldInfo => ExtractorType::FieldInfo,
            Self::BqlSendQuery => ExtractorType::Bql,
            Self::ExcelGetGrid => ExtractorType::Bsrch,
            // All others default to Generic
            Self::FieldSearch | Self::Beqs | Self::PortfolioData
            | Self::InstrumentList | Self::CurveList | Self::GovtList
            | Self::StudyRequest | Self::RawRequest | Self::Custom(_) => ExtractorType::Generic,
        }
    }

    /// Returns the default service for this operation, if known.
    pub fn default_service(&self) -> Option<Service> {
        match self {
            Self::ReferenceData | Self::HistoricalData | Self::IntradayBar
            | Self::IntradayTick | Self::Beqs | Self::PortfolioData => Some(Service::RefData),
            Self::FieldInfo | Self::FieldSearch => Some(Service::ApiFlds),
            Self::InstrumentList | Self::CurveList | Self::GovtList => Some(Service::Instruments),
            Self::BqlSendQuery => Some(Service::BqlSvc),
            Self::ExcelGetGrid => Some(Service::ExrSvc),
            Self::StudyRequest => Some(Service::TaSvc),
            Self::RawRequest | Self::Custom(_) => None,
        }
    }
}

impl fmt::Display for Operation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for Operation {
    type Err = Infallible;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let op = match s {
            "ReferenceDataRequest" => Self::ReferenceData,
            "HistoricalDataRequest" => Self::HistoricalData,
            "IntradayBarRequest" => Self::IntradayBar,
            "IntradayTickRequest" => Self::IntradayTick,
            "FieldInfoRequest" => Self::FieldInfo,
            "FieldSearchRequest" => Self::FieldSearch,
            "BeqsRequest" => Self::Beqs,
            "PortfolioDataRequest" => Self::PortfolioData,
            "instrumentListRequest" => Self::InstrumentList,
            "curveListRequest" => Self::CurveList,
            "govtListRequest" => Self::GovtList,
            "sendQuery" => Self::BqlSendQuery,
            "ExcelGetGridRequest" => Self::ExcelGetGrid,
            "studyRequest" => Self::StudyRequest,
            "" => Self::RawRequest,
            other => Self::Custom(other.to_string()),
        };
        Ok(op)
    }
}

impl Serialize for Operation {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(self.as_str())
    }
}

impl<'de> Deserialize<'de> for Operation {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        Ok(Self::from_str(&s).unwrap()) // Infallible
    }
}

/// Output format for reference data (bdp/bdh).
///
/// Controls the shape and typing of the output Arrow table.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Format {
    /// Long format with all values as strings (default, backwards-compatible).
    #[default]
    Long,
    /// Long format with typed value columns.
    LongTyped,
    /// Long format with string values and dtype metadata column.
    LongWithMetadata,
    /// Wide format with fields as columns (DEPRECATED).
    Wide,
}

impl Format {
    /// Returns the format identifier string.
    pub fn as_str(&self) -> &str {
        match self {
            Self::Long => "long",
            Self::LongTyped => "long_typed",
            Self::LongWithMetadata => "long_metadata",
            Self::Wide => "wide",
        }
    }
}

impl fmt::Display for Format {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for Format {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "long" => Ok(Self::Long),
            "long_typed" => Ok(Self::LongTyped),
            "long_metadata" => Ok(Self::LongWithMetadata),
            "wide" => Ok(Self::Wide),
            other => Err(format!("Unknown format: {}", other)),
        }
    }
}

/// Output mode for generic requests.
///
/// Controls how Bloomberg responses are converted before returning.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OutputMode {
    /// Convert to Arrow RecordBatch using appropriate extractor.
    #[default]
    Arrow,
    /// Return raw JSON as a single-column Arrow table.
    Json,
}

impl OutputMode {
    /// Returns the output mode identifier string.
    pub fn as_str(&self) -> &str {
        match self {
            Self::Arrow => "arrow",
            Self::Json => "json",
        }
    }
}

impl fmt::Display for OutputMode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for OutputMode {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "arrow" => Ok(Self::Arrow),
            "json" => Ok(Self::Json),
            other => Err(format!("Unknown output mode: {}", other)),
        }
    }
}

// ============================================================================
// Deprecated aliases for backwards compatibility
// ============================================================================

/// Reference data service (bdp, bdh, bds).
#[deprecated(since = "1.0.0", note = "Use Service::RefData instead")]
pub const REFDATA: &str = "//blp/refdata";

/// Real-time market data service (subscriptions).
#[deprecated(since = "1.0.0", note = "Use Service::MktData instead")]
pub const MKTDATA: &str = "//blp/mktdata";

/// API field info service (field metadata, validation).
#[deprecated(since = "1.0.0", note = "Use Service::ApiFlds instead")]
pub const APIFLDS: &str = "//blp/apiflds";

// ============================================================================
// Unit tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // ========================================================================
    // Service tests
    // ========================================================================

    #[test]
    fn service_roundtrip() {
        assert_eq!(Service::from_str("//blp/refdata").unwrap(), Service::RefData);
        assert_eq!(Service::RefData.as_str(), "//blp/refdata");
        assert_eq!(Service::RefData.to_string(), "//blp/refdata");
    }

    #[test]
    fn service_custom() {
        let custom = Service::from_str("//blp/custom").unwrap();
        assert_eq!(custom, Service::Custom("//blp/custom".to_string()));
        assert_eq!(custom.as_str(), "//blp/custom");
    }

    #[test]
    fn service_all_known() {
        for (uri, expected) in [
            ("//blp/refdata", Service::RefData),
            ("//blp/mktdata", Service::MktData),
            ("//blp/apiflds", Service::ApiFlds),
            ("//blp/instruments", Service::Instruments),
            ("//blp/bqlsvc", Service::BqlSvc),
            ("//blp/exrsvc", Service::ExrSvc),
            ("//blp/tasvc", Service::TaSvc),
            ("//blp/mktvwap", Service::MktVwap),
            ("//blp/mktbar", Service::MktBar),
            ("//blp/mktdepthdata", Service::MktDepth),
            ("//blp/mktlist", Service::MktList),
        ] {
            assert_eq!(Service::from_str(uri).unwrap(), expected);
            assert_eq!(expected.as_str(), uri);
        }
    }

    #[test]
    fn service_serde() {
        let svc = Service::RefData;
        let json = serde_json::to_string(&svc).unwrap();
        assert_eq!(json, r#""//blp/refdata""#);
        let back: Service = serde_json::from_str(&json).unwrap();
        assert_eq!(back, Service::RefData);
    }

    // ========================================================================
    // Operation tests
    // ========================================================================

    #[test]
    fn operation_roundtrip() {
        assert_eq!(
            Operation::from_str("ReferenceDataRequest").unwrap(),
            Operation::ReferenceData
        );
        assert_eq!(Operation::ReferenceData.as_str(), "ReferenceDataRequest");
        assert_eq!(Operation::ReferenceData.to_string(), "ReferenceDataRequest");
    }

    #[test]
    fn operation_custom() {
        let custom = Operation::from_str("CustomRequest").unwrap();
        assert_eq!(custom, Operation::Custom("CustomRequest".to_string()));
        assert_eq!(custom.as_str(), "CustomRequest");
    }

    #[test]
    fn operation_lowercase_operations() {
        // Test lowercase operations from Bloomberg (instrumentListRequest, etc.)
        assert_eq!(
            Operation::from_str("instrumentListRequest").unwrap(),
            Operation::InstrumentList
        );
        assert_eq!(Operation::InstrumentList.as_str(), "instrumentListRequest");

        assert_eq!(
            Operation::from_str("curveListRequest").unwrap(),
            Operation::CurveList
        );
        assert_eq!(Operation::CurveList.as_str(), "curveListRequest");

        assert_eq!(
            Operation::from_str("govtListRequest").unwrap(),
            Operation::GovtList
        );
        assert_eq!(Operation::GovtList.as_str(), "govtListRequest");

        assert_eq!(Operation::from_str("sendQuery").unwrap(), Operation::BqlSendQuery);
        assert_eq!(Operation::BqlSendQuery.as_str(), "sendQuery");

        assert_eq!(
            Operation::from_str("studyRequest").unwrap(),
            Operation::StudyRequest
        );
        assert_eq!(Operation::StudyRequest.as_str(), "studyRequest");
    }

    #[test]
    fn operation_default_extractor() {
        assert_eq!(
            Operation::ReferenceData.default_extractor(),
            ExtractorType::RefData
        );
        assert_eq!(
            Operation::HistoricalData.default_extractor(),
            ExtractorType::HistData
        );
        assert_eq!(
            Operation::IntradayBar.default_extractor(),
            ExtractorType::IntradayBar
        );
        assert_eq!(
            Operation::IntradayTick.default_extractor(),
            ExtractorType::IntradayTick
        );
        assert_eq!(Operation::FieldInfo.default_extractor(), ExtractorType::FieldInfo);
        assert_eq!(Operation::BqlSendQuery.default_extractor(), ExtractorType::Bql);
        assert_eq!(Operation::ExcelGetGrid.default_extractor(), ExtractorType::Bsrch);
        assert_eq!(Operation::FieldSearch.default_extractor(), ExtractorType::Generic);
        assert_eq!(Operation::Beqs.default_extractor(), ExtractorType::Generic);
        assert_eq!(
            Operation::Custom("foo".into()).default_extractor(),
            ExtractorType::Generic
        );
    }

    #[test]
    fn operation_default_service() {
        assert_eq!(
            Operation::ReferenceData.default_service(),
            Some(Service::RefData)
        );
        assert_eq!(
            Operation::FieldInfo.default_service(),
            Some(Service::ApiFlds)
        );
        assert_eq!(
            Operation::InstrumentList.default_service(),
            Some(Service::Instruments)
        );
        assert_eq!(
            Operation::BqlSendQuery.default_service(),
            Some(Service::BqlSvc)
        );
        assert_eq!(Operation::RawRequest.default_service(), None);
        assert_eq!(Operation::Custom("foo".into()).default_service(), None);
    }

    #[test]
    fn operation_serde() {
        let op = Operation::HistoricalData;
        let json = serde_json::to_string(&op).unwrap();
        assert_eq!(json, r#""HistoricalDataRequest""#);
        let back: Operation = serde_json::from_str(&json).unwrap();
        assert_eq!(back, Operation::HistoricalData);
    }

    // ========================================================================
    // Format tests
    // ========================================================================

    #[test]
    fn format_roundtrip() {
        assert_eq!(Format::from_str("long").unwrap(), Format::Long);
        assert_eq!(Format::Long.as_str(), "long");
        assert_eq!(Format::Long.to_string(), "long");
    }

    #[test]
    fn format_all_variants() {
        for (s, expected) in [
            ("long", Format::Long),
            ("long_typed", Format::LongTyped),
            ("long_metadata", Format::LongWithMetadata),
            ("wide", Format::Wide),
        ] {
            assert_eq!(Format::from_str(s).unwrap(), expected);
            assert_eq!(expected.as_str(), s);
        }
    }

    #[test]
    fn format_invalid() {
        assert!(Format::from_str("invalid").is_err());
    }

    #[test]
    fn format_serde() {
        let fmt = Format::LongTyped;
        let json = serde_json::to_string(&fmt).unwrap();
        assert_eq!(json, r#""long_typed""#);
        let back: Format = serde_json::from_str(&json).unwrap();
        assert_eq!(back, Format::LongTyped);
    }

    // ========================================================================
    // OutputMode tests
    // ========================================================================

    #[test]
    fn output_mode_roundtrip() {
        assert_eq!(OutputMode::from_str("arrow").unwrap(), OutputMode::Arrow);
        assert_eq!(OutputMode::Arrow.as_str(), "arrow");
        assert_eq!(OutputMode::Arrow.to_string(), "arrow");
    }

    #[test]
    fn output_mode_all_variants() {
        for (s, expected) in [("arrow", OutputMode::Arrow), ("json", OutputMode::Json)] {
            assert_eq!(OutputMode::from_str(s).unwrap(), expected);
            assert_eq!(expected.as_str(), s);
        }
    }

    #[test]
    fn output_mode_invalid() {
        assert!(OutputMode::from_str("invalid").is_err());
    }

    #[test]
    fn output_mode_serde() {
        let mode = OutputMode::Json;
        let json = serde_json::to_string(&mode).unwrap();
        assert_eq!(json, r#""json""#);
        let back: OutputMode = serde_json::from_str(&json).unwrap();
        assert_eq!(back, OutputMode::Json);
    }
}
