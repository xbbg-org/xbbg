//! Arrow-backed column carrier data.

use arrow_array::ArrayRef;
use arrow_schema::FieldRef;

use crate::error::{ArrowCoreError, Result};

/// A logical Arrow column made of one or more chunks.
#[derive(Clone, Debug)]
pub struct ColumnData {
    /// Column name as exposed by the table schema.
    pub name: String,
    /// Arrow field metadata for this column.
    pub field: FieldRef,
    /// Physical array chunks for this logical column.
    pub chunks: Vec<ArrayRef>,
}

impl ColumnData {
    /// Create column data from field and chunk arrays.
    pub fn new(name: String, field: FieldRef, chunks: Vec<ArrayRef>) -> Result<Self> {
        for chunk in &chunks {
            if chunk.data_type() != field.data_type() {
                return Err(ArrowCoreError::Arrow(
                    arrow_schema::ArrowError::SchemaError(format!(
                        "column {name} chunk type {} does not match field type {}",
                        chunk.data_type(),
                        field.data_type()
                    )),
                ));
            }
        }
        Ok(Self {
            name,
            field,
            chunks,
        })
    }

    /// Number of logical values across all chunks.
    pub fn len(&self) -> usize {
        self.chunks.iter().map(|chunk| chunk.len()).sum()
    }

    /// Whether the column contains no logical values.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Total physical null count across all chunks.
    pub fn null_count(&self) -> usize {
        self.chunks.iter().map(|chunk| chunk.null_count()).sum()
    }

    /// Approximate bytes referenced by this column's Arrow buffers.
    pub fn nbytes(&self) -> usize {
        self.chunks
            .iter()
            .map(|chunk| chunk.get_buffer_memory_size())
            .sum()
    }

    /// Return the chunk and local index for a logical row index.
    pub fn chunk_for_index(&self, index: usize) -> Result<(&ArrayRef, usize)> {
        let mut offset = 0;
        for chunk in &self.chunks {
            let end = offset + chunk.len();
            if index < end {
                return Ok((chunk, index - offset));
            }
            offset = end;
        }
        Err(ArrowCoreError::RowIndexOutOfRange)
    }

    /// Return a zero-copy slice of this logical column.
    pub fn slice(&self, offset: usize, length: Option<usize>) -> Self {
        let total = self.len();
        if offset >= total {
            return Self {
                name: self.name.clone(),
                field: self.field.clone(),
                chunks: Vec::new(),
            };
        }

        let mut remaining = length.unwrap_or(total - offset).min(total - offset);
        let mut skipped = 0;
        let mut chunks = Vec::new();
        for chunk in &self.chunks {
            if remaining == 0 {
                break;
            }
            let chunk_len = chunk.len();
            if skipped + chunk_len <= offset {
                skipped += chunk_len;
                continue;
            }
            let local_offset = offset.saturating_sub(skipped);
            let take = remaining.min(chunk_len - local_offset);
            chunks.push(chunk.slice(local_offset, take));
            remaining -= take;
            skipped += chunk_len;
        }

        Self {
            name: self.name.clone(),
            field: self.field.clone(),
            chunks,
        }
    }
}
