def test_imports():
    import importlib
    import os
    import sys

    # Ensure the scaffolded py-xbbg/src package is preferred
    pkg_root = os.path.dirname(os.path.dirname(__file__))  # py-xbbg
    python_src = os.path.join(pkg_root, "src")
    if python_src not in sys.path:
        sys.path.insert(0, python_src)
    import xbbg

    assert xbbg is not None
    mod = importlib.import_module("xbbg._core")
    assert hasattr(mod, "__version__")
