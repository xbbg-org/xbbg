//! Futures resolution recipes.
//!
//! These recipes resolve generic futures tickers to specific contract tickers,
//! determine active contracts, and handle CDX series resolution.
//!
//! # Recipes
//!
//! - [`recipe_fut_ticker`]: Resolve generic ticker to specific contract
//! - [`recipe_active_futures`]: Find most active futures contract
//! - [`recipe_cdx_ticker`]: Resolve CDX series
//! - [`recipe_active_cdx`]: Find most active CDX series

use arrow::array::RecordBatch;
use xbbg_async::engine::{Engine, RequestParams};
use xbbg_async::services::{Operation, Service};
use crate::error::Result;

pub async fn recipe_fut_ticker(
    engine: &Engine,
    gen_ticker: String,
    _dt: String,
    _freq: Option<String>,
) -> Result<RecordBatch> {
    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(vec![gen_ticker]),
        fields: Some(vec!["LAST_TRADEABLE_DT".to_string()]),
        ..Default::default()
    };
    engine.request(params).await.map_err(Into::into)
}
