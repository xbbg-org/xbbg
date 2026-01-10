# Contributing to xbbg

Thank you for your interest in contributing to xbbg! We welcome contributions from the community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Changelog and Releases](#changelog-and-releases)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/xbbg.git
   cd xbbg
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/alpha-xone/xbbg.git
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Bloomberg C++ SDK version 3.12.1 or higher
- Bloomberg official Python API (blpapi)
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Installation

1. **Create virtual environment and install dependencies**:
   ```bash
   uv venv .venv
   # On Windows:
   .\.venv\Scripts\Activate.ps1
   # On Linux/macOS:
   source .venv/bin/activate
   
   uv sync --locked --extra dev --extra test
   ```

2. **Install Bloomberg API**:
   ```bash
   pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
   ```

3. **Install pre-commit hooks** (optional but recommended):
   ```bash
   uv run pre-commit install
   ```

### Verify Installation

```bash
# Run linter
uv run ruff check xbbg

# Run tests (without Bloomberg connection)
uv run pytest --doctest-modules -v xbbg

# Run tests with Bloomberg connection (if available)
uv run pytest --doctest-modules --run-xbbg-live -v xbbg
```

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Environment details**: Python version, OS, xbbg version
- **Code samples** or error messages (if applicable)

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear title and description**
- **Use case**: Why is this enhancement needed?
- **Proposed solution** (if you have one)
- **Alternatives considered**

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

### Contributing Code

1. **Check existing issues** or create a new one to discuss your proposed changes
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following our [coding standards](#coding-standards)
4. **Add tests** for your changes
5. **Update documentation** if needed
6. **Run tests and linting** locally
7. **Commit your changes** with clear, descriptive messages
8. **Push to your fork** and submit a pull request

## Pull Request Process

1. **Update documentation**: Ensure README.md, docstrings, and other docs reflect your changes
2. **Add tests**: All new code should have corresponding tests
3. **Run the full test suite**:
   ```bash
   uv run ruff check xbbg
   uv run pytest --doctest-modules --cov -v xbbg
   ```
4. **Update CHANGELOG.md**: Add your changes under the `[Unreleased]` section (see [Changelog and Releases](#changelog-and-releases))
5. **Ensure CI passes**: All GitHub Actions workflows must pass
6. **Request review**: Tag maintainers or wait for automatic review assignment
7. **Address feedback**: Respond to review comments and make requested changes
8. **Squash commits** (if requested): Keep git history clean

### Pull Request Guidelines

- **One feature per PR**: Keep pull requests focused on a single feature or fix
- **Clear title**: Use descriptive titles (e.g., "feat: Add support for BTA service" or "fix: Handle empty DataFrame in bdib")
- **Description**: Explain what changes you made and why
- **Link issues**: Reference related issues (e.g., "Closes #123")
- **Keep it small**: Smaller PRs are easier to review and merge

### Commit Message Format

We follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates

**Examples:**
```
feat(api): add support for Bloomberg Technical Analysis (BTA)

fix(bdib): handle empty DataFrame when no data available

docs(README): update installation instructions for Python 3.14
```

## Changelog and Releases

### CHANGELOG.md as Single Source of Truth

We use `CHANGELOG.md` as the single source of truth for release notes. This ensures consistency across:
- GitHub Releases
- README.md
- Documentation (docs/index.rst)
- PyPI release descriptions

### How It Works

1. **Contributors** update `CHANGELOG.md` under the `[Unreleased]` section when submitting PRs
2. **Release workflow** extracts content from `[Unreleased]` for GitHub Release notes
3. **Release workflow** renames `[Unreleased]` to the version number with date
4. **Release workflow** creates a new empty `[Unreleased]` section

### Updating the Changelog

When contributing, add your changes to `CHANGELOG.md` under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New `bta()` function for Bloomberg Technical Analysis (#175)

### Changed
- Improved performance of `bdib()` for large date ranges

### Fixed
- Fixed empty DataFrame handling in `bdh()` (#123)
```

### Changelog Categories

Follow [Keep a Changelog](https://keepachangelog.com/) format:

| Category | Use For |
|----------|---------|
| **Added** | New features |
| **Changed** | Changes to existing functionality |
| **Deprecated** | Features that will be removed in future versions |
| **Removed** | Features removed in this release |
| **Fixed** | Bug fixes |
| **Security** | Security vulnerability fixes |

### Best Practices

- **Be concise**: One line per change, focused on *what* changed
- **Link issues/PRs**: Reference related issues (e.g., `(#123)`)
- **User perspective**: Describe changes from the user's point of view
- **Group related changes**: Keep related items together under the same category

### Example Entry

```markdown
### Added
- Multi-backend support with `Backend` enum (narwhals, pandas, polars, pyarrow, duckdb)
- Output format control with `Format` enum (long, semi_long, wide)
- `bta()` function for Bloomberg Technical Analysis (#175)
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`

### Changed
- All API functions now accept `backend` and `format` parameters
- Internal pipeline uses PyArrow tables with narwhals transformations

### Deprecated
- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()` instead

### Fixed
- Empty DataFrame handling in helper functions with LONG format output
```

### Release Process (Maintainers)

1. Ensure `[Unreleased]` section in `CHANGELOG.md` is up to date
2. Run the `semantic_version.yml` workflow:
   - Select bump type (major/minor/patch)
   - Select pre-release type if applicable (alpha/beta/rc)
3. Workflow automatically:
   - Extracts release notes from `[Unreleased]`
   - Creates GitHub Release with those notes
   - Updates `CHANGELOG.md` (renames section, adds new `[Unreleased]`)
   - Triggers asset upload, docs update, etc.
4. Manually trigger `pypi_upload.yml` to publish to PyPI

## Coding Standards

### Python Style

- **Follow PEP 8** with line length of 120 characters
- **Use Ruff** for linting and formatting
- **Type hints**: Add type hints to all function signatures
- **Docstrings**: Use Google-style docstrings for all public functions/classes

### Code Quality

- **Complexity**: Keep McCabe complexity ≤ 12
- **DRY principle**: Don't repeat yourself
- **SOLID principles**: Follow object-oriented design principles
- **Error handling**: Use specific exceptions, avoid bare `except:`
- **Logging**: Use the `logging` module, not `print()`

### Example

```python
def bdp(
    tickers: str | list[str],
    flds: str | list[str],
    **kwargs: Any,
) -> pd.DataFrame:
    """Fetch reference data from Bloomberg.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields.
        **kwargs: Additional Bloomberg overrides.

    Returns:
        DataFrame with tickers as index and fields as columns.

    Raises:
        ValueError: If tickers or flds are empty.
        ConnectionError: If Bloomberg connection fails.

    Examples:
        >>> blp.bdp('AAPL US Equity', 'PX_LAST')  # doctest: +SKIP
    """
    # Implementation
```

## Testing

### Running Tests

```bash
# Run all tests (without Bloomberg connection)
uv run pytest --doctest-modules -v xbbg

# Run with coverage report
uv run pytest --doctest-modules --cov -v xbbg

# Run specific test file
uv run pytest xbbg/tests/test_helpers.py -v

# Run live endpoint tests (requires Bloomberg connection)
uv run pytest --run-xbbg-live -v xbbg
```

### Writing Tests

- **Use pytest**: All tests should use pytest framework
- **Test coverage**: Aim for >80% coverage for new code
- **Test naming**: Use descriptive names (e.g., `test_bdp_single_ticker_single_field`)
- **Fixtures**: Use pytest fixtures for common setup
- **Mocking**: Mock Bloomberg API calls when testing without connection
- **Doctests**: Add doctests to docstrings for simple examples

### Test Structure

```python
def test_bdp_single_ticker_single_field():
    """Test bdp with single ticker and single field."""
    # Arrange
    ticker = 'AAPL US Equity'
    field = 'PX_LAST'
    
    # Act
    result = blp.bdp(ticker, field)
    
    # Assert
    assert isinstance(result, pd.DataFrame)
    assert result.index[0] == ticker
    assert field.lower() in result.columns
```

## Documentation

### Docstrings

- **All public functions/classes** must have docstrings
- **Use Google style** for consistency
- **Include examples** using doctests when appropriate
- **Document parameters** with types and descriptions
- **Document return values** and exceptions

### README and Docs

- **Update README.md** if you add new features
- **Update Sphinx docs** in `docs/` directory
- **Add examples** to `examples/` directory if applicable
- **Keep docs in sync** with code changes

### Building Documentation

```bash
# Install docs dependencies
uv sync --locked --extra docs

# Build HTML documentation
uv run sphinx-build -b html docs docs/_build/html

# View documentation
# Open docs/_build/html/index.html in your browser
```

## Community

### Getting Help

- **Discord**: Join our [Discord community](https://discord.gg/fUUy2nfzxM) for discussions and help
- **GitHub Issues**: Search existing issues or create a new one
- **Documentation**: Check [ReadTheDocs](https://xbbg.readthedocs.io/)

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests, technical discussions
- **Discord**: General questions, community support, announcements
- **Pull Requests**: Code reviews, implementation discussions

### Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes (for significant contributions)
- Community acknowledgments

## License

By contributing to xbbg, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

Thank you for contributing to xbbg! 🎉
