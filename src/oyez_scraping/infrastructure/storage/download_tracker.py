"""Download tracking module for managing download state and retry logic.

This module provides functionality for tracking the state of downloads,
particularly for handling failed downloads and implementing retry logic.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any


class DownloadTracker:
    """Track and manage the state of downloads, including retry logic for failed items.

    This class keeps track of which items have failed during download and
    provides mechanisms for retrying them with appropriate backoff.
    """

    def __init__(
        self,
        storage: Any,
        cache_dir: Path,
        tracker_filename: str = "download_tracker.json",
        max_retry_attempts: int = 3,
    ) -> None:
        """Initialize the download tracker.

        Args:
            storage: A storage service instance for file operations
            cache_dir: Directory where the tracker file will be stored
            tracker_filename: Name of the tracker file
            max_retry_attempts: Maximum number of retry attempts for failed items

        Raises
        ------
            Exception: If the tracker file cannot be created or read
        """
        self.storage = storage
        self.cache_dir = cache_dir
        self.tracker_path = cache_dir / tracker_filename
        self.max_retry_attempts = max_retry_attempts
        self.logger = logging.getLogger(__name__)

        # Initialize or load the tracker
        self.failed_items: dict[str, dict[str, Any]] = {}
        self._load_or_initialize_tracker()

    def _load_or_initialize_tracker(self) -> None:
        """Load an existing tracker file or initialize a new one.

        Returns
        -------
            None
        """
        try:
            if self.tracker_path.exists():
                try:
                    with open(self.tracker_path, encoding="utf-8") as f:
                        data = json.load(f)
                        self.failed_items = data.get("failed_items", {})
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load download tracker from {self.tracker_path}: {e}"
                    )
                    self.failed_items = {}
            else:
                # If the tracker file doesn't exist, create a new one
                self.failed_items = {}
                data = {
                    "failed_items": self.failed_items,
                    "last_updated": time.time(),
                    "version": "1.0",
                }
                # Ensure directory exists
                self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
                # Use the storage service to write the file
                self._save_tracker()
        except Exception as e:
            self.logger.warning(f"Error initializing download tracker: {e}")
            self.failed_items = {}

    def _save_tracker(self) -> None:
        """Save the current state of the tracker to disk.

        Returns
        -------
            None
        """
        try:
            data = {
                "failed_items": self.failed_items,
                "last_updated": time.time(),
                "version": "1.0",
            }
            self.storage.write_json(self.tracker_path, data)
        except Exception as e:
            self.logger.warning(
                f"Failed to save download tracker to {self.tracker_path}: {e}"
            )

    def mark_failed(self, item_id: str, item_data: dict[str, Any]) -> None:
        """Mark an item as failed in the tracker.

        Args:
            item_id: Unique identifier for the item
            item_data: Data associated with the item

        Returns
        -------
            None
        """
        if item_id in self.failed_items:
            # Increment the attempts counter for existing items
            self.failed_items[item_id]["attempts"] += 1
        else:
            # Add a new entry for first-time failures
            self.failed_items[item_id] = {
                "item_data": item_data,
                "attempts": 1,
                "last_attempt": time.time(),
            }

        # Save the updated tracker
        self._save_tracker()

    def mark_successful(self, item_id: str) -> None:
        """Mark an item as successfully processed, removing it from failed items.

        Args:
            item_id: Unique identifier for the item

        Returns
        -------
            None
        """
        if item_id in self.failed_items:
            del self.failed_items[item_id]
            self._save_tracker()

    def get_failed_items_for_retry(self) -> list[tuple[str, dict[str, Any]]]:
        """Get a list of failed items that can be retried.

        Returns
        -------
            List of tuples containing (item_id, item_data) for items that can be retried
        """
        retry_items = []

        for item_id, item_info in self.failed_items.items():
            attempts = item_info.get("attempts", 0)

            # Only include items that haven't exceeded the retry limit
            if attempts <= self.max_retry_attempts:
                retry_items.append((item_id, item_info["item_data"]))

        return retry_items

    def has_failed_items_for_retry(self) -> bool:
        """Check if there are any failed items eligible for retry.

        Returns
        -------
            True if there are failed items eligible for retry, False otherwise
        """
        for item_info in self.failed_items.values():
            attempts = item_info.get("attempts", 0)
            if attempts <= self.max_retry_attempts:
                return True
        return False

    def get_stats(self) -> dict[str, int]:
        """Get statistics about failed items.

        Returns
        -------
            Dictionary with statistics including total_failed, retriable, and permanent_failures
        """
        total_failed = len(self.failed_items)
        retriable = 0
        permanent_failures = 0

        for item_info in self.failed_items.values():
            attempts = item_info.get("attempts", 0)
            if attempts <= self.max_retry_attempts:
                retriable += 1
            else:
                permanent_failures += 1

        return {
            "total_failed": total_failed,
            "retriable": retriable,
            "permanent_failures": permanent_failures,
        }

    def reset(self) -> None:
        """Reset the tracker, clearing all failed items.

        Returns
        -------
            None
        """
        self.failed_items = {}
        self._save_tracker()
