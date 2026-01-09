"""Benchmark BDIB (Intraday Bars) across packages.

Data usage: ~50-100 data points per run (30 minutes of 5-min bars)
"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
import time
import tracemalloc

from config import (
    BDIB_DATE,
    BDIB_END_TIME,
    BDIB_INTERVAL,
    BDIB_START_TIME,
    ITERATIONS,
    TICKERS_SINGLE,
    WARMUP_ITERATIONS,
)


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""

    package: str
    operation: str
    cold_start_ms: float
    warm_mean_ms: float
    warm_median_ms: float
    warm_p95_ms: float
    warm_p99_ms: float
    warm_std_ms: float
    memory_peak_mb: float
    data_shape: tuple
    iterations: int


def benchmark_bdib(
    package_name: str, bdib_func, ticker, event_type, date, start_time, end_time, interval
) -> BenchmarkResult:
    """Benchmark BDIB operation.

    Args:
        package_name: Name of package being benchmarked
        bdib_func: Function to call for bdib(ticker, event_type, date, start_time, end_time, interval)
        ticker: Ticker symbol
        event_type: Event type (TRADE, BID, ASK, etc.)
        date: Date
        start_time: Start time
        end_time: End time
        interval: Bar interval in minutes

    Returns:
        BenchmarkResult with timing and memory stats
    """
    times = []
    result = None

    # Start memory tracking
    tracemalloc.start()

    # Warmup iterations (discarded)
    for _ in range(WARMUP_ITERATIONS):
        bdib_func(ticker, event_type, date, start_time, end_time, interval)

    # Measured iterations
    for _i in range(ITERATIONS):
        start = time.perf_counter()
        result = bdib_func(ticker, event_type, date, start_time, end_time, interval)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    # Get memory usage
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_mb = peak / 1024 / 1024

    # Get result shape
    if hasattr(result, "shape"):
        shape = result.shape
    elif hasattr(result, "__len__"):
        shape = (len(result),)
    else:
        shape = (1,)

    # Calculate statistics
    cold_start = times[0]
    warm_times = times[1:] if len(times) > 1 else times
    warm_mean = statistics.mean(warm_times)
    warm_median = statistics.median(warm_times)
    warm_std = statistics.stdev(warm_times) if len(warm_times) > 1 else 0

    # Percentiles
    sorted_times = sorted(warm_times)
    p95_idx = int(len(sorted_times) * 0.95)
    p99_idx = int(len(sorted_times) * 0.99)
    warm_p95 = sorted_times[p95_idx] if sorted_times else warm_mean
    warm_p99 = sorted_times[p99_idx] if sorted_times else warm_mean

    return BenchmarkResult(
        package=package_name,
        operation=f"bdib({ticker}, {event_type}, {interval}m bars)",
        cold_start_ms=cold_start,
        warm_mean_ms=warm_mean,
        warm_median_ms=warm_median,
        warm_p95_ms=warm_p95,
        warm_p99_ms=warm_p99,
        warm_std_ms=warm_std,
        memory_peak_mb=memory_mb,
        data_shape=shape,
        iterations=ITERATIONS,
    )


def run_xbbg_rust(ticker, event_type, date, start_time, end_time, interval):
    """Benchmark xbbg Rust version."""
    import xbbg

    return xbbg.bdib(ticker, event_type, date, start_time, end_time, interval)


def run_xbbg_legacy(ticker, event_type, date, start_time, end_time, interval):
    """Benchmark legacy xbbg Python version."""
    try:
        import xbbg_legacy

        return xbbg_legacy.bdib(ticker, event_type, date, start_time, end_time, interval)
    except ImportError:
        print("Warning: xbbg legacy not installed")
        return None


def run_pdblp(ticker, event_type, date, start_time, end_time, interval):
    """Benchmark pdblp."""
    try:
        from datetime import datetime

        import pdblp

        con = pdblp.BCon(debug=False, timeout=5000)
        con.start()

        # pdblp uses different API - convert parameters
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")

        result = con.bdib(ticker, event_type, start_datetime, end_datetime, interval=interval)
        con.stop()
        return result
    except ImportError:
        print("Warning: pdblp not installed")
        return None
    except Exception as e:
        print(f"Warning: pdblp error: {e}")
        return None


def main():
    """Run all BDIB benchmarks."""
    print("=" * 70)
    print("BDIB (Intraday Bars) Benchmark")
    print("=" * 70)
    print(f"\nIterations: {ITERATIONS}")
    print(f"Warmup: {WARMUP_ITERATIONS}")
    print(f"Date: {BDIB_DATE}")
    print(f"Time range: {BDIB_START_TIME} to {BDIB_END_TIME}")
    print(f"Interval: {BDIB_INTERVAL} minutes")

    results = []

    event_types = ["TRADE"]  # Could also test BID, ASK, BEST_BID, BEST_ASK

    for event_type in event_types:
        print(f"\n\nTest: {event_type} events")
        print("-" * 70)

        if True:  # xbbg Rust
            print("Running xbbg (Rust)...")
            try:
                result = benchmark_bdib(
                    "xbbg-rust",
                    run_xbbg_rust,
                    TICKERS_SINGLE[0],
                    event_type,
                    BDIB_DATE,
                    BDIB_START_TIME,
                    BDIB_END_TIME,
                    BDIB_INTERVAL,
                )
                results.append(result)
                print(
                    f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                )
            except Exception as e:
                print(f"  ✗ Error: {e}")

        if True:  # xbbg Legacy
            print("Running xbbg (legacy)...")
            try:
                result = benchmark_bdib(
                    "xbbg-legacy",
                    run_xbbg_legacy,
                    TICKERS_SINGLE[0],
                    event_type,
                    BDIB_DATE,
                    BDIB_START_TIME,
                    BDIB_END_TIME,
                    BDIB_INTERVAL,
                )
                if result:
                    results.append(result)
                    print(
                        f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                    )
            except Exception as e:
                print(f"  ✗ Error: {e}")

        if True:  # pdblp
            print("Running pdblp...")
            try:
                result = benchmark_bdib(
                    "pdblp",
                    run_pdblp,
                    TICKERS_SINGLE[0],
                    event_type,
                    BDIB_DATE,
                    BDIB_START_TIME,
                    BDIB_END_TIME,
                    BDIB_INTERVAL,
                )
                if result:
                    results.append(result)
                    print(
                        f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                    )
            except Exception as e:
                print(f"  ✗ Error: {e}")

    # Print summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for result in results:
        print(f"\n{result.package} - {result.operation}")
        print(f"  Cold start: {result.cold_start_ms:.2f}ms")
        print(f"  Warm mean:  {result.warm_mean_ms:.2f}ms ± {result.warm_std_ms:.2f}ms")
        print(f"  Warm p95:   {result.warm_p95_ms:.2f}ms")
        print(f"  Memory:     {result.memory_peak_mb:.2f}MB")
        print(f"  Shape:      {result.data_shape}")

    # Calculate speedups
    xbbg_rust_results = [r for r in results if r.package == "xbbg-rust"]
    legacy_results = [r for r in results if r.package == "xbbg-legacy"]

    if xbbg_rust_results and legacy_results:
        rust_time = sum(r.warm_mean_ms for r in xbbg_rust_results)
        legacy_time = sum(r.warm_mean_ms for r in legacy_results)
        speedup = legacy_time / rust_time if rust_time > 0 else 0

        print(f"\n\n{'=' * 70}")
        print(f"xbbg Rust vs Legacy Speedup: {speedup:.2f}x faster")
        print(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    main()
