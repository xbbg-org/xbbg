//! Benchmarks for Name type
//!
//! These benchmarks require a Bloomberg connection (the DLL must be loaded).
//!
//! Run with: cargo bench --package xbbg_core --bench name

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use xbbg_core::Name;

fn bench_name_compare(c: &mut Criterion) {
    let name1 = Name::new("PX_LAST").expect("failed to create name");
    let name2 = Name::new("PX_LAST").expect("failed to create name");

    c.bench_function("name_compare", |b| {
        b.iter(|| black_box(&name1) == black_box(&name2));
    });
}

fn bench_name_to_str(c: &mut Criterion) {
    let name = Name::new("SECURITY_DATA").expect("failed to create name");

    c.bench_function("name_to_str", |b| {
        b.iter(|| black_box(name.as_str()));
    });
}

criterion_group!(benches, bench_name_compare, bench_name_to_str);
criterion_main!(benches);
