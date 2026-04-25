//! One-command xbbg benchmark suite.
//!
//! Runs tiny live Bloomberg probes plus large synthetic workloads in one report.
//! Live probes intentionally keep Bloomberg data usage low; synthetic workloads
//! provide scale without additional Bloomberg requests.

use std::fs;
use std::hint::black_box;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use arrow::array::{ArrayRef, Float64Array, Int64Array, StringArray, TimestampMicrosecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{Datelike, Duration as ChronoDuration, Local, NaiveDate, Weekday};
use std::sync::Arc;
use tokio::runtime::Runtime;
use xbbg_async::BlpAsyncError;
use xbbg_async::engine::{Engine, EngineConfig, ExtractorType, RequestParams, ServerAddr, Transport};

#[derive(Clone, Copy, Debug)]
enum BenchProfile {
    Smoke,
    Standard,
    Stress,
}

impl BenchProfile {
    fn from_env() -> Self {
        match std::env::var("BENCH_PROFILE")
            .unwrap_or_else(|_| "standard".to_string())
            .to_ascii_lowercase()
            .as_str()
        {
            "smoke" => Self::Smoke,
            "stress" => Self::Stress,
            _ => Self::Standard,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Smoke => "smoke",
            Self::Standard => "standard",
            Self::Stress => "stress",
        }
    }

    fn synthetic_shape(self) -> SyntheticShape {
        match self {
            Self::Smoke => SyntheticShape {
                bdp_securities: 1_000,
                bdp_fields: 5,
                bdh_securities: 100,
                bdh_dates: 20,
                bdh_fields: 3,
                bdtick_ticks: 100_000,
                bql_rows: 10_000,
                bql_columns: 10,
                sub_messages: 100_000,
                sub_topics: 10,
                sub_fields: 3,
            },
            Self::Standard => SyntheticShape {
                bdp_securities: 10_000,
                bdp_fields: 10,
                bdh_securities: 1_000,
                bdh_dates: 252,
                bdh_fields: 3,
                bdtick_ticks: 1_000_000,
                bql_rows: 100_000,
                bql_columns: 10,
                sub_messages: 1_000_000,
                sub_topics: 100,
                sub_fields: 3,
            },
            Self::Stress => SyntheticShape {
                bdp_securities: 100_000,
                bdp_fields: 20,
                bdh_securities: 10_000,
                bdh_dates: 252,
                bdh_fields: 5,
                bdtick_ticks: 10_000_000,
                bql_rows: 1_000_000,
                bql_columns: 10,
                sub_messages: 10_000_000,
                sub_topics: 1_000,
                sub_fields: 3,
            },
        }
    }

    fn subscription_collect_ms(self) -> u64 {
        let default = match self {
            Self::Smoke => 2_000,
            Self::Standard => 5_000,
            Self::Stress => 10_000,
        };
        env_u64("BENCH_SUB_COLLECT_MS", default)
    }
}

#[derive(Clone, Copy, Debug)]
struct SyntheticShape {
    bdp_securities: usize,
    bdp_fields: usize,
    bdh_securities: usize,
    bdh_dates: usize,
    bdh_fields: usize,
    bdtick_ticks: usize,
    bql_rows: usize,
    bql_columns: usize,
    sub_messages: usize,
    sub_topics: usize,
    sub_fields: usize,
}

#[derive(Debug)]
struct BenchRecord {
    suite: &'static str,
    scenario: String,
    status: String,
    elapsed_us: u128,
    rows: usize,
    columns: usize,
    values: usize,
    throughput_name: &'static str,
    throughput_per_sec: f64,
    detail: String,
}

impl BenchRecord {
    fn ok(
        suite: &'static str,
        scenario: impl Into<String>,
        elapsed: Duration,
        rows: usize,
        columns: usize,
        values: usize,
        throughput_name: &'static str,
        detail: impl Into<String>,
    ) -> Self {
        let elapsed_secs = elapsed.as_secs_f64().max(0.000_001);
        let throughput_per_sec = values as f64 / elapsed_secs;
        Self {
            suite,
            scenario: scenario.into(),
            status: "ok".to_string(),
            elapsed_us: elapsed.as_micros(),
            rows,
            columns,
            values,
            throughput_name,
            throughput_per_sec,
            detail: detail.into(),
        }
    }

    fn error(suite: &'static str, scenario: impl Into<String>, elapsed: Duration, detail: impl Into<String>) -> Self {
        Self {
            suite,
            scenario: scenario.into(),
            status: "error".to_string(),
            elapsed_us: elapsed.as_micros(),
            rows: 0,
            columns: 0,
            values: 0,
            throughput_name: "items",
            throughput_per_sec: 0.0,
            detail: detail.into(),
        }
    }
}

fn main() {
    let profile = BenchProfile::from_env();
    let shape = profile.synthetic_shape();
    let timestamp = now_secs();
    let git_sha = git_sha();

    println!("xbbg benchmark suite");
    println!("====================\n");
    println!("Profile: {}", profile.as_str());
    println!("Git SHA: {}", git_sha);
    println!("Bloomberg: {}:{}", blp_host(), blp_port());
    println!();
    print_usage(profile, shape);

    let mut records = Vec::new();

    println!("\n[1/3] Live Bloomberg probes");
    let rt = Runtime::new().expect("tokio runtime");
    let live_records = match create_engine() {
        Ok(engine) => {
            let records = rt.block_on(run_live_suite(&engine, profile));
            drop(engine);
            records
        }
        Err(err) => {
            let detail = format!("failed to start engine: {err}");
            ["bdp_smoke", "bdh_smoke", "bdtick_smoke", "bql_smoke", "subscription_live"]
                .into_iter()
                .map(|scenario| BenchRecord::error("live", scenario, Duration::ZERO, detail.clone()))
                .collect()
        }
    };
    records.extend(live_records);

    println!("\n[2/3] Synthetic massive workloads");
    records.push(synthetic_bdp(shape));
    records.push(synthetic_bdh(shape));
    records.push(synthetic_bdtick(shape));
    records.push(synthetic_bql(shape));
    records.push(synthetic_subscriptions(shape));

    println!("\n[3/3] Summary");
    print_summary(&records);

    let json = render_json(profile, timestamp, &git_sha, shape, &records);
    let markdown = render_markdown(profile, timestamp, &git_sha, shape, &records);
    write_results(timestamp, &json, &markdown);
}

async fn run_live_suite(engine: &Engine, profile: BenchProfile) -> Vec<BenchRecord> {
    let mut records = Vec::new();

    records.push(live_request(&engine, "bdp_smoke", bdp_params()).await);
    records.push(live_request(&engine, "bdh_smoke", bdh_params()).await);
    records.push(live_request(&engine, "bdtick_smoke", bdtick_params()).await);
    records.push(live_request(&engine, "bql_smoke", bql_params()).await);
    records.push(live_subscription(&engine, profile.subscription_collect_ms()).await);

    records
}

fn create_engine() -> Result<Engine, BlpAsyncError> {
    let config = EngineConfig {
        transport: Transport::Direct(vec![ServerAddr::new(blp_host(), blp_port())]),
        ..Default::default()
    };
    Engine::start(config)
}

async fn live_request(engine: &Engine, scenario: &'static str, params: RequestParams) -> BenchRecord {
    let start = Instant::now();
    match engine.request(params).await {
        Ok(batch) => {
            let elapsed = start.elapsed();
            let rows = batch.num_rows();
            let columns = batch.num_columns();
            BenchRecord::ok(
                "live_requests",
                scenario,
                elapsed,
                rows,
                columns,
                rows.saturating_mul(columns),
                "cells",
                format!("schema={}", schema_summary(&batch)),
            )
        }
        Err(err) => BenchRecord::error("live_requests", scenario, start.elapsed(), err.to_string()),
    }
}

async fn live_subscription(engine: &Engine, collect_ms: u64) -> BenchRecord {
    let topics = vec!["IBM US Equity".to_string(), "AAPL US Equity".to_string(), "MSFT US Equity".to_string()];
    let fields = vec!["LAST_PRICE".to_string(), "BID".to_string(), "ASK".to_string()];
    let start = Instant::now();
    let mut stream = match engine.subscribe(topics.clone(), fields.clone(), false).await {
        Ok(stream) => stream,
        Err(err) => return BenchRecord::error("live_subscriptions", "sub_3_topics_3_fields", start.elapsed(), err.to_string()),
    };

    let mut batches = 0usize;
    let mut rows = 0usize;
    let deadline = Instant::now() + Duration::from_millis(collect_ms);
    while Instant::now() < deadline {
        let remaining = deadline.saturating_duration_since(Instant::now());
        match tokio::time::timeout(remaining, stream.next()).await {
            Ok(Some(Ok(batch))) => {
                batches += 1;
                rows += batch.num_rows();
            }
            Ok(Some(Err(err))) => {
                let _ = stream.unsubscribe(true).await;
                return BenchRecord::error("live_subscriptions", "sub_3_topics_3_fields", start.elapsed(), err.to_string());
            }
            Ok(None) | Err(_) => break,
        }
    }
    let elapsed = start.elapsed();
    let _ = stream.unsubscribe(true).await;
    BenchRecord::ok(
        "live_subscriptions",
        "sub_3_topics_3_fields",
        elapsed,
        rows,
        fields.len(),
        rows,
        "rows",
        format!("topics={}, fields={}, batches={}, collect_ms={}", topics.len(), fields.len(), batches, collect_ms),
    )
}

fn bdp_params() -> RequestParams {
    RequestParams {
        service: "//blp/refdata".to_string(),
        operation: "ReferenceDataRequest".to_string(),
        extractor: ExtractorType::RefData,
        securities: Some(vec!["IBM US Equity".to_string()]),
        fields: Some(vec!["PX_LAST".to_string()]),
        ..Default::default()
    }
}

fn bdh_params() -> RequestParams {
    RequestParams {
        service: "//blp/refdata".to_string(),
        operation: "HistoricalDataRequest".to_string(),
        extractor: ExtractorType::HistData,
        securities: Some(vec!["IBM US Equity".to_string()]),
        fields: Some(vec!["PX_LAST".to_string()]),
        start_date: Some("20241202".to_string()),
        end_date: Some("20241206".to_string()),
        ..Default::default()
    }
}

fn bdtick_params() -> RequestParams {
    let date = previous_weekday().format("%Y-%m-%d").to_string();
    RequestParams {
        service: "//blp/refdata".to_string(),
        operation: "IntradayTickRequest".to_string(),
        extractor: ExtractorType::IntradayTick,
        security: Some("IBM US Equity".to_string()),
        start_datetime: Some(format!("{date}T14:30:00")),
        end_datetime: Some(format!("{date}T14:31:00")),
        event_types: Some(vec!["TRADE".to_string()]),
        request_tz: Some("UTC".to_string()),
        output_tz: Some("UTC".to_string()),
        ..Default::default()
    }
}

fn bql_params() -> RequestParams {
    RequestParams {
        service: "//blp/bqlsvc".to_string(),
        operation: "sendQuery".to_string(),
        extractor: ExtractorType::Bql,
        elements: Some(vec![
            (
                "expression".to_string(),
                "get(px_last) for(['IBM US Equity'])".to_string(),
            ),
        ]),
        ..Default::default()
    }
}

fn previous_weekday() -> NaiveDate {
    let mut date = Local::now().date_naive() - ChronoDuration::days(1);
    while matches!(date.weekday(), Weekday::Sat | Weekday::Sun) {
        date -= ChronoDuration::days(1);
    }
    date
}

fn synthetic_bdp(shape: SyntheticShape) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bdp_securities.saturating_mul(shape.bdp_fields);
    let mut tickers = Vec::with_capacity(rows);
    let mut fields = Vec::with_capacity(rows);
    let mut nums = Vec::with_capacity(rows);
    let mut strings = Vec::with_capacity(rows);
    for s in 0..shape.bdp_securities {
        let ticker = format!("SYN{s:06} US Equity");
        for f in 0..shape.bdp_fields {
            tickers.push(ticker.clone());
            fields.push(format!("FIELD_{f:02}"));
            if f % 7 == 0 {
                nums.push(None);
                strings.push(Some(format!("TXT_{}", s % 97)));
            } else {
                nums.push(Some((s as f64 * 0.01) + f as f64));
                strings.push(None);
            }
        }
    }
    let batch = RecordBatch::try_new(
        Arc::new(Schema::new(vec![
            Field::new("ticker", DataType::Utf8, false),
            Field::new("field", DataType::Utf8, false),
            Field::new("value_num", DataType::Float64, true),
            Field::new("value_str", DataType::Utf8, true),
        ])),
        vec![
            Arc::new(StringArray::from(tickers)) as ArrayRef,
            Arc::new(StringArray::from(fields)) as ArrayRef,
            Arc::new(Float64Array::from(nums)) as ArrayRef,
            Arc::new(StringArray::from(strings)) as ArrayRef,
        ],
    )
    .expect("synthetic bdp batch");
    black_box(&batch);
    BenchRecord::ok(
        "synthetic_bdp",
        format!("bdp_{}s_{}f", shape.bdp_securities, shape.bdp_fields),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows,
        "values",
        "generated mixed numeric/string/null reference-data rows",
    )
}

fn synthetic_bdh(shape: SyntheticShape) -> BenchRecord {
    let start = Instant::now();
    let output_rows = shape.bdh_securities.saturating_mul(shape.bdh_dates);
    let values = output_rows.saturating_mul(shape.bdh_fields);
    let mut tickers = Vec::with_capacity(output_rows);
    let mut dates = Vec::with_capacity(output_rows);
    let base_date = NaiveDate::from_ymd_opt(2024, 1, 1).expect("valid base date");
    for s in 0..shape.bdh_securities {
        let ticker = format!("SYN{s:06} US Equity");
        for d in 0..shape.bdh_dates {
            tickers.push(ticker.clone());
            let date = base_date + ChronoDuration::days(d as i64);
            dates.push(format!("{:04}{:02}{:02}", date.year(), date.month(), date.day()));
        }
    }

    let mut schema_fields = vec![
        Field::new("ticker", DataType::Utf8, false),
        Field::new("date", DataType::Utf8, false),
    ];
    let mut arrays: Vec<ArrayRef> = vec![
        Arc::new(StringArray::from(tickers)) as ArrayRef,
        Arc::new(StringArray::from(dates)) as ArrayRef,
    ];
    for f in 0..shape.bdh_fields {
        schema_fields.push(Field::new(format!("HIST_FIELD_{f:02}"), DataType::Float64, true));
        let column: Vec<Option<f64>> = (0..output_rows)
            .map(|row| {
                if (row + f) % 23 == 0 {
                    None
                } else {
                    Some(row as f64 * 0.1 + f as f64)
                }
            })
            .collect();
        arrays.push(Arc::new(Float64Array::from(column)) as ArrayRef);
    }

    let batch = RecordBatch::try_new(Arc::new(Schema::new(schema_fields)), arrays)
        .expect("synthetic bdh batch");
    black_box(&batch);
    BenchRecord::ok(
        "synthetic_bdh",
        format!("bdh_{}s_{}d_{}f", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        values,
        "values",
        "generated wide historical rows with sparse nulls",
    )
}

fn synthetic_bdtick(shape: SyntheticShape) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bdtick_ticks;
    let base = 1_735_564_200_000_000_i64;
    let mut times = Vec::with_capacity(rows);
    let mut event_types = Vec::with_capacity(rows);
    let mut values = Vec::with_capacity(rows);
    let mut sizes = Vec::with_capacity(rows);
    for i in 0..rows {
        times.push(base + i as i64 * 1_000);
        event_types.push(match i % 3 {
            0 => "TRADE",
            1 => "BID",
            _ => "ASK",
        });
        values.push(100.0 + (i % 10_000) as f64 * 0.0001);
        sizes.push((i % 1_000) as i64 + 1);
    }
    let time_array = TimestampMicrosecondArray::from(times).with_timezone("UTC");
    let batch = RecordBatch::try_new(
        Arc::new(Schema::new(vec![
            Field::new("time", DataType::Timestamp(TimeUnit::Microsecond, Some("UTC".into())), false),
            Field::new("event_type", DataType::Utf8, false),
            Field::new("value", DataType::Float64, false),
            Field::new("size", DataType::Int64, false),
        ])),
        vec![
            Arc::new(time_array) as ArrayRef,
            Arc::new(StringArray::from(event_types)) as ArrayRef,
            Arc::new(Float64Array::from(values)) as ArrayRef,
            Arc::new(Int64Array::from(sizes)) as ArrayRef,
        ],
    )
    .expect("synthetic bdtick batch");
    black_box(&batch);
    BenchRecord::ok(
        "synthetic_bdtick",
        format!("bdtick_{}ticks", rows),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows,
        "ticks",
        "generated mixed TRADE/BID/ASK tick rows",
    )
}

fn synthetic_bql(shape: SyntheticShape) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bql_rows;
    let columns = shape.bql_columns;
    let mut schema_fields = Vec::with_capacity(columns + 1);
    let mut arrays: Vec<ArrayRef> = Vec::with_capacity(columns + 1);
    let ids: Vec<String> = (0..rows).map(|i| format!("ID_{i:08}")).collect();
    schema_fields.push(Field::new("id", DataType::Utf8, false));
    arrays.push(Arc::new(StringArray::from(ids)) as ArrayRef);
    for c in 0..columns {
        schema_fields.push(Field::new(format!("value_{c:02}"), DataType::Float64, true));
        let values: Vec<Option<f64>> = (0..rows)
            .map(|r| if (r + c) % 29 == 0 { None } else { Some(r as f64 * 0.01 + c as f64) })
            .collect();
        arrays.push(Arc::new(Float64Array::from(values)) as ArrayRef);
    }
    let batch = RecordBatch::try_new(Arc::new(Schema::new(schema_fields)), arrays)
        .expect("synthetic bql batch");
    black_box(&batch);
    BenchRecord::ok(
        "synthetic_bql",
        format!("bql_{}r_{}c", rows, columns),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows.saturating_mul(columns),
        "cells",
        "generated dynamic-column BQL-style table",
    )
}

fn synthetic_subscriptions(shape: SyntheticShape) -> BenchRecord {
    let start = Instant::now();
    let mut checksum = 0.0f64;
    for i in 0..shape.sub_messages {
        let topic_id = i % shape.sub_topics;
        for f in 0..shape.sub_fields {
            checksum += ((topic_id + f + i) % 10_000) as f64 * 0.0001;
        }
    }
    black_box(checksum);
    BenchRecord::ok(
        "synthetic_subscriptions",
        format!("sub_{}topics_{}messages_{}fields", shape.sub_topics, shape.sub_messages, shape.sub_fields),
        start.elapsed(),
        shape.sub_messages,
        shape.sub_fields,
        shape.sub_messages,
        "messages",
        format!("checksum={checksum:.4}"),
    )
}

fn schema_summary(batch: &RecordBatch) -> String {
    batch
        .schema()
        .fields()
        .iter()
        .map(|field| format!("{}:{:?}", field.name(), field.data_type()))
        .collect::<Vec<_>>()
        .join("|")
}

fn print_usage(profile: BenchProfile, shape: SyntheticShape) {
    println!("Estimated Bloomberg usage:");
    println!("  BDP:      1 request / 1 data point");
    println!("  BDH:      1 request / ~5 data points");
    println!("  BDTICK:   1 short intraday request");
    println!("  BQL:      1 tiny query");
    println!("  SUB:      1 live subscription window / {}ms", profile.subscription_collect_ms());
    println!("  Synthetic: no Bloomberg data usage");
    println!("Synthetic scale:");
    println!("  BDP:    {} securities × {} fields", shape.bdp_securities, shape.bdp_fields);
    println!("  BDH:    {} securities × {} dates × {} fields", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields);
    println!("  BDTICK: {} ticks", shape.bdtick_ticks);
    println!("  BQL:    {} rows × {} columns", shape.bql_rows, shape.bql_columns);
    println!("  SUB:    {} messages × {} fields", shape.sub_messages, shape.sub_fields);
}

fn print_summary(records: &[BenchRecord]) {
    println!("{:<28} {:<34} {:<8} {:>12} {:>12} {:>14}", "suite", "scenario", "status", "elapsed_ms", "rows", "throughput");
    println!("{:-<112}", "");
    for r in records {
        println!(
            "{:<28} {:<34} {:<8} {:>12.2} {:>12} {:>10.2} {}/s",
            r.suite,
            truncate(&r.scenario, 34),
            r.status,
            r.elapsed_us as f64 / 1000.0,
            r.rows,
            r.throughput_per_sec,
            r.throughput_name
        );
    }
}

fn render_json(profile: BenchProfile, timestamp: u64, git_sha: &str, shape: SyntheticShape, records: &[BenchRecord]) -> String {
    let records_json = records
        .iter()
        .map(|r| {
            format!(
                "    {{\n      \"suite\": \"{}\",\n      \"scenario\": \"{}\",\n      \"status\": \"{}\",\n      \"elapsed_us\": {},\n      \"rows\": {},\n      \"columns\": {},\n      \"values\": {},\n      \"throughput_name\": \"{}\",\n      \"throughput_per_sec\": {:.4},\n      \"detail\": \"{}\"\n    }}",
                escape_json(r.suite),
                escape_json(&r.scenario),
                escape_json(&r.status),
                r.elapsed_us,
                r.rows,
                r.columns,
                r.values,
                escape_json(r.throughput_name),
                r.throughput_per_sec,
                escape_json(&r.detail)
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!(
        "{{\n  \"suite\": \"xbbg_benchmark_suite\",\n  \"timestamp\": {},\n  \"profile\": \"{}\",\n  \"git_sha\": \"{}\",\n  \"bloomberg\": {{\n    \"host\": \"{}\",\n    \"port\": {}\n  }},\n  \"synthetic_shape\": {{\n    \"bdp_securities\": {},\n    \"bdp_fields\": {},\n    \"bdh_securities\": {},\n    \"bdh_dates\": {},\n    \"bdh_fields\": {},\n    \"bdtick_ticks\": {},\n    \"bql_rows\": {},\n    \"bql_columns\": {},\n    \"sub_messages\": {},\n    \"sub_topics\": {},\n    \"sub_fields\": {}\n  }},\n  \"benchmarks\": [\n{}\n  ]\n}}\n",
        timestamp,
        profile.as_str(),
        escape_json(git_sha),
        escape_json(&blp_host()),
        blp_port(),
        shape.bdp_securities,
        shape.bdp_fields,
        shape.bdh_securities,
        shape.bdh_dates,
        shape.bdh_fields,
        shape.bdtick_ticks,
        shape.bql_rows,
        shape.bql_columns,
        shape.sub_messages,
        shape.sub_topics,
        shape.sub_fields,
        records_json
    )
}

fn render_markdown(profile: BenchProfile, timestamp: u64, git_sha: &str, shape: SyntheticShape, records: &[BenchRecord]) -> String {
    let mut out = String::new();
    out.push_str("# xbbg Benchmark Suite\n\n");
    out.push_str(&format!("- Timestamp: `{timestamp}`\n"));
    out.push_str(&format!("- Profile: `{}`\n", profile.as_str()));
    out.push_str(&format!("- Git SHA: `{git_sha}`\n"));
    out.push_str(&format!("- Bloomberg: `{}:{}`\n\n", blp_host(), blp_port()));
    out.push_str("## Synthetic Shape\n\n");
    out.push_str(&format!("- BDP: {} securities × {} fields\n", shape.bdp_securities, shape.bdp_fields));
    out.push_str(&format!("- BDH: {} securities × {} dates × {} fields\n", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields));
    out.push_str(&format!("- BDTICK: {} ticks\n", shape.bdtick_ticks));
    out.push_str(&format!("- BQL: {} rows × {} columns\n", shape.bql_rows, shape.bql_columns));
    out.push_str(&format!("- SUB: {} messages × {} fields\n\n", shape.sub_messages, shape.sub_fields));
    out.push_str("## Results\n\n");
    out.push_str("| Suite | Scenario | Status | Elapsed ms | Rows | Throughput |\n");
    out.push_str("|---|---|---:|---:|---:|---:|\n");
    for r in records {
        out.push_str(&format!(
            "| {} | {} | {} | {:.2} | {} | {:.2} {}/s |\n",
            r.suite,
            r.scenario,
            r.status,
            r.elapsed_us as f64 / 1000.0,
            r.rows,
            r.throughput_per_sec,
            r.throughput_name
        ));
    }
    out
}

fn write_results(timestamp: u64, json: &str, markdown: &str) {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("benchmarks/results");
    fs::create_dir_all(&dir).expect("create benchmark results directory");
    let json_path = dir.join(format!("xbbg_benchmark_suite_{timestamp}.json"));
    let json_latest = dir.join("xbbg_benchmark_suite_latest.json");
    let md_path = dir.join(format!("xbbg_benchmark_suite_{timestamp}.md"));
    let md_latest = dir.join("xbbg_benchmark_suite_latest.md");
    write_file(&json_path, json);
    write_file(&json_latest, json);
    write_file(&md_path, markdown);
    write_file(&md_latest, markdown);
    println!("\nResults written:");
    println!("  {}", json_path.display());
    println!("  {}", json_latest.display());
    println!("  {}", md_path.display());
    println!("  {}", md_latest.display());
}

fn write_file(path: &Path, content: &str) {
    fs::write(path, content).unwrap_or_else(|err| panic!("failed to write {}: {err}", path.display()));
}

fn blp_host() -> String {
    std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string())
}

fn blp_port() -> u16 {
    std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194)
}

fn env_u64(name: &str, default: u64) -> u64 {
    std::env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn git_sha() -> String {
    Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .output()
        .ok()
        .and_then(|out| if out.status.success() { Some(out.stdout) } else { None })
        .and_then(|stdout| String::from_utf8(stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".to_string())
}

fn escape_json(input: &str) -> String {
    input
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max.saturating_sub(1)])
    }
}
