"""Benchmark BDTICK (Tick Data) across packages.

Data usage: ~100-200 data points per run (5 minutes of tick data)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import statistics
import time
import tracemalloc

logger = logging.getLogger(__name__)

from config import (
    BDTICK_DATE,
    BDTICK_END_TIME,
    BDTICK_START_TIME,
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


def benchmark_bdtick(
    package_name: str, bdtick_func, ticker, event_types, date, start_time, end_time
) -> BenchmarkResult:
    """Benchmark BDTICK operation.

    Args:
        package_name: Name of package being benchmarked
        bdtick_func: Function to call for bdtick(ticker, event_types, date, start_time, end_time)
        ticker: Ticker symbol
        event_types: List of event types (TRADE, BID, ASK, etc.)
        date: Date
        start_time: Start time
        end_time: End time

    Returns:
        BenchmarkResult with timing and memory stats
    """
    times = []
    result = None

    # Start memory tracking
    tracemalloc.start()

    # Warmup iterations (discarded)
    for _ in range(WARMUP_ITERATIONS):
        bdtick_func(ticker, event_types, date, start_time, end_time)

    # Measured iterations
    for _i in range(ITERATIONS):
        start = time.perf_counter()
        result = bdtick_func(ticker, event_types, date, start_time, end_time)
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

    event_str = ",".join(event_types) if isinstance(event_types, list) else event_types

    return BenchmarkResult(
        package=package_name,
        operation=f"bdtick({ticker}, [{event_str}])",
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


def run_xbbg_rust(ticker, event_types, date, start_time, end_time):
    """Benchmark xbbg Rust version."""
    import xbbg

    return xbbg.bdtick(ticker, event_types, date, start_time, end_time)


def run_xbbg_legacy(ticker, event_types, date, start_time, end_time):
    """Benchmark legacy xbbg Python version."""
    try:
        import xbbg_legacy

        return xbbg_legacy.bdtick(ticker, event_types, date, start_time, end_time)
    except ImportError:
        logger.warning("xbbg legacy not installed")
        return None


def run_pdblp(ticker, event_types, date, start_time, end_time):
    """Benchmark pdblp."""
    try:
        from datetime import datetime

        import pdblp

        con = pdblp.BCon(debug=False, timeout=5000)
        con.start()

        # pdblp uses different API - convert parameters
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M:%S")

        # pdblp may not support bdtick - handle gracefully
        if hasattr(con, "bdtick"):
            result = con.bdtick(ticker, event_types, start_datetime, end_datetime)
        else:
            logger.warning("pdblp does not support bdtick")
            result = None

        con.stop()
        return result
    except ImportError:
        logger.warning("pdblp not installed")
        return None
    except Exception as e:
        logger.warning(f"pdblp error: {e}")
        return None


def main():
    """Run all BDTICK benchmarks."""
    logger.info("=" * 70)
    logger.info("BDTICK (Tick Data) Benchmark")
    logger.info("=" * 70)
    logger.info(f"\nIterations: {ITERATIONS}")
    logger.info(f"Warmup: {WARMUP_ITERATIONS}")
    logger.info(f"Date: {BDTICK_DATE}")
    logger.info(f"Time range: {BDTICK_START_TIME} to {BDTICK_END_TIME}")

    results = []

    # Test different event type combinations
    test_cases = [
        (["TRADE"], "TRADE only"),
        (["BID", "ASK"], "BID + ASK"),
        (["TRADE", "BID", "ASK"], "All events"),
    ]

    for event_types, description in test_cases:
        logger.info(f"\n\nTest: {description}")
        logger.info("-" * 70)

        if True:  # xbbg Rust
            logger.info("Running xbbg (Rust)...")
            try:
                result = benchmark_bdtick(
                    "xbbg-rust",
                    run_xbbg_rust,
                    TICKERS_SINGLE[0],
                    event_types,
                    BDTICK_DATE,
                    BDTICK_START_TIME,
                    BDTICK_END_TIME,
                )
                results.append(result)
                logger.info(
                    f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                )
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

        if True:  # xbbg Legacy
            logger.info("Running xbbg (legacy)...")
            try:
                result = benchmark_bdtick(
                    "xbbg-legacy",
                    run_xbbg_legacy,
                    TICKERS_SINGLE[0],
                    event_types,
                    BDTICK_DATE,
                    BDTICK_START_TIME,
                    BDTICK_END_TIME,
                )
                if result:
                    results.append(result)
                    logger.info(
                        f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                    )
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

        if True:  # pdblp
            logger.info("Running pdblp...")
            try:
                result = benchmark_bdtick(
                    "pdblp",
                    run_pdblp,
                    TICKERS_SINGLE[0],
                    event_types,
                    BDTICK_DATE,
                    BDTICK_START_TIME,
                    BDTICK_END_TIME,
                )
                if result:
                    results.append(result)
                    logger.info(
                        f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                    )
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

    # Print summary
    logger.info("\n\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    for result in results:
        logger.info(f"\n{result.package} - {result.operation}")
        logger.info(f"  Cold start: {result.cold_start_ms:.2f}ms")
        logger.info(f"  Warm mean:  {result.warm_mean_ms:.2f}ms ± {result.warm_std_ms:.2f}ms")
        logger.info(f"  Warm p95:   {result.warm_p95_ms:.2f}ms")
        logger.info(f"  Memory:     {result.memory_peak_mb:.2f}MB")
        logger.info(f"  Shape:      {result.data_shape}")

    # Calculate speedups
    xbbg_rust_results = [r for r in results if r.package == "xbbg-rust"]
    legacy_results = [r for r in results if r.package == "xbbg-legacy"]

    if xbbg_rust_results and legacy_results:
        rust_time = sum(r.warm_mean_ms for r in xbbg_rust_results)
        legacy_time = sum(r.warm_mean_ms for r in legacy_results)
        speedup = legacy_time / rust_time if rust_time > 0 else 0

        logger.info(f"\n\n{'=' * 70}")
        logger.info(f"xbbg Rust vs Legacy Speedup: {speedup:.2f}x faster")
        logger.info(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
