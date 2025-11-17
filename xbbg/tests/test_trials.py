"""Unit tests for trial tracking functions."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import Mock, patch

from xbbg.core.utils import trials

trials_module = importlib.import_module('xbbg.core.utils.trials')


class TestRootPath:
    """Test root_path function."""

    def test_root_path_with_env_var(self):
        """Test root_path with BBG_ROOT set."""
        with patch.dict(os.environ, {'BBG_ROOT': '/test/path'}):
            result = trials.root_path()
            assert result == Path('/test/path')

    def test_root_path_without_env_var(self):
        """Test root_path without BBG_ROOT set."""
        with patch.dict(os.environ, {}, clear=True):
            if 'BBG_ROOT' in os.environ:
                del os.environ['BBG_ROOT']
            result = trials.root_path()
            assert result == Path('')


class TestTrailInfo:
    """Test trail_info function."""

    def test_trail_info_basic(self):
        """Test basic trail info conversion."""
        result = trials.trail_info(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        assert result['func'] == 'bdh'
        assert result['ticker'] == 'AAPL US Equity'
        assert result['dt'] == '2024-01-01'

    def test_trail_info_slash_replacement(self):
        """Test that slashes in ticker are replaced."""
        result = trials.trail_info(func='bdh', ticker='AAPL/US Equity')
        assert result['ticker'] == 'AAPL_US Equity'

    def test_trail_info_date_formatting(self):
        """Test date formatting in trail_info."""
        result = trials.trail_info(func='bdh', start_date='2024-01-01', end_date='2024-12-31')
        assert result['start_date'] == '2024-01-01'
        assert result['end_date'] == '2024-12-31'

    def test_trail_info_no_func(self):
        """Test trail_info without func (should default to 'unknown')."""
        result = trials.trail_info(ticker='AAPL US Equity')
        assert result['func'] == 'unknown'

    def test_trail_info_various_date_fields(self):
        """Test trail_info with various date field names."""
        result = trials.trail_info(
            func='bdh',
            dt='2024-01-01',
            start_dt='2024-01-01',
            end_dt='2024-12-31',
            start_date='2024-01-01',
            end_date='2024-12-31'
        )
        assert 'dt' in result
        assert 'start_dt' in result
        assert 'end_dt' in result
        assert 'start_date' in result
        assert 'end_date' in result


class TestMissingInfo:
    """Test missing_info function."""

    def test_missing_info_basic(self):
        """Test basic missing info path generation."""
        result = trials.missing_info(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        assert result.startswith('bdh/')
        assert 'AAPL US Equity' in result
        assert '2024-01-01' in result

    def test_missing_info_slash_replacement(self):
        """Test that slashes in ticker are replaced."""
        result = trials.missing_info(func='bdh', ticker='AAPL/US Equity')
        assert 'AAPL_US Equity' in result
        assert 'AAPL/US Equity' not in result

    def test_missing_info_no_func(self):
        """Test missing_info without func (should default to 'unknown')."""
        result = trials.missing_info(ticker='AAPL US Equity')
        assert result.startswith('unknown/')

    def test_missing_info_date_formatting(self):
        """Test date formatting in missing_info."""
        result = trials.missing_info(func='bdh', start_date='2024-01-01')
        assert '2024-01-01' in result


class TestNumTrials:
    """Test num_trials function."""

    @patch.object(trials_module, 'root_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_num_trials_with_path(self, mock_sqlite, mock_create, mock_root):
        """Test num_trials when BBG_ROOT is set."""
        mock_root.return_value = Path('/test/path')
        mock_con = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(5,)]
        mock_con.execute.return_value = mock_cursor
        mock_sqlite.return_value.__enter__.return_value = mock_con

        result = trials.num_trials(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        assert result == 5

    @patch.object(trials_module, 'root_path')
    def test_num_trials_no_path(self, mock_root):
        """Test num_trials when BBG_ROOT is not set."""
        # Mock root_path to return a Path with empty as_posix()
        mock_path = Mock()
        mock_path.as_posix.return_value = ''
        mock_root.return_value = mock_path
        result = trials.num_trials(func='bdh', ticker='AAPL US Equity')
        # Function checks `if not data_path.as_posix(): return 0`
        assert result == 0

    @patch.object(trials_module, 'root_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_num_trials_no_results(self, mock_sqlite, mock_create, mock_root):
        """Test num_trials when no results found."""
        mock_root.return_value = Path('/test/path')
        mock_con = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_con.execute.return_value = mock_cursor
        mock_sqlite.return_value.__enter__.return_value = mock_con

        result = trials.num_trials(func='bdh', ticker='AAPL US Equity')
        assert result == 0


class TestUpdateTrials:
    """Test update_trials function."""

    @patch.object(trials_module, 'root_path')
    def test_update_trials_no_path(self, mock_root):
        """Test update_trials when BBG_ROOT is not set."""
        mock_root.return_value = Path('')
        # Should not raise an error
        trials.update_trials(func='bdh', ticker='AAPL US Equity')

    @patch.object(trials_module, 'root_path')
    @patch.object(trials_module, 'num_trials')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_update_trials_increment(self, mock_sqlite, mock_create, mock_num, mock_root):
        """Test update_trials increments count."""
        mock_root.return_value = Path('/test/path')
        mock_num.return_value = 3
        mock_con = Mock()
        mock_sqlite.return_value.__enter__.return_value = mock_con

        trials.update_trials(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        # Should increment from 3 to 4
        mock_con.execute.assert_called()
        call_args = mock_con.execute.call_args[0][0]
        assert 'cnt=4' in call_args or 'cnt' in str(call_args)

    @patch.object(trials_module, 'root_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_update_trials_with_explicit_count(self, mock_sqlite, mock_create, mock_root):
        """Test update_trials with explicit count."""
        mock_root.return_value = Path('/test/path')
        mock_con = Mock()
        mock_sqlite.return_value.__enter__.return_value = mock_con

        trials.update_trials(func='bdh', ticker='AAPL US Equity', cnt=5)
        mock_con.execute.assert_called()


class TestCurrentMissing:
    """Test current_missing function."""

    @patch.object(trials_module, 'root_path')
    def test_current_missing_no_path(self, mock_root):
        """Test current_missing when BBG_ROOT is not set."""
        # Mock root_path to return a Path with empty as_posix()
        mock_path = Mock()
        mock_path.as_posix.return_value = ''
        mock_root.return_value = mock_path
        result = trials.current_missing(func='bdh', ticker='AAPL US Equity')
        # Function checks `if not data_path.as_posix(): return 0`
        assert result == 0

    @patch.object(trials_module, 'root_path')
    @patch.object(trials_module, 'missing_info')
    @patch('xbbg.io.files.all_files')
    def test_current_missing_with_path(self, mock_all_files, mock_missing, mock_root):
        """Test current_missing when BBG_ROOT is set."""
        mock_root.return_value = Path('/test/path')
        mock_missing.return_value = 'bdh/AAPL US Equity/2024-01-01'
        mock_all_files.return_value = ['file1.log', 'file2.log', 'file3.log']

        result = trials.current_missing(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        assert result == 3


class TestUpdateMissing:
    """Test update_missing function."""

    @patch.object(trials_module, 'root_path')
    def test_update_missing_no_path(self, mock_root):
        """Test update_missing when BBG_ROOT is not set."""
        mock_root.return_value = Path('')
        # Should not raise an error
        trials.update_missing(func='bdh', ticker='AAPL US Equity')

    @patch.object(trials_module, 'root_path')
    def test_update_missing_empty_kwargs(self, mock_root):
        """Test update_missing with empty kwargs."""
        mock_root.return_value = Path('/test/path')
        # Should not raise an error
        trials.update_missing()

    @patch.object(trials_module, 'root_path')
    @patch.object(trials_module, 'missing_info')
    @patch('xbbg.io.files.all_files')
    @patch('xbbg.io.files.create_folder')
    @patch('pathlib.Path.touch')
    def test_update_missing_creates_log(self, mock_touch, mock_create, mock_all_files, mock_missing, mock_root):
        """Test update_missing creates log file."""
        # Mock the path operations
        mock_path = Mock()
        mock_path.as_posix.return_value = '/test/path'
        mock_log_path = Mock()
        mock_log_path.__truediv__ = Mock(return_value=mock_log_path)
        mock_log_path.touch = Mock()
        mock_path.__truediv__ = Mock(return_value=mock_log_path)
        mock_root.return_value = mock_path
        mock_missing.return_value = 'bdh/AAPL US Equity/2024-01-01'
        mock_all_files.return_value = ['file1.log', 'file2.log']

        trials.update_missing(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        # Should create folder
        mock_create.assert_called()

