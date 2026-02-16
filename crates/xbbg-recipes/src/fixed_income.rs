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
        assert!(overrides.iter().any(|(k, v)| k == "YAS_SETTLE_DT" && v == "20240115"));
        assert!(overrides.iter().any(|(k, v)| k == "YAS_YLD_FLAG" && v == "1"));
        assert!(overrides.iter().any(|(k, v)| k == "YAS_BOND_PX" && v == "99.5"));
    }
}
