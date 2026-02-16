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

use std::sync::Arc;

use arrow::array::{Array, Date32Array, RecordBatch, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use chrono::{Datelike, Duration, NaiveDate};
use xbbg_async::engine::{Engine, RequestParams};
use xbbg_async::services::{Operation, Service};
use xbbg_ext::resolvers::cdx::{cdx_series_from_ticker, gen_to_specific, previous_series_ticker};
use xbbg_ext::resolvers::futures::{
    contract_index, generate_futures_candidates, validate_generic_ticker, RollFrequency,
};
use xbbg_ext::{fmt_date, parse_date, parse_ticker_parts};

use crate::error::{RecipeError, Result};

/// Resolve a generic futures ticker to a specific contract ticker for a date.
///
/// Workflow:
/// 1. Parse `dt` and resolve contract index from generic ticker.
/// 2. Generate contract candidates via `xbbg-ext` futures resolver.
/// 3. Query Bloomberg `LAST_TRADEABLE_DT` for all candidates.
/// 4. Keep contracts maturing after `dt`, sort by maturity, and select by index.
/// 5. Return the selected ticker as a single-row `RecordBatch`.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `gen_ticker` - Generic futures ticker (e.g. `ES1 Index`, `CL2 Comdty`)
/// * `dt` - Reference date (`YYYYMMDD`)
/// * `freq` - Optional roll frequency (`M` monthly, `Q`/`QE` quarterly)
pub async fn recipe_fut_ticker(
    engine: &Engine,
    gen_ticker: String,
    dt: String,
    freq: Option<String>,
) -> Result<RecordBatch> {
    let dt_parsed = parse_date(&dt)?;
    let idx = contract_index(&gen_ticker)?;

    use std::str::FromStr;
    let freq = freq
        .as_deref()
        .and_then(|s| RollFrequency::from_str(s).ok())
        .unwrap_or(RollFrequency::Monthly);

    let count = futures_candidate_count(&gen_ticker, idx)?;
    let candidates = generate_futures_candidates(&gen_ticker, dt_parsed, freq, count)?;

    if candidates.is_empty() {
        return Err(RecipeError::Other(format!(
            "no futures candidates generated for '{gen_ticker}'"
        )));
    }

    let candidate_tickers: Vec<String> = candidates.into_iter().map(|c| c.ticker).collect();
    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(candidate_tickers),
        fields: Some(vec!["LAST_TRADEABLE_DT".to_string()]),
        ..Default::default()
    };

    let maturity_batch = engine.request(params).await?;
    let mut valid_contracts = extract_refdata_date_values(&maturity_batch, "LAST_TRADEABLE_DT")?
        .into_iter()
        .filter(|(_, maturity)| *maturity > dt_parsed)
        .collect::<Vec<_>>();

    valid_contracts.sort_by_key(|(_, maturity)| *maturity);

    let selected = valid_contracts
        .get(idx)
        .map(|(ticker, _)| ticker.clone())
        .ok_or_else(|| {
            RecipeError::Other(format!(
                "unable to resolve futures contract for '{gen_ticker}' on {dt}: requested index {} but only {} valid maturities",
                idx + 1,
                valid_contracts.len()
            ))
        })?;

    build_single_ticker_batch(selected)
}

/// Resolve the most active futures contract around a reference date.
///
/// Workflow:
/// 1. Validate generic ticker input and build front/second generic contracts.
/// 2. Resolve both generics to specific contracts via [`recipe_fut_ticker`].
/// 3. Compare front maturity month vs `dt`.
/// 4. If near roll, query 10-day historical `VOLUME` and compare contracts.
/// 5. Return the selected active ticker as a single-row `RecordBatch`.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `gen_ticker` - Generic futures ticker (e.g. `ES1 Index`)
/// * `dt` - Reference date (`YYYYMMDD`)
/// * `freq` - Optional roll frequency (`M` monthly, `Q`/`QE` quarterly)
pub async fn recipe_active_futures(
    engine: &Engine,
    gen_ticker: String,
    dt: String,
    freq: Option<String>,
) -> Result<RecordBatch> {
    validate_generic_ticker(&gen_ticker)?;
    let dt_parsed = parse_date(&dt)?;

    let front_gen = with_generic_index(&gen_ticker, 1)?;
    let second_gen = with_generic_index(&gen_ticker, 2)?;

    let front_ticker = {
        let batch = recipe_fut_ticker(engine, front_gen, dt.clone(), freq.clone()).await?;
        extract_single_ticker(&batch)?
    };

    let second_ticker = match recipe_fut_ticker(engine, second_gen, dt.clone(), freq).await {
        Ok(batch) => extract_single_ticker(&batch)?,
        Err(_) => return build_single_ticker_batch(front_ticker),
    };

    let maturity_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(vec![front_ticker.clone(), second_ticker.clone()]),
        fields: Some(vec!["LAST_TRADEABLE_DT".to_string()]),
        ..Default::default()
    };

    let maturity_batch = engine.request(maturity_params).await?;
    if let Some(front_maturity) = extract_refdata_date_for_ticker(
        &maturity_batch,
        &front_ticker,
        "LAST_TRADEABLE_DT",
    )? {
        let dt_month = (dt_parsed.year(), dt_parsed.month());
        let maturity_month = (front_maturity.year(), front_maturity.month());
        if dt_month < maturity_month {
            return build_single_ticker_batch(front_ticker);
        }
    }

    let start_date = dt_parsed - Duration::days(10);
    let volume_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::HistoricalData.to_string(),
        securities: Some(vec![front_ticker.clone(), second_ticker.clone()]),
        fields: Some(vec!["VOLUME".to_string()]),
        start_date: Some(fmt_date(start_date, None)),
        end_date: Some(fmt_date(dt_parsed, None)),
        ..Default::default()
    };

    let volume_batch = engine.request(volume_params).await?;
    let front_volume = latest_history_numeric_point(&volume_batch, &front_ticker, "VOLUME")?;
    let second_volume = latest_history_numeric_point(&volume_batch, &second_ticker, "VOLUME")?;

    let selected = match (front_volume, second_volume) {
        (Some((_, f)), Some((_, s))) if s > f => second_ticker,
        (Some(_), Some(_)) => front_ticker,
        (Some(_), None) => front_ticker,
        (None, Some(_)) => second_ticker,
        (None, None) => front_ticker,
    };

    build_single_ticker_batch(selected)
}

/// Resolve a generic CDX ticker (`GEN`) to the active specific series (`Sxx`).
///
/// Workflow:
/// 1. Parse `dt` and validate CDX generic ticker structure.
/// 2. Query Bloomberg `ROLLING_SERIES` and `CDS_FIRST_ACCRUAL_START_DATE`.
/// 3. Convert generic ticker to specific via `gen_to_specific`.
/// 4. If `dt` is before accrual start, roll back one series when possible.
/// 5. Return resolved specific ticker as a single-row `RecordBatch`.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `gen_ticker` - Generic CDX ticker (e.g. `CDX IG CDSI GEN 5Y Corp`)
/// * `dt` - Reference date (`YYYYMMDD`)
pub async fn recipe_cdx_ticker(
    engine: &Engine,
    gen_ticker: String,
    dt: String,
) -> Result<RecordBatch> {
    let dt_parsed = parse_date(&dt)?;

    let cdx_info = cdx_series_from_ticker(&gen_ticker)?;
    if !cdx_info.is_generic {
        return Err(RecipeError::InvalidArgument(format!(
            "'{gen_ticker}' must be a generic CDX ticker containing GEN"
        )));
    }

    let params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(vec![gen_ticker.clone()]),
        fields: Some(vec![
            "ROLLING_SERIES".to_string(),
            "CDS_FIRST_ACCRUAL_START_DATE".to_string(),
        ]),
        ..Default::default()
    };

    let batch = engine.request(params).await?;
    let series_raw = extract_refdata_string_for_ticker(&batch, &gen_ticker, "ROLLING_SERIES")?
        .ok_or_else(|| {
            RecipeError::Other(format!(
                "missing ROLLING_SERIES for '{gen_ticker}' in Bloomberg response"
            ))
        })?;

    let series = parse_series_number(&series_raw).ok_or_else(|| {
        RecipeError::Other(format!(
            "unable to parse ROLLING_SERIES='{series_raw}' for '{gen_ticker}'"
        ))
    })?;

    let accrual_dt = extract_refdata_date_for_ticker(
        &batch,
        &gen_ticker,
        "CDS_FIRST_ACCRUAL_START_DATE",
    )?;

    let resolved_series = if accrual_dt.is_some_and(|start| dt_parsed < start) && series > 1 {
        series - 1
    } else {
        series
    };

    let resolved_ticker = gen_to_specific(&gen_ticker, resolved_series)?;
    build_single_ticker_batch(resolved_ticker)
}

/// Resolve the most active CDX series around a reference date.
///
/// Workflow:
/// 1. Resolve current series via [`recipe_cdx_ticker`].
/// 2. Generate previous series ticker via `previous_series_ticker`.
/// 3. If `dt` is before current accrual start, return previous series.
/// 4. Query historical `PX_LAST` for both series over a lookback window.
/// 5. Select the series with the most recent non-null price and return it.
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `gen_ticker` - Generic CDX ticker (e.g. `CDX IG CDSI GEN 5Y Corp`)
/// * `dt` - Reference date (`YYYYMMDD`)
/// * `lookback_days` - Optional lookback window for activity comparison (default `10`)
pub async fn recipe_active_cdx(
    engine: &Engine,
    gen_ticker: String,
    dt: String,
    lookback_days: Option<i32>,
) -> Result<RecordBatch> {
    let dt_parsed = parse_date(&dt)?;
    let lookback_days = lookback_days.unwrap_or(10).max(1) as i64;

    let current_ticker = {
        let batch = recipe_cdx_ticker(engine, gen_ticker, dt.clone()).await?;
        extract_single_ticker(&batch)?
    };

    let Some(previous_ticker) = previous_series_ticker(&current_ticker)? else {
        return build_single_ticker_batch(current_ticker);
    };

    let metadata_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        securities: Some(vec![current_ticker.clone()]),
        fields: Some(vec!["CDS_FIRST_ACCRUAL_START_DATE".to_string()]),
        ..Default::default()
    };

    let metadata_batch = engine.request(metadata_params).await?;
    if let Some(start_dt) = extract_refdata_date_for_ticker(
        &metadata_batch,
        &current_ticker,
        "CDS_FIRST_ACCRUAL_START_DATE",
    )? {
        if dt_parsed < start_dt {
            return build_single_ticker_batch(previous_ticker);
        }
    }

    let start_date = dt_parsed - Duration::days(lookback_days);
    let price_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::HistoricalData.to_string(),
        securities: Some(vec![current_ticker.clone(), previous_ticker.clone()]),
        fields: Some(vec!["PX_LAST".to_string()]),
        start_date: Some(fmt_date(start_date, None)),
        end_date: Some(fmt_date(dt_parsed, None)),
        ..Default::default()
    };

    let price_batch = engine.request(price_params).await?;
    let current_latest = latest_history_numeric_point(&price_batch, &current_ticker, "PX_LAST")?
        .map(|(date, _)| date);
    let previous_latest =
        latest_history_numeric_point(&price_batch, &previous_ticker, "PX_LAST")?
            .map(|(date, _)| date);

    let selected = match (current_latest, previous_latest) {
        (Some(cur), Some(prev)) if prev > cur => previous_ticker,
        (Some(_), Some(_)) => current_ticker,
        (Some(_), None) => current_ticker,
        (None, Some(_)) => previous_ticker,
        (None, None) => current_ticker,
    };

    build_single_ticker_batch(selected)
}

fn futures_candidate_count(gen_ticker: &str, idx: usize) -> Result<usize> {
    let parts = parse_ticker_parts(gen_ticker)?;
    let month_ext = if parts.asset == "Comdty" { 4 } else { 2 };
    Ok(std::cmp::max(idx + month_ext, 3))
}

fn with_generic_index(gen_ticker: &str, index: u32) -> Result<String> {
    let parts = parse_ticker_parts(gen_ticker)?;

    let ticker = match parts.asset.as_str() {
        "Equity" => {
            let exchange = parts.exchange.unwrap_or_else(|| "US".to_string());
            format!("{}{} {} {}", parts.prefix, index, exchange, parts.asset)
        }
        _ => format!("{}{} {}", parts.prefix, index, parts.asset),
    };

    Ok(ticker)
}

fn build_single_ticker_batch(ticker: String) -> Result<RecordBatch> {
    let schema = Arc::new(Schema::new(vec![Field::new("ticker", DataType::Utf8, false)]));
    let ticker_array = StringArray::from(vec![ticker]);
    RecordBatch::try_new(schema, vec![Arc::new(ticker_array)]).map_err(Into::into)
}

fn extract_single_ticker(batch: &RecordBatch) -> Result<String> {
    let ticker_col = batch
        .column_by_name("ticker")
        .ok_or_else(|| RecipeError::Other("missing 'ticker' column".to_string()))?
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| RecipeError::Other("'ticker' column must be Utf8".to_string()))?;

    if ticker_col.is_empty() || ticker_col.is_null(0) {
        return Err(RecipeError::Other(
            "resolved ticker batch is empty or null".to_string(),
        ));
    }

    Ok(ticker_col.value(0).to_string())
}

fn extract_refdata_string_for_ticker(
    batch: &RecordBatch,
    ticker: &str,
    field: &str,
) -> Result<Option<String>> {
    let ticker_col = as_string_col(batch, "ticker")?;
    let field_col = as_string_col(batch, "field")?;
    let value_col = as_string_col(batch, "value")?;

    for row in 0..batch.num_rows() {
        if ticker_col.is_null(row) || field_col.is_null(row) || value_col.is_null(row) {
            continue;
        }

        if ticker_col.value(row) != ticker || !field_col.value(row).eq_ignore_ascii_case(field) {
            continue;
        }

        let raw = value_col.value(row).trim();
        if raw.is_empty() {
            continue;
        }

        return Ok(Some(raw.to_string()));
    }

    Ok(None)
}

fn extract_refdata_date_values(batch: &RecordBatch, field: &str) -> Result<Vec<(String, NaiveDate)>> {
    let ticker_col = as_string_col(batch, "ticker")?;
    let field_col = as_string_col(batch, "field")?;
    let value_col = as_string_col(batch, "value")?;

    let mut output = Vec::new();

    for row in 0..batch.num_rows() {
        if ticker_col.is_null(row) || field_col.is_null(row) || value_col.is_null(row) {
            continue;
        }

        if !field_col.value(row).eq_ignore_ascii_case(field) {
            continue;
        }

        let Some(parsed) = parse_any_date(value_col.value(row)) else {
            continue;
        };

        output.push((ticker_col.value(row).to_string(), parsed));
    }

    Ok(output)
}

fn extract_refdata_date_for_ticker(
    batch: &RecordBatch,
    ticker: &str,
    field: &str,
) -> Result<Option<NaiveDate>> {
    let raw = extract_refdata_string_for_ticker(batch, ticker, field)?;
    Ok(raw.and_then(|v| parse_any_date(&v)))
}

fn latest_history_numeric_point(
    batch: &RecordBatch,
    ticker: &str,
    field: &str,
) -> Result<Option<(NaiveDate, f64)>> {
    let ticker_col = as_string_col(batch, "ticker")?;
    let field_col = as_string_col(batch, "field")?;
    let value_col = as_string_col(batch, "value")?;

    let date_col = batch
        .column_by_name("date")
        .ok_or_else(|| RecipeError::Other("missing 'date' column".to_string()))?;
    let date32_col = date_col.as_any().downcast_ref::<Date32Array>();
    let date_str_col = date_col.as_any().downcast_ref::<StringArray>();

    let mut best: Option<(NaiveDate, f64)> = None;

    for row in 0..batch.num_rows() {
        if ticker_col.is_null(row) || field_col.is_null(row) || value_col.is_null(row) {
            continue;
        }

        if ticker_col.value(row) != ticker || !field_col.value(row).eq_ignore_ascii_case(field) {
            continue;
        }

        let raw_value = value_col.value(row).trim();
        if raw_value.is_empty() {
            continue;
        }

        let Ok(value) = raw_value.parse::<f64>() else {
            continue;
        };

        let row_date = if let Some(col) = date32_col {
            if col.is_null(row) {
                None
            } else {
                date32_to_naive(col.value(row))
            }
        } else if let Some(col) = date_str_col {
            if col.is_null(row) {
                None
            } else {
                parse_any_date(col.value(row))
            }
        } else {
            None
        };

        let Some(row_date) = row_date else {
            continue;
        };

        match best {
            Some((best_date, _)) if row_date < best_date => {}
            _ => best = Some((row_date, value)),
        }
    }

    Ok(best)
}

fn parse_series_number(value: &str) -> Option<u32> {
    let value = value.trim();

    if let Ok(v) = value.parse::<u32>() {
        return Some(v);
    }

    let parsed = value.parse::<f64>().ok()?;
    if !parsed.is_finite() || parsed < 1.0 || parsed.fract() != 0.0 {
        return None;
    }

    Some(parsed as u32)
}

fn parse_any_date(value: &str) -> Option<NaiveDate> {
    let value = value.trim();

    if value.is_empty() {
        return None;
    }

    parse_date(value)
        .ok()
        .or_else(|| value.get(..10).and_then(|prefix| parse_date(prefix).ok()))
}

fn date32_to_naive(days_since_epoch: i32) -> Option<NaiveDate> {
    let epoch = NaiveDate::from_ymd_opt(1970, 1, 1)?;
    epoch.checked_add_signed(Duration::days(days_since_epoch as i64))
}

fn as_string_col<'a>(batch: &'a RecordBatch, column: &str) -> Result<&'a StringArray> {
    batch
        .column_by_name(column)
        .ok_or_else(|| RecipeError::Other(format!("missing '{column}' column")))?
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| RecipeError::Other(format!("'{column}' column must be Utf8")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_futures_candidate_count_rules() {
        let idx0 = futures_candidate_count("ES1 Index", 0).unwrap();
        let idx2 = futures_candidate_count("CL3 Comdty", 2).unwrap();

        assert_eq!(idx0, 3);
        assert_eq!(idx2, 6);
    }

    #[test]
    fn test_with_generic_index_preserves_asset_shape() {
        assert_eq!(with_generic_index("ES1 Index", 2).unwrap(), "ES2 Index");
        assert_eq!(
            with_generic_index("SPY1 US Equity", 2).unwrap(),
            "SPY2 US Equity"
        );
    }

    #[test]
    fn test_extract_refdata_date_values_parses_iso_dates() {
        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value", DataType::Utf8, false),
        ]));

        let batch = RecordBatch::try_new(
            schema,
            vec![
                Arc::new(StringArray::from(vec!["ESH24 Index", "ESM24 Index"])),
                Arc::new(StringArray::from(vec!["LAST_TRADEABLE_DT", "LAST_TRADEABLE_DT"])),
                Arc::new(StringArray::from(vec!["2024-03-15", "2024-06-21"])),
            ],
        )
        .unwrap();

        let parsed = extract_refdata_date_values(&batch, "LAST_TRADEABLE_DT").unwrap();
        assert_eq!(parsed.len(), 2);
        assert_eq!(parsed[0].0, "ESH24 Index");
        assert_eq!(parsed[0].1, NaiveDate::from_ymd_opt(2024, 3, 15).unwrap());
    }

    #[test]
    fn test_latest_history_numeric_point_uses_latest_non_null_row() {
        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("date", DataType::Date32, true),
            Field::new("field", DataType::Utf8, false),
            Field::new("value", DataType::Utf8, true),
        ]));

        let d1 = (NaiveDate::from_ymd_opt(2024, 1, 2).unwrap()
            - NaiveDate::from_ymd_opt(1970, 1, 1).unwrap())
        .num_days() as i32;
        let d2 = (NaiveDate::from_ymd_opt(2024, 1, 3).unwrap()
            - NaiveDate::from_ymd_opt(1970, 1, 1).unwrap())
        .num_days() as i32;

        let batch = RecordBatch::try_new(
            schema,
            vec![
                Arc::new(StringArray::from(vec![
                    "ESH24 Index",
                    "ESH24 Index",
                    "ESM24 Index",
                ])),
                Arc::new(Date32Array::from(vec![Some(d1), Some(d2), Some(d2)])),
                Arc::new(StringArray::from(vec!["VOLUME", "VOLUME", "VOLUME"])),
                Arc::new(StringArray::from(vec!["100", "250", "175"])),
            ],
        )
        .unwrap();

        let latest = latest_history_numeric_point(&batch, "ESH24 Index", "VOLUME")
            .unwrap()
            .unwrap();

        assert_eq!(latest.0, NaiveDate::from_ymd_opt(2024, 1, 3).unwrap());
        assert_eq!(latest.1, 250.0);
    }

    #[test]
    fn test_parse_series_number_accepts_int_and_decimal_text() {
        assert_eq!(parse_series_number("45"), Some(45));
        assert_eq!(parse_series_number("45.0"), Some(45));
        assert_eq!(parse_series_number("45.5"), None);
        assert_eq!(parse_series_number("abc"), None);
    }

    #[test]
    fn test_build_and_extract_single_ticker_batch() {
        let batch = build_single_ticker_batch("CDX IG CDSI S45 5Y Corp".to_string()).unwrap();
        let ticker = extract_single_ticker(&batch).unwrap();
        assert_eq!(ticker, "CDX IG CDSI S45 5Y Corp");
    }
}
