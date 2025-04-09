"""Unit tests for the download tracker module."""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest

from oyez_scraping.infrastructure.storage.download_tracker import DownloadTracker
from oyez_scraping.infrastructure.storage.filesystem import FilesystemStorage


@pytest.fixture
def storage() -> FilesystemStorage:
    """Create a FilesystemStorage instance for testing."""
    return FilesystemStorage()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def download_tracker(storage: FilesystemStorage, temp_dir: Path) -> DownloadTracker:
    """Create a DownloadTracker instance for testing."""
    return DownloadTracker(
        storage=storage,
        cache_dir=temp_dir,
        tracker_filename="test_tracker.json",
        max_retry_attempts=3,
    )


def test_init_creates_new_tracker_file(
    download_tracker: DownloadTracker, temp_dir: Path
) -> None:
    """Test that initializing a DownloadTracker creates a new tracker file."""
    # Verify that the tracker was created
    assert download_tracker is not None

    tracker_path = temp_dir / "test_tracker.json"
    assert tracker_path.exists()

    # File should contain an empty failed_items dict
    with open(tracker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "failed_items" in data
    assert isinstance(data["failed_items"], dict)
    assert len(data["failed_items"]) == 0


def test_mark_failed(download_tracker: DownloadTracker) -> None:
    """Test marking an item as failed."""
    item_id = "test_item"
    item_data = {"key": "value"}

    download_tracker.mark_failed(item_id, item_data)

    failed_items = download_tracker.failed_items
    assert item_id in failed_items
    assert failed_items[item_id]["item_data"] == item_data
    assert failed_items[item_id]["attempts"] == 1


def test_mark_failed_increments_attempts(download_tracker: DownloadTracker) -> None:
    """Test that marking an already failed item increments the attempts counter."""
    item_id = "test_item"
    item_data = {"key": "value"}

    download_tracker.mark_failed(item_id, item_data)
    download_tracker.mark_failed(item_id, item_data)

    failed_items = download_tracker.failed_items
    assert item_id in failed_items
    assert failed_items[item_id]["attempts"] == 2


def test_mark_successful(download_tracker: DownloadTracker) -> None:
    """Test marking an item as successful removes it from failed items."""
    item_id = "test_item"
    item_data = {"key": "value"}

    download_tracker.mark_failed(item_id, item_data)
    assert item_id in download_tracker.failed_items

    download_tracker.mark_successful(item_id)
    assert item_id not in download_tracker.failed_items


def test_mark_successful_does_nothing_for_nonexistent_item(
    download_tracker: DownloadTracker,
) -> None:
    """Test marking a non-existent item as successful does not cause errors."""
    item_id = "nonexistent_item"

    # This should not raise an exception
    download_tracker.mark_successful(item_id)


def test_get_failed_items_for_retry(download_tracker: DownloadTracker) -> None:
    """Test getting failed items for retry."""
    # Add some failed items
    download_tracker.mark_failed("item1", {"key": "value1"})
    download_tracker.mark_failed("item2", {"key": "value2"})

    # Add an item with too many attempts
    download_tracker.mark_failed("item3", {"key": "value3"})
    download_tracker.mark_failed("item3", {"key": "value3"})
    download_tracker.mark_failed("item3", {"key": "value3"})
    download_tracker.mark_failed(
        "item3", {"key": "value3"}
    )  # 4 attempts exceeds max_retry_attempts

    retry_items = download_tracker.get_failed_items_for_retry()

    # Should only include items with attempts <= max_retry_attempts
    assert len(retry_items) == 2

    # Convert to dict for easier checking
    retry_dict = {item_id: item_data for item_id, item_data in retry_items}
    assert "item1" in retry_dict
    assert "item2" in retry_dict
    assert "item3" not in retry_dict


def test_has_failed_items_for_retry(download_tracker: DownloadTracker) -> None:
    """Test checking if there are failed items for retry."""
    # Initially should not have any failed items
    assert not download_tracker.has_failed_items_for_retry()

    # Add a failed item
    download_tracker.mark_failed("item1", {"key": "value1"})
    assert download_tracker.has_failed_items_for_retry()

    # Mark it successful
    download_tracker.mark_successful("item1")
    assert not download_tracker.has_failed_items_for_retry()

    # Add an item with too many attempts
    download_tracker.mark_failed("item2", {"key": "value2"})
    for _ in range(3):  # Exceed max_retry_attempts
        download_tracker.mark_failed("item2", {"key": "value2"})

    assert not download_tracker.has_failed_items_for_retry()


def test_get_stats(download_tracker: DownloadTracker) -> None:
    """Test getting statistics about failed items."""
    # Add some failed items
    download_tracker.mark_failed("item1", {"key": "value1"})
    download_tracker.mark_failed("item2", {"key": "value2"})

    # Add an item with too many attempts
    download_tracker.mark_failed("item3", {"key": "value3"})
    for _ in range(3):  # Exceed max_retry_attempts
        download_tracker.mark_failed("item3", {"key": "value3"})

    stats = download_tracker.get_stats()

    assert stats["total_failed"] == 3
    assert stats["retriable"] == 2
    assert stats["permanent_failures"] == 1


def test_reset(download_tracker: DownloadTracker) -> None:
    """Test resetting the tracker."""
    # Add some failed items
    download_tracker.mark_failed("item1", {"key": "value1"})
    download_tracker.mark_failed("item2", {"key": "value2"})

    assert len(download_tracker.failed_items) == 2

    download_tracker.reset()

    assert len(download_tracker.failed_items) == 0


def test_load_existing_tracker(storage: FilesystemStorage, temp_dir: Path) -> None:
    """Test loading an existing tracker file."""
    # Create a tracker file
    tracker_path = temp_dir / "existing_tracker.json"
    tracker_data = {
        "failed_items": {
            "existing_item": {
                "item_data": {"key": "value"},
                "attempts": 2,
                "last_attempt": 1234567890.0,
            }
        },
        "last_updated": 1234567890.0,
        "version": "1.0",
    }

    with open(tracker_path, "w", encoding="utf-8") as f:
        json.dump(tracker_data, f)

    # Create a new tracker that should load the existing file
    download_tracker = DownloadTracker(
        storage=storage,
        cache_dir=temp_dir,
        tracker_filename="existing_tracker.json",
        max_retry_attempts=3,
    )

    # Check that the existing data was loaded
    assert "existing_item" in download_tracker.failed_items
    assert download_tracker.failed_items["existing_item"]["attempts"] == 2


def test_handles_corrupted_tracker_file(
    storage: FilesystemStorage, temp_dir: Path
) -> None:
    """Test that the tracker gracefully handles a corrupted tracker file."""
    # Create a corrupted tracker file
    tracker_path = temp_dir / "corrupted_tracker.json"
    with open(tracker_path, "w", encoding="utf-8") as f:
        f.write("This is not valid JSON")

    # Mock logger to check for warning
    with mock.patch("logging.Logger.warning") as mock_warning:
        download_tracker = DownloadTracker(
            storage=storage,
            cache_dir=temp_dir,
            tracker_filename="corrupted_tracker.json",
            max_retry_attempts=3,
        )

        # Should have logged a warning
        mock_warning.assert_called_once()
        assert "Failed to load download tracker" in mock_warning.call_args[0][0]

        # Should have initialized an empty tracker
        assert len(download_tracker.failed_items) == 0


def test_save_error_handling(storage: FilesystemStorage, temp_dir: Path) -> None:
    """Test error handling when saving the tracker file fails."""
    download_tracker = DownloadTracker(
        storage=storage,
        cache_dir=temp_dir,
        tracker_filename="test_tracker.json",
        max_retry_attempts=3,
    )

    # Mock write_json to raise an exception
    with (
        mock.patch.object(
            storage, "write_json", side_effect=Exception("Mock save error")
        ) as mock_write,
        mock.patch("logging.Logger.warning") as mock_warning,
    ):
        # This should trigger a save
        download_tracker.mark_failed("item1", {"key": "value1"})

        # Should have called write_json
        mock_write.assert_called_once()

        # Should have logged a warning
        mock_warning.assert_called_once()
        assert "Failed to save download tracker" in mock_warning.call_args[0][0]
