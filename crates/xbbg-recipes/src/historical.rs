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

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use crate::error::Result;
use arrow::array::RecordBatch;
use arrow::array::{
    Array, ArrayRef, Float64Array, Int32Array, Int64Array, LargeStringArray, StringArray,
};
use arrow::datatypes::{DataType, Field, Schema};
use xbbg_async::engine::{Engine, ExtractorType, RequestParams};
use xbbg_async::services::{Operation, Service};
use xbbg_ext::transforms::historical::{apply_column_renames, calculate_level_percentages};

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
        overrides: if overrides.is_empty() {
            None
        } else {
            Some(overrides)
        },
        ..Default::default()
    };
    engine.request(params).await.map_err(Into::into)
}

/// Fetch earnings bulk data and derive hierarchical percentages.
///
/// Workflow:
/// 1. Query `PG_Bulk_Header` using the bulk extractor to discover dynamic period labels.
/// 2. Query `PG_{typ}` for the actual earnings values.
/// 3. Rename period columns using header-derived names (for example, `Period 1 Value` -> `fy2024`).
/// 4. Add `{period}_pct` columns using hierarchy semantics:
///    - level 1 rows: percentage of total level 1 sum
///    - level 2 rows: percentage of parent level 1 group sum
///
/// # Arguments
///
/// * `engine` - Bloomberg engine reference
/// * `tickers` - Securities to query
/// * `by` - Period granularity override (`Q` or `A`)
/// * `typ` - Earnings type (`IS`, `BS`, or `CF`)
/// * `ccy` - Currency override
/// * `level` - Optional hierarchy level filter (`1` or `2`)
pub async fn recipe_earning(
    engine: &Engine,
    tickers: Vec<String>,
    by: Option<String>,
    typ: String,
    ccy: Option<String>,
    level: Option<i32>,
) -> Result<RecordBatch> {
    let typ = normalize_earning_type(&typ)?;
    let data_field = format!("PG_{typ}");

    let (header_overrides, data_overrides) =
        build_earning_overrides(by.as_deref(), ccy.as_deref(), level)?;

    let header_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        extractor: ExtractorType::BulkData,
        extractor_set: true,
        securities: Some(tickers.clone()),
        fields: Some(vec!["PG_Bulk_Header".to_string()]),
        overrides: to_option_overrides(header_overrides),
        ..Default::default()
    };

    let data_params = RequestParams {
        service: Service::RefData.to_string(),
        operation: Operation::ReferenceData.to_string(),
        extractor: ExtractorType::BulkData,
        extractor_set: true,
        securities: Some(tickers),
        fields: Some(vec![data_field]),
        overrides: to_option_overrides(data_overrides),
        ..Default::default()
    };

    let header_batch = engine.request(header_params).await?;
    let mut data_batch = engine.request(data_params).await?;

    if header_batch.num_rows() > 0 && data_batch.num_rows() > 0 {
        let renames = build_earning_header_rename(&header_batch, &data_batch);
        if !renames.is_empty() {
            data_batch = apply_column_renames(&data_batch, &renames)?;
        }
    }

    add_earning_percentage_columns(data_batch)
}

fn normalize_earning_type(typ: &str) -> Result<String> {
    let normalized = typ.trim().to_ascii_uppercase();
    let normalized = normalized.strip_prefix("PG_").unwrap_or(&normalized);

    match normalized {
        "IS" | "BS" | "CF" => Ok(normalized.to_string()),
        _ => Err(crate::error::RecipeError::InvalidArgument(format!(
            "unsupported earning type '{typ}', expected IS/BS/CF"
        ))),
    }
}

type OverridePairs = Vec<(String, String)>;
type EarningOverrides = (OverridePairs, OverridePairs);

fn build_earning_overrides(
    by: Option<&str>,
    ccy: Option<&str>,
    level: Option<i32>,
) -> Result<EarningOverrides> {
    let mut header_overrides = Vec::new();
    let mut data_overrides = Vec::new();

    if let Some(period) = by {
        let period = period.trim().to_ascii_uppercase();
        if !period.is_empty() {
            if period != "Q" && period != "A" {
                return Err(crate::error::RecipeError::InvalidArgument(format!(
                    "unsupported by='{period}', expected Q or A"
                )));
            }

            header_overrides.push(("PER".to_string(), period.clone()));
            data_overrides.push(("PER".to_string(), period));
        }
    }

    if let Some(currency) = ccy {
        let currency = currency.trim().to_ascii_uppercase();
        if !currency.is_empty() {
            data_overrides.push(("CURRENCY".to_string(), currency));
        }
    }

    if let Some(hierarchy_level) = level {
        if hierarchy_level != 1 && hierarchy_level != 2 {
            return Err(crate::error::RecipeError::InvalidArgument(format!(
                "unsupported level='{hierarchy_level}', expected 1 or 2"
            )));
        }
        data_overrides.push((
            "PG_Hierarchy_Level".to_string(),
            hierarchy_level.to_string(),
        ));
    }

    Ok((header_overrides, data_overrides))
}

fn to_option_overrides(overrides: Vec<(String, String)>) -> Option<Vec<(String, String)>> {
    if overrides.is_empty() {
        None
    } else {
        Some(overrides)
    }
}

fn build_earning_header_rename(
    header_batch: &RecordBatch,
    data_batch: &RecordBatch,
) -> Vec<(String, String)> {
    let mut header_values: HashMap<String, String> = HashMap::new();

    for field in header_batch.schema().fields() {
        let column_name = field.name();
        if column_name == "ticker" || column_name == "field" {
            continue;
        }

        let Some(column) = header_batch.column_by_name(column_name) else {
            continue;
        };

        let first_value = (0..header_batch.num_rows())
            .find_map(|idx| array_value_as_string(column, idx))
            .map(|raw| raw.trim().to_string())
            .filter(|raw| !raw.is_empty());

        if let Some(value) = first_value {
            header_values.insert(column_name.to_string(), value);
        }
    }

    if header_values.is_empty() {
        return Vec::new();
    }

    let mut used_names: HashSet<String> = data_batch
        .schema()
        .fields()
        .iter()
        .map(|field| field.name().to_ascii_lowercase())
        .collect();

    let mut renames = Vec::new();
    for field in data_batch.schema().fields() {
        let data_col = field.name();
        if data_col == "ticker" || data_col == "field" {
            continue;
        }

        let header_col = if let Some(period_col) = data_col.strip_suffix(" Value") {
            format!("{period_col} Header")
        } else {
            format!("{data_col} Header")
        };

        let Some(raw_header_value) = header_values.get(&header_col) else {
            continue;
        };

        let normalized_name = normalize_earning_header_value(raw_header_value);
        if normalized_name.is_empty() {
            continue;
        }

        let normalized_key = normalized_name.to_ascii_lowercase();
        if normalized_key == data_col.to_ascii_lowercase() || used_names.contains(&normalized_key) {
            continue;
        }

        renames.push((data_col.to_string(), normalized_name.clone()));
        used_names.insert(normalized_key);
    }

    renames
}

fn normalize_earning_header_value(value: &str) -> String {
    let mut normalized = value
        .trim()
        .to_ascii_lowercase()
        .replace([' ', '-', '/', '.'], "_");

    while normalized.contains("__") {
        normalized = normalized.replace("__", "_");
    }

    normalized = normalized.replace("_20", "20");
    normalized.trim_matches('_').to_string()
}

fn array_value_as_string(array: &ArrayRef, idx: usize) -> Option<String> {
    if idx >= array.len() || array.is_null(idx) {
        return None;
    }

    if let Some(arr) = array.as_any().downcast_ref::<StringArray>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<LargeStringArray>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Float64Array>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int64Array>() {
        return Some(arr.value(idx).to_string());
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int32Array>() {
        return Some(arr.value(idx).to_string());
    }

    None
}

fn add_earning_percentage_columns(batch: RecordBatch) -> Result<RecordBatch> {
    let Some(level_col_name) = find_level_column_name(&batch) else {
        return Ok(batch);
    };

    let Some(level_col) = batch.column_by_name(&level_col_name) else {
        return Ok(batch);
    };
    let levels = extract_level_values(level_col);

    if levels.iter().all(Option::is_none) {
        return Ok(batch);
    }

    let value_cols = earning_value_columns(&batch);
    let mut output = batch;

    for value_col in value_cols {
        let pct_col = format!("{value_col}_pct");
        if output.column_by_name(&pct_col).is_some() {
            continue;
        }

        let Some(values_col) = output.column_by_name(&value_col) else {
            continue;
        };

        let values = extract_numeric_values(values_col);
        if values.iter().all(Option::is_none) {
            continue;
        }

        let percentages = calculate_level_percentages(&values, &levels);
        output = insert_pct_column_after(&output, &value_col, &pct_col, percentages)?;
    }

    Ok(output)
}

fn find_level_column_name(batch: &RecordBatch) -> Option<String> {
    if batch.column_by_name("level").is_some() {
        return Some("level".to_string());
    }

    batch
        .schema()
        .fields()
        .iter()
        .find(|field| field.name().eq_ignore_ascii_case("level"))
        .map(|field| field.name().to_string())
}

fn earning_value_columns(batch: &RecordBatch) -> Vec<String> {
    batch
        .schema()
        .fields()
        .iter()
        .map(|field| field.name())
        .filter(|name| is_earning_value_column(name))
        .cloned()
        .collect()
}

fn is_earning_value_column(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    (lower.starts_with("fy") && !lower.ends_with("_pct")) || lower.ends_with(" value")
}

fn extract_numeric_values(array: &ArrayRef) -> Vec<Option<f64>> {
    if let Some(arr) = array.as_any().downcast_ref::<Float64Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    Some(arr.value(idx))
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int64Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    Some(arr.value(idx) as f64)
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int32Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    Some(arr.value(idx) as f64)
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<StringArray>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    parse_f64_like(arr.value(idx))
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<LargeStringArray>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    parse_f64_like(arr.value(idx))
                }
            })
            .collect();
    }

    vec![None; array.len()]
}

fn extract_level_values(array: &ArrayRef) -> Vec<Option<i64>> {
    if let Some(arr) = array.as_any().downcast_ref::<Int64Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    Some(arr.value(idx))
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<Int32Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    Some(arr.value(idx) as i64)
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<Float64Array>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    let v = arr.value(idx);
                    if v.is_finite() && v.fract() == 0.0 {
                        Some(v as i64)
                    } else {
                        None
                    }
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<StringArray>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    parse_i64_like(arr.value(idx))
                }
            })
            .collect();
    }
    if let Some(arr) = array.as_any().downcast_ref::<LargeStringArray>() {
        return (0..arr.len())
            .map(|idx| {
                if arr.is_null(idx) {
                    None
                } else {
                    parse_i64_like(arr.value(idx))
                }
            })
            .collect();
    }

    vec![None; array.len()]
}

fn parse_f64_like(value: &str) -> Option<f64> {
    let cleaned = value.trim().replace(',', "");
    if cleaned.is_empty() {
        None
    } else {
        cleaned.parse::<f64>().ok()
    }
}

fn parse_i64_like(value: &str) -> Option<i64> {
    let cleaned = value.trim();
    if cleaned.is_empty() {
        return None;
    }

    if let Ok(parsed) = cleaned.parse::<i64>() {
        return Some(parsed);
    }

    let parsed = cleaned.parse::<f64>().ok()?;
    if parsed.is_finite() && parsed.fract() == 0.0 {
        Some(parsed as i64)
    } else {
        None
    }
}

fn insert_pct_column_after(
    batch: &RecordBatch,
    after_col: &str,
    pct_col: &str,
    percentages: Vec<Option<f64>>,
) -> Result<RecordBatch> {
    if percentages.len() != batch.num_rows() {
        return Err(crate::error::RecipeError::Other(format!(
            "percentage length mismatch for '{pct_col}'"
        )));
    }

    let insert_after_idx = batch
        .schema()
        .index_of(after_col)
        .map_err(|_| crate::error::RecipeError::Other(format!("missing '{after_col}' column")))?;

    let pct_array: ArrayRef = Arc::new(Float64Array::from(percentages));

    let mut fields = Vec::with_capacity(batch.num_columns() + 1);
    let mut columns = Vec::with_capacity(batch.num_columns() + 1);

    for idx in 0..batch.num_columns() {
        fields.push(batch.schema().field(idx).as_ref().clone());
        columns.push(batch.column(idx).clone());

        if idx == insert_after_idx {
            fields.push(Field::new(pct_col, DataType::Float64, true));
            columns.push(pct_array.clone());
        }
    }

    let schema = Arc::new(Schema::new_with_metadata(
        fields,
        batch.schema().metadata().clone(),
    ));
    RecordBatch::try_new(schema, columns).map_err(Into::into)
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
        overrides: if overrides.is_empty() {
            None
        } else {
            Some(overrides)
        },
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
    use std::sync::Arc;

    use arrow::array::{Float64Array, Int32Array, StringArray};
    use arrow::datatypes::{DataType, Field, Schema};

    use super::*;

    #[test]
    fn test_build_earning_header_rename() {
        let header_schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("Period 1 Header", DataType::Utf8, true),
            Field::new("Period 2 Header", DataType::Utf8, true),
        ]));

        let header_batch = RecordBatch::try_new(
            header_schema,
            vec![
                Arc::new(StringArray::from(vec!["AAPL US Equity"])),
                Arc::new(StringArray::from(vec!["PG_Bulk_Header"])),
                Arc::new(StringArray::from(vec!["FY 2023"])),
                Arc::new(StringArray::from(vec!["FY 2024"])),
            ],
        )
        .unwrap();

        let data_schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("Period 1 Value", DataType::Float64, true),
            Field::new("Period 2 Value", DataType::Float64, true),
        ]));

        let data_batch = RecordBatch::try_new(
            data_schema,
            vec![
                Arc::new(StringArray::from(vec!["AAPL US Equity"])),
                Arc::new(StringArray::from(vec!["PG_IS"])),
                Arc::new(Float64Array::from(vec![Some(100.0)])),
                Arc::new(Float64Array::from(vec![Some(120.0)])),
            ],
        )
        .unwrap();

        let rename_map = build_earning_header_rename(&header_batch, &data_batch);

        assert!(rename_map.contains(&("Period 1 Value".to_string(), "fy2023".to_string())));
        assert!(rename_map.contains(&("Period 2 Value".to_string(), "fy2024".to_string())));
    }

    #[test]
    fn test_add_earning_percentage_columns_fy_data() {
        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("level", DataType::Utf8, true),
            Field::new("fy2023", DataType::Float64, true),
            Field::new("fy2024", DataType::Float64, true),
        ]));

        let batch = RecordBatch::try_new(
            schema,
            vec![
                Arc::new(StringArray::from(vec![
                    "AAPL US Equity",
                    "AAPL US Equity",
                    "AAPL US Equity",
                    "AAPL US Equity",
                ])),
                Arc::new(StringArray::from(vec!["PG_IS", "PG_IS", "PG_IS", "PG_IS"])),
                Arc::new(StringArray::from(vec!["1", "1", "2", "2"])),
                Arc::new(Float64Array::from(vec![
                    Some(100.0),
                    Some(200.0),
                    Some(50.0),
                    Some(50.0),
                ])),
                Arc::new(Float64Array::from(vec![
                    Some(300.0),
                    Some(100.0),
                    Some(60.0),
                    Some(40.0),
                ])),
            ],
        )
        .unwrap();

        let output = add_earning_percentage_columns(batch).unwrap();

        let fy23_idx = output.schema().index_of("fy2023").unwrap();
        let fy23_pct_idx = output.schema().index_of("fy2023_pct").unwrap();
        assert_eq!(fy23_pct_idx, fy23_idx + 1);

        let fy23_pct = output
            .column_by_name("fy2023_pct")
            .unwrap()
            .as_any()
            .downcast_ref::<Float64Array>()
            .unwrap();
        assert!((fy23_pct.value(0) - 33.333).abs() < 0.01);
        assert!((fy23_pct.value(1) - 66.667).abs() < 0.01);
        assert!((fy23_pct.value(2) - 50.0).abs() < 0.01);
        assert!((fy23_pct.value(3) - 50.0).abs() < 0.01);
    }

    #[test]
    fn test_add_earning_percentage_columns_case_insensitive_level() {
        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("Level", DataType::Int32, true),
            Field::new("fy2023", DataType::Utf8, true),
        ]));

        let batch = RecordBatch::try_new(
            schema,
            vec![
                Arc::new(StringArray::from(vec![
                    "AAPL US Equity",
                    "AAPL US Equity",
                    "AAPL US Equity",
                ])),
                Arc::new(StringArray::from(vec!["PG_IS", "PG_IS", "PG_IS"])),
                Arc::new(Int32Array::from(vec![Some(1), Some(1), Some(2)])),
                Arc::new(StringArray::from(vec!["100", "200", "50"])),
            ],
        )
        .unwrap();

        let output = add_earning_percentage_columns(batch).unwrap();
        let pct_col = output
            .column_by_name("fy2023_pct")
            .unwrap()
            .as_any()
            .downcast_ref::<Float64Array>()
            .unwrap();

        assert!((pct_col.value(0) - 33.333).abs() < 0.01);
        assert!((pct_col.value(1) - 66.667).abs() < 0.01);
        assert!((pct_col.value(2) - 100.0).abs() < 0.01);
    }

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
        assert_eq!(
            overrides[0],
            ("EQY_FUND_CRNCY".to_string(), "USD".to_string())
        );
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
