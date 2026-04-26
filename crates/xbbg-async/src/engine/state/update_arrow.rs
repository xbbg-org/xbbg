use std::sync::Arc;

use arrow_array::builder::{
    BooleanBuilder, Date32Builder, Float64Builder, Int32Builder, Int64Builder, StringBuilder,
    Time64MicrosecondBuilder, TimestampMicrosecondBuilder,
};
use arrow_array::{ArrayRef, RecordBatch};
use arrow_schema::{DataType, Field, Schema, TimeUnit};
use xbbg_core::BlpError;

use super::update::{FieldKind, SubscriptionUpdate, UpdateValue};

pub fn subscription_update_to_record_batch(
    update: &SubscriptionUpdate,
) -> Result<RecordBatch, BlpError> {
    let mut timestamp = TimestampMicrosecondBuilder::new();
    timestamp.append_value(update.timestamp_us);

    let mut topic = StringBuilder::new();
    topic.append_value(update.topic.as_ref());

    let mut value_by_index = vec![None; update.layout.fields.len()];
    for field in update.values.iter() {
        if let Some(slot) = value_by_index.get_mut(field.index as usize) {
            *slot = Some(&field.value);
        }
    }

    let mut fields = vec![
        Field::new(
            "timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, Some("UTC".into())),
            false,
        ),
        Field::new("topic", DataType::Utf8, false),
    ];
    let mut columns: Vec<ArrayRef> = vec![
        Arc::new(timestamp.finish().with_timezone("UTC")),
        Arc::new(topic.finish()),
    ];

    for meta in update.layout.fields.iter() {
        let value = value_by_index
            .get(meta.index as usize)
            .and_then(|value| *value);
        let kind = match value {
            Some(UpdateValue::Null) | None => meta.kind,
            Some(value) => meta.kind.merge_observed(FieldKind::from_value(value)),
        };
        fields.push(Field::new(meta.name.as_ref(), arrow_datatype(kind), true));
        columns.push(single_value_array(kind, value));
    }

    RecordBatch::try_new(Arc::new(Schema::new(fields)), columns).map_err(|err| BlpError::Internal {
        detail: format!("failed to create subscription RecordBatch: {err}"),
    })
}

fn arrow_datatype(kind: FieldKind) -> DataType {
    match kind {
        FieldKind::Unknown | FieldKind::Str => DataType::Utf8,
        FieldKind::Bool => DataType::Boolean,
        FieldKind::I32 => DataType::Int32,
        FieldKind::I64 => DataType::Int64,
        FieldKind::F64 => DataType::Float64,
        FieldKind::Date32 => DataType::Date32,
        FieldKind::Time64Micros => DataType::Time64(TimeUnit::Microsecond),
        FieldKind::TimestampMicros => {
            DataType::Timestamp(TimeUnit::Microsecond, Some("UTC".into()))
        }
    }
}

fn single_value_array(kind: FieldKind, value: Option<&UpdateValue>) -> ArrayRef {
    match kind {
        FieldKind::Bool => {
            let mut b = BooleanBuilder::new();
            match value {
                Some(UpdateValue::Bool(v)) => b.append_value(*v),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::I32 => {
            let mut b = Int32Builder::new();
            match value {
                Some(UpdateValue::I32(v)) => b.append_value(*v),
                Some(UpdateValue::I64(v)) => b.append_value(*v as i32),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::I64 => {
            let mut b = Int64Builder::new();
            match value {
                Some(UpdateValue::I64(v)) => b.append_value(*v),
                Some(UpdateValue::I32(v)) => b.append_value(*v as i64),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::F64 => {
            let mut b = Float64Builder::new();
            match value {
                Some(UpdateValue::F64(v)) => b.append_value(*v),
                Some(UpdateValue::I32(v)) => b.append_value(*v as f64),
                Some(UpdateValue::I64(v)) => b.append_value(*v as f64),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::Date32 => {
            let mut b = Date32Builder::new();
            match value {
                Some(UpdateValue::Date32(v)) => b.append_value(*v),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::Time64Micros => {
            let mut b = Time64MicrosecondBuilder::new();
            match value {
                Some(UpdateValue::Time64Micros(v)) => b.append_value(*v),
                _ => b.append_null(),
            }
            Arc::new(b.finish())
        }
        FieldKind::TimestampMicros => {
            let mut b = TimestampMicrosecondBuilder::new();
            match value {
                Some(UpdateValue::TimestampMicros(v)) => b.append_value(*v),
                _ => b.append_null(),
            }
            Arc::new(b.finish().with_timezone("UTC"))
        }
        FieldKind::Unknown | FieldKind::Str => {
            let mut b = StringBuilder::new();
            match value.and_then(UpdateValue::as_string_lossy) {
                Some(v) => b.append_value(&v),
                None => b.append_null(),
            }
            Arc::new(b.finish())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::state::update::{FieldLayout, FieldMeta, UpdateField};

    #[test]
    fn arrow_adapter_null_fills_sparse_layout() {
        let layout = Arc::new(FieldLayout::new(
            2,
            vec![
                FieldMeta::new("BID", 0, FieldKind::F64),
                FieldMeta::new("ASK", 1, FieldKind::F64),
            ],
        ));
        let update = SubscriptionUpdate {
            timestamp_us: 10,
            topic_id: 1,
            topic: Arc::from("IBM US Equity"),
            layout,
            values: vec![UpdateField {
                index: 0,
                value: UpdateValue::F64(1.25),
            }]
            .into_boxed_slice(),
        };

        let batch = subscription_update_to_record_batch(&update).unwrap();
        assert_eq!(batch.num_rows(), 1);
        assert_eq!(batch.num_columns(), 4);
        assert_eq!(batch.schema().field(2).name(), "BID");
        assert_eq!(batch.schema().field(3).name(), "ASK");
    }
}
