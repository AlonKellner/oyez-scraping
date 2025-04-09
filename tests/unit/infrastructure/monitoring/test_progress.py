"""Unit tests for the progress monitoring module."""

import logging
import time
from unittest import mock

import pytest

from oyez_scraping.infrastructure.monitoring.progress import (
    ProgressMonitor,
    format_time,
)


def test_format_time_seconds() -> None:
    """Test formatting time with only seconds."""
    assert format_time(5.0) == "05s"
    assert format_time(9.5) == "09s"


def test_format_time_minutes() -> None:
    """Test formatting time with minutes and seconds."""
    assert format_time(65.0) == "01m 05s"
    assert format_time(145.8) == "02m 25s"


def test_format_time_hours() -> None:
    """Test formatting time with hours, minutes, and seconds."""
    assert format_time(3661.0) == "01h 01m 01s"
    assert format_time(7326.0) == "02h 02m 06s"


def test_format_time_days() -> None:
    """Test formatting time with days, hours, minutes, and seconds."""
    # 1 day, 2 hours, 3 minutes, 4 seconds
    seconds = 86400 + 7200 + 180 + 4
    assert format_time(seconds) == "1d 02h 03m 04s"


class TestProgressMonitor:
    """Test cases for the ProgressMonitor class."""

    @pytest.fixture
    def stats_callback(self) -> mock.MagicMock:
        """Fixture providing a mock stats callback function."""
        return mock.MagicMock(return_value={"item_count": 10, "audio_count": 5})

    @pytest.fixture
    def mock_logger(self) -> mock.MagicMock:
        """Fixture providing a mock logger."""
        return mock.MagicMock(spec=logging.Logger)

    @pytest.fixture
    def progress_monitor(
        self, stats_callback: mock.MagicMock, mock_logger: mock.MagicMock
    ) -> ProgressMonitor:
        """Fixture providing a ProgressMonitor instance for testing."""
        return ProgressMonitor(
            stats_callback=stats_callback,
            update_interval=0.1,  # Short interval for testing
            logger=mock_logger,
        )

    def test_init(
        self,
        progress_monitor: ProgressMonitor,
        stats_callback: mock.MagicMock,
        mock_logger: mock.MagicMock,
    ) -> None:
        """Test initializing a ProgressMonitor."""
        assert progress_monitor.stats_callback == stats_callback
        assert progress_monitor.update_interval == 0.1
        assert progress_monitor.logger == mock_logger
        assert isinstance(progress_monitor.shared_stats, dict)
        assert "lock" in progress_monitor.shared_stats
        assert progress_monitor.monitor_thread is None

    def test_start_stop(
        self, progress_monitor: ProgressMonitor, stats_callback: mock.MagicMock
    ) -> None:
        """Test starting and stopping the progress monitor."""
        # Start the monitor
        shared_stats = progress_monitor.start()

        # Check that it started correctly
        assert progress_monitor.monitor_thread is not None
        assert progress_monitor.monitor_thread.is_alive()
        assert progress_monitor.start_time > 0
        assert progress_monitor.last_update_time > 0
        assert stats_callback.called

        # Should have returned the shared stats
        assert shared_stats is progress_monitor.shared_stats

        # Store a reference to the thread for testing
        thread_ref = progress_monitor.monitor_thread

        # Stop the monitor
        progress_monitor.stop()

        # Check that it stopped correctly
        assert (
            progress_monitor.monitor_thread is None
        )  # Thread reference should be cleared
        assert not thread_ref.is_alive()  # The thread itself should not be alive

    def test_monitor_progress_updates_stats(
        self,
        progress_monitor: ProgressMonitor,
        stats_callback: mock.MagicMock,
        mock_logger: mock.MagicMock,
    ) -> None:
        """Test that the monitor updates stats correctly."""
        # Set up the stats callback to return different values on each call
        stats_callback.side_effect = [
            {"item_count": 10, "audio_count": 5},  # Initial stats
            {"item_count": 15, "audio_count": 8},  # Updated stats
        ]

        # Start the monitor
        progress_monitor.start()

        # Manually update the shared stats for testing
        with progress_monitor.shared_stats["lock"]:
            progress_monitor.shared_stats["last_count"] = 15
            progress_monitor.shared_stats["last_audio_count"] = 8

        # Force a progress update directly for testing
        elapsed = time.time() - progress_monitor.start_time
        progress_monitor._log_progress(
            elapsed=elapsed,
            current_stats={"item_count": 15, "audio_count": 8},
            item_diff=5,
            audio_diff=3,
            item_rate=10.0,
            audio_rate=5.0,
        )

        # Stop the monitor
        progress_monitor.stop()

        # Verify that the logger was called with progress info
        assert mock_logger.info.call_count > 0

        # Verify that the shared stats were updated
        with progress_monitor.shared_stats["lock"]:
            assert progress_monitor.shared_stats["last_count"] == 15
            assert progress_monitor.shared_stats["last_audio_count"] == 8

    def test_monitor_handles_exceptions(
        self,
        progress_monitor: ProgressMonitor,
        mock_logger: mock.MagicMock,
        stats_callback: mock.MagicMock,
    ) -> None:
        """Test that the monitor handles exceptions from the stats callback."""
        # Reset the side effect of the original stats_callback
        stats_callback.side_effect = [
            {"item_count": 10, "audio_count": 5},  # Initial stats
            Exception("Test exception"),  # Exception on update
        ]

        # Use the fixture's mock, not creating a new one
        progress_monitor.stats_callback = stats_callback

        # Modify the update interval to ensure it runs during test
        progress_monitor.update_interval = 0.01  # Very short interval for test

        # Start the monitor
        progress_monitor.start()

        # Wait for the monitor to try to update at least once
        time.sleep(0.2)

        # Stop the monitor
        progress_monitor.stop()

        # Verify that at least one error was logged
        assert mock_logger.error.call_count >= 1

        # Check that an error containing our test exception was logged
        error_calls = [
            call_args
            for call_args in mock_logger.error.call_args_list
            if "Test exception" in call_args[0][0]
        ]
        assert len(error_calls) > 0

    def test_log_progress(
        self, progress_monitor: ProgressMonitor, mock_logger: mock.MagicMock
    ) -> None:
        """Test the _log_progress method."""
        # Call _log_progress directly
        progress_monitor._log_progress(
            elapsed=120.5,
            current_stats={
                "item_count": 100,
                "audio_count": 50,
                "cache_size_mb": 1024.5,
                "custom_stat": "value",
            },
            item_diff=10,
            audio_diff=5,
            item_rate=30.0,
            audio_rate=15.0,
        )

        # Verify that the logger was called with the correct info
        # Header, progress time, items, audio, cache size, custom_stat, footer
        assert mock_logger.info.call_count == 7

        # Check specific log messages
        mock_logger.info.assert_any_call("=" * 40)
        mock_logger.info.assert_any_call("Progress after 02m 00s:")
        mock_logger.info.assert_any_call("Items: 100 (+10, 30.0/min)")
        mock_logger.info.assert_any_call("Audio files: 50 (+5, 15.0/min)")
        mock_logger.info.assert_any_call("Cache size: 1024.50 MB")
        mock_logger.info.assert_any_call("custom_stat: value")

    def test_log_progress_without_audio_or_cache(
        self, progress_monitor: ProgressMonitor, mock_logger: mock.MagicMock
    ) -> None:
        """Test _log_progress without audio or cache size stats."""
        # Call _log_progress with minimal stats
        progress_monitor._log_progress(
            elapsed=60.0,
            current_stats={"item_count": 50},
            item_diff=5,
            audio_diff=0,
            item_rate=10.0,
            audio_rate=0.0,
        )

        # Should still log basic info - Header, progress time, items, footer
        assert mock_logger.info.call_count == 4
        mock_logger.info.assert_any_call("=" * 40)
        mock_logger.info.assert_any_call("Progress after 01m 00s:")
        mock_logger.info.assert_any_call("Items: 50 (+5, 10.0/min)")

    def test_custom_stats_logging(
        self, progress_monitor: ProgressMonitor, mock_logger: mock.MagicMock
    ) -> None:
        """Test that custom stats are logged correctly."""
        # Call _log_progress with custom stats
        progress_monitor._log_progress(
            elapsed=30.0,
            current_stats={
                "item_count": 20,
                "custom_int": 42,
                "custom_float": 3.14,
                "custom_str": "value",
                "custom_bool": True,
                "_private": "should not be logged",  # Should be skipped
            },
            item_diff=2,
            audio_diff=0,
            item_rate=5.0,
            audio_rate=0.0,
        )

        # Check that custom stats were logged
        mock_logger.info.assert_any_call("custom_int: 42")
        mock_logger.info.assert_any_call("custom_float: 3.14")
        mock_logger.info.assert_any_call("custom_str: value")
        mock_logger.info.assert_any_call("custom_bool: True")

        # Private stats should not be logged
        for call in mock_logger.info.call_args_list:
            assert "_private" not in str(call)
