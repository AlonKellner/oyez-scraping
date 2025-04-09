"""Progress monitoring module for tracking long-running operations.

This module provides functionality for tracking and reporting the progress of
long-running operations such as downloads.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Any


def format_time(seconds: float) -> str:
    """Format a time duration in seconds into a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns
    -------
        Human-readable string representation of the duration
    """
    if seconds < 60:
        return f"{int(seconds):02d}s"

    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes):02d}m {int(seconds):02d}s"

    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{int(hours):02d}h {int(minutes):02d}m {int(seconds):02d}s"

    days, hours = divmod(hours, 24)
    return f"{int(days)}d {int(hours):02d}h {int(minutes):02d}m {int(seconds):02d}s"


class ProgressMonitor:
    """Monitor and report progress for long-running operations.

    This class periodically collects statistics about an operation and logs
    progress information at regular intervals.
    """

    def __init__(
        self,
        stats_callback: Callable[[], dict[str, Any]],
        update_interval: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the progress monitor.

        Args:
            stats_callback: A function that returns a dictionary of current statistics
            update_interval: How often to update progress (in seconds)
            logger: Logger instance to use, or None to use the module logger
        """
        self.stats_callback = stats_callback
        self.update_interval = update_interval
        self.logger = logger or logging.getLogger(__name__)

        # Thread-safe storage for shared statistics
        self.shared_stats: dict[str, Any] = {
            "lock": threading.Lock(),
            "current_rate": 0.0,
            "current_audio_rate": 0.0,
            "last_count": 0,
            "last_audio_count": 0,
        }

        # Monitor thread properties
        self.monitor_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.start_time = 0.0
        self.last_update_time = 0.0

    def start(self) -> dict[str, Any]:
        """Start the progress monitoring thread.

        Returns
        -------
            Dictionary with shared statistics that can be accessed by other components
        """
        self.start_time = time.time()
        self.last_update_time = self.start_time

        # Initialize from current stats
        try:
            current_stats = self.stats_callback()
            with self.shared_stats["lock"]:
                self.shared_stats["last_count"] = current_stats.get("item_count", 0)
                self.shared_stats["last_audio_count"] = current_stats.get(
                    "audio_count", 0
                )
        except Exception as e:
            self.logger.error(f"Error initializing progress monitor: {e}")

        # Start the monitoring thread
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_progress, daemon=True
        )
        self.monitor_thread.start()

        return self.shared_stats

    def stop(self) -> None:
        """Stop the progress monitoring thread.

        Returns
        -------
            None
        """
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            self.stop_event.set()
            self.monitor_thread.join(
                timeout=2.0
            )  # Wait up to 2 seconds for thread to stop

        # Always reset the thread reference, even if it was None or already stopped
        self.monitor_thread = None

    def _monitor_progress(self) -> None:
        """Monitor progress in a loop until stopped.

        This method runs in a separate thread and periodically logs progress.

        Returns
        -------
            None
        """
        try:
            # Get initial stats
            current_stats = self.stats_callback()

            # Continue until stop is signaled
            while not self.stop_event.is_set():
                # Sleep for the update interval, checking stop flag periodically
                for _ in range(int(self.update_interval * 10)):
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.1)

                # Calculate elapsed time
                now = time.time()
                elapsed = now - self.start_time
                update_interval = now - self.last_update_time

                try:
                    # Get updated stats
                    current_stats = self.stats_callback()

                    # Calculate item processing rates
                    with self.shared_stats["lock"]:
                        # Item counts
                        last_count = self.shared_stats["last_count"]
                        current_count = current_stats.get("item_count", 0)
                        item_diff = current_count - last_count

                        # Audio counts
                        last_audio_count = self.shared_stats["last_audio_count"]
                        current_audio_count = current_stats.get("audio_count", 0)
                        audio_diff = current_audio_count - last_audio_count

                        # Calculate rates (items per minute)
                        item_rate = (
                            (item_diff / update_interval) * 60
                            if update_interval > 0
                            else 0
                        )
                        audio_rate = (
                            (audio_diff / update_interval) * 60
                            if update_interval > 0
                            else 0
                        )

                        # Update shared stats
                        self.shared_stats["current_rate"] = item_rate
                        self.shared_stats["current_audio_rate"] = audio_rate
                        self.shared_stats["last_count"] = current_count
                        self.shared_stats["last_audio_count"] = current_audio_count

                    # Log progress
                    self._log_progress(
                        elapsed=elapsed,
                        current_stats=current_stats,
                        item_diff=item_diff,
                        audio_diff=audio_diff,
                        item_rate=item_rate,
                        audio_rate=audio_rate,
                    )

                    # Update last update time
                    self.last_update_time = now

                except Exception as e:
                    # Log the specific error from the stats_callback
                    self.logger.error(f"Error in progress monitor: {e}")

        except Exception as e:
            # Log unexpected errors in the monitor thread itself
            self.logger.error(f"Unexpected error in progress monitor thread: {e}")

    def _log_progress(
        self,
        elapsed: float,
        current_stats: dict[str, Any],
        item_diff: int,
        audio_diff: int,
        item_rate: float,
        audio_rate: float,
    ) -> None:
        """Log current progress information.

        Args:
            elapsed: Time elapsed since start (seconds)
            current_stats: Dictionary with current statistics
            item_diff: Number of items processed since last update
            audio_diff: Number of audio files processed since last update
            item_rate: Items processed per minute
            audio_rate: Audio files processed per minute

        Returns
        -------
            None
        """
        # Format elapsed time
        elapsed_str = format_time(elapsed)

        # Log header
        self.logger.info("=" * 40)
        self.logger.info(f"Progress after {elapsed_str}:")

        # Log item count
        item_count = current_stats.get("item_count", 0)
        if item_count > 0:
            self.logger.info(f"Items: {item_count} (+{item_diff}, {item_rate:.1f}/min)")

        # Log audio count if available
        audio_count = current_stats.get("audio_count", 0)
        if audio_count > 0:
            self.logger.info(
                f"Audio files: {audio_count} (+{audio_diff}, {audio_rate:.1f}/min)"
            )

        # Log cache size if available
        cache_size = current_stats.get("cache_size_mb", 0)
        if cache_size > 0:
            self.logger.info(f"Cache size: {cache_size:.2f} MB")

        # Log custom statistics (skip private keys starting with _)
        for key, value in current_stats.items():
            if key not in (
                "item_count",
                "audio_count",
                "cache_size_mb",
            ) and not key.startswith("_"):
                self.logger.info(f"{key}: {value}")

        # Log footer
        self.logger.info("=" * 40)
