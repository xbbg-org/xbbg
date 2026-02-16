//! Currency conversion recipe.
//!
//! Adjusts data columns by fetching FX rates from Bloomberg and applying
//! conversion factors via Arrow compute operations.
//!
//! # Recipes
//!
//! - [`recipe_adjust_ccy`]: Convert data values to a target currency

use arrow::array::RecordBatch;
use xbbg_async::engine::{Engine, RequestParams};
use xbbg_async::services::{Operation, Service};
use crate::error::Result;

pub async fn recipe_currency_conversion(
    engine: &Engine,
    ticker: String,
    target_ccy: String,
    start_date: String,
    end_date: String,
) -> Result<RecordBatch> {
    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::HistoricalData.to_string(),
        securities: Some(vec![ticker]),
        fields: Some(vec!["PX_LAST".to_string()]),
        start_date: Some(start_date),
        end_date: Some(end_date),
        overrides: Some(vec![("CRNCY".to_string(), target_ccy)]),
        ..Default::default()
    };
    engine.request(params).await.map_err(Into::into)
}
