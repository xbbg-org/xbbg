//! Arrow table carrier data and pure table operations.

use std::collections::{HashMap, HashSet};
use std::str::FromStr;
use std::sync::Arc;

use arrow_array::{ArrayRef, BooleanArray, RecordBatch, RecordBatchOptions, StringArray};
use arrow_ord::sort::{lexsort_to_indices, SortColumn, SortOptions};
use arrow_schema::{DataType, Field, FieldRef, Schema, SchemaRef};
use arrow_select::concat::concat_batches;
use arrow_select::filter::filter_record_batch;
use arrow_select::take::take_record_batch;

use crate::column::ColumnData;
use crate::error::{ArrowCoreError, Result};
use crate::scalar::{build_array, cell_matches, cell_to_string, CellValue};

/// Sort direction for Arrow table sorting.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SortDirection {
    Ascending,
    Descending,
}

impl SortDirection {
    /// Whether this direction is descending for arrow-rs sort options.
    pub fn is_descending(self) -> bool {
        matches!(self, Self::Descending)
    }
}

impl FromStr for SortDirection {
    type Err = ();

    fn from_str(value: &str) -> std::result::Result<Self, Self::Err> {
        match value.to_ascii_lowercase().as_str() {
            "asc" | "ascending" => Ok(Self::Ascending),
            "desc" | "descending" => Ok(Self::Descending),
            _ => Err(()),
        }
    }
}

/// A logical Arrow table made of schema-compatible record batches.
#[derive(Clone, Debug)]
pub struct TableData {
    /// Physical Arrow record batches.
    pub batches: Vec<RecordBatch>,
    /// Shared logical table schema.
    pub schema: SchemaRef,
}

impl TableData {
    /// Create a table from record batches that all share one schema.
    pub fn try_new(batches: Vec<RecordBatch>) -> Result<Self> {
        let schema = table_schema(&batches);
        for batch in &batches {
            ensure_compatible_schema(&schema, batch)?;
        }
        Ok(Self { batches, schema })
    }

    /// Create an empty table with UTF-8 columns by name.
    pub fn empty_from_columns(columns: Vec<String>) -> Result<Self> {
        let fields = columns
            .iter()
            .map(|name| Field::new(name, DataType::Utf8, true))
            .collect::<Vec<_>>();
        let arrays = columns
            .iter()
            .map(|_| Arc::new(StringArray::from(Vec::<Option<String>>::new())) as ArrayRef)
            .collect::<Vec<_>>();
        let batch = RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?;
        Self::try_new(vec![batch])
    }

    /// Concatenate logical tables by appending their batches.
    pub fn concat_tables(tables: &[Self]) -> Result<Self> {
        let mut batches = Vec::new();
        let mut expected_schema: Option<SchemaRef> = None;
        for table in tables {
            if let Some(schema) = &expected_schema {
                if table.schema != *schema {
                    return Err(ArrowCoreError::IncompatibleTableSchemas);
                }
            } else {
                expected_schema = Some(table.schema.clone());
            }
            batches.extend(table.batches.iter().cloned());
        }
        Self::try_new(batches)
    }

    /// Total number of rows.
    pub fn num_rows(&self) -> usize {
        self.batches.iter().map(RecordBatch::num_rows).sum()
    }

    /// Total number of columns.
    pub fn num_columns(&self) -> usize {
        self.schema.fields().len()
    }

    /// `(num_rows, num_columns)`.
    pub fn shape(&self) -> (usize, usize) {
        (self.num_rows(), self.num_columns())
    }

    /// Approximate bytes referenced by all Arrow column buffers.
    pub fn nbytes(&self) -> usize {
        self.batches
            .iter()
            .flat_map(|batch| batch.columns())
            .map(|array| array.get_buffer_memory_size())
            .sum()
    }

    /// Row count for each physical chunk/batch.
    pub fn chunk_lengths(&self) -> Vec<usize> {
        self.batches.iter().map(RecordBatch::num_rows).collect()
    }

    /// Column names in schema order.
    pub fn column_names(&self) -> Vec<String> {
        self.schema
            .fields()
            .iter()
            .map(|field| field.name().clone())
            .collect()
    }

    /// Find a column index by name.
    pub fn column_index(&self, name: &str) -> Result<usize> {
        self.schema
            .index_of(name)
            .map_err(|_| ArrowCoreError::UnknownColumn(name.to_string()))
    }

    /// Field for a column index.
    pub fn field(&self, index: usize) -> Result<FieldRef> {
        self.schema
            .fields()
            .get(index)
            .cloned()
            .ok_or(ArrowCoreError::ColumnIndexOutOfRange)
    }

    /// Extract a logical column by index.
    pub fn column_by_index(&self, index: usize) -> Result<ColumnData> {
        let field = self.field(index)?;
        let name = field.name().clone();
        let chunks = self
            .batches
            .iter()
            .map(|batch| batch.column(index).clone())
            .collect::<Vec<_>>();
        ColumnData::new(name, field, chunks)
    }

    /// Extract a logical column by name.
    pub fn column_by_name(&self, name: &str) -> Result<ColumnData> {
        self.column_by_index(self.column_index(name)?)
    }

    /// Select columns by name.
    pub fn select_names(&self, names: &[String]) -> Result<Self> {
        let indices = names
            .iter()
            .map(|name| self.column_index(name))
            .collect::<Result<Vec<_>>>()?;
        self.select_indices(&indices)
    }

    /// Select columns by index.
    pub fn select_indices(&self, indices: &[usize]) -> Result<Self> {
        let projected = self
            .batches
            .iter()
            .map(|batch| select_batch(batch, indices))
            .collect::<Result<Vec<_>>>()?;
        Self::try_new(projected)
    }

    /// Drop named columns; unknown names are ignored to preserve existing xbbg behavior.
    pub fn drop_columns(&self, names: &[String]) -> Result<Self> {
        let drop = names.iter().collect::<HashSet<_>>();
        let keep = self
            .column_names()
            .into_iter()
            .filter(|name| !drop.contains(name))
            .collect::<Vec<_>>();
        self.select_names(&keep)
    }

    /// Rename columns by mapping existing names to new names.
    pub fn rename_columns(&self, mapping: &HashMap<String, String>) -> Result<Self> {
        let renamed = self
            .batches
            .iter()
            .map(|batch| rename_batch(batch, mapping))
            .collect::<Result<Vec<_>>>()?;
        Self::try_new(renamed)
    }

    /// Return a zero-copy row slice across physical batches.
    pub fn slice(&self, offset: usize, length: Option<usize>) -> Result<Self> {
        let total = self.num_rows();
        if offset >= total || length == Some(0) {
            return Self::try_new(vec![RecordBatch::new_empty(self.schema.clone())]);
        }

        let mut remaining = length.unwrap_or(total - offset).min(total - offset);
        let mut skipped = 0;
        let mut out = Vec::new();
        for batch in &self.batches {
            if remaining == 0 {
                break;
            }
            let batch_rows = batch.num_rows();
            if skipped + batch_rows <= offset {
                skipped += batch_rows;
                continue;
            }
            let local_offset = offset.saturating_sub(skipped);
            let take = remaining.min(batch_rows - local_offset);
            out.push(batch.slice(local_offset, take));
            remaining -= take;
            skipped += batch_rows;
        }
        Self::try_new(out)
    }

    /// Return the first `n` rows.
    pub fn head(&self, n: usize) -> Result<Self> {
        self.slice(0, Some(n))
    }

    /// Return the last `n` rows.
    pub fn tail(&self, n: usize) -> Result<Self> {
        let rows = self.num_rows();
        if n >= rows {
            return Ok(self.clone());
        }
        self.slice(rows - n, Some(n))
    }

    /// Materialize batches as one batch when multiple chunks are present.
    pub fn combined_batch(&self) -> Result<RecordBatch> {
        if self.batches.len() == 1 {
            return Ok(self.batches[0].clone());
        }
        concat_batches(&self.schema, self.batches.iter()).map_err(Into::into)
    }

    /// Sort rows by named columns.
    pub fn sort_by(&self, sort_keys: &[(String, SortDirection)]) -> Result<Self> {
        if sort_keys.is_empty() || self.num_rows() == 0 {
            return Ok(self.clone());
        }
        let batch = self.combined_batch()?;
        let schema = batch.schema();
        let columns = sort_keys
            .iter()
            .map(|(name, direction)| {
                let idx = schema
                    .index_of(name)
                    .map_err(|_| ArrowCoreError::UnknownColumn(name.clone()))?;
                Ok(SortColumn {
                    values: batch.column(idx).clone(),
                    options: Some(SortOptions {
                        descending: direction.is_descending(),
                        nulls_first: false,
                    }),
                })
            })
            .collect::<Result<Vec<_>>>()?;
        let indices = lexsort_to_indices(&columns, None)?;
        let sorted = take_record_batch(&batch, &indices)?;
        Self::try_new(vec![sorted])
    }

    /// Filter rows where a column equals a scalar value.
    pub fn filter_eq(&self, column: &str, value: &CellValue) -> Result<Self> {
        let idx = self.column_index(column)?;
        let filtered = self
            .batches
            .iter()
            .map(|batch| {
                let mask = BooleanArray::from(
                    (0..batch.num_rows())
                        .map(|row| cell_matches(batch.column(idx).as_ref(), row, value))
                        .collect::<Vec<_>>(),
                );
                filter_record_batch(batch, &mask).map_err(Into::into)
            })
            .collect::<Result<Vec<_>>>()?;
        Self::try_new(filtered)
    }

    /// Insert a scalar-built column at `index`.
    pub fn add_column(&self, index: usize, name: &str, cells: &[CellValue]) -> Result<Self> {
        self.with_cells_column(index, name, cells, false, false)
    }

    /// Replace a scalar-built column at `index`.
    pub fn set_column(&self, index: usize, name: &str, cells: &[CellValue]) -> Result<Self> {
        self.with_cells_column(index, name, cells, true, false)
    }

    /// Insert or replace a column, optionally forcing UTF-8 output.
    pub fn with_cells_column(
        &self,
        index: usize,
        name: &str,
        cells: &[CellValue],
        replace: bool,
        force_text: bool,
    ) -> Result<Self> {
        let max_index = self.num_columns();
        if replace {
            if index >= max_index {
                return Err(ArrowCoreError::ColumnIndexOutOfRange);
            }
        } else if index > max_index {
            return Err(ArrowCoreError::ColumnIndexOutOfRange);
        }

        let chunks = split_cells_for_batches(cells, &self.batches)?;
        let mut out = Vec::with_capacity(self.batches.len());
        for (batch, chunk) in self.batches.iter().zip(chunks.iter()) {
            let (field, array) = if force_text {
                let values: Vec<Option<String>> = chunk.iter().map(cell_to_string).collect();
                (
                    Field::new(name, DataType::Utf8, true),
                    Arc::new(StringArray::from(values)) as ArrayRef,
                )
            } else {
                build_array(name, chunk)
            };
            let mut fields = batch
                .schema()
                .fields()
                .iter()
                .map(|field| field.as_ref().clone())
                .collect::<Vec<_>>();
            let mut columns = batch.columns().to_vec();
            if replace {
                fields[index] = field;
                columns[index] = array;
            } else {
                fields.insert(index, field);
                columns.insert(index, array);
            }
            out.push(RecordBatch::try_new(
                Arc::new(Schema::new_with_metadata(
                    fields,
                    batch.schema().metadata().clone(),
                )),
                columns,
            )?);
        }
        Self::try_new(out)
    }
}

fn table_schema(batches: &[RecordBatch]) -> SchemaRef {
    batches
        .first()
        .map(|batch| batch.schema())
        .unwrap_or_else(|| Arc::new(Schema::empty()))
}

fn ensure_compatible_schema(expected: &SchemaRef, batch: &RecordBatch) -> Result<()> {
    if batch.schema_ref() != expected {
        return Err(ArrowCoreError::IncompatibleSchemas);
    }
    Ok(())
}

fn select_batch(batch: &RecordBatch, indices: &[usize]) -> Result<RecordBatch> {
    let schema = batch.schema();
    let mut fields = Vec::with_capacity(indices.len());
    let mut columns = Vec::with_capacity(indices.len());
    for &idx in indices {
        let field = schema
            .fields()
            .get(idx)
            .cloned()
            .ok_or(ArrowCoreError::ColumnIndexOutOfRange)?;
        fields.push(field.as_ref().clone());
        columns.push(batch.column(idx).clone());
    }
    let projected_schema = Arc::new(Schema::new_with_metadata(fields, schema.metadata().clone()));
    let options = RecordBatchOptions::new().with_row_count(Some(batch.num_rows()));
    RecordBatch::try_new_with_options(projected_schema, columns, &options).map_err(Into::into)
}

fn rename_batch(batch: &RecordBatch, mapping: &HashMap<String, String>) -> Result<RecordBatch> {
    let schema = batch.schema();
    let fields = schema
        .fields()
        .iter()
        .map(|field| {
            mapping
                .get(field.name().as_str())
                .map(|new_name| field.as_ref().clone().with_name(new_name))
                .unwrap_or_else(|| field.as_ref().clone())
        })
        .collect::<Vec<_>>();
    RecordBatch::try_new(
        Arc::new(Schema::new_with_metadata(fields, schema.metadata().clone())),
        batch.columns().to_vec(),
    )
    .map_err(Into::into)
}

/// Split one logical column's cells across the table's physical batches.
pub fn split_cells_for_batches(
    cells: &[CellValue],
    batches: &[RecordBatch],
) -> Result<Vec<Vec<CellValue>>> {
    let expected = batches.iter().map(RecordBatch::num_rows).sum::<usize>();
    if cells.len() != expected {
        return Err(ArrowCoreError::ColumnLengthMismatch {
            actual: cells.len(),
            expected,
        });
    }
    let mut offset = 0;
    Ok(batches
        .iter()
        .map(|batch| {
            let end = offset + batch.num_rows();
            let chunk = cells[offset..end].to_vec();
            offset = end;
            chunk
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use arrow_array::{Float64Array, Int64Array, RecordBatch, StringArray};
    use arrow_schema::{DataType, Field, Schema};

    use super::*;

    fn sample_table() -> TableData {
        let schema = Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, true),
            Field::new("px_last", DataType::Float64, true),
            Field::new("volume", DataType::Int64, true),
        ]));
        let batch = RecordBatch::try_new(
            schema,
            vec![
                Arc::new(StringArray::from(vec!["MSFT", "AAPL", "IBM"])) as ArrayRef,
                Arc::new(Float64Array::from(vec![380.0, 150.0, 190.0])) as ArrayRef,
                Arc::new(Int64Array::from(vec![2_i64, 3, 1])) as ArrayRef,
            ],
        )
        .unwrap();
        TableData::try_new(vec![batch]).unwrap()
    }

    #[test]
    fn selects_drops_and_renames_columns() {
        let table = sample_table();
        let selected = table
            .select_names(&["ticker".to_string(), "volume".to_string()])
            .unwrap();
        assert_eq!(selected.column_names(), ["ticker", "volume"]);

        let dropped = table.drop_columns(&["volume".to_string()]).unwrap();
        assert_eq!(dropped.column_names(), ["ticker", "px_last"]);

        let renamed = table
            .rename_columns(&HashMap::from([(
                "px_last".to_string(),
                "last".to_string(),
            )]))
            .unwrap();
        assert_eq!(renamed.column_names(), ["ticker", "last", "volume"]);
    }

    #[test]
    fn slices_head_and_tail_across_batches() {
        let table = sample_table();
        assert_eq!(table.slice(1, Some(1)).unwrap().num_rows(), 1);
        assert_eq!(table.head(2).unwrap().num_rows(), 2);
        assert_eq!(table.tail(2).unwrap().num_rows(), 2);
        assert_eq!(table.slice(99, None).unwrap().chunk_lengths(), [0]);
    }

    #[test]
    fn extracts_column_chunks_without_materializing_python_values() {
        let table = sample_table();
        let column = table.column_by_name("ticker").unwrap();
        assert_eq!(column.name, "ticker");
        assert_eq!(column.len(), 3);
        assert_eq!(column.null_count(), 0);
        assert_eq!(column.chunk_for_index(2).unwrap().1, 2);
    }

    #[test]
    fn filters_and_sorts_rows() {
        let table = sample_table();
        let filtered = table
            .filter_eq("ticker", &CellValue::Text("AAPL".to_string()))
            .unwrap();
        assert_eq!(filtered.num_rows(), 1);

        let sorted = table
            .sort_by(&[("volume".to_string(), SortDirection::Ascending)])
            .unwrap();
        let column = sorted.column_by_name("ticker").unwrap();
        let (chunk, _) = column.chunk_for_index(0).unwrap();
        let values = chunk.as_any().downcast_ref::<StringArray>().unwrap();
        assert_eq!(values.value(0), "IBM");
    }

    #[test]
    fn adds_and_sets_cell_columns() {
        let table = sample_table();
        let added = table
            .add_column(
                1,
                "side",
                &[
                    CellValue::Text("B".to_string()),
                    CellValue::Text("A".to_string()),
                    CellValue::Text("I".to_string()),
                ],
            )
            .unwrap();
        assert_eq!(
            added.column_names(),
            ["ticker", "side", "px_last", "volume"]
        );

        let replaced = added
            .set_column(
                1,
                "side2",
                &[
                    CellValue::Text("buy".to_string()),
                    CellValue::Text("ask".to_string()),
                    CellValue::Text("indic".to_string()),
                ],
            )
            .unwrap();
        assert_eq!(
            replaced.column_names(),
            ["ticker", "side2", "px_last", "volume"]
        );
    }
}
