//! Historical data transformation utilities.
//!
//! Column renaming, percentage calculations for dividend and earnings data.

use std::sync::Arc;

use arrow::array::{Array, ArrayRef, Float64Array, RecordBatch, StringArray};
use arrow::datatypes::{DataType, Field, Schema};

use crate::constants::{DVD_COLS, ETF_COLS};
use crate::error::{ExtError, Result};

/// Rename dividend columns from Bloomberg names to clean names.
///
/// Uses the `DVD_COLS` mapping to transform column names like
/// "Declared Date" to "dec_date".
///
/// # Arguments
///
/// * `columns` - Slice of column names to rename
///
/// # Returns
///
/// A vector of (old_name, new_name) pairs for columns that need renaming.
///
/// # Examples
///
/// ```
/// use xbbg_ext::transforms::historical::rename_dividend_columns;
///
/// let columns = vec!["ticker", "Declared Date", "Ex-Date", "Dividend Amount"];
/// let renames = rename_dividend_columns(&columns);
///
/// assert_eq!(renames.len(), 3);
/// assert!(renames.iter().any(|(old, new)| old == "Declared Date" && new == "dec_date"));
/// ```
pub fn rename_dividend_columns(columns: &[&str]) -> Vec<(String, String)> {
    columns
        .iter()
        .filter_map(|col| {
            DVD_COLS
                .get(*col)
                .map(|new_name| (col.to_string(), new_name.to_string()))
        })
        .collect()
}

/// Rename ETF holdings columns from Bloomberg names to clean names.
///
/// Uses the `ETF_COLS` mapping.
pub fn rename_etf_columns(columns: &[&str]) -> Vec<(String, String)> {
    columns
        .iter()
        .filter_map(|col| {
            ETF_COLS
                .get(*col)
                .map(|new_name| (col.to_string(), new_name.to_string()))
        })
        .collect()
}

/// Apply column renaming to a RecordBatch.
///
/// Creates a new RecordBatch with renamed columns based on the provided mapping.
pub fn apply_column_renames(
    batch: &RecordBatch,
    renames: &[(String, String)],
) -> Result<RecordBatch> {
    let schema = batch.schema();

    // Build new schema with renamed fields
    let new_fields: Vec<Field> = schema
        .fields()
        .iter()
        .map(|field| {
            let new_name = renames
                .iter()
                .find(|(old, _)| old == field.name())
                .map(|(_, new)| new.as_str())
                .unwrap_or(field.name());

            Field::new(new_name, field.data_type().clone(), field.is_nullable())
        })
        .collect();

    let new_schema = Arc::new(Schema::new(new_fields));

    // Columns stay the same, just schema changes
    let columns: Vec<ArrayRef> = (0..batch.num_columns())
        .map(|i| batch.column(i).clone())
        .collect();

    RecordBatch::try_new(new_schema, columns).map_err(ExtError::Arrow)
}

/// Calculate percentage values within groups.
///
/// For earnings data, calculates what percentage each row represents
/// of its group total (e.g., geographic breakdown as % of total).
///
/// # Arguments
///
/// * `values` - The numeric values
/// * `levels` - The hierarchy levels (1 = top level, 2 = sub-level, etc.)
///
/// # Returns
///
/// A vector of percentages (0-100) for each row.
pub fn calculate_level_percentages(
    values: &[Option<f64>],
    levels: &[Option<i64>],
) -> Vec<Option<f64>> {
    if values.len() != levels.len() {
        return vec![None; values.len()];
    }

    let mut percentages = vec![None; values.len()];

    // Calculate level 1 percentages (% of total level 1)
    let level_1_indices: Vec<usize> = levels
        .iter()
        .enumerate()
        .filter_map(|(i, lvl)| if *lvl == Some(1) { Some(i) } else { None })
        .collect();

    if !level_1_indices.is_empty() {
        let level_1_sum: f64 = level_1_indices.iter().filter_map(|&i| values[i]).sum();

        if level_1_sum != 0.0 {
            for &i in &level_1_indices {
                if let Some(val) = values[i] {
                    percentages[i] = Some(100.0 * val / level_1_sum);
                }
            }
        }
    }

    // Calculate level 2 percentages (% of parent level 1 group)
    // Iterate backwards to group level 2 rows by their level 1 parent
    let mut level_2_group: Vec<usize> = Vec::new();

    for i in (0..levels.len()).rev() {
        match levels[i] {
            Some(2) => {
                level_2_group.push(i);
            }
            Some(1) => {
                // Calculate percentage for this level 2 group
                if !level_2_group.is_empty() {
                    let group_sum: f64 = level_2_group.iter().filter_map(|&j| values[j]).sum();

                    if group_sum != 0.0 {
                        for &j in &level_2_group {
                            if let Some(val) = values[j] {
                                percentages[j] = Some(100.0 * val / group_sum);
                            }
                        }
                    }
                }
                level_2_group.clear();
            }
            _ => {}
        }
    }

    percentages
}

/// Add a percentage column to a RecordBatch.
///
/// Creates a new RecordBatch with an additional column containing percentages.
pub fn add_percentage_column(
    batch: &RecordBatch,
    value_col_name: &str,
    level_col_name: &str,
    pct_col_name: &str,
) -> Result<RecordBatch> {
    let schema = batch.schema();

    // Get value column
    let value_idx = schema
        .index_of(value_col_name)
        .map_err(|_| ExtError::MissingColumn(value_col_name.into()))?;
    let value_col = batch.column(value_idx);

    // Get level column
    let level_idx = schema
        .index_of(level_col_name)
        .map_err(|_| ExtError::MissingColumn(level_col_name.into()))?;
    let level_col = batch.column(level_idx);

    // Extract values as f64
    let values: Vec<Option<f64>> =
        if let Some(arr) = value_col.as_any().downcast_ref::<Float64Array>() {
            (0..arr.len())
                .map(|i| {
                    if arr.is_null(i) {
                        None
                    } else {
                        Some(arr.value(i))
                    }
                })
                .collect()
        } else if let Some(arr) = value_col.as_any().downcast_ref::<StringArray>() {
            (0..arr.len())
                .map(|i| {
                    if arr.is_null(i) {
                        None
                    } else {
                        arr.value(i).parse::<f64>().ok()
                    }
                })
                .collect()
        } else {
            return Err(ExtError::MissingColumn(format!(
                "{} must be numeric or string",
                value_col_name
            )));
        };

    // Extract levels as i64
    let levels: Vec<Option<i64>> =
        if let Some(arr) = level_col.as_any().downcast_ref::<StringArray>() {
            (0..arr.len())
                .map(|i| {
                    if arr.is_null(i) {
                        None
                    } else {
                        arr.value(i).parse::<i64>().ok()
                    }
                })
                .collect()
        } else {
            return Err(ExtError::MissingColumn(format!(
                "{} must be string",
                level_col_name
            )));
        };

    // Calculate percentages
    let percentages = calculate_level_percentages(&values, &levels);

    // Build new schema with percentage column
    let mut new_fields: Vec<Field> = schema.fields().iter().map(|f| f.as_ref().clone()).collect();
    new_fields.push(Field::new(pct_col_name, DataType::Float64, true));
    let new_schema = Arc::new(Schema::new(new_fields));

    // Build columns
    let mut columns: Vec<ArrayRef> = (0..batch.num_columns())
        .map(|i| batch.column(i).clone())
        .collect();
    columns.push(Arc::new(Float64Array::from(percentages)));

    RecordBatch::try_new(new_schema, columns).map_err(ExtError::Arrow)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rename_dividend_columns() {
        let columns = vec!["ticker", "Declared Date", "Ex-Date", "Unknown"];
        let renames = rename_dividend_columns(&columns);

        assert_eq!(renames.len(), 2);
        assert!(renames.contains(&("Declared Date".to_string(), "dec_date".to_string())));
        assert!(renames.contains(&("Ex-Date".to_string(), "ex_date".to_string())));
    }

    #[test]
    fn test_rename_etf_columns() {
        let columns = vec!["Holding Name", "Weight", "Unknown"];
        let renames = rename_etf_columns(&columns);

        assert_eq!(renames.len(), 2);
        assert!(renames.contains(&("Holding Name".to_string(), "name".to_string())));
        assert!(renames.contains(&("Weight".to_string(), "weight".to_string())));
    }

    #[test]
    fn test_calculate_level_percentages() {
        let values = vec![Some(100.0), Some(200.0), Some(50.0), Some(50.0)];
        let levels = vec![Some(1), Some(1), Some(2), Some(2)];

        let pcts = calculate_level_percentages(&values, &levels);

        // Level 1: 100/(100+200) = 33.33%, 200/(100+200) = 66.67%
        assert!((pcts[0].unwrap() - 33.333).abs() < 0.01);
        assert!((pcts[1].unwrap() - 66.667).abs() < 0.01);

        // Level 2: 50/(50+50) = 50%, 50/(50+50) = 50%
        assert!((pcts[2].unwrap() - 50.0).abs() < 0.01);
        assert!((pcts[3].unwrap() - 50.0).abs() < 0.01);
    }

    #[test]
    fn test_calculate_level_percentages_with_nones() {
        let values = vec![Some(100.0), None, Some(200.0)];
        let levels = vec![Some(1), Some(1), Some(1)];

        let pcts = calculate_level_percentages(&values, &levels);

        // Sum is 300 (ignoring None)
        assert!((pcts[0].unwrap() - 33.333).abs() < 0.01);
        assert!(pcts[1].is_none());
        assert!((pcts[2].unwrap() - 66.667).abs() < 0.01);
    }
}
