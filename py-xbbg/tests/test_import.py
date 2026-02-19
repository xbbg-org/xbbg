from __future__ import annotations


def test_imports():
    """Test that the xbbg package and its Rust extension can be imported."""
    # Import from installed package (not local source)
    import xbbg

    assert xbbg is not None
    # Access _core through the package to trigger __getattr__ which sets up DLL paths
    assert xbbg._core is not None
    assert hasattr(xbbg._core, "__version__")
