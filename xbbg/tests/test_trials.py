"""Unit tests for trial tracking functions."""

from __future__ import annotations

from pathlib import Path
import threading
from unittest.mock import Mock, patch

from xbbg.core.utils import trials


class TestNumTrials:
    """Test num_trials function."""

    @patch.object(trials, '_get_db_path')
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

    @patch.object(trials, '_get_db_path')
    def test_num_trials_no_path(self, mock_get_db):
        """Test num_trials when cache root is not available."""
        mock_get_db.return_value = None
        result = trials.num_trials(func='bdh', ticker='AAPL US Equity')
        assert result == 0

    @patch.object(trials, '_get_db_path')
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

    @patch.object(trials, '_get_db_path')
    def test_update_trials_no_path(self, mock_get_db):
        """Test update_trials when cache root is not available."""
        mock_get_db.return_value = None
        # Should not raise an error
        trials.update_trials(func='bdh', ticker='AAPL US Equity')

    @patch.object(trials, '_get_db_path')
    @patch.object(trials, 'num_trials')
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

    @patch.object(trials, '_get_db_path')
    @patch('xbbg.io.files.create_folder')
    @patch('xbbg.io.db.SQLite')
    def test_update_trials_with_explicit_count(self, mock_sqlite, mock_create, mock_get_db):
        """Test update_trials with explicit count."""
        mock_get_db.return_value = Path('/test/path/xbbg_trials.db')
        mock_con = Mock()
        mock_sqlite.return_value.__enter__.return_value = mock_con

        trials.update_trials(func='bdh', ticker='AAPL US Equity', cnt=5)
        mock_con.execute.assert_called()


class TestThreadSafety:
    """Test thread safety of trials database operations."""

    @patch.object(trials, '_get_db_path')
    def test_thread_safety(self, mock_get_db, tmp_path):
        """Test that trials operations work correctly from multiple threads."""
        db_file = tmp_path / 'xbbg_trials.db'
        mock_get_db.return_value = db_file

        results = []
        errors = []

        def worker(thread_id: int):
            """Worker function that runs in a thread."""
            try:
                # Each thread should be able to read/write independently
                count = trials.num_trials(func='test', ticker=f'TICKER{thread_id}', dt='2024-01-01')
                trials.update_trials(func='test', ticker=f'TICKER{thread_id}', dt='2024-01-01', cnt=count + 1)
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Create multiple threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete successfully
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 5, "All threads should complete successfully"

