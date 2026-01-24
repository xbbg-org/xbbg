#!/usr/bin/env python
"""Benchmark xbbg Bloomberg API calls.

Measures time spent in different parts of the pipeline:
- Total call time
- Bloomberg network I/O (estimated)
- Python processing (parsing, transformation)

Usage:
    python scripts/benchmark_blp.py

Requires Bloomberg Terminal connection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from statistics import mean, stdev

# Check Bloomberg availability first
try:
    from xbbg import blp
except ImportError:
    print("xbbg not installed. Run: pip install -e .")
    exit(1)


@dataclass
class BenchmarkResult:
    """Benchmark result for a single operation."""

    name: str
    times: list[float]

    @property
    def mean_ms(self) -> float:
        return mean(self.times) * 1000

    @property
    def stdev_ms(self) -> float:
        return stdev(self.times) * 1000 if len(self.times) > 1 else 0

    @property
    def min_ms(self) -> float:
        return min(self.times) * 1000

    @property
    def max_ms(self) -> float:
        return max(self.times) * 1000

    def __str__(self) -> str:
        return (
            f"{self.name:40} "
            f"mean={self.mean_ms:8.2f}ms  "
            f"std={self.stdev_ms:7.2f}ms  "
            f"min={self.min_ms:8.2f}ms  "
            f"max={self.max_ms:8.2f}ms"
        )


def benchmark(name: str, func, warmup: int = 1, iterations: int = 5) -> BenchmarkResult:
    """Run a benchmark with warmup and multiple iterations."""
    # Warmup
    for _ in range(warmup):
        func()

    # Timed runs
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)

    return BenchmarkResult(name=name, times=times)


def main():
    print("=" * 80)
    print("xbbg Bloomberg API Benchmark")
    print("=" * 80)
    print()

    results: list[BenchmarkResult] = []

    # Test 1: Simple BDP - single ticker, single field
    print("Running: bdp single ticker/field...")
    results.append(
        benchmark(
            "bdp(1 ticker, 1 field)",
            lambda: blp.bdp("AAPL US Equity", "PX_LAST"),
        )
    )

    # Test 2: BDP - single ticker, multiple fields
    print("Running: bdp single ticker, 5 fields...")
    results.append(
        benchmark(
            "bdp(1 ticker, 5 fields)",
            lambda: blp.bdp("AAPL US Equity", ["PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW", "VOLUME"]),
        )
    )

    # Test 3: BDP - multiple tickers, single field
    print("Running: bdp 5 tickers, 1 field...")
    tickers_5 = ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity", "AMZN US Equity", "META US Equity"]
    results.append(
        benchmark(
            "bdp(5 tickers, 1 field)",
            lambda: blp.bdp(tickers_5, "PX_LAST"),
        )
    )

    # Test 4: BDP - multiple tickers, multiple fields
    print("Running: bdp 5 tickers, 5 fields...")
    fields_5 = ["PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW", "VOLUME"]
    results.append(
        benchmark(
            "bdp(5 tickers, 5 fields)",
            lambda: blp.bdp(tickers_5, fields_5),
        )
    )

    # Test 5: BDH - historical data (small)
    print("Running: bdh 1 ticker, 1 month...")
    results.append(
        benchmark(
            "bdh(1 ticker, 1 month)",
            lambda: blp.bdh("SPY US Equity", "PX_LAST", "2024-12-01", "2024-12-31"),
        )
    )

    # Test 6: BDH - historical data (larger)
    print("Running: bdh 1 ticker, 1 year...")
    results.append(
        benchmark(
            "bdh(1 ticker, 1 year)",
            lambda: blp.bdh("SPY US Equity", "PX_LAST", "2024-01-01", "2024-12-31"),
            iterations=3,  # Fewer iterations for longer operation
        )
    )

    # Test 7: BDS - bulk data
    print("Running: bds dividend history...")
    results.append(
        benchmark(
            "bds(DVD_Hist_All, 1 year)",
            lambda: blp.bds("AAPL US Equity", "DVD_Hist_All", DVD_Start_Dt="20240101", DVD_End_Dt="20241231"),
        )
    )

    # Print results
    print()
    print("=" * 80)
    print("Results (5 iterations after 1 warmup, unless noted)")
    print("=" * 80)
    print()

    for r in results:
        print(r)

    print()
    print("=" * 80)
    print("Notes:")
    print("- Times include: network I/O + Bloomberg processing + Python parsing")
    print("- Network latency dominates for simple queries")
    print("- Python parsing overhead increases with data volume")
    print("- Rust backend would primarily speed up parsing, not network I/O")
    print("=" * 80)


if __name__ == "__main__":
    main()
