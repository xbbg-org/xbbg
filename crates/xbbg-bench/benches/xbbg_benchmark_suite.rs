//! One-command xbbg benchmark suite.
//!
//! Runs tiny live Bloomberg probes plus large synthetic workloads in one report.
//! Live probes intentionally keep Bloomberg data usage low; synthetic workloads
//! provide scale without additional Bloomberg requests.

use std::alloc::{GlobalAlloc, Layout, System};
use std::fs;
use std::hint::black_box;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use arrow::array::{ArrayRef, Float64Array, Int64Array, StringArray, TimestampMicrosecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use chrono::{Datelike, Duration as ChronoDuration, Local, NaiveDate, Weekday};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use tokio::runtime::Runtime;
use tokio::sync::{mpsc, oneshot};
use xbbg_async::engine::{
    BqlState, BulkDataState, Engine, EngineConfig, ExtractorType, HistDataState,
    IntradayTickState, LongMode, OutputFormat, RefDataState, RequestParams, ServerAddr,
    SubscriptionState, Transport,
};
use xbbg_async::BlpAsyncError;
use xbbg_bench::{open_service, setup_session};
use xbbg_core::{BlpError, CorrelationId, Event, EventType, Name, SubscriptionList};
struct TrackingAllocator;

static TRACK_ALLOCATIONS: AtomicBool = AtomicBool::new(false);
static ALLOC_COUNT: AtomicU64 = AtomicU64::new(0);
static ALLOC_BYTES: AtomicU64 = AtomicU64::new(0);
static DEALLOC_COUNT: AtomicU64 = AtomicU64::new(0);
static DEALLOC_BYTES: AtomicU64 = AtomicU64::new(0);

#[global_allocator]
static GLOBAL_ALLOCATOR: TrackingAllocator = TrackingAllocator;

unsafe impl GlobalAlloc for TrackingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        if TRACK_ALLOCATIONS.load(Ordering::Relaxed) {
            ALLOC_COUNT.fetch_add(1, Ordering::Relaxed);
            ALLOC_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        }
        System.alloc(layout)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        if TRACK_ALLOCATIONS.load(Ordering::Relaxed) {
            DEALLOC_COUNT.fetch_add(1, Ordering::Relaxed);
            DEALLOC_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        }
        System.dealloc(ptr, layout);
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        if TRACK_ALLOCATIONS.load(Ordering::Relaxed) {
            DEALLOC_COUNT.fetch_add(1, Ordering::Relaxed);
            DEALLOC_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
            ALLOC_COUNT.fetch_add(1, Ordering::Relaxed);
            ALLOC_BYTES.fetch_add(new_size as u64, Ordering::Relaxed);
        }
        System.realloc(ptr, layout, new_size)
    }
}


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

    fn replay_iterations(self) -> usize {
        let default = match self {
            Self::Smoke => 100,
            Self::Standard => 1_000,
            Self::Stress => 5_000,
        };
        env_usize("BENCH_REPLAY_ITERATIONS", default)
    }

    fn subscription_replay_messages(self) -> usize {
        let default = match self {
            Self::Smoke => 10_000,
            Self::Standard => 1_000_000,
            Self::Stress => 10_000_000,
        };
        env_usize("BENCH_SUB_REPLAY_MESSAGES", default)
    }

    fn subscription_replay_topics(self) -> usize {
        let default = match self {
            Self::Smoke => 10,
            Self::Standard => 1_000,
            Self::Stress => 10_000,
        };
        env_usize("BENCH_SUB_REPLAY_TOPICS", default)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ProfileMode {
    Normal,
    Detail,
}

impl ProfileMode {
    fn from_env() -> Self {
        match std::env::var("BENCH_PROFILE_MODE")
            .unwrap_or_else(|_| "none".to_string())
            .to_ascii_lowercase()
            .as_str()
        {
            "detail" => Self::Detail,
            _ => Self::Normal,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Normal => "none",
            Self::Detail => "detail",
        }
    }

    fn is_detail(self) -> bool {
        self == Self::Detail
    }
}

#[derive(Clone, Debug)]
struct SuiteConfig {
    profile: BenchProfile,
    profile_mode: ProfileMode,
    only: Option<String>,
}

impl SuiteConfig {
    fn from_env() -> Self {
        Self {
            profile: BenchProfile::from_env(),
            profile_mode: ProfileMode::from_env(),
            only: std::env::var("BENCH_ONLY")
                .ok()
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty()),
        }
    }

    fn should_run(&self, suite: &str, scenario: &str) -> bool {
        let Some(only) = &self.only else {
            return true;
        };
        suite.to_ascii_lowercase().contains(only) || scenario.to_ascii_lowercase().contains(only)
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

#[derive(Clone, Debug)]
struct PhaseMetric {
    name: &'static str,
    elapsed_us: u128,
}

#[derive(Clone, Copy, Debug, Default)]
struct AllocSnapshot {
    alloc_count: u64,
    alloc_bytes: u64,
    dealloc_count: u64,
    dealloc_bytes: u64,
}

#[derive(Clone, Copy, Debug)]
struct AllocDelta {
    alloc_count: u64,
    alloc_bytes: u64,
    dealloc_count: u64,
    dealloc_bytes: u64,
    net_alloc_bytes: i128,
    allocs_per_row: f64,
    bytes_per_row: f64,
    allocs_per_value: f64,
    bytes_per_value: f64,
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
    phases: Vec<PhaseMetric>,
    allocations: Option<AllocDelta>,
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
            phases: Vec::new(),
            allocations: None,
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
            phases: Vec::new(),
            allocations: None,
        }
    }
}

fn alloc_snapshot() -> AllocSnapshot {
    AllocSnapshot {
        alloc_count: ALLOC_COUNT.load(Ordering::Relaxed),
        alloc_bytes: ALLOC_BYTES.load(Ordering::Relaxed),
        dealloc_count: DEALLOC_COUNT.load(Ordering::Relaxed),
        dealloc_bytes: DEALLOC_BYTES.load(Ordering::Relaxed),
    }
}

fn alloc_delta(before: AllocSnapshot, after: AllocSnapshot, rows: usize, values: usize) -> AllocDelta {
    let alloc_count = after.alloc_count.saturating_sub(before.alloc_count);
    let alloc_bytes = after.alloc_bytes.saturating_sub(before.alloc_bytes);
    let dealloc_count = after.dealloc_count.saturating_sub(before.dealloc_count);
    let dealloc_bytes = after.dealloc_bytes.saturating_sub(before.dealloc_bytes);
    let row_divisor = rows.max(1) as f64;
    let value_divisor = values.max(1) as f64;
    AllocDelta {
        alloc_count,
        alloc_bytes,
        dealloc_count,
        dealloc_bytes,
        net_alloc_bytes: alloc_bytes as i128 - dealloc_bytes as i128,
        allocs_per_row: alloc_count as f64 / row_divisor,
        bytes_per_row: alloc_bytes as f64 / row_divisor,
        allocs_per_value: alloc_count as f64 / value_divisor,
        bytes_per_value: alloc_bytes as f64 / value_divisor,
    }
}

fn profile_record<F>(config: &SuiteConfig, suite: &'static str, _scenario: &str, run: F) -> BenchRecord
where
    F: FnOnce(bool) -> BenchRecord,
{
    if !config.profile_mode.is_detail() {
        return run(false);
    }

    TRACK_ALLOCATIONS.store(true, Ordering::SeqCst);
    let before = alloc_snapshot();
    let mut record = run(true);
    let after = alloc_snapshot();
    TRACK_ALLOCATIONS.store(false, Ordering::SeqCst);
    let allocation = alloc_delta(before, after, record.rows, record.values);
    if record.phases.is_empty() {
        record.phases.push(PhaseMetric {
            name: suite,
            elapsed_us: record.elapsed_us,
        });
    }
    record.allocations = Some(allocation);
    record
}

fn phase(name: &'static str, elapsed: Duration) -> PhaseMetric {
    PhaseMetric {
        name,
        elapsed_us: elapsed.as_micros(),
    }
}

fn main() {
    let config = SuiteConfig::from_env();
    let profile = config.profile;
    let shape = profile.synthetic_shape();
    let timestamp = now_secs();
    let git_sha = git_sha();

    println!("xbbg benchmark suite");
    println!("====================\n");
    println!("Profile: {}", profile.as_str());
    println!("Profile mode: {}", config.profile_mode.as_str());
    if let Some(only) = &config.only {
        println!("Scenario filter: {only}");
    }
    println!("Git SHA: {}", git_sha);
    println!("Bloomberg: {}:{}", blp_host(), blp_port());
    suppress_blpapi_warnings();
    println!();
    print_usage(profile, shape);

    let mut records = Vec::new();

    if should_run_live(&config) {
        println!("\n[1/4] Live Bloomberg probes");
        let rt = Runtime::new().expect("tokio runtime");
        let live_records = match create_engine() {
            Ok(engine) => {
                let records = rt.block_on(run_live_suite(&engine, &config));
                drop(engine);
                records
            }
            Err(err) => {
                let detail = format!("failed to start engine: {err}");
                ["bdp_smoke", "bdh_smoke", "bdtick_smoke", "bql_smoke", "subscription_live"]
                    .into_iter()
                    .filter(|scenario| config.should_run("live", scenario) || config.should_run("live_requests", scenario) || config.should_run("live_subscriptions", scenario))
                    .map(|scenario| BenchRecord::error("live", scenario, Duration::ZERO, detail.clone()))
                    .collect()
            }
        };
        records.extend(live_records);
    } else {
        println!("\n[1/4] Live Bloomberg probes skipped by BENCH_ONLY");
    }

    if should_run_replay(&config) {
        println!("\n[2/4] Cached Bloomberg event replay");
        records.extend(run_replay_suite(&config));
    } else {
        println!("\n[2/4] Cached Bloomberg event replay skipped by BENCH_ONLY");
    }

    println!("\n[3/4] Synthetic massive workloads");
    if config.should_run("synthetic_bdp", &format!("bdp_{}s_{}f", shape.bdp_securities, shape.bdp_fields)) {
        records.push(profile_record(&config, "synthetic_bdp", "synthetic_bdp", |_| synthetic_bdp(shape, config.profile_mode.is_detail())));
    }
    if config.should_run("synthetic_bdh", &format!("bdh_{}s_{}d_{}f", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields)) {
        records.push(profile_record(&config, "synthetic_bdh", "synthetic_bdh", |_| synthetic_bdh(shape, config.profile_mode.is_detail())));
    }
    if config.should_run("synthetic_bdtick", &format!("bdtick_{}ticks", shape.bdtick_ticks)) {
        records.push(profile_record(&config, "synthetic_bdtick", "synthetic_bdtick", |_| synthetic_bdtick(shape, config.profile_mode.is_detail())));
    }
    if config.should_run("synthetic_bql", &format!("bql_{}r_{}c", shape.bql_rows, shape.bql_columns)) {
        records.push(profile_record(&config, "synthetic_bql", "synthetic_bql", |_| synthetic_bql(shape, config.profile_mode.is_detail())));
    }
    if config.should_run("synthetic_subscriptions", &format!("sub_{}topics_{}messages_{}fields", shape.sub_topics, shape.sub_messages, shape.sub_fields)) {
        records.push(profile_record(&config, "synthetic_subscriptions", "synthetic_subscriptions", |_| synthetic_subscriptions(shape, config.profile_mode.is_detail())));
    }

    println!("\n[4/4] Summary");
    print_summary(&records);

    let json = render_json(&config, timestamp, &git_sha, shape, &records);
    let markdown = render_markdown(&config, timestamp, &git_sha, shape, &records);
    write_results(timestamp, &json, &markdown);
}

fn suppress_blpapi_warnings() {
    unsafe {
        let _ = xbbg_core::ffi::blpapi_Logging_registerCallback(
            None,
            xbbg_core::ffi::blpapi_Logging_Severity_t_blpapi_Logging_SEVERITY_ERROR
                as xbbg_core::ffi::blpapi_Logging_Severity_t,
        );
    }
}

fn should_run_live(config: &SuiteConfig) -> bool {
    config.should_run("live", "bdp_smoke")
        || config.should_run("live_requests", "bdp_smoke")
        || config.should_run("live_requests", "bdh_smoke")
        || config.should_run("live_requests", "bdtick_smoke")
        || config.should_run("live_requests", "bql_smoke")
        || config.should_run("live_subscriptions", "sub_3_topics_3_fields")
}

fn should_run_replay(config: &SuiteConfig) -> bool {
    config.should_run("replay", "bdp_refdata")
        || config.should_run("replay", "bdh_historical")
        || config.should_run("replay", "bds_bulk_late_fields")
        || config.should_run("replay", "bdtick_optional_fields")
        || config.should_run("replay", "bql_response")
        || config.should_run("subscription_replay", "requested_fields")
        || config.should_run("subscription_replay", "all_fields")
        || config.should_run("subscription_replay", "high_message_count")
        || config.should_run("subscription_replay", "high_topic_count")
}

fn run_replay_suite(config: &SuiteConfig) -> Vec<BenchRecord> {
    let mut records = Vec::new();
    let iterations = config.profile.replay_iterations();

    let sess = setup_session();
    open_service(&sess, "//blp/refdata");

    if config.should_run("replay", "bdp_refdata") {
        records.push(match fetch_bdp_events(&sess) {
            Ok(events) => profile_record(config, "replay", "bdp_refdata", |_| {
                replay_request_events("bdp_refdata", &events, iterations, || {
                    make_refdata_state(vec!["PX_LAST".to_string(), "VOLUME".to_string()])
                })
            }),
            Err(err) => BenchRecord::error("replay", "bdp_refdata", Duration::ZERO, err),
        });
    }

    if config.should_run("replay", "bdh_historical") {
        records.push(match fetch_bdh_events(&sess) {
            Ok(events) => profile_record(config, "replay", "bdh_historical", |_| {
                replay_request_events("bdh_historical", &events, iterations, || {
                    make_histdata_state(vec!["PX_LAST".to_string(), "VOLUME".to_string()])
                })
            }),
            Err(err) => BenchRecord::error("replay", "bdh_historical", Duration::ZERO, err),
        });
    }

    if config.should_run("replay", "bds_bulk_late_fields") {
        records.push(match fetch_bds_events(&sess) {
            Ok(events) => profile_record(config, "replay", "bds_bulk_late_fields", |_| {
                replay_request_events("bds_bulk_late_fields", &events, iterations, || {
                    make_bulkdata_state("INDX_MEMBERS".to_string())
                })
            }),
            Err(err) => BenchRecord::error("replay", "bds_bulk_late_fields", Duration::ZERO, err),
        });
    }

    if config.should_run("replay", "bdtick_optional_fields") {
        records.push(match fetch_bdtick_events(&sess) {
            Ok(events) => profile_record(config, "replay", "bdtick_optional_fields", |_| {
                replay_request_events("bdtick_optional_fields", &events, iterations, || {
                    make_intradaytick_state("IBM US Equity".to_string())
                })
            }),
            Err(err) => BenchRecord::error("replay", "bdtick_optional_fields", Duration::ZERO, err),
        });
    }

    if config.should_run("replay", "bql_response") {
        open_service(&sess, "//blp/bqlsvc");
        records.push(match fetch_bql_events(&sess) {
            Ok(events) => profile_record(config, "replay", "bql_response", |_| {
                replay_request_events("bql_response", &events, iterations, make_bql_state)
            }),
            Err(err) => BenchRecord::error("replay", "bql_response", Duration::ZERO, err),
        });
    }

    if should_run_subscription_replay(config) {
        open_service(&sess, "//blp/mktdata");
        let collect_ms = config.profile.subscription_collect_ms();
        match fetch_subscription_events(&sess, collect_ms) {
            Ok(events) => {
                if config.should_run("subscription_replay", "requested_fields") {
                    records.push(profile_record(config, "subscription_replay", "requested_fields", |_| {
                        replay_subscription_events("requested_fields", &events, config.profile.subscription_replay_messages().min(100_000), 1, false, &["LAST_PRICE", "BID", "ASK"])
                    }));
                }
                if config.should_run("subscription_replay", "all_fields") {
                    records.push(profile_record(config, "subscription_replay", "all_fields", |_| {
                        replay_subscription_events("all_fields", &events, config.profile.subscription_replay_messages().min(100_000), 1, true, &["LAST_PRICE", "BID", "ASK"])
                    }));
                }
                if config.should_run("subscription_replay", "high_message_count") {
                    records.push(profile_record(config, "subscription_replay", "high_message_count", |_| {
                        replay_subscription_events("high_message_count", &events, config.profile.subscription_replay_messages(), 1, false, &["LAST_PRICE", "BID", "ASK"])
                    }));
                }
                if config.should_run("subscription_replay", "high_topic_count") {
                    records.push(profile_record(config, "subscription_replay", "high_topic_count", |_| {
                        replay_subscription_events("high_topic_count", &events, config.profile.subscription_replay_messages().min(100_000), config.profile.subscription_replay_topics(), false, &["LAST_PRICE", "BID", "ASK"])
                    }));
                }
            }
            Err(err) => records.push(BenchRecord::error("subscription_replay", "capture", Duration::ZERO, err)),
        }
    }

    sess.stop();
    records
}

fn should_run_subscription_replay(config: &SuiteConfig) -> bool {
    config.should_run("subscription_replay", "requested_fields")
        || config.should_run("subscription_replay", "all_fields")
        || config.should_run("subscription_replay", "high_message_count")
        || config.should_run("subscription_replay", "high_topic_count")
}

enum ReplayState {
    RefData(RefDataState),
    HistData(HistDataState),
    BulkData(BulkDataState),
    IntradayTick(IntradayTickState),
    Bql(BqlState),
}

impl ReplayState {
    fn on_partial(&mut self, msg: &xbbg_core::Message<'_>) {
        match self {
            Self::RefData(state) => state.on_partial(msg),
            Self::HistData(state) => state.on_partial(msg),
            Self::BulkData(state) => state.on_partial(msg),
            Self::IntradayTick(state) => state.on_partial(msg),
            Self::Bql(state) => state.on_partial(msg),
        }
    }

    fn finish(self, msg: &xbbg_core::Message<'_>) {
        match self {
            Self::RefData(state) => state.finish(msg),
            Self::HistData(state) => state.finish(msg),
            Self::BulkData(state) => state.finish(msg),
            Self::IntradayTick(state) => state.finish(msg),
            Self::Bql(state) => state.finish(msg),
        }
    }
}

fn make_refdata_state(fields: Vec<String>) -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>) {
    let (tx, rx) = oneshot::channel();
    (
        ReplayState::RefData(RefDataState::with_format(
            fields,
            OutputFormat::Long,
            LongMode::String,
            None,
            false,
            tx,
        )),
        rx,
    )
}

fn make_histdata_state(fields: Vec<String>) -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>) {
    let (tx, rx) = oneshot::channel();
    (
        ReplayState::HistData(HistDataState::with_format(
            fields,
            OutputFormat::Long,
            LongMode::String,
            None,
            tx,
        )),
        rx,
    )
}

fn make_bulkdata_state(field: String) -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>) {
    let (tx, rx) = oneshot::channel();
    (ReplayState::BulkData(BulkDataState::new(field, tx)), rx)
}

fn make_intradaytick_state(ticker: String) -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>) {
    let (tx, rx) = oneshot::channel();
    (ReplayState::IntradayTick(IntradayTickState::new(ticker, tx)), rx)
}

fn make_bql_state() -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>) {
    let (tx, rx) = oneshot::channel();
    (ReplayState::Bql(BqlState::new(tx)), rx)
}

fn replay_request_events<F>(
    scenario: &'static str,
    events: &[Event],
    iterations: usize,
    mut make_state: F,
 ) -> BenchRecord
where
    F: FnMut() -> (ReplayState, oneshot::Receiver<Result<RecordBatch, BlpError>>),
{
    let start = Instant::now();
    let mut rows = 0usize;
    let mut columns = 0usize;
    let mut ok_iterations = 0usize;
    let mut last_error: Option<String> = None;

    for _ in 0..iterations {
        let (mut state, rx) = make_state();
        let mut finished = false;
        'events: for event in events {
            match event.event_type() {
                EventType::PartialResponse => {
                    for msg in event.messages() {
                        state.on_partial(&msg);
                    }
                }
                EventType::Response => {
                    if let Some(msg) = event.messages().next() {
                        state.finish(&msg);
                        finished = true;
                        break 'events;
                    }
                }
                _ => {}
            }
        }

        if !finished {
            last_error = Some("no response message in cached events".to_string());
            continue;
        }

        match rx.blocking_recv() {
            Ok(Ok(batch)) => {
                rows += batch.num_rows();
                columns = batch.num_columns();
                ok_iterations += 1;
                black_box(batch);
            }
            Ok(Err(err)) => last_error = Some(err.to_string()),
            Err(err) => last_error = Some(err.to_string()),
        }
    }

    let elapsed = start.elapsed();
    if ok_iterations == 0 {
        return BenchRecord::error(
            "replay",
            scenario,
            elapsed,
            last_error.unwrap_or_else(|| "all replay iterations failed".to_string()),
        );
    }

    BenchRecord::ok(
        "replay",
        scenario,
        elapsed,
        rows,
        columns,
        rows,
        "rows",
        format!("iterations={ok_iterations}, cached_events={}", events.len()),
    )
}

fn collect_response_events<F>(
    sess: &xbbg_core::Session,
    service: &str,
    operation: &str,
    build: F,
 ) -> Result<Vec<Event>, String>
where
    F: FnOnce(&mut xbbg_core::Request) -> Result<(), BlpError>,
{
    let svc = sess
        .get_service(service)
        .map_err(|err| format!("get_service {service}: {err}"))?;
    let mut req = svc
        .create_request(operation)
        .map_err(|err| format!("create_request {operation}: {err}"))?;
    build(&mut req).map_err(|err| format!("build {operation}: {err}"))?;
    sess.send_request(&req, None, None)
        .map_err(|err| format!("send_request {operation}: {err}"))?;

    let mut events = Vec::new();
    loop {
        let event = sess
            .next_event(Some(10_000))
            .map_err(|err| format!("next_event {operation}: {err}"))?;
        match event.event_type() {
            EventType::PartialResponse => events.push(event),
            EventType::Response => {
                events.push(event);
                return Ok(events);
            }
            EventType::RequestStatus => {
                return Err(format!("request status before response for {operation}"));
            }
            _ => {}
        }
    }
}

fn fetch_bdp_events(sess: &xbbg_core::Session) -> Result<Vec<Event>, String> {
    collect_response_events(sess, "//blp/refdata", "ReferenceDataRequest", |req| {
        req.append_str("securities", "IBM US Equity")?;
        req.append_str("fields", "PX_LAST")?;
        req.append_str("fields", "VOLUME")?;
        Ok(())
    })
}

fn fetch_bdh_events(sess: &xbbg_core::Session) -> Result<Vec<Event>, String> {
    collect_response_events(sess, "//blp/refdata", "HistoricalDataRequest", |req| {
        req.append_str("securities", "IBM US Equity")?;
        req.append_str("fields", "PX_LAST")?;
        req.append_str("fields", "VOLUME")?;
        req.set_str("startDate", "20241202")?;
        req.set_str("endDate", "20241206")?;
        Ok(())
    })
}

fn fetch_bds_events(sess: &xbbg_core::Session) -> Result<Vec<Event>, String> {
    collect_response_events(sess, "//blp/refdata", "ReferenceDataRequest", |req| {
        req.append_str("securities", "INDU Index")?;
        req.append_str("fields", "INDX_MEMBERS")?;
        Ok(())
    })
}

fn fetch_bdtick_events(sess: &xbbg_core::Session) -> Result<Vec<Event>, String> {
    let date = previous_weekday().format("%Y-%m-%d").to_string();
    collect_response_events(sess, "//blp/refdata", "IntradayTickRequest", |req| {
        req.set_str("security", "IBM US Equity")?;
        req.append_str("eventTypes", "TRADE")?;
        req.set_datetime("startDateTime", &format!("{date}T14:30:00"))?;
        req.set_datetime("endDateTime", &format!("{date}T14:31:00"))?;
        req.set_bool(&Name::get_or_intern("includeConditionCodes"), true)?;
        req.set_bool(&Name::get_or_intern("includeExchangeCodes"), true)?;
        Ok(())
    })
}

fn fetch_bql_events(sess: &xbbg_core::Session) -> Result<Vec<Event>, String> {
    collect_response_events(sess, "//blp/bqlsvc", "sendQuery", |req| {
        req.set_str("expression", "get(px_last) for(['IBM US Equity'])")?;
        Ok(())
    })
}

fn fetch_subscription_events(sess: &xbbg_core::Session, collect_ms: u64) -> Result<Vec<Event>, String> {
    let mut sub_list = SubscriptionList::new();
    let cid = CorrelationId::new_int(10_001);
    sub_list
        .add(
            "IBM US Equity",
            &["LAST_PRICE", "BID", "ASK"],
            "",
            &cid,
        )
        .map_err(|err| format!("add subscription: {err}"))?;
    sess.subscribe(&sub_list, None)
        .map_err(|err| format!("subscribe: {err}"))?;

    let deadline = Instant::now() + Duration::from_millis(collect_ms);
    let mut events = Vec::new();
    while Instant::now() < deadline {
        let remaining = deadline.saturating_duration_since(Instant::now());
        let timeout = remaining.as_millis().clamp(1, u32::MAX as u128) as u32;
        if let Ok(event) = sess.next_event(Some(timeout)) {
            match event.event_type() {
                EventType::SubscriptionData => events.push(event),
                EventType::SubscriptionStatus => {}
                _ => {}
            }
        }
    }
    let _ = sess.unsubscribe(&sub_list);

    if events.is_empty() {
        Err("subscription capture produced no data events".to_string())
    } else {
        Ok(events)
    }
}

fn replay_subscription_events(
    scenario: &'static str,
    events: &[Event],
    target_messages: usize,
    topic_count: usize,
    all_fields: bool,
    fields: &[&str],
 ) -> BenchRecord {
    let start = Instant::now();
    if events.is_empty() {
        return BenchRecord::error(
            "subscription_replay",
            scenario,
            Duration::ZERO,
            "no cached subscription events",
        );
    }

    let cached_messages = events
        .iter()
        .map(|event| event.messages().count())
        .sum::<usize>()
        .max(1);
    let repeats_per_message = (target_messages / cached_messages).max(1);

    let topic_count = topic_count.max(1);
    let (tx, mut rx) = mpsc::channel(topic_count.saturating_mul(4).max(16));
    let field_vec = fields.iter().map(|field| (*field).to_string()).collect::<Vec<_>>();
    let mut states = (0..topic_count)
        .map(|idx| {
            SubscriptionState::new(
                format!("SYN{idx:05} US Equity"),
                field_vec.clone(),
                tx.clone(),
                target_messages.saturating_add(1),
                all_fields,
            )
        })
        .collect::<Vec<_>>();
    drop(tx);

    let process_start = Instant::now();
    let mut processed = 0usize;
    while processed < target_messages {
        for event in events {
            for msg in event.messages() {
                for _ in 0..repeats_per_message {
                    let idx = processed % topic_count;
                    states[idx].on_message(&msg);
                    processed += 1;
                    if processed >= target_messages {
                        break;
                    }
                }
            }
            if processed >= target_messages {
                break;
            }
        }
    }
    let process_elapsed = process_start.elapsed();

    let flush_start = Instant::now();
    for state in &mut states {
        state.flush();
    }
    let flush_elapsed = flush_start.elapsed();

    let drain_start = Instant::now();
    let mut rows = 0usize;
    let mut columns = 0usize;
    let mut batches = 0usize;
    while let Ok(item) = rx.try_recv() {
        if let Ok(batch) = item {
            rows += batch.num_rows();
            columns = columns.max(batch.num_columns());
            batches += 1;
            black_box(batch);
        }
    }
    let drain_elapsed = drain_start.elapsed();

    let mut record = BenchRecord::ok(
        "subscription_replay",
        scenario,
        start.elapsed(),
        rows,
        columns,
        processed,
        "messages",
        format!(
            "target_messages={target_messages}, topics={topic_count}, batches={batches}, all_fields={all_fields}, cached_events={}, cached_messages={cached_messages}, repeats_per_message={repeats_per_message}",
            events.len()
        ),
    );
    record.phases = vec![
        phase("process_messages_through_subscription_state", process_elapsed),
        phase("flush_arrow_batches", flush_elapsed),
        phase("drain_batches", drain_elapsed),
        phase("total", Duration::from_micros(record.elapsed_us as u64)),
    ];
    record
}

async fn run_live_suite(engine: &Engine, config: &SuiteConfig) -> Vec<BenchRecord> {
    let mut records = Vec::new();

    if config.should_run("live_requests", "bdp_smoke") {
        records.push(live_request(&engine, "bdp_smoke", bdp_params()).await);
    }
    if config.should_run("live_requests", "bdh_smoke") {
        records.push(live_request(&engine, "bdh_smoke", bdh_params()).await);
    }
    if config.should_run("live_requests", "bdtick_smoke") {
        records.push(live_request(&engine, "bdtick_smoke", bdtick_params()).await);
    }
    if config.should_run("live_requests", "bql_smoke") {
        records.push(live_request(&engine, "bql_smoke", bql_params()).await);
    }
    if config.should_run("live_subscriptions", "sub_3_topics_3_fields") {
        records.push(live_subscription(&engine, config.profile.subscription_collect_ms()).await);
    }

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

fn synthetic_bdp(shape: SyntheticShape, detail: bool) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bdp_securities.saturating_mul(shape.bdp_fields);
    let generate_start = Instant::now();
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
    let generate_elapsed = generate_start.elapsed();
    let build_start = Instant::now();
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
    let build_elapsed = build_start.elapsed();
    black_box(&batch);
    let mut record = BenchRecord::ok(
        "synthetic_bdp",
        format!("bdp_{}s_{}f", shape.bdp_securities, shape.bdp_fields),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows,
        "values",
        "generated mixed numeric/string/null reference-data rows",
    );
    if detail {
        record.phases = vec![
            phase("generate_values", generate_elapsed),
            phase("build_arrow_batch", build_elapsed),
            phase("total", Duration::from_micros(record.elapsed_us as u64)),
        ];
    }
    record
}

fn synthetic_bdh(shape: SyntheticShape, detail: bool) -> BenchRecord {
    let start = Instant::now();
    let output_rows = shape.bdh_securities.saturating_mul(shape.bdh_dates);
    let values = output_rows.saturating_mul(shape.bdh_fields);
    let keys_start = Instant::now();
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
    let keys_elapsed = keys_start.elapsed();

    let values_start = Instant::now();
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
    let values_elapsed = values_start.elapsed();

    let build_start = Instant::now();
    let batch = RecordBatch::try_new(Arc::new(Schema::new(schema_fields)), arrays)
        .expect("synthetic bdh batch");
    let build_elapsed = build_start.elapsed();
    black_box(&batch);
    let mut record = BenchRecord::ok(
        "synthetic_bdh",
        format!("bdh_{}s_{}d_{}f", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        values,
        "values",
        "generated wide historical rows with sparse nulls",
    );
    if detail {
        record.phases = vec![
            phase("generate_keys", keys_elapsed),
            phase("generate_field_values", values_elapsed),
            phase("build_record_batch", build_elapsed),
            phase("total", Duration::from_micros(record.elapsed_us as u64)),
        ];
    }
    record
}

fn synthetic_bdtick(shape: SyntheticShape, detail: bool) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bdtick_ticks;
    let generate_start = Instant::now();
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
    let generate_elapsed = generate_start.elapsed();
    let build_start = Instant::now();
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
    let build_elapsed = build_start.elapsed();
    black_box(&batch);
    let mut record = BenchRecord::ok(
        "synthetic_bdtick",
        format!("bdtick_{}ticks", rows),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows,
        "ticks",
        "generated mixed TRADE/BID/ASK tick rows",
    );
    if detail {
        record.phases = vec![
            phase("generate_ticks", generate_elapsed),
            phase("build_arrow_batch", build_elapsed),
            phase("total", Duration::from_micros(record.elapsed_us as u64)),
        ];
    }
    record
}

fn synthetic_bql(shape: SyntheticShape, detail: bool) -> BenchRecord {
    let start = Instant::now();
    let rows = shape.bql_rows;
    let columns = shape.bql_columns;
    let generate_start = Instant::now();
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
    let generate_elapsed = generate_start.elapsed();
    let build_start = Instant::now();
    let batch = RecordBatch::try_new(Arc::new(Schema::new(schema_fields)), arrays)
        .expect("synthetic bql batch");
    let build_elapsed = build_start.elapsed();
    black_box(&batch);
    let mut record = BenchRecord::ok(
        "synthetic_bql",
        format!("bql_{}r_{}c", rows, columns),
        start.elapsed(),
        batch.num_rows(),
        batch.num_columns(),
        rows.saturating_mul(columns),
        "cells",
        "generated dynamic-column BQL-style table",
    );
    if detail {
        record.phases = vec![
            phase("generate_columns", generate_elapsed),
            phase("build_record_batch", build_elapsed),
            phase("total", Duration::from_micros(record.elapsed_us as u64)),
        ];
    }
    record
}

fn synthetic_subscriptions(shape: SyntheticShape, detail: bool) -> BenchRecord {
    let start = Instant::now();
    let process_start = Instant::now();
    let mut checksum = 0.0f64;
    for i in 0..shape.sub_messages {
        let topic_id = i % shape.sub_topics;
        for f in 0..shape.sub_fields {
            checksum += ((topic_id + f + i) % 10_000) as f64 * 0.0001;
        }
    }
    let process_elapsed = process_start.elapsed();
    black_box(checksum);
    let mut record = BenchRecord::ok(
        "synthetic_subscriptions",
        format!("sub_{}topics_{}messages_{}fields", shape.sub_topics, shape.sub_messages, shape.sub_fields),
        start.elapsed(),
        shape.sub_messages,
        shape.sub_fields,
        shape.sub_messages,
        "messages",
        format!("checksum={checksum:.4}"),
    );
    if detail {
        record.phases = vec![
            phase("process_messages", process_elapsed),
            phase("total", Duration::from_micros(record.elapsed_us as u64)),
        ];
    }
    record
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
    println!("  Replay:    1 seed request per selected replay case, then cached SDK Event replay");
    println!("Replay scale:");
    println!("  Request event replay iterations: {}", profile.replay_iterations());
    println!("  Subscription replay messages: {}", profile.subscription_replay_messages());
    println!("  Subscription replay topics: {}", profile.subscription_replay_topics());
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

fn render_phases_json(phases: &[PhaseMetric]) -> String {
    if phases.is_empty() {
        return "[]".to_string();
    }
    let items = phases
        .iter()
        .map(|p| {
            format!(
                "{{\"name\":\"{}\",\"elapsed_us\":{}}}",
                escape_json(p.name),
                p.elapsed_us
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    format!("[{}]", items)
}

fn render_allocations_json(allocations: Option<AllocDelta>) -> String {
    match allocations {
        Some(a) => format!(
            "{{\"alloc_count\":{},\"alloc_bytes\":{},\"dealloc_count\":{},\"dealloc_bytes\":{},\"net_alloc_bytes\":{},\"allocs_per_row\":{:.8},\"bytes_per_row\":{:.4},\"allocs_per_value\":{:.8},\"bytes_per_value\":{:.4}}}",
            a.alloc_count,
            a.alloc_bytes,
            a.dealloc_count,
            a.dealloc_bytes,
            a.net_alloc_bytes,
            a.allocs_per_row,
            a.bytes_per_row,
            a.allocs_per_value,
            a.bytes_per_value
        ),
        None => "null".to_string(),
    }
}

fn render_optional_string(value: Option<&str>) -> String {
    value
        .map(|v| format!("\"{}\"", escape_json(v)))
        .unwrap_or_else(|| "null".to_string())
}

fn render_json(config: &SuiteConfig, timestamp: u64, git_sha: &str, shape: SyntheticShape, records: &[BenchRecord]) -> String {
    let records_json = records
        .iter()
        .map(|r| {
            let phases_json = render_phases_json(&r.phases);
            let allocations_json = render_allocations_json(r.allocations);
            format!(
                "    {{\n      \"suite\": \"{}\",\n      \"scenario\": \"{}\",\n      \"status\": \"{}\",\n      \"elapsed_us\": {},\n      \"rows\": {},\n      \"columns\": {},\n      \"values\": {},\n      \"throughput_name\": \"{}\",\n      \"throughput_per_sec\": {:.4},\n      \"detail\": \"{}\",\n      \"phases\": {},\n      \"allocations\": {}\n    }}",
                escape_json(r.suite),
                escape_json(&r.scenario),
                escape_json(&r.status),
                r.elapsed_us,
                r.rows,
                r.columns,
                r.values,
                escape_json(r.throughput_name),
                r.throughput_per_sec,
                escape_json(&r.detail),
                phases_json,
                allocations_json
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!(
        "{{\n  \"suite\": \"xbbg_benchmark_suite\",\n  \"timestamp\": {},\n  \"profile\": \"{}\",\n  \"profile_mode\": \"{}\",\n  \"bench_only\": {},\n  \"git_sha\": \"{}\",\n  \"bloomberg\": {{\n    \"host\": \"{}\",\n    \"port\": {}\n  }},\n  \"synthetic_shape\": {{\n    \"bdp_securities\": {},\n    \"bdp_fields\": {},\n    \"bdh_securities\": {},\n    \"bdh_dates\": {},\n    \"bdh_fields\": {},\n    \"bdtick_ticks\": {},\n    \"bql_rows\": {},\n    \"bql_columns\": {},\n    \"sub_messages\": {},\n    \"sub_topics\": {},\n    \"sub_fields\": {}\n  }},\n  \"benchmarks\": [\n{}\n  ]\n}}\n",
        timestamp,
        config.profile.as_str(),
        config.profile_mode.as_str(),
        render_optional_string(config.only.as_deref()),
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

fn render_markdown(config: &SuiteConfig, timestamp: u64, git_sha: &str, shape: SyntheticShape, records: &[BenchRecord]) -> String {
    let mut out = String::new();
    out.push_str("# xbbg Benchmark Suite\n\n");
    out.push_str(&format!("- Timestamp: `{timestamp}`\n"));
    out.push_str(&format!("- Profile: `{}`\n", config.profile.as_str()));
    out.push_str(&format!("- Profile mode: `{}`\n", config.profile_mode.as_str()));
    if let Some(only) = &config.only {
        out.push_str(&format!("- Scenario filter: `{only}`\n"));
    }
    out.push_str(&format!("- Git SHA: `{git_sha}`\n"));
    out.push_str(&format!("- Bloomberg: `{}:{}`\n\n", blp_host(), blp_port()));
    out.push_str("## Synthetic Shape\n\n");
    out.push_str(&format!("- BDP: {} securities × {} fields\n", shape.bdp_securities, shape.bdp_fields));
    out.push_str(&format!("- BDH: {} securities × {} dates × {} fields\n", shape.bdh_securities, shape.bdh_dates, shape.bdh_fields));
    out.push_str(&format!("- BDTICK: {} ticks\n", shape.bdtick_ticks));
    out.push_str(&format!("- BQL: {} rows × {} columns\n", shape.bql_rows, shape.bql_columns));
    out.push_str(&format!("- SUB: {} messages × {} fields\n\n", shape.sub_messages, shape.sub_fields));
    out.push_str("## Results\n\n");
    out.push_str("| Suite | Scenario | Status | Elapsed ms | Rows | Throughput | Alloc bytes |\n");
    out.push_str("|---|---|---:|---:|---:|---:|---:|\n");
    for r in records {
        let alloc_bytes = r.allocations.map(|a| a.alloc_bytes.to_string()).unwrap_or_else(|| "-".to_string());
        out.push_str(&format!(
            "| {} | {} | {} | {:.2} | {} | {:.2} {}/s | {} |\n",
            r.suite,
            r.scenario,
            r.status,
            r.elapsed_us as f64 / 1000.0,
            r.rows,
            r.throughput_per_sec,
            r.throughput_name,
            alloc_bytes
        ));
    }
    if config.profile_mode.is_detail() {
        out.push_str("\n## Detail profiling\n\n");
        for r in records {
            out.push_str(&format!("### {} / {}\n\n", r.suite, r.scenario));
            if !r.phases.is_empty() {
                out.push_str("Phase timings:\n\n");
                for p in &r.phases {
                    out.push_str(&format!("- `{}`: {} µs\n", p.name, p.elapsed_us));
                }
                out.push('\n');
            }
            if let Some(a) = r.allocations {
                out.push_str(&format!(
                    "Allocations: {} allocs / {} bytes; {:.4} allocs/row; {:.2} bytes/row; {:.4} allocs/value; {:.2} bytes/value\n\n",
                    a.alloc_count, a.alloc_bytes, a.allocs_per_row, a.bytes_per_row, a.allocs_per_value, a.bytes_per_value
                ));
            }
        }
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

fn env_usize(name: &str, default: usize) -> usize {
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
