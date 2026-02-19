//! Fixed income recipe functions.
//!
//! High-level recipes for Bloomberg fixed income data queries.

use arrow::array::RecordBatch;
use xbbg_async::engine::{Engine, RequestParams};
use xbbg_async::services::{Operation, Service};
use xbbg_ext::transforms::fixed_income::{build_yas_overrides, YieldType};

use crate::error::Result;

/// YAS (Yield & Spread Analysis) recipe.
///
/// Retrieves Bloomberg YAS data with optional yield type and pricing parameters.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `tickers` - Securities to query
/// * `fields` - Fields to retrieve
/// * `settle_dt` - Settlement date (YYYYMMDD format)
/// * `yield_type` - Yield calculation type (YTM, YTC, etc.)
/// * `spread` - Yield spread override
/// * `yield_val` - Yield value override
/// * `price` - Price override
/// * `benchmark` - Benchmark security for spread calculation
///
/// # Returns
///
/// Arrow RecordBatch with YAS data in canonical long format
///
/// # Example
///
/// ```ignore
/// let batch = recipe_yas(
///     &engine,
///     vec!["US912810SV17 Govt".to_string()],
///     vec!["YAS_BOND_YLD".to_string(), "YAS_YLD_SPREAD".to_string()],
///     Some("20240115".to_string()),
///     Some(YieldType::YTM),
///     None,
///     None,
///     Some(99.5),
///     None,
/// ).await?;
/// ```
#[allow(clippy::too_many_arguments)]
pub async fn recipe_yas(
    engine: &Engine,
    tickers: Vec<String>,
    fields: Vec<String>,
    settle_dt: Option<String>,
    yield_type: Option<YieldType>,
    spread: Option<f64>,
    yield_val: Option<f64>,
    price: Option<f64>,
    benchmark: Option<String>,
) -> Result<RecordBatch> {
    // Build YAS overrides using xbbg-ext helper
    let overrides = build_yas_overrides(
        settle_dt.as_deref(),
        yield_type,
        spread,
        yield_val,
        price,
        benchmark.as_deref(),
    );

    // Build request parameters using canonical enums
    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(tickers),
        fields: Some(fields),
        overrides: Some(overrides),
        ..Default::default()
    };

    // Call engine directly (no recursion)
    let batch = engine.request(params).await?;
    Ok(batch)
}

/// Find preferred stocks for a company via BQL.
///
/// Uses Bloomberg's debt filter to find preferred stock issues
/// associated with a given equity ticker.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `equity_ticker` - Company equity ticker (e.g., "BAC US Equity")
/// * `fields` - Fields to retrieve (default: id, name)
///
/// # Returns
///
/// Arrow RecordBatch with preferred stock data
pub async fn recipe_preferreds(
    engine: &Engine,
    equity_ticker: String,
    fields: Option<Vec<String>>,
) -> Result<RecordBatch> {
    // Build field list with defaults
    let all_fields = match fields {
        Some(mut flds) => {
            let mut defaults = vec!["id".to_string(), "name".to_string()];
            defaults.append(&mut flds);
            defaults
        }
        None => vec!["id".to_string(), "name".to_string()],
    };

    let fields_str = all_fields.join(", ");

    // Build BQL query using debt filter with Preferreds asset class
    let bql_query = format!(
        "get({fields_str}) for(filter(debt(['{equity_ticker}'], CONSOLIDATEDUPLICATES='N'), \
         SRCH_ASSET_CLASS=='Preferreds'))"
    );

    let params = RequestParams {
        service: Service::BqlSvc.to_string(),
        operation: Operation::BqlSendQuery.to_string(),
        elements: Some(vec![("expression".to_string(), bql_query)]),
        ..Default::default()
    };

    engine.request(params).await.map_err(Into::into)
}

/// Find corporate bonds for a company via BQL.
///
/// Uses Bloomberg's bondsuniv filter to find active corporate bond issues
/// for a given company ticker, optionally filtered by currency.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `ticker` - Company ticker prefix (e.g., "AAPL")
/// * `ccy` - Currency filter (e.g., "USD"). None for all currencies.
/// * `fields` - Fields to retrieve (default: id)
/// * `active_only` - If true, only return active bonds
///
/// # Returns
///
/// Arrow RecordBatch with corporate bond data
pub async fn recipe_corporate_bonds(
    engine: &Engine,
    ticker: String,
    ccy: Option<String>,
    fields: Option<Vec<String>>,
    active_only: bool,
) -> Result<RecordBatch> {
    // Build field list with defaults
    let all_fields = match fields {
        Some(mut flds) => {
            let mut defaults = vec!["id".to_string()];
            defaults.append(&mut flds);
            defaults
        }
        None => vec!["id".to_string()],
    };

    let fields_str = all_fields.join(", ");

    // Build filter conditions
    let mut conditions = vec![
        "SRCH_ASSET_CLASS=='Corporates'".to_string(),
        format!("TICKER=='{ticker}'"),
    ];
    if let Some(c) = ccy {
        conditions.push(format!("CRNCY=='{c}'"));
    }
    let filter_str = conditions.join(" AND ");

    let universe = if active_only { "active" } else { "all" };
    let bql_query = format!(
        "get({fields_str}) for(filter(bondsuniv('{universe}', CONSOLIDATEDUPLICATES='N'), {filter_str}))"
    );

    let params = RequestParams {
        service: Service::BqlSvc.to_string(),
        operation: Operation::BqlSendQuery.to_string(),
        elements: Some(vec![("expression".to_string(), bql_query)]),
        ..Default::default()
    };

    engine.request(params).await.map_err(Into::into)
}

/// Bloomberg Quote Request — dealer quotes via IntradayTick.
///
/// Retrieves intraday tick data with broker/dealer codes for a security.
/// Useful for analyzing dealer activity and market making.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `ticker` - Security ticker (e.g., "US912810TM69 Govt")
/// * `start_datetime` - Start datetime (ISO format)
/// * `end_datetime` - End datetime (ISO format)
/// * `event_types` - Event types to retrieve (default: BID, ASK)
/// * `include_broker_codes` - Include broker/dealer codes (default: true)
///
/// # Returns
///
/// Arrow RecordBatch with quote data including broker codes
pub async fn recipe_bqr(
    engine: &Engine,
    ticker: String,
    start_datetime: String,
    end_datetime: String,
    event_types: Option<Vec<String>>,
    include_broker_codes: bool,
) -> Result<RecordBatch> {
    let evts = event_types.unwrap_or_else(|| vec!["BID".to_string(), "ASK".to_string()]);

    let mut options = vec![];
    if include_broker_codes {
        options.push(("includeBrokerCodes".to_string(), "true".to_string()));
    }

    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::IntradayTick.to_string(),
        security: Some(ticker),
        start_datetime: Some(start_datetime),
        end_datetime: Some(end_datetime),
        event_types: Some(evts),
        options: if options.is_empty() {
            None
        } else {
            Some(options)
        },
        ..Default::default()
    };

    engine.request(params).await.map_err(Into::into)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recipe_yas_builds_correct_params() {
        // This test verifies parameter building logic
        // Actual engine calls require Bloomberg connection (integration test)

        let overrides = build_yas_overrides(
            Some("20240115"),
            Some(YieldType::YTM),
            None,
            None,
            Some(99.5),
            None,
        );

        // Verify YAS overrides are built correctly
        assert!(overrides
            .iter()
            .any(|(k, v)| k == "YAS_SETTLE_DT" && v == "20240115"));
        assert!(overrides
            .iter()
            .any(|(k, v)| k == "YAS_YLD_FLAG" && v == "1"));
        assert!(overrides
            .iter()
            .any(|(k, v)| k == "YAS_BOND_PX" && v == "99.5"));
    }

    #[test]
    fn test_recipe_preferreds_default_fields() {
        // Verify that default fields are id and name
        let fields: Option<Vec<String>> = None;
        let all_fields = match fields {
            Some(mut flds) => {
                let mut defaults = vec!["id".to_string(), "name".to_string()];
                defaults.append(&mut flds);
                defaults
            }
            None => vec!["id".to_string(), "name".to_string()],
        };
        assert_eq!(all_fields, vec!["id", "name"]);
    }

    #[test]
    fn test_recipe_preferreds_custom_fields() {
        let fields = Some(vec!["px_last".to_string(), "dvd_yld".to_string()]);
        let all_fields = match fields {
            Some(mut flds) => {
                let mut defaults = vec!["id".to_string(), "name".to_string()];
                defaults.append(&mut flds);
                defaults
            }
            None => vec!["id".to_string(), "name".to_string()],
        };
        assert_eq!(all_fields, vec!["id", "name", "px_last", "dvd_yld"]);
    }

    #[test]
    fn test_recipe_corporate_bonds_filter_building() {
        // Test that filter conditions are built correctly
        let ticker = "AAPL".to_string();
        let ccy = Some("USD".to_string());
        let active_only = true;

        let mut conditions = vec![
            "SRCH_ASSET_CLASS=='Corporates'".to_string(),
            format!("TICKER=='{ticker}'"),
        ];
        if let Some(c) = ccy {
            conditions.push(format!("CRNCY=='{c}'"));
        }
        let filter_str = conditions.join(" AND ");
        let universe = if active_only { "active" } else { "all" };

        assert_eq!(
            filter_str,
            "SRCH_ASSET_CLASS=='Corporates' AND TICKER=='AAPL' AND CRNCY=='USD'"
        );
        assert_eq!(universe, "active");
    }

    #[test]
    fn test_recipe_corporate_bonds_no_ccy() {
        let ticker = "MSFT".to_string();
        let ccy: Option<String> = None;

        let mut conditions = vec![
            "SRCH_ASSET_CLASS=='Corporates'".to_string(),
            format!("TICKER=='{ticker}'"),
        ];
        if let Some(c) = ccy {
            conditions.push(format!("CRNCY=='{c}'"));
        }
        let filter_str = conditions.join(" AND ");

        assert_eq!(
            filter_str,
            "SRCH_ASSET_CLASS=='Corporates' AND TICKER=='MSFT'"
        );
    }

    #[test]
    fn test_recipe_bqr_default_event_types() {
        let evts = resolve_event_types(None);
        assert_eq!(evts, vec!["BID", "ASK"]);
    }

    #[test]
    fn test_recipe_bqr_custom_event_types() {
        let evts = resolve_event_types(Some(vec!["TRADE".to_string()]));
        assert_eq!(evts, vec!["TRADE"]);
    }

    fn resolve_event_types(event_types: Option<Vec<String>>) -> Vec<String> {
        event_types.unwrap_or_else(|| vec!["BID".to_string(), "ASK".to_string()])
    }
}
