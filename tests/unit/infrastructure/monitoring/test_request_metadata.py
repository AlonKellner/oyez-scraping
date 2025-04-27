"""Unit tests for the request metadata model."""

import json
from datetime import datetime, timezone

import pytest

from oyez_scraping.infrastructure.monitoring.request_metadata import RequestMetadata


def test_required_fields() -> None:
    """Test that url and method are required fields."""
    # These should work
    metadata = RequestMetadata(url="https://api.example.com", method="GET")
    assert metadata.url == "https://api.example.com"
    assert metadata.method == "GET"

    # These should raise exceptions
    with pytest.raises(ValueError):
        RequestMetadata(url="", method="GET")

    with pytest.raises(ValueError):
        RequestMetadata(url="https://api.example.com", method="")


def test_default_values() -> None:
    """Test that default values are set correctly."""
    metadata = RequestMetadata(url="https://api.example.com", method="GET")

    # Check defaults
    assert metadata.timestamp is not None
    assert metadata.request_id is not None
    assert metadata.params is None
    assert metadata.headers is None
    assert metadata.response_status is None
    assert metadata.response_time_ms is None
    assert metadata.error is None
    assert metadata.related_file is None
    assert metadata.pagination_info is None


def test_to_dict() -> None:
    """Test conversion to dictionary."""
    now = datetime.now(timezone.utc)
    metadata = RequestMetadata(
        url="https://api.example.com",
        method="GET",
        timestamp=now,
        request_id="test-id-123",
        params={"page": 1},
        headers={"Accept": "application/json"},
        response_status=200,
        response_time_ms=123.45,
        error=None,
        related_file="cases/test.json",
        pagination_info={"page": 1, "total": 10},
    )

    data_dict = metadata.to_dict()

    # Check conversion
    assert data_dict["url"] == "https://api.example.com"
    assert data_dict["method"] == "GET"
    assert data_dict["timestamp"] == now.isoformat()
    assert data_dict["request_id"] == "test-id-123"
    assert data_dict["params"] == {"page": 1}
    assert data_dict["headers"] == {"Accept": "application/json"}
    assert data_dict["response_status"] == 200
    assert data_dict["response_time_ms"] == 123.45
    assert data_dict["error"] is None
    assert data_dict["related_file"] == "cases/test.json"
    assert data_dict["pagination_info"] == {"page": 1, "total": 10}


def test_from_dict() -> None:
    """Test creation from dictionary."""
    now = datetime.now(timezone.utc)
    data_dict = {
        "url": "https://api.example.com",
        "method": "GET",
        "timestamp": now.isoformat(),
        "request_id": "test-id-123",
        "params": {"page": 1},
        "headers": {"Accept": "application/json"},
        "response_status": 200,
        "response_time_ms": 123.45,
        "error": None,
        "related_file": "cases/test.json",
        "pagination_info": {"page": 1, "total": 10},
    }

    metadata = RequestMetadata.from_dict(data_dict)

    # Check conversion
    assert metadata.url == "https://api.example.com"
    assert metadata.method == "GET"
    assert metadata.timestamp.isoformat() == now.isoformat()
    assert metadata.request_id == "test-id-123"
    assert metadata.params == {"page": 1}
    assert metadata.headers == {"Accept": "application/json"}
    assert metadata.response_status == 200
    assert metadata.response_time_ms == 123.45
    assert metadata.error is None
    assert metadata.related_file == "cases/test.json"
    assert metadata.pagination_info == {"page": 1, "total": 10}


def test_to_json() -> None:
    """Test conversion to JSON string."""
    now = datetime.now(timezone.utc)
    metadata = RequestMetadata(
        url="https://api.example.com",
        method="GET",
        timestamp=now,
        request_id="test-id-123",
    )

    json_str = metadata.to_json()
    data_dict = json.loads(json_str)

    # Check JSON conversion
    assert data_dict["url"] == "https://api.example.com"
    assert data_dict["method"] == "GET"
    assert data_dict["timestamp"] == now.isoformat()
    assert data_dict["request_id"] == "test-id-123"


def test_from_json() -> None:
    """Test creation from JSON string."""
    now = datetime.now(timezone.utc)
    json_str = json.dumps(
        {
            "url": "https://api.example.com",
            "method": "GET",
            "timestamp": now.isoformat(),
            "request_id": "test-id-123",
        }
    )

    metadata = RequestMetadata.from_json(json_str)

    # Check conversion
    assert metadata.url == "https://api.example.com"
    assert metadata.method == "GET"
    assert metadata.timestamp.isoformat() == now.isoformat()
    assert metadata.request_id == "test-id-123"


def test_invalid_json() -> None:
    """Test handling of invalid JSON."""
    with pytest.raises(json.JSONDecodeError):
        RequestMetadata.from_json("invalid json")


def test_missing_required_fields_in_dict() -> None:
    """Test handling of missing required fields when creating from dict."""
    with pytest.raises(KeyError):
        RequestMetadata.from_dict({"method": "GET"})

    with pytest.raises(KeyError):
        RequestMetadata.from_dict({"url": "https://api.example.com"})


def test_invalid_timestamp_format() -> None:
    """Test handling of invalid timestamp format."""
    # Should handle invalid timestamp format gracefully
    data_dict = {
        "url": "https://api.example.com",
        "method": "GET",
        "timestamp": "invalid-timestamp",
    }

    metadata = RequestMetadata.from_dict(data_dict)
    assert metadata.url == "https://api.example.com"
    assert metadata.method == "GET"
    assert metadata.timestamp is not None  # Should default to current time
