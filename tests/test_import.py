def test_imports():
    import importlib
    import os
    import sys
    # Ensure the scaffolded python/ package is preferred over legacy_code/xbbg
    repo_root = os.path.dirname(os.path.dirname(__file__))
    python_src = os.path.join(repo_root, "python")
    if python_src not in sys.path:
        sys.path.insert(0, python_src)
    import xbbg

    assert xbbg is not None
    mod = importlib.import_module("xbbg._core")
    assert hasattr(mod, "__version__")


