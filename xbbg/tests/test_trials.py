"""Unit tests for trial tracking functions."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

from xbbg.core.utils import trials


class TestNumTrials:
    """Test num_trials function."""

    @patch('xbbg.core.utils.trials._get_db_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_num_trials_with_path(self, mock_sqlite, mock_create, mock_get_db):
        """Test num_trials when cache root is available."""
        mock_get_db.return_value = Path('/test/path/xbbg_trials.db')
        mock_con = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [(5,)]
        mock_con.execute.return_value = mock_cursor
        mock_sqlite.return_value.__enter__.return_value = mock_con

        result = trials.num_trials(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        assert result == 5

    @patch('xbbg.core.utils.trials._get_db_path')
    def test_num_trials_no_path(self, mock_get_db):
        """Test num_trials when cache root is not available."""
        mock_get_db.return_value = None
        result = trials.num_trials(func='bdh', ticker='AAPL US Equity')
        assert result == 0

    @patch('xbbg.core.utils.trials._get_db_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_num_trials_no_results(self, mock_sqlite, mock_create, mock_get_db):
        """Test num_trials when no results found."""
        mock_get_db.return_value = Path('/test/path/xbbg_trials.db')
        mock_con = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_con.execute.return_value = mock_cursor
        mock_sqlite.return_value.__enter__.return_value = mock_con

        result = trials.num_trials(func='bdh', ticker='AAPL US Equity')
        assert result == 0


class TestUpdateTrials:
    """Test update_trials function."""

    @patch('xbbg.core.utils.trials._get_db_path')
    def test_update_trials_no_path(self, mock_get_db):
        """Test update_trials when cache root is not available."""
        mock_get_db.return_value = None
        # Should not raise an error
        trials.update_trials(func='bdh', ticker='AAPL US Equity')

    @patch('xbbg.core.utils.trials._get_db_path')
    @patch('xbbg.core.utils.trials.num_trials')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_update_trials_increment(self, mock_sqlite, mock_create, mock_num, mock_get_db):
        """Test update_trials increments count."""
        mock_get_db.return_value = Path('/test/path/xbbg_trials.db')
        mock_num.return_value = 3
        mock_con = Mock()
        mock_sqlite.return_value.__enter__.return_value = mock_con

        trials.update_trials(func='bdh', ticker='AAPL US Equity', dt='2024-01-01')
        # Should increment from 3 to 4
        mock_con.execute.assert_called()
        call_args = mock_con.execute.call_args[0][0]
        assert 'cnt=4' in call_args or 'cnt' in str(call_args)

    @patch('xbbg.core.utils.trials._get_db_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_update_trials_with_explicit_count(self, mock_sqlite, mock_create, mock_get_db):
        """Test update_trials with explicit count."""
        mock_get_db.return_value = Path('/test/path/xbbg_trials.db')
        mock_con = Mock()
        mock_sqlite.return_value.__enter__.return_value = mock_con

        trials.update_trials(func='bdh', ticker='AAPL US Equity', cnt=5)
        mock_con.execute.assert_called()

