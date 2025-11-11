def __getattr__(name: str):
    if name == "_core":
        from . import _core as mod  # type: ignore[attr-defined]

        return mod
    raise AttributeError(name)

__all__ = ["_core"]


