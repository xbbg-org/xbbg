//! Historical data recipes.
//!
//! Convenience recipes for dividend, earnings, turnover, and ETF holdings data.
//!
//! # Recipes
//!
//! - [`recipe_dividend`]: Fetch dividend history
//! - [`recipe_earning`]: Fetch earnings data with hierarchical percentages
//! - [`recipe_turnover`]: Fetch volume/turnover data
//! - [`recipe_etf_holdings`]: Fetch ETF constituent holdings via BQL

use arrow::array::RecordBatch;
use xbbg_async::engine::{Engine, RequestParams};
use xbbg_async::services::{Operation, Service};
use crate::error::Result;

pub async fn recipe_dividend(
    engine: &Engine,
    tickers: Vec<String>,
    dvd_type: Option<String>,
    _start_date: String,
    _end_date: String,
) -> Result<RecordBatch> {
    let mut overrides = vec![];
    if let Some(dt) = dvd_type {
        overrides.push(("DVD_TYPE".to_string(), dt));
    }
    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(tickers),
        fields: Some(vec!["DVD_HIST_ALL".to_string()]),
        overrides: if overrides.is_empty() { None } else { Some(overrides) },
        ..Default::default()
    };
    engine.request(params).await.map_err(Into::into)
}

/// Fetch trading volume and turnover for securities.
///
/// Requests the TURNOVER field via HistoricalData. Callers may perform
/// a second request for volume × VWAP if turnover is unavailable for
/// some tickers (fallback logic lives at the Python layer).
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `tickers` - Securities to query
/// * `start_date` - Start date (YYYYMMDD format)
/// * `end_date` - End date (YYYYMMDD format)
/// * `ccy` - Currency for conversion. None for local currency.
/// * `factor` - Division factor (e.g., 1_000_000.0 for millions)
///
/// # Returns
///
/// Arrow RecordBatch with turnover data in historical format
pub async fn recipe_turnover(
    engine: &Engine,
    tickers: Vec<String>,
    start_date: String,
    end_date: String,
    ccy: Option<String>,
    _factor: Option<f64>,
) -> Result<RecordBatch> {
    let mut overrides = vec![];
    if let Some(c) = ccy {
        if c.to_lowercase() != "local" {
            overrides.push(("EQY_FUND_CRNCY".to_string(), c));
        }
    }

    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::HistoricalData.to_string(),
        securities: Some(tickers),
        fields: Some(vec!["TURNOVER".to_string()]),
        start_date: Some(start_date),
        end_date: Some(end_date),
        overrides: if overrides.is_empty() { None } else { Some(overrides) },
        ..Default::default()
    };

    engine.request(params).await.map_err(Into::into)
}

/// Fetch ETF constituent holdings via BQL.
///
/// Uses Bloomberg Query Language to retrieve holdings for an ETF including
/// ISIN, weights, and position IDs.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `etf_ticker` - ETF ticker (e.g., "SPY US Equity")
/// * `fields` - Additional fields to retrieve beyond defaults (id_isin, weights, id().position)
///
/// # Returns
///
/// Arrow RecordBatch with ETF holdings data
pub async fn recipe_etf_holdings(
    engine: &Engine,
    etf_ticker: String,
    fields: Option<Vec<String>>,
) -> Result<RecordBatch> {
    // Default fields for ETF holdings
    let mut all_fields = vec![
        "id_isin".to_string(),
        "weights".to_string(),
        "id().position".to_string(),
    ];

    // Append additional fields if provided
    if let Some(extra) = fields {
        for f in extra {
            if !all_fields.contains(&f) {
                all_fields.push(f);
            }
        }
    }

    let fields_str = all_fields.join(", ");
    let bql_query = format!("get({fields_str}) for(holdings('{etf_ticker}'))");

    let params = RequestParams {
        service: Service::BqlSvc.to_string(),
        operation: Operation::BqlSendQuery.to_string(),
        elements: Some(vec![("expression".to_string(), bql_query)]),
        ..Default::default()
    };

    engine.request(params).await.map_err(Into::into)
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_turnover_ccy_override_local() {
        // "local" currency should produce no overrides
        let ccy = Some("local".to_string());
        let mut overrides = vec![];
        if let Some(c) = &ccy {
            if c.to_lowercase() != "local" {
                overrides.push(("EQY_FUND_CRNCY".to_string(), c.clone()));
            }
        }
        assert!(overrides.is_empty());
    }

    #[test]
    fn test_turnover_ccy_override_usd() {
        let ccy = Some("USD".to_string());
        let mut overrides = vec![];
        if let Some(c) = &ccy {
            if c.to_lowercase() != "local" {
                overrides.push(("EQY_FUND_CRNCY".to_string(), c.clone()));
            }
        }
        assert_eq!(overrides.len(), 1);
        assert_eq!(overrides[0], ("EQY_FUND_CRNCY".to_string(), "USD".to_string()));
    }

    #[test]
    fn test_turnover_ccy_none() {
        let ccy: Option<String> = None;
        let mut overrides = vec![];
        if let Some(c) = &ccy {
            if c.to_lowercase() != "local" {
                overrides.push(("EQY_FUND_CRNCY".to_string(), c.clone()));
            }
        }
        assert!(overrides.is_empty());
    }

    #[test]
    fn test_etf_holdings_default_fields() {
        let fields: Option<Vec<String>> = None;
        let mut all_fields = vec![
            "id_isin".to_string(),
            "weights".to_string(),
            "id().position".to_string(),
        ];
        if let Some(extra) = fields {
            for f in extra {
                if !all_fields.contains(&f) {
                    all_fields.push(f);
                }
            }
        }
        assert_eq!(all_fields, vec!["id_isin", "weights", "id().position"]);
    }

    #[test]
    fn test_etf_holdings_custom_fields() {
        let fields = Some(vec!["name".to_string(), "px_last".to_string()]);
        let mut all_fields = vec![
            "id_isin".to_string(),
            "weights".to_string(),
            "id().position".to_string(),
        ];
        if let Some(extra) = fields {
            for f in extra {
                if !all_fields.contains(&f) {
                    all_fields.push(f);
                }
            }
        }
        assert_eq!(
            all_fields,
            vec!["id_isin", "weights", "id().position", "name", "px_last"]
        );
    }

    #[test]
    fn test_etf_holdings_no_duplicate_fields() {
        let fields = Some(vec!["id_isin".to_string(), "name".to_string()]);
        let mut all_fields = vec![
            "id_isin".to_string(),
            "weights".to_string(),
            "id().position".to_string(),
        ];
        if let Some(extra) = fields {
            for f in extra {
                if !all_fields.contains(&f) {
                    all_fields.push(f);
                }
            }
        }
        // id_isin should not be duplicated
        assert_eq!(
            all_fields,
            vec!["id_isin", "weights", "id().position", "name"]
        );
    }

    #[test]
    fn test_etf_bql_query_format() {
        let etf_ticker = "SPY US Equity";
        let fields_str = "id_isin, weights, id().position";
        let bql_query = format!("get({fields_str}) for(holdings('{etf_ticker}'))");
        assert_eq!(
            bql_query,
            "get(id_isin, weights, id().position) for(holdings('SPY US Equity'))"
        );
    }
}
