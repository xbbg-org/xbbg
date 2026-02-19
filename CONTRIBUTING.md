# Contributing to xbbg

Thank you for your interest in contributing to xbbg!

## Development Setup

### Prerequisites

- Python 3.10+
- Rust 1.70+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Bloomberg C++ SDK (for building the Rust backend)

### Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/alpha-xone/xbbg.git
   cd xbbg
   ```

2. Set up the Bloomberg SDK:
   ```bash
   # Set BLPAPI_ROOT to your SDK location
   export BLPAPI_ROOT=/path/to/blpapi_cpp_x.x.x.x
   ```

3. Install dependencies and build:
   ```bash
   uv sync
   uv run maturin develop
   ```

4. Run tests:
   ```bash
   uv run pytest
   ```

## Code Style

### Python
- We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Run `uvx ruff check .` and `uvx ruff format .` before committing

### Rust
- Run `cargo fmt` for formatting
- Run `cargo clippy` for linting

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Ensure tests pass and code is formatted
5. Commit with a descriptive message following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `refactor:` for code refactoring
   - `test:` for adding tests
   - `ci:` for CI/CD changes
6. Push and open a pull request

## Reporting Issues

Please use [GitHub Issues](https://github.com/alpha-xone/xbbg/issues) to report bugs or request features.

When reporting a bug, include:
- Python version (`python --version`)
- xbbg version (`python -c "import xbbg; print(xbbg.__version__)"`)
- Operating system
- Minimal code to reproduce the issue

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
