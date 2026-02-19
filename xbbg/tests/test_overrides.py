"""Unit tests for override processing functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from xbbg.core.config import overrides


class TestProcOvrds:
    """Test proc_ovrds function."""

    def test_proc_ovrds_simple(self):
        """Test processing simple overrides."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt="20180101"))
        assert result == [("DVD_Start_Dt", "20180101")]

    def test_proc_ovrds_excludes_preserved_cols(self):
        """Test that preserved columns are excluded."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt="20180101", cache=True, has_date=True))
        assert result == [("DVD_Start_Dt", "20180101")]
        assert ("cache", True) not in result
        assert ("has_date", True) not in result

    def test_proc_ovrds_excludes_element_keys(self):
        """Test that element keys are excluded."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt="20180101", Per="W", Period="M"))
        assert result == [("DVD_Start_Dt", "20180101")]
        assert ("Per", "W") not in result
        assert ("Period", "M") not in result

    def test_proc_ovrds_multiple_overrides(self):
        """Test processing multiple overrides."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt="20180101", DVD_End_Dt="20180501", Custom_Field="value"))
        assert len(result) == 3
        assert ("DVD_Start_Dt", "20180101") in result
        assert ("DVD_End_Dt", "20180501") in result
        assert ("Custom_Field", "value") in result

    def test_proc_ovrds_empty(self):
        """Test processing empty kwargs."""
        result = list(overrides.proc_ovrds())
        assert result == []

    def test_proc_ovrds_all_excluded(self):
        """Test when all kwargs are excluded."""
        result = list(overrides.proc_ovrds(cache=True, has_date=True, Per="W", Period="M"))
        assert result == []


class TestProcElms:
    """Test proc_elms function."""

    def test_proc_elms_periodicity_aliases(self):
        """Test periodicity adjustment aliases."""
        result = list(overrides.proc_elms(PerAdj="A", Per="W"))
        assert ("periodicityAdjustment", "ACTUAL") in result
        assert ("periodicitySelection", "WEEKLY") in result

    def test_proc_elms_fill_options(self):
        """Test fill option aliases."""
        result = list(overrides.proc_elms(Days="A", Fill="B"))
        assert ("nonTradingDayFillOption", "ALL_CALENDAR_DAYS") in result
        assert ("nonTradingDayFillMethod", "NIL_VALUE") in result

    def test_proc_elms_adjustment_flags(self):
        """Test adjustment flags."""
        result = list(overrides.proc_elms(CshAdjNormal=False, CshAdjAbnormal=True))
        assert ("adjustmentNormal", False) in result
        assert ("adjustmentAbnormal", True) in result

    def test_proc_elms_quote_options(self):
        """Test quote option aliases."""
        result = list(overrides.proc_elms(Quote="Average"))
        assert ("overrideOption", "OVERRIDE_OPTION_GPA") in result

    def test_proc_elms_pricing_options(self):
        """Test pricing option aliases."""
        result = list(overrides.proc_elms(QuoteType="Y"))
        assert ("pricingOption", "PRICING_OPTION_YIELD") in result

    def test_proc_elms_excludes_preserved_cols(self):
        """Test that preserved columns are excluded."""
        result = list(overrides.proc_elms(QuoteType="Y", cache=True, start_date="2018-01-10"))
        assert ("pricingOption", "PRICING_OPTION_YIELD") in result
        assert ("cache", True) not in result
        assert ("start_date", "2018-01-10") not in result

    def test_proc_elms_canonical_keys(self):
        """Test using canonical keys directly."""
        result = list(overrides.proc_elms(periodicitySelection="WEEKLY"))
        assert ("periodicitySelection", "WEEKLY") in result

    def test_proc_elms_unknown_value(self):
        """Test unknown values pass through."""
        result = list(overrides.proc_elms(currency="UNKNOWN_VALUE"))
        assert ("currency", "UNKNOWN_VALUE") in result

    def test_proc_elms_empty(self):
        """Test processing empty kwargs."""
        result = list(overrides.proc_elms())
        assert result == []

    def test_proc_elms_all_periodicity_selections(self):
        """Test all periodicity selection values."""
        selections = {
            "D": "DAILY",
            "W": "WEEKLY",
            "M": "MONTHLY",
            "Q": "QUARTERLY",
            "S": "SEMI_ANNUALLY",
            "Y": "YEARLY",
        }
        for alias, expected in selections.items():
            result = list(overrides.proc_elms(Per=alias))
            assert ("periodicitySelection", expected) in result

    def test_proc_elms_all_periodicity_adjustments(self):
        """Test all periodicity adjustment values."""
        adjustments = {"A": "ACTUAL", "C": "CALENDAR", "F": "FISCAL"}
        for alias, expected in adjustments.items():
            result = list(overrides.proc_elms(PerAdj=alias))
            assert ("periodicityAdjustment", expected) in result


class TestInfoQry:
    """Test info_qry function."""

    def test_info_qry_simple(self):
        """Test info query with simple inputs."""
        result = overrides.info_qry(tickers=["NVDA US Equity"], flds=["Name", "Security_Name"])
        assert "tickers: ['NVDA US Equity']" in result
        assert "fields:  ['Name', 'Security_Name']" in result

    def test_info_qry_multiple_tickers(self):
        """Test info query with multiple tickers."""
        tickers = [f"TICKER{i} US Equity" for i in range(10)]
        result = overrides.info_qry(tickers=tickers, flds=["PX_LAST"])
        assert "tickers: [" in result
        assert "fields:  ['PX_LAST']" in result

    def test_info_qry_long_ticker_list(self):
        """Test info query with long ticker list (wraps to multiple lines)."""
        tickers = [f"TICKER{i} US Equity" for i in range(20)]
        result = overrides.info_qry(tickers=tickers, flds=["PX_LAST"])
        # Should wrap to multiple lines
        lines = result.split("\n")
        assert len([line for line in lines if line.startswith("tickers:") or line.startswith("         ")]) >= 3

    def test_info_qry_empty_tickers(self):
        """Test info query with empty tickers."""
        result = overrides.info_qry(tickers=[], flds=["PX_LAST"])
        assert "tickers: []" in result
        assert "fields:  ['PX_LAST']" in result

    def test_info_qry_empty_fields(self):
        """Test info query with empty fields."""
        result = overrides.info_qry(tickers=["AAPL US Equity"], flds=[])
        assert "tickers: ['AAPL US Equity']" in result
        assert "fields:  []" in result


class TestIssue145Regression:
    """Regression tests for #145: interval leaked as Bloomberg override field.

    When calling bdib(session='open'), the `interval` parameter was being passed
    through to proc_ovrds() and sent as a Bloomberg override, causing:
        "Invalid override field: interval"

    Fixed by adding 'interval' to PRSV_COLS so it's excluded from overrides.
    """

    def test_interval_excluded_from_overrides(self):
        """Interval must not appear in proc_ovrds() output (#145)."""
        result = list(overrides.proc_ovrds(interval=1, DVD_Start_Dt="20180101"))
        keys = [k for k, _ in result]
        assert "interval" not in keys
        assert "DVD_Start_Dt" in keys

    def test_interval_excluded_from_elements(self):
        """Interval must not appear in proc_elms() output either."""
        result = list(overrides.proc_elms(interval=1, Per="W"))
        keys = [k for k, _ in result]
        assert "interval" not in keys
        assert "periodicitySelection" in keys

    def test_bdib_session_params_excluded_from_overrides(self):
        """All bdib-specific params (interval, typ, session, etc.) must be excluded."""
        bdib_kwargs = {
            "interval": 1,
            "typ": "TRADE",
            "intervalHasSeconds": True,
            "time_range": ("09:30", "16:00"),
            "batch": False,
            "reload": False,
            "DVD_Start_Dt": "20180101",  # This IS a real override
        }
        result = list(overrides.proc_ovrds(**bdib_kwargs))
        keys = [k for k, _ in result]
        # Only the real Bloomberg override should remain
        assert keys == ["DVD_Start_Dt"]

    def test_preserved_cols_contains_interval(self):
        """PRSV_COLS must include 'interval' to prevent override leakage."""
        assert "interval" in overrides.PRSV_COLS

    def test_preserved_cols_contains_all_bdib_params(self):
        """PRSV_COLS must include all bdib-specific parameters."""
        for param in ["interval", "typ", "types", "intervalHasSeconds", "time_range", "batch", "reload"]:
            assert param in overrides.PRSV_COLS, f"'{param}' missing from PRSV_COLS"


class TestCreateRequestOvrdsRegression:
    """Regression tests for create_request ovrds=dict crash.

    When passing ovrds as a dict (e.g., ovrds={"PRICING_SOURCE": "BGN"}),
    create_request crashed with:
        ValueError: too many values to unpack (expected 2)

    Root cause: iterating a dict yields keys (strings), and unpacking a
    multi-char string into (fld, val) fails. Fixed by normalizing dict
    to list of tuples before iteration.

    See: https://stackoverflow.com/questions/79880156
    """

    def _mock_bbg_service(self):
        """Create a mock Bloomberg service with trackable override elements."""
        mock_overrides_element = MagicMock()
        mock_items = []

        def track_append():
            item = MagicMock()
            elements = {}

            def set_element(name, value):
                elements[str(name)] = value

            item.setElement = set_element
            item._elements = elements
            mock_items.append(item)
            return item

        mock_overrides_element.appendElement = track_append

        mock_request = MagicMock()
        mock_request.getElement = MagicMock(return_value=mock_overrides_element)

        mock_service = MagicMock()
        mock_service.createRequest = MagicMock(return_value=mock_request)

        return mock_service, mock_request, mock_items

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_dict_does_not_crash(self, mock_bbg_service):
        """ovrds=dict must not raise ValueError (was crashing before fix)."""
        from xbbg.core.process import create_request

        mock_service, _, _ = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        # This used to raise: ValueError: too many values to unpack (expected 2)
        req = create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds={"PRICING_SOURCE": "BGN"},
        )
        assert req is not None

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_dict_sets_overrides_correctly(self, mock_bbg_service):
        """ovrds=dict must produce the same override elements as list of tuples."""
        from xbbg.core.process import create_request

        mock_service, _, mock_items = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds={"PRICING_SOURCE": "BGN"},
        )

        assert len(mock_items) == 1
        assert mock_items[0]._elements["fieldId"] == "PRICING_SOURCE"
        assert mock_items[0]._elements["value"] == "BGN"

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_dict_multiple_overrides(self, mock_bbg_service):
        """ovrds=dict with multiple keys must set all overrides."""
        from xbbg.core.process import create_request

        mock_service, _, mock_items = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds={"PRICING_SOURCE": "BGN", "SETTLE_DT": "20260121"},
        )

        assert len(mock_items) == 2
        fields_set = {item._elements["fieldId"] for item in mock_items}
        assert fields_set == {"PRICING_SOURCE", "SETTLE_DT"}

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_list_of_tuples_still_works(self, mock_bbg_service):
        """ovrds=list[tuple] must continue to work (backward compat)."""
        from xbbg.core.process import create_request

        mock_service, _, mock_items = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds=[("PRICING_SOURCE", "BGN")],
        )

        assert len(mock_items) == 1
        assert mock_items[0]._elements["fieldId"] == "PRICING_SOURCE"
        assert mock_items[0]._elements["value"] == "BGN"

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_none_skips_overrides(self, mock_bbg_service):
        """ovrds=None must not touch the overrides element."""
        from xbbg.core.process import create_request

        mock_service, mock_request, _ = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds=None,
        )

        mock_request.getElement.assert_not_called()

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_empty_dict_skips_overrides(self, mock_bbg_service):
        """ovrds={} must not touch the overrides element."""
        from xbbg.core.process import create_request

        mock_service, mock_request, _ = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds={},
        )

        mock_request.getElement.assert_not_called()

    @patch("xbbg.core.process.conn.bbg_service")
    def test_ovrds_empty_list_skips_overrides(self, mock_bbg_service):
        """ovrds=[] must not touch the overrides element."""
        from xbbg.core.process import create_request

        mock_service, mock_request, _ = self._mock_bbg_service()
        mock_bbg_service.return_value = mock_service

        create_request(
            service="//blp/refdata",
            request="HistoricalDataRequest",
            ovrds=[],
        )

        mock_request.getElement.assert_not_called()
