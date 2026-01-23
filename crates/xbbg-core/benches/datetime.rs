//! Benchmarks for HighPrecisionDatetime
//!
//! These benchmarks do NOT require Bloomberg connection (pure Rust computation).
//!
//! Run with: cargo bench --package xbbg_core --bench datetime

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use xbbg_core::datetime::HighPrecisionDatetime;
use xbbg_core::ffi;

fn make_datetime(
    year: u16,
    month: u8,
    day: u8,
    hours: u8,
    minutes: u8,
    seconds: u8,
    milliseconds: u16,
) -> HighPrecisionDatetime {
    HighPrecisionDatetime::from_raw(ffi::blpapi_HighPrecisionDatetime_t {
        parts: 0xFF,
        hours,
        minutes,
        seconds,
        milliseconds,
        month,
        day,
        year,
        offset: 0,
        picoseconds: 0,
    })
}

fn bench_datetime_to_micros(c: &mut Criterion) {
    let dt = make_datetime(2024, 6, 15, 14, 30, 45, 123);

    c.bench_function("datetime_to_micros", |b| {
        b.iter(|| black_box(&dt).to_micros());
    });
}

fn bench_datetime_to_nanos(c: &mut Criterion) {
    let dt = make_datetime(2024, 6, 15, 14, 30, 45, 123);

    c.bench_function("datetime_to_nanos", |b| {
        b.iter(|| black_box(&dt).to_nanos());
    });
}

criterion_group!(benches, bench_datetime_to_micros, bench_datetime_to_nanos);
criterion_main!(benches);
