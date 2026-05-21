from __future__ import annotations

import pytest

from xbbg import Backend, blp

WEATHER_PARAMS = {
    "provider": "wsi",
    "location": "nwe",
    "weight_type": "population",
    "model": "ecmwf",
    "type": "ENSEMBLE_MEDIAN",
    "publication_date": "2025-12-01T00:00:00",
    "fields": "HDD_18C",
    "location_time": True,
}


def _skip_if_bloomberg_unavailable() -> None:
    try:
        blp.bdp("AAPL US Equity", "PX_LAST", backend=Backend.NATIVE)
    except Exception as exc:  # pragma: no cover - depends on Bloomberg availability
        pytest.skip(f"Bloomberg native backend unavailable in this environment: {exc}")


def _skip_if_weather_bsrch_unavailable(exc: Exception) -> None:
    message = str(exc)
    unavailable_markers = (
        "NOT_ENTITLED",
        "not entitled",
        "NOT_AUTHORIZED",
        "Problem accessing the saved search",
    )
    if any(marker in message for marker in unavailable_markers):
        pytest.skip(f"Bloomberg weather BSRCH unavailable in this environment: {exc}")
    raise exc


@pytest.mark.parametrize("style", ["kwargs", "overrides"])
def test_bsrch_weather_excel_grid_response_returns_rows(style: str):
    _skip_if_bloomberg_unavailable()
    try:
        if style == "kwargs":
            table = blp.bsrch("COMDTY:WEATHER", backend=Backend.NATIVE, **WEATHER_PARAMS)
        else:
            overrides = {**WEATHER_PARAMS, "location_time": "true"}
            table = blp.bsrch("COMDTY:WEATHER", overrides=overrides, backend=Backend.NATIVE)
    except Exception as exc:
        _skip_if_weather_bsrch_unavailable(exc)

    assert table.num_rows > 0
    assert "Reported Time" in table.column_names
    assert any("Heating Degree Days" in column for column in table.column_names)
