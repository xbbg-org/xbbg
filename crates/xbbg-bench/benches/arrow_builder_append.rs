//! Offline Arrow builder append/finalize benchmarks.
//!
//! Pure Rust only: no Bloomberg session, network, datamock, or production hot-path changes.
//!
//! Run after wiring this bench target:
//!   ARROW_BENCH_ROWS=100000 ARROW_BENCH_ITERATIONS=5 \
//!     cargo bench --package xbbg-bench --bench arrow_builder_append

use std::collections::HashMap;
use std::fmt::Write as _;
use std::hint::black_box;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use arrow_array::{ ArrayRef, Float64Array };
use arrow_schema::{ DataType, Field, Schema };
use arrow_array::RecordBatch;
use xbbg_async::engine::state::typed_builder::{ArrowType, TypedBuilder};
use xbbg_core::Value;

const DEFAULT_ROWS: usize = 100_000;
const DEFAULT_ITERATIONS: usize = 5;

struct ColumnSet {
    fields: Vec<String>,
    indices: HashMap<String, usize>,
    builders: Vec<TypedBuilder>,
    present: Vec<bool>,
    rows: usize,
}

impl ColumnSet {
    fn with_type_hints<I>(hints: I) -> Self
    where
        I: IntoIterator<Item = (String, ArrowType)>,
    {
        let mut fields = Vec::new();
        let mut indices = HashMap::new();
        let mut builders = Vec::new();

        for (field, arrow_type) in hints {
            if indices.contains_key(&field) {
                continue;
            }
            let idx = fields.len();
            indices.insert(field.clone(), idx);
            fields.push(field);
            builders.push(TypedBuilder::new(arrow_type));
        }

        let present = vec![false; fields.len()];
        Self {
            fields,
            indices,
            builders,
            present,
            rows: 0,
        }
    }

    fn append(&mut self, field: &str, value: Value<'_>) {
        let idx = *self
            .indices
            .get(field)
            .expect("benchmark field should have a type hint");
        self.builders[idx].append_value(Some(value));
        self.present[idx] = true;
    }

    fn end_row(&mut self) {
        for (idx, builder) in self.builders.iter_mut().enumerate() {
            if !self.present[idx] {
                builder.append_null();
            }
        }
        self.present.fill(false);
        self.rows += 1;
    }

    fn finish(mut self) -> Result<RecordBatch, arrow::error::ArrowError> {
        let mut fields = Vec::with_capacity(self.fields.len());
        let mut arrays = Vec::with_capacity(self.fields.len());

        for (name, builder) in self.fields.iter().zip(self.builders.iter_mut()) {
            fields.push(Field::new(name.as_str(), builder.data_type(), true));
            arrays.push(builder.finish());
        }

        RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)
    }

    fn finish_with_order(
        mut self,
        order: &[&str],
    ) -> Result<RecordBatch, arrow::error::ArrowError> {
        let mut fields = Vec::with_capacity(order.len());
        let mut arrays = Vec::with_capacity(order.len());

        for &name in order {
            let idx = *self
                .indices
                .get(name)
                .expect("benchmark output order should reference an existing field");
            fields.push(Field::new(name, self.builders[idx].data_type(), true));
            arrays.push(self.builders[idx].finish());
        }

        RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)
    }
}

#[derive(Clone, Debug)]
struct BenchResult {
    name: &'static str,
    rows: usize,
    columns: usize,
    iterations: usize,
    values_per_iteration: usize,
    best_ns: u128,
    avg_ns: u128,
    rows_per_second: f64,
    values_per_second: f64,
}

fn main() {
    let rows = env_usize("ARROW_BENCH_ROWS", DEFAULT_ROWS);
    let iterations = env_usize("ARROW_BENCH_ITERATIONS", DEFAULT_ITERATIONS);

    let scenarios: &[(&str, usize, fn(usize) -> usize)] = &[
        ("dense_float64", 1, bench_dense_float64),
        ("sparse_float64_null", 1, bench_sparse_float64_null),
        ("dense_string", 1, bench_dense_string),
        ("mixed_5_column_rows", 5, bench_mixed_5_column_rows),
        ("wide_100_column_rows", 100, bench_wide_100_column_rows),
        (
            "late_column_null_backfill",
            2,
            bench_late_column_null_backfill,
        ),
        (
            "record_batch_finalization",
            5,
            bench_record_batch_finalization,
        ),
    ];

    let mut results = Vec::with_capacity(scenarios.len());
    for &(name, columns, scenario) in scenarios {
        results.push(run_scenario(name, rows, columns, iterations, scenario));
    }

    print_table(&results);
    write_results(&results, rows, iterations);
}

fn env_usize(name: &str, default: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .filter(|value| *value > 0)
        .unwrap_or(default)
}

fn run_scenario(
    name: &'static str,
    rows: usize,
    columns: usize,
    iterations: usize,
    scenario: fn(usize) -> usize,
) -> BenchResult {
    let mut timings = Vec::with_capacity(iterations);
    let mut values_per_iteration = 0;

    for _ in 0..iterations {
        let started = Instant::now();
        values_per_iteration = scenario(rows);
        timings.push(started.elapsed());
    }

    let best = timings.iter().copied().min().unwrap_or(Duration::ZERO);
    let total_ns: u128 = timings.iter().map(Duration::as_nanos).sum();
    let avg_ns = total_ns / iterations as u128;
    let avg_secs = avg_ns as f64 / 1_000_000_000.0;

    BenchResult {
        name,
        rows,
        columns,
        iterations,
        values_per_iteration,
        best_ns: best.as_nanos(),
        avg_ns,
        rows_per_second: rows as f64 / avg_secs,
        values_per_second: values_per_iteration as f64 / avg_secs,
    }
}

fn bench_dense_float64(rows: usize) -> usize {
    let mut builder = TypedBuilder::new(ArrowType::Float64);
    for row in 0..rows {
        builder.append_value(Some(Value::Float64(row as f64 * 0.25)));
    }

    let array = builder.finish();
    black_box(array.len());
    rows
}

fn bench_sparse_float64_null(rows: usize) -> usize {
    let mut builder = TypedBuilder::new(ArrowType::Float64);
    for row in 0..rows {
        if row % 10 == 0 {
            builder.append_null();
        } else {
            builder.append_value(Some(Value::Float64(row as f64 * 0.5)));
        }
    }

    let array = builder.finish();
    black_box(array.null_count());
    rows
}

fn bench_dense_string(rows: usize) -> usize {
    let values: Vec<String> = (0..1024).map(|idx| format!("SECURITY_{idx:04}")).collect();
    let mut builder = TypedBuilder::new(ArrowType::String);

    for row in 0..rows {
        builder.append_value(Some(Value::String(values[row & 1023].as_str())));
    }

    let array = builder.finish();
    black_box(array.len());
    rows
}

fn bench_mixed_5_column_rows(rows: usize) -> usize {
    let mut cols = ColumnSet::with_type_hints([
        ("ticker".to_string(), ArrowType::String),
        ("px_last".to_string(), ArrowType::Float64),
        ("volume".to_string(), ArrowType::Int64),
        ("is_active".to_string(), ArrowType::Bool),
        ("trade_date".to_string(), ArrowType::Date32),
    ]);

    for row in 0..rows {
        cols.append("ticker", Value::String("AAPL US Equity"));
        cols.append("px_last", Value::Float64(150.0 + row as f64 * 0.01));
        cols.append("volume", Value::Int64(1_000_000 + row as i64));
        cols.append("is_active", Value::Bool(row % 2 == 0));
        cols.append("trade_date", Value::Date32(19_000 + (row % 250) as i32));
        cols.end_row();
    }

    let batch = cols.finish().expect("mixed rows should build RecordBatch");
    black_box(batch.num_columns());
    rows * 5
}

fn bench_wide_100_column_rows(rows: usize) -> usize {
    let hints = (0..100).map(|col| (format!("px_{col:03}"), ArrowType::Float64));
    let mut cols = ColumnSet::with_type_hints(hints);
    let names: Vec<String> = (0..100).map(|col| format!("px_{col:03}")).collect();

    for row in 0..rows {
        for (col, name) in names.iter().enumerate() {
            cols.append(name, Value::Float64(row as f64 + col as f64));
        }
        cols.end_row();
    }

    let batch = cols.finish().expect("wide rows should build RecordBatch");
    black_box(batch.num_columns());
    rows * 100
}

fn bench_late_column_null_backfill(rows: usize) -> usize {
    let mut cols = ColumnSet::with_type_hints([
        ("px_last".to_string(), ArrowType::Float64),
        ("late_string".to_string(), ArrowType::String),
    ]);
    let late_at = rows / 2;

    for row in 0..rows {
        cols.append("px_last", Value::Float64(row as f64));
        if row >= late_at {
            cols.append("late_string", Value::String("late"));
        }
        cols.end_row();
    }

    let batch = cols
        .finish_with_order(&["px_last", "late_string"])
        .expect("late column should backfill nulls and build RecordBatch");
    black_box(batch.column(1).null_count());
    rows * 2
}

fn bench_record_batch_finalization(rows: usize) -> usize {
    let mut fields = Vec::with_capacity(5);
    let mut arrays = Vec::with_capacity(5);

    for col in 0..5 {
        let mut builder = TypedBuilder::new(ArrowType::Float64);
        for row in 0..rows {
            builder.append_value(Some(Value::Float64(row as f64 + col as f64)));
        }
        fields.push(Field::new(format!("value_{col}"), DataType::Float64, true));
        arrays.push(builder.finish());
    }

    let schema = Arc::new(Schema::new(fields));
    let batch = RecordBatch::try_new(schema, arrays).expect("arrays should share row count");
    black_box(batch.num_rows());
    rows * 5
}

#[allow(dead_code)]
fn direct_arrow_record_batch(rows: usize) -> RecordBatch {
    let array: ArrayRef = Arc::new(Float64Array::from_iter_values(
        (0..rows).map(|row| row as f64),
    ));
    let schema = Arc::new(Schema::new(vec![Field::new(
        "value",
        DataType::Float64,
        false,
    )]));
    RecordBatch::try_new(schema, vec![array]).expect("direct Arrow batch should be valid")
}

fn print_table(results: &[BenchResult]) {
    println!(
        "{:<30} {:>10} {:>8} {:>12} {:>14} {:>14} {:>14}",
        "scenario", "rows", "cols", "avg_ms", "best_ms", "rows/s", "values/s"
    );
    println!("{}", "-".repeat(110));

    for result in results {
        println!(
            "{:<30} {:>10} {:>8} {:>12.3} {:>14.3} {:>14.0} {:>14.0}",
            result.name,
            result.rows,
            result.columns,
            nanos_to_millis(result.avg_ns),
            nanos_to_millis(result.best_ns),
            result.rows_per_second,
            result.values_per_second,
        );
    }
}

fn nanos_to_millis(ns: u128) -> f64 {
    ns as f64 / 1_000_000.0
}

fn write_results(results: &[BenchResult], rows: usize, iterations: usize) {
    let timestamp = unix_timestamp();
    let json = results_json(results, rows, iterations, timestamp);
    let dir = PathBuf::from("benchmarks/results");
    let timestamped = dir.join(format!("arrow_builder_append_{timestamp}.json"));
    let latest = dir.join("arrow_builder_append_latest.json");

    xbbg_bench::write_json(&timestamped, &json);
    xbbg_bench::write_json(&latest, &json);
}

fn unix_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock should be after Unix epoch")
        .as_secs()
}

fn results_json(results: &[BenchResult], rows: usize, iterations: usize, timestamp: u64) -> String {
    let mut json = String::new();
    writeln!(&mut json, "{{").unwrap();
    writeln!(&mut json, "  \"benchmark\": \"arrow_builder_append\",").unwrap();
    writeln!(&mut json, "  \"timestamp_unix\": {timestamp},").unwrap();
    writeln!(&mut json, "  \"rows\": {rows},").unwrap();
    writeln!(&mut json, "  \"iterations\": {iterations},").unwrap();
    writeln!(&mut json, "  \"results\": [").unwrap();

    for (idx, result) in results.iter().enumerate() {
        let comma = if idx + 1 == results.len() { "" } else { "," };
        writeln!(&mut json, "    {{").unwrap();
        writeln!(
            &mut json,
            "      \"name\": \"{}\",",
            json_escape(result.name)
        )
        .unwrap();
        writeln!(&mut json, "      \"rows\": {},", result.rows).unwrap();
        writeln!(&mut json, "      \"columns\": {},", result.columns).unwrap();
        writeln!(&mut json, "      \"iterations\": {},", result.iterations).unwrap();
        writeln!(
            &mut json,
            "      \"values_per_iteration\": {},",
            result.values_per_iteration
        )
        .unwrap();
        writeln!(&mut json, "      \"best_ns\": {},", result.best_ns).unwrap();
        writeln!(&mut json, "      \"avg_ns\": {},", result.avg_ns).unwrap();
        writeln!(
            &mut json,
            "      \"rows_per_second\": {:.3},",
            result.rows_per_second
        )
        .unwrap();
        writeln!(
            &mut json,
            "      \"values_per_second\": {:.3}",
            result.values_per_second
        )
        .unwrap();
        writeln!(&mut json, "    }}{comma}").unwrap();
    }

    writeln!(&mut json, "  ]").unwrap();
    writeln!(&mut json, "}}").unwrap();
    json
}

fn json_escape(value: &str) -> String {
    value
        .chars()
        .flat_map(|ch| match ch {
            '"' => "\\\"".chars().collect::<Vec<_>>(),
            '\\' => "\\\\".chars().collect::<Vec<_>>(),
            '\n' => "\\n".chars().collect::<Vec<_>>(),
            '\r' => "\\r".chars().collect::<Vec<_>>(),
            '\t' => "\\t".chars().collect::<Vec<_>>(),
            _ => vec![ch],
        })
        .collect()
}
