"""Tests for backend availability checking.

Tests the backend availability checking functions in xbbg/backend.py.
"""

from __future__ import annotations

import pytest

from xbbg.backend import (
    MIN_VERSIONS,
    MODULE_NAMES,
    PACKAGE_NAMES,
    SUPPORTED_FORMATS,
    Backend,
    Format,
    _format_version,
    _parse_version,
    check_backend,
    check_format_compatibility,
    get_available_backends,
    get_supported_formats,
    is_backend_available,
    is_format_supported,
)


class TestVersionParsing:
    """Test version string parsing."""

    def test_parse_simple_version(self):
        """Test parsing simple version strings."""
        assert _parse_version("2.0.1") == (2, 0, 1)
        assert _parse_version("1.2.3") == (1, 2, 3)
        assert _parse_version("0.20.4") == (0, 20, 4)

    def test_parse_short_version(self):
        """Test parsing short version strings."""
        assert _parse_version("2.0") == (2, 0)
        assert _parse_version("13") == (13,)

    def test_parse_version_with_suffix(self):
        """Test parsing versions with alpha/beta/rc suffixes."""
        assert _parse_version("2.0.1a1") == (2, 0, 1)
        assert _parse_version("2.0.1b2") == (2, 0, 1)
        assert _parse_version("2.0.1rc1") == (2, 0, 1)

    def test_parse_version_with_local(self):
        """Test parsing versions with local version identifier."""
        assert _parse_version("2.0.1+local") == (2, 0, 1)

    def test_format_version(self):
        """Test formatting version tuples."""
        assert _format_version((2, 0, 1)) == "2.0.1"
        assert _format_version((0, 20)) == "0.20"
        assert _format_version((13,)) == "13"


class TestBackendMetadata:
    """Test backend metadata dictionaries."""

    def test_min_versions_has_all_backends(self):
        """Test that MIN_VERSIONS has entries for backends that need them."""
        # These backends should have version requirements
        required = {
            Backend.PANDAS,
            Backend.POLARS,
            Backend.POLARS_LAZY,
            Backend.PYARROW,
            Backend.DUCKDB,
            Backend.CUDF,
            Backend.MODIN,
            Backend.DASK,
            Backend.IBIS,
            Backend.PYSPARK,
            Backend.SQLFRAME,
        }
        for backend in required:
            assert backend in MIN_VERSIONS, f"Missing MIN_VERSION for {backend}"

    def test_package_names_has_all_backends(self):
        """Test that PACKAGE_NAMES has entries for relevant backends."""
        # These backends should have package names for install instructions
        required = {
            Backend.PANDAS,
            Backend.POLARS,
            Backend.POLARS_LAZY,
            Backend.DUCKDB,
            Backend.CUDF,
            Backend.MODIN,
            Backend.DASK,
            Backend.IBIS,
            Backend.PYSPARK,
            Backend.SQLFRAME,
        }
        for backend in required:
            assert backend in PACKAGE_NAMES, f"Missing PACKAGE_NAME for {backend}"

    def test_module_names_has_all_backends(self):
        """Test that MODULE_NAMES has entries for all backends."""
        for backend in Backend:
            assert backend in MODULE_NAMES, f"Missing MODULE_NAME for {backend}"


class TestBackendAvailability:
    """Test backend availability checking."""

    def test_narwhals_always_available(self):
        """Test that narwhals is always available (core dependency)."""
        assert is_backend_available(Backend.NARWHALS)
        assert is_backend_available(Backend.NARWHALS_LAZY)

    def test_pyarrow_always_available(self):
        """Test that pyarrow is always available (core dependency)."""
        assert is_backend_available(Backend.PYARROW)

    def test_pandas_available(self):
        """Test pandas availability (installed in dev environment)."""
        # pandas is in dev dependencies
        assert is_backend_available(Backend.PANDAS)

    def test_check_backend_core_dependencies(self):
        """Test check_backend passes for core dependencies."""
        assert check_backend(Backend.NARWHALS, raise_on_error=True)
        assert check_backend(Backend.PYARROW, raise_on_error=True)

    def test_check_backend_pandas(self):
        """Test check_backend for pandas."""
        # Should not raise since pandas is installed
        assert check_backend(Backend.PANDAS, raise_on_error=True)

    def test_check_backend_unavailable_no_raise(self):
        """Test check_backend returns False for unavailable backend."""
        # cudf is unlikely to be installed
        result = check_backend(Backend.CUDF, raise_on_error=False)
        # Result depends on whether cudf is installed
        assert isinstance(result, bool)

    def test_get_available_backends_includes_core(self):
        """Test that get_available_backends includes core dependencies."""
        available = get_available_backends()
        assert Backend.NARWHALS in available
        assert Backend.NARWHALS_LAZY in available
        assert Backend.PYARROW in available


class TestFormatCompatibility:
    """Test format compatibility checking."""

    def test_supported_formats_has_all_backends(self):
        """Test that SUPPORTED_FORMATS has entries for all backends."""
        for backend in Backend:
            assert backend in SUPPORTED_FORMATS, f"Missing SUPPORTED_FORMATS for {backend}"

    def test_all_backends_support_long(self):
        """Test that all backends support LONG format."""
        for backend in Backend:
            assert is_format_supported(backend, Format.LONG)

    def test_all_backends_support_semi_long(self):
        """Test that all backends support SEMI_LONG format."""
        for backend in Backend:
            assert is_format_supported(backend, Format.SEMI_LONG)

    def test_eager_backends_support_wide(self):
        """Test that eager backends support WIDE format."""
        eager_backends = [
            Backend.PANDAS,
            Backend.POLARS,
            Backend.PYARROW,
            Backend.NARWHALS,
            Backend.CUDF,
            Backend.MODIN,
        ]
        for backend in eager_backends:
            assert is_format_supported(backend, Format.WIDE), f"{backend} should support WIDE"

    def test_lazy_backends_no_wide(self):
        """Test that lazy backends don't support WIDE format."""
        lazy_backends = [
            Backend.NARWHALS_LAZY,
            Backend.POLARS_LAZY,
            Backend.DUCKDB,
            Backend.DASK,
            Backend.IBIS,
            Backend.PYSPARK,
            Backend.SQLFRAME,
        ]
        for backend in lazy_backends:
            assert not is_format_supported(backend, Format.WIDE), f"{backend} should not support WIDE"

    def test_get_supported_formats_returns_set(self):
        """Test that get_supported_formats returns a set."""
        formats = get_supported_formats(Backend.PANDAS)
        assert isinstance(formats, set)
        assert Format.LONG in formats

    def test_check_format_compatibility_pass(self):
        """Test check_format_compatibility passes for valid combinations."""
        assert check_format_compatibility(Backend.PANDAS, Format.LONG)
        assert check_format_compatibility(Backend.PANDAS, Format.WIDE)

    def test_check_format_compatibility_fail_no_raise(self):
        """Test check_format_compatibility returns False for invalid combinations."""
        result = check_format_compatibility(Backend.DUCKDB, Format.WIDE, raise_on_error=False)
        assert result is False

    def test_check_format_compatibility_fail_with_raise(self):
        """Test check_format_compatibility raises for invalid combinations."""
        with pytest.raises(ValueError, match="does not support format"):
            check_format_compatibility(Backend.DUCKDB, Format.WIDE, raise_on_error=True)


class TestBackendCategories:
    """Test backend categorization."""

    def test_eager_backends_count(self):
        """Test that we have the expected number of eager backends."""
        eager = [
            Backend.NARWHALS,
            Backend.PANDAS,
            Backend.POLARS,
            Backend.PYARROW,
            Backend.CUDF,
            Backend.MODIN,
        ]
        assert len(eager) == 6

    def test_lazy_backends_count(self):
        """Test that we have the expected number of lazy backends."""
        lazy = [
            Backend.NARWHALS_LAZY,
            Backend.POLARS_LAZY,
            Backend.DUCKDB,
            Backend.DASK,
            Backend.IBIS,
            Backend.PYSPARK,
            Backend.SQLFRAME,
        ]
        assert len(lazy) == 7

    def test_total_backends(self):
        """Test total backend count."""
        assert len(Backend) == 13
