# pyo3-xbbg

PyO3 bindings for the xbbg Bloomberg engine.

This crate provides Python bindings via PyO3, exposing the Rust engine to Python as the `xbbg._core` module.

## Features

- Async API (abdp, abdh, abds, abdib, abdtick)
- Zero-copy Arrow data transfer via PyArrow
- GIL released during Bloomberg SDK operations
