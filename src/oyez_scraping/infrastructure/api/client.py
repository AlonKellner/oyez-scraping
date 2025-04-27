"""Base client for accessing the Oyez API.

This module provides a base client with common functionality for
interacting with the Oyez API, including rate limiting and retry logic.
"""

import logging
from typing import Any

import backoff
import requests
from ratelimit import RateLimitException, limits

from ..exceptions.api_exceptions import (
    OyezApiConnectionError,
    OyezApiError,
    OyezApiResponseError,
    OyezResourceNotFoundError,
)

# Configure logger
logger = logging.getLogger(__name__)


class OyezClient:
    """Base client for interacting with the Oyez API.

    This class provides common functionality for Oyez API clients,
    including session management, rate limiting, retry logic, and URL normalization.
    """

    BASE_URL = "https://api.oyez.org"

    def __init__(
        self,
        timeout: int = 30,
        session: requests.Session | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the Oyez API client.

        Args:
            timeout: Request timeout in seconds
            session: Optional requests session to use for API calls
            base_url: Optional custom base URL (primarily for testing)
        """
        self.timeout = timeout
        self.session = session or requests.Session()

        # Allow overriding base URL (for testing)
        self.base_url = base_url or self.BASE_URL

        # Set default headers for all requests
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json",
            }
        )

    def _normalize_url(self, url_or_path: str) -> str:
        """Normalize a URL or path to a full URL.

        Args:
            url_or_path: URL or path to normalize

        Returns
        -------
            A full URL
        """
        if url_or_path.startswith("http"):
            return url_or_path

        # Handle relative paths
        if url_or_path.startswith("/"):
            return f"{self.base_url}{url_or_path}"

        return f"{self.base_url}/{url_or_path}"

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, RateLimitException),
        max_tries=5,
        jitter=backoff.full_jitter,
    )
    @limits(calls=1, period=1)  # Maximum 1 request per second
    def get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list:
        """Make a GET request to the API with retries and rate limiting.

        Args:
            endpoint: API endpoint path (without base URL)
            params: Optional query parameters

        Returns
        -------
            JSON response as a dictionary or list

        Raises
        ------
            OyezApiConnectionError: If connection to the API fails
            OyezApiResponseError: If the API returns an error response
            OyezResourceNotFoundError: If the requested resource is not found
        """
        url = self._normalize_url(endpoint)
        logger.debug(f"Making GET request to {url} with params: {params}")

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)

            # Handle HTTP errors
            if response.status_code == 404:
                raise OyezResourceNotFoundError(f"Resource not found: {url}")

            response.raise_for_status()

            # Parse JSON response
            try:
                return response.json()
            except ValueError as e:
                raise OyezApiResponseError(f"Failed to parse JSON response: {e}") from e

        except requests.exceptions.RequestException as e:
            # Convert requests exceptions to our custom exceptions
            if isinstance(e, requests.exceptions.ConnectionError):
                raise OyezApiConnectionError(
                    f"Failed to connect to Oyez API: {e}"
                ) from e
            elif isinstance(e, requests.exceptions.Timeout):
                raise OyezApiConnectionError(
                    f"Request to Oyez API timed out: {e}"
                ) from e
            else:
                raise OyezApiError(f"Error making request to Oyez API: {e}") from e

    def head(self, url: str) -> bool:
        """Make a HEAD request to verify a URL is accessible.

        Args:
            url: The URL to check

        Returns
        -------
            True if the URL is accessible, False otherwise

        Raises
        ------
            OyezApiConnectionError: If there's a connection error
        """
        try:
            # Try a HEAD request first to avoid downloading the file
            response = self.session.head(url, timeout=self.timeout)
            return response.status_code == 200
        except requests.RequestException as e:
            raise OyezApiConnectionError(f"Failed to verify URL {url}: {e}") from e
