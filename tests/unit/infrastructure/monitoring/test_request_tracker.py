"""Unit tests for the request tracker middleware."""

from datetime import datetime, timezone
from unittest import mock

import pytest
import requests

from oyez_scraping.infrastructure.monitoring.request_logger import RequestLogger
from oyez_scraping.infrastructure.monitoring.request_metadata import RequestMetadata
from oyez_scraping.infrastructure.monitoring.request_tracker import (
    RequestTrackerMiddleware,
)


@pytest.fixture
def mock_logger() -> mock.Mock:
    """Create a mock RequestLogger for testing."""
    return mock.Mock(spec=RequestLogger)


@pytest.fixture
def successful_response() -> mock.Mock:
    """Create a mock successful HTTP response."""
    mock_resp = mock.Mock(spec=requests.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/json"}

    # Create a mock elapsed attribute with total_seconds method
    mock_elapsed = mock.Mock()
    mock_elapsed.total_seconds.return_value = 0.5
    mock_resp.elapsed = mock_elapsed

    mock_resp.ok = True
    return mock_resp


@pytest.fixture
def error_response() -> mock.Mock:
    """Create a mock error HTTP response."""
    mock_resp = mock.Mock(spec=requests.Response)
    mock_resp.status_code = 429  # Too Many Requests
    mock_resp.headers = {"Content-Type": "application/json"}

    # Create a mock elapsed attribute with total_seconds method
    mock_elapsed = mock.Mock()
    mock_elapsed.total_seconds.return_value = 0.5
    mock_resp.elapsed = mock_elapsed

    mock_resp.ok = False
    mock_resp.text = '{"error": "Rate limit exceeded"}'
    return mock_resp


def test_init_with_logger() -> None:
    """Test initialization with a logger."""
    logger = mock.Mock(spec=RequestLogger)
    middleware = RequestTrackerMiddleware(logger)
    assert middleware.logger == logger


def test_before_request() -> None:
    """Test capturing metadata before a request."""
    logger = mock.Mock(spec=RequestLogger)
    middleware = RequestTrackerMiddleware(logger)

    metadata = middleware.before_request(
        url="https://api.example.com/cases",
        method="GET",
        params={"page": 1},
        headers={"Accept": "application/json"},
    )

    # Check that metadata was properly captured
    assert metadata.url == "https://api.example.com/cases"
    assert metadata.method == "GET"
    assert metadata.params == {"page": 1}
    assert metadata.headers == {"Accept": "application/json"}
    assert isinstance(metadata.timestamp, datetime)
    assert metadata.request_id is not None
    assert metadata.response_status is None  # Not yet set
    assert metadata.response_time_ms is None  # Not yet set
    assert metadata.error is None  # Not yet set


def test_after_request_success(
    mock_logger: mock.Mock, successful_response: mock.Mock
) -> None:
    """Test updating metadata after a successful request."""
    middleware = RequestTrackerMiddleware(mock_logger)

    # Create initial metadata
    metadata = RequestMetadata(
        url="https://api.example.com/cases",
        method="GET",
        timestamp=datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
    )

    # Update metadata with response details
    updated_metadata = middleware.after_request(
        metadata=metadata,
        response=successful_response,
        data_type="cases",
        data_filename="test.json",
    )

    # Check that metadata was properly updated
    assert updated_metadata.response_status == 200
    assert updated_metadata.response_time_ms == 500.0  # 0.5 seconds in milliseconds
    assert updated_metadata.error is None

    # Check that the logger was called with the updated metadata
    mock_logger.log_request.assert_called_once_with(
        updated_metadata, "cases", "test.json"
    )


def test_after_request_error(mock_logger: mock.Mock, error_response: mock.Mock) -> None:
    """Test updating metadata after a failed request."""
    middleware = RequestTrackerMiddleware(mock_logger)

    # Create initial metadata
    metadata = RequestMetadata(
        url="https://api.example.com/cases",
        method="GET",
        timestamp=datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
    )

    # Update metadata with error response details
    updated_metadata = middleware.after_request(
        metadata=metadata,
        response=error_response,
        data_type="cases",
        data_filename="test.json",
    )

    # Check that metadata was properly updated with error info
    assert updated_metadata.response_status == 429
    assert updated_metadata.response_time_ms == 500.0
    assert updated_metadata.error == "Rate limit exceeded"

    # Check that the logger was called with the updated metadata
    mock_logger.log_request.assert_called_once_with(
        updated_metadata, "cases", "test.json"
    )


def test_after_request_exception(mock_logger: mock.Mock) -> None:
    """Test updating metadata after an exception occurred."""
    middleware = RequestTrackerMiddleware(mock_logger)

    # Create initial metadata
    metadata = RequestMetadata(
        url="https://api.example.com/cases",
        method="GET",
        timestamp=datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
    )

    # Create an exception
    exception = requests.ConnectionError("Connection refused")

    # Update metadata with exception details
    updated_metadata = middleware.after_exception(
        metadata=metadata,
        exception=exception,
        elapsed_ms=300.0,
        data_type="cases",
        data_filename="test.json",
    )

    # Check that metadata was properly updated with error info
    assert updated_metadata.response_status is None
    assert updated_metadata.response_time_ms == 300.0
    # Fix type checking issue by checking if error is not None first
    assert updated_metadata.error is not None
    assert "Connection refused" in updated_metadata.error


def test_log_request_without_file(mock_logger: mock.Mock) -> None:
    """Test logging a request without associating it with a file."""
    middleware = RequestTrackerMiddleware(mock_logger)

    # Create metadata
    metadata = RequestMetadata(
        url="https://api.example.com/cases",
        method="GET",
        timestamp=datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
        response_status=200,
    )

    # Log request without file
    middleware.log_request(metadata)

    # Check that the logger was not called
    mock_logger.log_request.assert_not_called()

    # Check that metadata wasn't modified
    assert metadata.related_file is None


def test_complete_request_flow(
    mock_logger: mock.Mock, successful_response: mock.Mock
) -> None:
    """Test a complete request flow from before to after request."""
    middleware = RequestTrackerMiddleware(mock_logger)

    # Before request
    metadata = middleware.before_request(
        url="https://api.example.com/cases",
        method="GET",
    )

    # After request
    updated_metadata = middleware.after_request(
        metadata=metadata,
        response=successful_response,
        data_type="cases",
        data_filename="test.json",
    )

    # Check that the metadata was properly updated
    assert updated_metadata.response_status == 200
    assert updated_metadata.response_time_ms == 500.0

    # Check that the logger was called
    mock_logger.log_request.assert_called_once()
