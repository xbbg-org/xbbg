from __future__ import annotations

import pytest

from xbbg import blp


@pytest.mark.parametrize(
    ("name", "needle"),
    [
        ("connect", "xbbg.configure"),
        ("disconnect", "xbbg.shutdown"),
        ("getBlpapiVersion", "xbbg.get_sdk_info"),
    ],
)
def test_removed_legacy_attr_points_to_replacement(name: str, needle: str) -> None:
    with pytest.raises(AttributeError, match=needle):
        getattr(blp, name)


def test_unknown_attr_still_raises_plain_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no attribute 'definitely_not_a_real_attr'"):
        blp.definitely_not_a_real_attr  # type: ignore[attr-defined]
