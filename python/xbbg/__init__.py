def __getattr__(name: str):
    # Lazy import compiled module on first attribute access
    if name == "_core":
        from . import _core as mod  # type: ignore[attr-defined]

        return mod
    raise AttributeError(name)

__all__ = ["_core"]


