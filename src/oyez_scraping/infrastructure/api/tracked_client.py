"""Tracked API client that integrates with request tracking middleware.

This module provides a wrapper around the base API client that integrates
with the request tracking middleware to track API requests.
"""

import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, TypeVar, Union

import requests

from oyez_scraping.infrastructure.api.client import OyezClient
from oyez_scraping.infrastructure.api.pagination_mixin import PaginationMixin
from oyez_scraping.infrastructure.api.rate_limiter import AdaptiveRateLimiter
from oyez_scraping.infrastructure.exceptions.api_exceptions import (
    NetworkError,
    OyezApiError,
    RateLimitError,
    ResponseFormatError,
)
from oyez_scraping.infrastructure.monitoring.request_logger import RequestLogger
from oyez_scraping.infrastructure.monitoring.request_tracker import (
    RequestTrackerMiddleware,
)

T = TypeVar("T")
JsonType = Union[dict[str, Any], list[dict[str, Any]], list[Any]]


class TrackedOyezClient(PaginationMixin):
    """A wrapper around OyezClient that tracks API requests.

    This class provides the same interface as OyezClient but adds request tracking
    capabilities using the RequestTrackerMiddleware. It also implements the
    PaginationMixin to provide consistent pagination functionality.

    Attributes
    ----------
        client: The underlying OyezClient instance
        tracker: The RequestTrackerMiddleware instance for tracking requests
        base_url: The base URL for the API (from OyezClient)
    """

    def __init__(
        self,
        timeout: int = 30,
        session: requests.Session | None = None,
        rate_limiter: AdaptiveRateLimiter | None = None,
        log_dir: Path | None = None,
    ) -> None:
        """Initialize the tracked client.

        Args:
            timeout: Request timeout in seconds
            session: Optional requests session to use for API calls
            rate_limiter: Optional rate limiter to use (not currently supported by OyezClient)
            log_dir: Directory for request logs (if None, tracking will be disabled)
        """
        # Store the rate limiter for future use if OyezClient supports it
        self.rate_limiter = rate_limiter

        # Create the underlying client
        self.client = OyezClient(timeout=timeout, session=session)

        # Use the same BASE_URL as OyezClient
        self.base_url = OyezClient.BASE_URL

        # Set up request tracking if log_dir is provided
        self.tracker = None
        if log_dir:
            logger = RequestLogger(log_dir)
            self.tracker = RequestTrackerMiddleware(logger)

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data_type: str | None = None,
        data_filename: str | None = None,
    ) -> JsonType:
        """Make a GET request to the API with request tracking.

        Args:
            endpoint: The API endpoint to request
            params: Optional query parameters
            headers: Optional HTTP headers
            data_type: Type of data being requested (for request logging)
            data_filename: Filename where data will be saved (for request logging)

        Returns
        -------
            The JSON response from the API

        Raises
        ------
            NetworkError: If there's a network-related error
            RateLimitError: If the API rate limit is exceeded
            ResponseFormatError: If the response cannot be parsed as JSON
            OyezApiError: For any other API-related errors
        """
        # Get the full URL for the request
        url = f"{self.base_url}/{endpoint}"

        # Start tracking the request if tracking is enabled
        metadata = None
        start_time = time.time()

        if self.tracker:
            metadata = self.tracker.before_request(
                url=url,
                method="GET",
                params=params,
                headers=headers,
            )

        try:
            # Make the request using the underlying client
            response_data = self.client.get(endpoint, params=params)

            # Track the response if tracking is enabled
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                # Create a mock response since we don't have access to the original
                mock_response = self._create_mock_response(
                    status_code=200,  # We only have successful responses here
                    elapsed_ms=elapsed_ms,
                )
                self.tracker.after_request(
                    metadata=metadata,
                    response=mock_response,
                    data_type=data_type,
                    data_filename=data_filename,
                )

            return response_data

        except (NetworkError, RateLimitError, ResponseFormatError, OyezApiError) as e:
            # Track the exception if tracking is enabled
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                self.tracker.after_exception(
                    metadata=metadata,
                    exception=e,
                    elapsed_ms=elapsed_ms,
                    data_type=data_type,
                    data_filename=data_filename,
                )
            raise

    def get_all_cases(
        self,
        term: str | None = None,
        docket_number: str | None = None,
        per_page: int | None = None,
        auto_paginate: bool = False,
        data_filename: str = "all_cases.json",
    ) -> list[dict[str, Any]]:
        """Retrieve all cases, optionally filtered by term or docket number.

        Args:
            term: Optional term to filter by
            docket_number: Optional docket number to filter by
            per_page: Optional number of cases per page
            auto_paginate: If True, automatically retrieve all pages of results
            data_filename: Filename where the data will be saved

        Returns
        -------
            List of case dictionaries

        Raises
        ------
            NetworkError: If there's a network-related error
            RateLimitError: If the API rate limit is exceeded
            ResponseFormatError: If the response cannot be parsed as JSON
            OyezApiError: For any other API-related errors
        """
        # Build the filter parameter
        filter_parts = []
        if term:
            filter_parts.append(f"term:{term}")
        if docket_number:
            filter_parts.append(f"docket_number:{docket_number}")

        filter_param = " ".join(filter_parts) if filter_parts else None

        # Build query parameters
        params: dict[str, Any] = {}
        if filter_param:
            params["filter"] = filter_param
        if per_page is not None:
            params["per_page"] = str(per_page)

        # Get the endpoint URL
        endpoint = "cases"

        # If auto-pagination is requested, use the paginated resource method
        if auto_paginate:
            # Start tracking the request (for the entire operation)
            url = f"{self.base_url}/{endpoint}"
            metadata = None
            start_time = time.time()

            if self.tracker:
                metadata = self.tracker.before_request(
                    url=url,
                    method="GET",
                    params=params,
                    headers=None,
                )
                if metadata:
                    metadata.pagination_info = {
                        "auto_paginate": True,
                        "requested_per_page": per_page,
                    }

            try:
                # Use the pagination mixin to get all pages
                cases = self.get_paginated_resource(endpoint, params)

                # Track the response
                if self.tracker and metadata:
                    elapsed_ms = (time.time() - start_time) * 1000
                    mock_response = self._create_mock_response(
                        status_code=200,
                        elapsed_ms=elapsed_ms,
                    )
                    # Add pagination results to metadata
                    if metadata.pagination_info:
                        metadata.pagination_info["returned_count"] = len(cases)

                    self.tracker.after_request(
                        metadata=metadata,
                        response=mock_response,
                        data_type="case_lists",
                        data_filename=data_filename,
                    )

                return cases if isinstance(cases, list) else []

            except (
                NetworkError,
                RateLimitError,
                ResponseFormatError,
                OyezApiError,
            ) as e:
                # Track the exception
                if self.tracker and metadata:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.tracker.after_exception(
                        metadata=metadata,
                        exception=e,
                        elapsed_ms=elapsed_ms,
                        data_type="case_lists",
                        data_filename=data_filename,
                    )
                raise

        # For non-paginated requests, use a simple get
        # Add pagination info to metadata
        pagination_info = {
            "auto_paginate": False,
            "requested_per_page": per_page,
        }

        # Start tracking the request
        url = f"{self.base_url}/{endpoint}"
        metadata = None
        start_time = time.time()

        if self.tracker:
            metadata = self.tracker.before_request(
                url=url,
                method="GET",
                params=params,
                headers=None,
            )
            if metadata:
                metadata.pagination_info = pagination_info

        try:
            # Make the request using the underlying client
            cases = self.client.get(endpoint, params=params)

            # Add pagination results to metadata
            if metadata and isinstance(cases, list):
                if metadata.pagination_info:
                    metadata.pagination_info["returned_count"] = len(cases)

            # Track the response
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                mock_response = self._create_mock_response(
                    status_code=200,
                    elapsed_ms=elapsed_ms,
                )
                self.tracker.after_request(
                    metadata=metadata,
                    response=mock_response,
                    data_type="case_lists",
                    data_filename=data_filename,
                )

            return cases if isinstance(cases, list) else []

        except (NetworkError, RateLimitError, ResponseFormatError, OyezApiError) as e:
            # Track the exception
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                self.tracker.after_exception(
                    metadata=metadata,
                    exception=e,
                    elapsed_ms=elapsed_ms,
                    data_type="case_lists",
                    data_filename=data_filename,
                )
            raise

    def iter_all_cases(
        self,
        term: str | None = None,
        docket_number: str | None = None,
        per_page: int | None = None,
        data_filename: str = "all_cases.json",
    ) -> Generator[dict[str, Any], None, None]:
        """Iterate over all cases, automatically handling pagination.

        Args:
            term: Optional term to filter by
            docket_number: Optional docket number to filter by
            per_page: Optional number of cases per page
            data_filename: Filename where the data will be saved

        Yields
        ------
            Case dictionaries one at a time

        Raises
        ------
            NetworkError: If there's a network-related error
            RateLimitError: If the API rate limit is exceeded
            ResponseFormatError: If the response cannot be parsed as JSON
            OyezApiError: For any other API-related errors
        """
        # Build the filter parameter
        filter_parts = []
        if term:
            filter_parts.append(f"term:{term}")
        if docket_number:
            filter_parts.append(f"docket_number:{docket_number}")

        filter_param = " ".join(filter_parts) if filter_parts else None

        # Build query parameters
        params: dict[str, Any] = {}
        if filter_param:
            params["filter"] = filter_param
        if per_page is not None:
            params["per_page"] = str(per_page)

        # Get the endpoint URL
        endpoint = "cases"

        # Start tracking the request (for the entire operation)
        url = f"{self.base_url}/{endpoint}"
        metadata = None
        start_time = time.time()
        item_count = 0

        if self.tracker:
            metadata = self.tracker.before_request(
                url=url,
                method="GET",
                params=params,
                headers=None,
            )
            if metadata:
                metadata.pagination_info = {
                    "iterator": True,
                    "requested_per_page": per_page,
                }

        try:
            # Use the pagination mixin's iterator
            for case in self.iter_paginated_resource(endpoint, params):
                item_count += 1
                yield case

            # Track successful completion after yielding all items
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                mock_response = self._create_mock_response(
                    status_code=200,
                    elapsed_ms=elapsed_ms,
                )
                # Add pagination results to metadata
                if metadata.pagination_info:
                    metadata.pagination_info["returned_count"] = item_count

                self.tracker.after_request(
                    metadata=metadata,
                    response=mock_response,
                    data_type="case_lists",
                    data_filename=data_filename,
                )

        except (NetworkError, RateLimitError, ResponseFormatError, OyezApiError) as e:
            # Track the exception
            if self.tracker and metadata:
                elapsed_ms = (time.time() - start_time) * 1000
                # Add partial pagination results to metadata
                if metadata.pagination_info:
                    metadata.pagination_info["returned_count"] = item_count
                    metadata.pagination_info["completed"] = False

                self.tracker.after_exception(
                    metadata=metadata,
                    exception=e,
                    elapsed_ms=elapsed_ms,
                    data_type="case_lists",
                    data_filename=data_filename,
                )
            raise

    def _create_mock_response(
        self, status_code: int, elapsed_ms: float
    ) -> requests.Response:
        """Create a mock response object for request tracking.

        Args:
            status_code: HTTP status code
            elapsed_ms: Response time in milliseconds

        Returns
        -------
            A mock Response object
        """
        # Create a mock Response object
        mock_response = requests.Response()
        mock_response.status_code = status_code

        # Mock the elapsed time
        class MockElapsed:
            def __init__(self, elapsed_seconds: float) -> None:
                self.elapsed_seconds = elapsed_seconds

            def total_seconds(self) -> float:
                return self.elapsed_seconds

        mock_response.elapsed = MockElapsed(elapsed_ms / 1000)

        return mock_response
