"""Request tracker middleware for intercepting API requests.

This module provides middleware that integrates with API clients to track
request details and log them using the request logger.
"""

import json
from typing import Any

import requests

from oyez_scraping.infrastructure.monitoring.request_logger import RequestLogger
from oyez_scraping.infrastructure.monitoring.request_metadata import RequestMetadata


class RequestTrackerMiddleware:
    """Middleware that hooks into API clients to track request details.

    This class provides methods to capture request metadata before and after
    requests, and logs the metadata using a RequestLogger.

    Attributes
    ----------
        logger: The RequestLogger instance to use for logging requests
    """

    def __init__(self, logger: RequestLogger) -> None:
        """Initialize the request tracker middleware.

        Args:
            logger: The RequestLogger to use for logging requests
        """
        self.logger = logger

    def before_request(
        self,
        url: str,
        method: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> RequestMetadata:
        """Capture request metadata before a request is made.

        Args:
            url: The URL of the request
            method: The HTTP method (GET, POST, etc.)
            params: Optional query parameters
            headers: Optional HTTP headers

        Returns
        -------
            A RequestMetadata instance with initial request details
        """
        return RequestMetadata(
            url=url,
            method=method,
            params=params,
            headers=headers,
        )

    def after_request(
        self,
        metadata: RequestMetadata,
        response: requests.Response,
        data_type: str | None = None,
        data_filename: str | None = None,
    ) -> RequestMetadata:
        """Update metadata after a request completes and log it.

        Args:
            metadata: The RequestMetadata instance to update
            response: The HTTP response object
            data_type: Optional type of data (audio, cases, etc.) for logging
            data_filename: Optional filename of the data file for logging

        Returns
        -------
            The updated RequestMetadata instance
        """
        # Update metadata with response details
        metadata.response_status = response.status_code
        metadata.response_time_ms = response.elapsed.total_seconds() * 1000

        # Extract error information if response is not OK
        if not response.ok:
            try:
                error_data = json.loads(response.text)
                metadata.error = error_data.get("error", response.text)
            except (json.JSONDecodeError, AttributeError):
                metadata.error = response.text if hasattr(response, "text") else None

        # Log the request if data_type and data_filename are provided
        if data_type and data_filename:
            self.logger.log_request(metadata, data_type, data_filename)

        return metadata

    def after_exception(
        self,
        metadata: RequestMetadata,
        exception: Exception,
        elapsed_ms: float,
        data_type: str | None = None,
        data_filename: str | None = None,
    ) -> RequestMetadata:
        """Update metadata after an exception occurs during a request and log it.

        Args:
            metadata: The RequestMetadata instance to update
            exception: The exception that occurred
            elapsed_ms: The elapsed time in milliseconds
            data_type: Optional type of data for logging
            data_filename: Optional filename of the data file for logging

        Returns
        -------
            The updated RequestMetadata instance
        """
        # Update metadata with exception details
        metadata.response_time_ms = elapsed_ms
        metadata.error = f"{type(exception).__name__}: {exception!s}"

        # Log the request if data_type and data_filename are provided
        if data_type and data_filename:
            self.logger.log_request(metadata, data_type, data_filename)

        return metadata

    def log_request(self, _metadata: RequestMetadata) -> str | None:
        """Log a request that's not associated with a specific data file.

        This is typically used for requests that don't result in file creation,
        like listing operations.

        Args:
            _metadata: The RequestMetadata instance to log (unused)

        Returns
        -------
            The request ID if logged, None otherwise
        """
        # We can't log without data_type and filename, so just keep the metadata
        return None
