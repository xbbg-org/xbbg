# xbbg

<img src="https://raw.githubusercontent.com/alpha-xone/xbbg/main/docs/xbbg.png" alt="xbbg" width="200">

An intuitive Bloomberg API for Python — now powered by Rust.

[![PyPI version](https://img.shields.io/pypi/v/xbbg.svg)](https://pypi.org/project/xbbg/)
[![Python versions](https://img.shields.io/pypi/pyversions/xbbg.svg)](https://pypi.org/project/xbbg/)
[![License](https://img.shields.io/github/license/alpha-xone/xbbg.svg)](https://github.com/alpha-xone/xbbg/blob/main/LICENSE)

## Version 1.0 — Complete Rewrite

This branch contains a complete rewrite of xbbg focused on **performance, flexibility, and reliability**.

See the [1.0.0 Milestone](https://github.com/alpha-xone/xbbg/milestone/1) for progress and planned features.

### What's New

- **Rust-Powered Backend** — Up to 10x faster data retrieval with Arrow integration and async I/O
- **Multi-Backend Support** — Use pandas, Polars, or PyArrow via [Narwhals](https://github.com/narwhals-dev/narwhals)
- **Async-First API** — Native async/await support with sync wrappers
- **Zero-Copy Data Transfer** — Arrow C Data Interface between Rust and Python

### Installation

```bash
pip install xbbg
```

Requires the Bloomberg C++ SDK. Install the official Python bindings:

```bash
pip install blpapi --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/
```

### Quick Start

```python
import xbbg

# Check version
print(xbbg.__version__)

# Reference data
df = xbbg.bdp(['AAPL US Equity'], ['PX_LAST', 'SECURITY_NAME'])
```

### Requirements

- Python 3.10+
- Bloomberg Terminal or BPIPE connection
- Bloomberg C++ SDK

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

Apache-2.0 — see [LICENSE](LICENSE)
