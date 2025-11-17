"""Unit tests for override processing functions."""

from __future__ import annotations

from xbbg.core.config import overrides


class TestProcOvrds:
    """Test proc_ovrds function."""

    def test_proc_ovrds_simple(self):
        """Test processing simple overrides."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt='20180101'))
        assert result == [('DVD_Start_Dt', '20180101')]

    def test_proc_ovrds_excludes_preserved_cols(self):
        """Test that preserved columns are excluded."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt='20180101', cache=True, has_date=True))
        assert result == [('DVD_Start_Dt', '20180101')]
        assert ('cache', True) not in result
        assert ('has_date', True) not in result

    def test_proc_ovrds_excludes_element_keys(self):
        """Test that element keys are excluded."""
        result = list(overrides.proc_ovrds(DVD_Start_Dt='20180101', Per='W', Period='M'))
        assert result == [('DVD_Start_Dt', '20180101')]
        assert ('Per', 'W') not in result
        assert ('Period', 'M') not in result

    def test_proc_ovrds_multiple_overrides(self):
        """Test processing multiple overrides."""
        result = list(overrides.proc_ovrds(
            DVD_Start_Dt='20180101',
            DVD_End_Dt='20180501',
            Custom_Field='value'
        ))
        assert len(result) == 3
        assert ('DVD_Start_Dt', '20180101') in result
        assert ('DVD_End_Dt', '20180501') in result
        assert ('Custom_Field', 'value') in result

    def test_proc_ovrds_empty(self):
        """Test processing empty kwargs."""
        result = list(overrides.proc_ovrds())
        assert result == []

    def test_proc_ovrds_all_excluded(self):
        """Test when all kwargs are excluded."""
        result = list(overrides.proc_ovrds(
            cache=True,
            has_date=True,
            Per='W',
            Period='M'
        ))
        assert result == []


class TestProcElms:
    """Test proc_elms function."""

    def test_proc_elms_periodicity_aliases(self):
        """Test periodicity adjustment aliases."""
        result = list(overrides.proc_elms(PerAdj='A', Per='W'))
        assert ('periodicityAdjustment', 'ACTUAL') in result
        assert ('periodicitySelection', 'WEEKLY') in result

    def test_proc_elms_fill_options(self):
        """Test fill option aliases."""
        result = list(overrides.proc_elms(Days='A', Fill='B'))
        assert ('nonTradingDayFillOption', 'ALL_CALENDAR_DAYS') in result
        assert ('nonTradingDayFillMethod', 'NIL_VALUE') in result

    def test_proc_elms_adjustment_flags(self):
        """Test adjustment flags."""
        result = list(overrides.proc_elms(CshAdjNormal=False, CshAdjAbnormal=True))
        assert ('adjustmentNormal', False) in result
        assert ('adjustmentAbnormal', True) in result

    def test_proc_elms_quote_options(self):
        """Test quote option aliases."""
        result = list(overrides.proc_elms(Quote='Average'))
        assert ('overrideOption', 'OVERRIDE_OPTION_GPA') in result

    def test_proc_elms_pricing_options(self):
        """Test pricing option aliases."""
        result = list(overrides.proc_elms(QuoteType='Y'))
        assert ('pricingOption', 'PRICING_OPTION_YIELD') in result

    def test_proc_elms_excludes_preserved_cols(self):
        """Test that preserved columns are excluded."""
        result = list(overrides.proc_elms(QuoteType='Y', cache=True, start_date='2018-01-10'))
        assert ('pricingOption', 'PRICING_OPTION_YIELD') in result
        assert ('cache', True) not in result
        assert ('start_date', '2018-01-10') not in result

    def test_proc_elms_canonical_keys(self):
        """Test using canonical keys directly."""
        result = list(overrides.proc_elms(periodicitySelection='WEEKLY'))
        assert ('periodicitySelection', 'WEEKLY') in result

    def test_proc_elms_unknown_value(self):
        """Test unknown values pass through."""
        result = list(overrides.proc_elms(currency='UNKNOWN_VALUE'))
        assert ('currency', 'UNKNOWN_VALUE') in result

    def test_proc_elms_empty(self):
        """Test processing empty kwargs."""
        result = list(overrides.proc_elms())
        assert result == []

    def test_proc_elms_all_periodicity_selections(self):
        """Test all periodicity selection values."""
        selections = {
            'D': 'DAILY',
            'W': 'WEEKLY',
            'M': 'MONTHLY',
            'Q': 'QUARTERLY',
            'S': 'SEMI_ANNUALLY',
            'Y': 'YEARLY'
        }
        for alias, expected in selections.items():
            result = list(overrides.proc_elms(Per=alias))
            assert ('periodicitySelection', expected) in result

    def test_proc_elms_all_periodicity_adjustments(self):
        """Test all periodicity adjustment values."""
        adjustments = {
            'A': 'ACTUAL',
            'C': 'CALENDAR',
            'F': 'FISCAL'
        }
        for alias, expected in adjustments.items():
            result = list(overrides.proc_elms(PerAdj=alias))
            assert ('periodicityAdjustment', expected) in result


class TestInfoQry:
    """Test info_qry function."""

    def test_info_qry_simple(self):
        """Test info query with simple inputs."""
        result = overrides.info_qry(
            tickers=['NVDA US Equity'],
            flds=['Name', 'Security_Name']
        )
        assert 'tickers: [\'NVDA US Equity\']' in result
        assert "fields:  ['Name', 'Security_Name']" in result

    def test_info_qry_multiple_tickers(self):
        """Test info query with multiple tickers."""
        tickers = [f'TICKER{i} US Equity' for i in range(10)]
        result = overrides.info_qry(tickers=tickers, flds=['PX_LAST'])
        assert 'tickers: [' in result
        assert 'fields:  [\'PX_LAST\']' in result

    def test_info_qry_long_ticker_list(self):
        """Test info query with long ticker list (wraps to multiple lines)."""
        tickers = [f'TICKER{i} US Equity' for i in range(20)]
        result = overrides.info_qry(tickers=tickers, flds=['PX_LAST'])
        # Should wrap to multiple lines
        lines = result.split('\n')
        assert len([line for line in lines if line.startswith('tickers:') or line.startswith('         ')]) >= 3

    def test_info_qry_empty_tickers(self):
        """Test info query with empty tickers."""
        result = overrides.info_qry(tickers=[], flds=['PX_LAST'])
        assert 'tickers: []' in result
        assert "fields:  ['PX_LAST']" in result

    def test_info_qry_empty_fields(self):
        """Test info query with empty fields."""
        result = overrides.info_qry(tickers=['AAPL US Equity'], flds=[])
        assert 'tickers: [\'AAPL US Equity\']' in result
        assert 'fields:  []' in result

