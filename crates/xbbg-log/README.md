# xbbg-log

Zero-GIL logging infrastructure for the xbbg workspace.

Provides a `tracing`-based setup designed for Rust-Python hybrid libraries where worker threads must never acquire the GIL. Python controls the log level via a single atomic store — no locks, no GIL, no contention.

## Why this crate exists

The standard `pyo3-log` bridge acquires the GIL on every log event to forward to Python's `logging` module. In xbbg, worker threads poll Bloomberg at 10ms intervals — GIL contention from logging caused measurable latency. This crate eliminates that entirely.

## Architecture

```text
tracing::debug!("...")
  → AtomicLevelFilter (reads AtomicU8, ~1ns, zero GIL)
  → fmt::layer
  → stderr
```

- **No GIL**: The atomic level check is a single `Relaxed` load
- **Simple output path**: Output goes directly to stderr; worker threads never touch Python logging
- **Python and Rust logging are separate**: Rust uses `tracing`, Python uses `logging` — no bridge

## Crate structure

```
xbbg-log/
├── Cargo.toml
└── src/
    └── lib.rs      AtomicLevelFilter, init(), set_level(), re-exported tracing macros
```

## Usage

### From Python

```python
import xbbg
xbbg.set_log_level("debug")   # sets AtomicU8, returns immediately
xbbg.set_log_level("warn")    # back to quiet (default)
```

### From Rust (other workspace crates)

```rust
use xbbg_log::{trace, debug, info, warn, error};

info!(worker_id = 0, "request completed");
debug!(ticker = "AAPL US Equity", "parsing response");
```

All workspace crates depend on `xbbg-log` instead of `tracing` directly, so the macro re-exports and subscriber setup are centralized.

### Developer override

Set `RUST_LOG` to a simple level to choose the initial Rust log level:

```bash
RUST_LOG=debug python my_script.py
```

Python can still change the level later via `xbbg.set_log_level()`.

## Modes

| `RUST_LOG` set? | Behaviour |
|-----------------|-----------|
| No (default) | `AtomicLevelFilter` — Python controls via `set_log_level()`, default WARN |
| Simple level | Sets the initial atomic level; Python can still update it |

## API

| Function | Description |
|----------|-------------|
| `init()` | Initialize subscriber (call once from PyO3 module init) |
| `set_level(Level)` | Set global log level (atomic store) |
| `current_level() → Level` | Get current level (atomic load) |
| `parse_level(&str) → Option<Level>` | Parse `"debug"`, `"warn"`, `"0"`–`"4"`, etc. |
