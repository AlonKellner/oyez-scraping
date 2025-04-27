"""Unit tests for the request logger."""

import json
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from oyez_scraping.infrastructure.monitoring.request_logger import RequestLogger
from oyez_scraping.infrastructure.monitoring.request_metadata import RequestMetadata


@pytest.fixture
def sample_metadata() -> RequestMetadata:
    """Create a sample RequestMetadata for testing."""
    return RequestMetadata(
        url="https://api.example.com/cases/1971/70-161",
        method="GET",
        timestamp=datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
        request_id="test-request-123",
        params={"include": "audio"},
        headers={"Accept": "application/json"},
        response_status=200,
        response_time_ms=150.75,
        error=None,
    )


@pytest.fixture
def temp_log_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for logs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_init_creates_directory(temp_log_dir: Path) -> None:
    """Test that initializing the logger creates the log directory."""
    # Create a subdirectory path that doesn't exist yet
    log_dir = temp_log_dir / "request_logs"

    # Initialize the logger
    RequestLogger(log_dir)

    # Check that the directory was created
    assert log_dir.exists()
    assert log_dir.is_dir()


def test_log_request_creates_file(
    temp_log_dir: Path, sample_metadata: RequestMetadata
) -> None:
    """Test that log_request creates a log file with the correct name and content."""
    logger = RequestLogger(temp_log_dir)

    # Log a request
    data_type = "cases"
    data_filename = "1971_70-161.json"
    logger.log_request(sample_metadata, data_type, data_filename)

    # Check that the directory for this data type was created
    data_type_dir = temp_log_dir / data_type
    assert data_type_dir.exists()
    assert data_type_dir.is_dir()

    # Check that the log file was created
    log_file = data_type_dir / "1971_70-161.request.json"
    assert log_file.exists()
    assert log_file.is_file()

    # Check the content of the log file
    with open(log_file) as f:
        log_data = json.load(f)

    assert log_data["url"] == sample_metadata.url
    assert log_data["method"] == sample_metadata.method
    assert log_data["request_id"] == sample_metadata.request_id
    assert log_data["params"] == sample_metadata.params
    assert log_data["response_status"] == sample_metadata.response_status


def test_updates_related_file_in_metadata(
    temp_log_dir: Path, sample_metadata: RequestMetadata
) -> None:
    """Test that the related_file field in metadata is updated by log_request."""
    logger = RequestLogger(temp_log_dir)

    # Log a request
    data_type = "audio"
    data_filename = "70-161.mp3"
    logger.log_request(sample_metadata, data_type, data_filename)

    # Check that related_file was updated in metadata
    assert sample_metadata.related_file == f"audio/{data_filename}"


def test_log_request_handles_existing_directory(
    temp_log_dir: Path, sample_metadata: RequestMetadata
) -> None:
    """Test that log_request handles existing directories gracefully."""
    # Create the directory structure beforehand
    data_type_dir = temp_log_dir / "cases"
    data_type_dir.mkdir(exist_ok=True)

    logger = RequestLogger(temp_log_dir)

    # Log a request
    logger.log_request(sample_metadata, "cases", "1971_70-161.json")

    # Check that the log file was created
    log_file = data_type_dir / "1971_70-161.request.json"
    assert log_file.exists()


def test_log_request_with_error_handling(
    temp_log_dir: Path, sample_metadata: RequestMetadata
) -> None:
    """Test error handling in log_request method."""
    logger = RequestLogger(temp_log_dir)

    # Mock open to raise an OSError
    with mock.patch("builtins.open", side_effect=OSError("Permission denied")):
        with pytest.raises(OSError) as excinfo:
            logger.log_request(sample_metadata, "cases", "1971_70-161.json")

        assert "Permission denied" in str(excinfo.value)


def test_find_request_log_for_data_file(
    temp_log_dir: Path, sample_metadata: RequestMetadata
) -> None:
    """Test finding a request log file for a given data file."""
    logger = RequestLogger(temp_log_dir)

    # Log a request
    data_type = "cases"
    data_filename = "1971_70-161.json"
    logger.log_request(sample_metadata, data_type, data_filename)

    # Construct a mock data file path
    data_file_path = temp_log_dir.parent / "raw" / data_type / data_filename

    # Find the request log for this data file
    log_file = logger.find_request_log_for_data_file(data_file_path)

    # Check the result
    expected_log_path = temp_log_dir / data_type / "1971_70-161.request.json"
    assert log_file == expected_log_path


def test_find_request_log_nonexistent_file(temp_log_dir: Path) -> None:
    """Test finding a request log for a nonexistent data file."""
    logger = RequestLogger(temp_log_dir)

    # Construct a path to a nonexistent data file
    data_file_path = temp_log_dir.parent / "raw" / "cases" / "nonexistent.json"

    # Find the request log for this data file
    log_file = logger.find_request_log_for_data_file(data_file_path)

    # Check that it returns None
    assert log_file is None
