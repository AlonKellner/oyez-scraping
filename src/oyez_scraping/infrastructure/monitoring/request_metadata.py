"""Request metadata model for tracking API requests.

This module provides a data model for capturing and persisting metadata
about API requests, including their URLs, methods, parameters, and response details.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any


class RequestMetadata:
    """Metadata about an API request.

    This class captures information about an API request, including its URL, method,
    parameters, headers, response status, timing, and related file information.

    Attributes
    ----------
        url: The URL of the request
        method: The HTTP method (GET, POST, etc.)
        timestamp: When the request was made
        request_id: Unique identifier for the request
        params: Optional query parameters
        headers: Optional HTTP headers
        response_status: HTTP status code of the response
        response_time_ms: Response time in milliseconds
        error: Error message if the request failed
        related_file: Path to the file that was created from this request
        pagination_info: Information about pagination for this request
    """

    def __init__(
        self,
        url: str,
        method: str,
        timestamp: datetime | None = None,
        request_id: str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        response_status: int | None = None,
        response_time_ms: float | None = None,
        error: str | None = None,
        related_file: str | None = None,
        pagination_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize request metadata.

        Args:
            url: The URL of the request
            method: The HTTP method (GET, POST, etc.)
            timestamp: When the request was made (defaults to now in UTC)
            request_id: Unique identifier for the request (defaults to UUID)
            params: Optional query parameters
            headers: Optional HTTP headers
            response_status: HTTP status code of the response
            response_time_ms: Response time in milliseconds
            error: Error message if the request failed
            related_file: Path to the file that was created from this request
            pagination_info: Information about pagination for this request

        Raises
        ------
            ValueError: If url or method is empty
        """
        # Validate required fields
        if not url:
            raise ValueError("URL is required")
        if not method:
            raise ValueError("HTTP method is required")

        self.url = url
        self.method = method
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.request_id = request_id or str(uuid.uuid4())
        self.params = params
        self.headers = headers
        self.response_status = response_status
        self.response_time_ms = response_time_ms
        self.error = error
        self.related_file = related_file
        self.pagination_info = pagination_info

    def to_dict(self) -> dict[str, Any]:
        """Convert the metadata to a dictionary.

        Returns
        -------
            Dict representation of the metadata
        """
        return {
            "url": self.url,
            "method": self.method,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "params": self.params,
            "headers": self.headers,
            "response_status": self.response_status,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
            "related_file": self.related_file,
            "pagination_info": self.pagination_info,
        }

    def to_json(self) -> str:
        """Convert the metadata to a JSON string.

        Returns
        -------
            JSON string representation of the metadata
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequestMetadata":
        """Create a RequestMetadata instance from a dictionary.

        Args:
            data: Dictionary containing metadata fields

        Returns
        -------
            A new RequestMetadata instance

        Raises
        ------
            KeyError: If required fields are missing
        """
        # Convert timestamp string back to datetime if needed
        timestamp = data.get("timestamp")
        if timestamp and isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                # Fallback to now if timestamp can't be parsed
                timestamp = datetime.now(timezone.utc)

        return cls(
            url=data["url"],  # Will raise KeyError if missing
            method=data["method"],  # Will raise KeyError if missing
            timestamp=timestamp,
            request_id=data.get("request_id"),
            params=data.get("params"),
            headers=data.get("headers"),
            response_status=data.get("response_status"),
            response_time_ms=data.get("response_time_ms"),
            error=data.get("error"),
            related_file=data.get("related_file"),
            pagination_info=data.get("pagination_info"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "RequestMetadata":
        """Create a RequestMetadata instance from a JSON string.

        Args:
            json_str: JSON string containing metadata fields

        Returns
        -------
            A new RequestMetadata instance

        Raises
        ------
            KeyError: If required fields are missing
            json.JSONDecodeError: If json_str is not valid JSON
        """
        data = json.loads(json_str)  # May raise JSONDecodeError
        return cls.from_dict(data)
