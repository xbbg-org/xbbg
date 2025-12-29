def test_imports():
    """Test that the xbbg package and its Rust extension can be imported."""
    import importlib

    # Import from installed package (not local source)
    import xbbg

    assert xbbg is not None
    mod = importlib.import_module("xbbg._core")
    assert hasattr(mod, "__version__")
