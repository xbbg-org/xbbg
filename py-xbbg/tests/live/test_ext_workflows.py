"""Live Bloomberg tests for native-backed extension workflows."""

from __future__ import annotations

import pandas as pd


def _pdf(frame) -> pd.DataFrame:
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    if hasattr(frame, "to_native"):
        native = frame.to_native()
        if hasattr(native, "to_pandas"):
            return native.to_pandas()
        return pd.DataFrame(native)
    return pd.DataFrame(frame)


def test_futures_curve_live_invariants():
    from xbbg.ext import futures_curve

    pdf = _pdf(futures_curve("ES1 Index", max_contracts=6, backend="pandas"))

    assert not pdf.empty
    assert {"source_ticker", "contract_ticker", "generic_number", "mid", "annualized_carry"}.issubset(pdf.columns)
    assert pdf["generic_number"].tolist() == sorted(pdf["generic_number"].tolist())
    assert pdf["contract_ticker"].notna().all()

    both_sides = pdf["px_bid"].notna() & pdf["px_ask"].notna()
    if both_sides.any():
        expected_mid = (pdf.loc[both_sides, "px_bid"] + pdf.loc[both_sides, "px_ask"]) / 2
        assert (pdf.loc[both_sides, "mid"] - expected_mid).abs().max() < 1e-9
    assert pdf.loc[~both_sides, "mid"].isna().all()


def test_vol_surface_live_tidy_and_derived_rows():
    from xbbg.ext import VolSurfacePreset, vol_surface

    pdf = _pdf(
        vol_surface(
            "SPX Index",
            start_date="2024-01-02",
            end_date="2024-01-05",
            preset=VolSurfacePreset.MONEYNESS_30D,
            include_derived=True,
            risk_free_rate=0.05,
            backend="pandas",
        )
    )

    assert not pdf.empty
    assert {"ticker", "date", "metric", "tenor", "point_type", "point", "field", "value"}.issubset(pdf.columns)
    assert (pdf.loc[pdf["metric"] == "implied_volatility", "value"].dropna() < 5).all()
    assert {"spot", "risk_free_rate"}.issubset(set(pdf["metric"]))
    assert {"forward", "discount_factor"}.intersection(set(pdf["metric"]))


def test_dividend_yield_live_realized_trailing_amount():
    from xbbg.ext import dividend_yield

    pdf = _pdf(
        dividend_yield(
            "AAPL US Equity",
            start_date="2023-01-01",
            end_date="2024-12-31",
            dividend_types=["Regular Cash"],
            backend="pandas",
        )
    )

    assert not pdf.empty
    assert {"ticker", "date", "dividend_amount", "trailing_dividend_amount", "price", "dividend_yield"}.issubset(
        pdf.columns
    )
    priced = pdf[pdf["price"].notna()]
    assert not priced.empty
    assert (priced["trailing_dividend_amount"].dropna() >= 0).all()
    assert (priced["dividend_yield"].dropna() > 0).any()
    event_cols = ["ticker", "date", "declared_date", "record_date", "payable_date", "dividend_type"]
    event_rows = pdf[pdf["dividend_amount"].notna()]
    assert not event_rows.duplicated(event_cols).any()


def test_index_members_live_asof_override():
    from xbbg.ext import index_members

    pdf = _pdf(index_members("SPX Index", field="INDX_MWEIGHT", asof="2024-01-02", backend="pandas"))

    assert not pdf.empty
    assert "member" in pdf.columns
    assert pdf["member"].notna().any()
    assert len(pdf.columns) > 3


def test_identifier_workflows_live_order_and_unresolved():
    from xbbg.ext import issuer_isins, resolve_isins

    resolved = _pdf(resolve_isins(["US0378331005", "INVALIDISIN000"], backend="pandas"))
    assert resolved["input_isin"].tolist() == ["US0378331005", "INVALIDISIN000"]
    assert resolved.loc[0, "status"] == "resolved"
    assert isinstance(resolved.loc[0, "resolved_ticker"], str)
    assert resolved.loc[1, "status"] == "unresolved"

    issuer = _pdf(issuer_isins(["US037833FB15", "INVALIDISIN000"], backend="pandas"))
    assert issuer["input_isin"].tolist() == ["US037833FB15", "INVALIDISIN000"]
    assert issuer.loc[0, "status"] == "resolved"
    assert isinstance(issuer.loc[0, "issuer_equity_isin"], str)
    assert issuer.loc[1, "status"] == "unresolved"
