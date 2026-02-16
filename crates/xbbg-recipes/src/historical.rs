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
