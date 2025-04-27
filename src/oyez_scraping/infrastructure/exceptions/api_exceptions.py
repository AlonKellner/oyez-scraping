"""Exceptions related to Oyez API operations.

This module provides custom exceptions for handling errors that occur
when interacting with the Oyez API.
"""


class OyezApiError(Exception):
    """Base exception for all Oyez API errors."""

    pass


class OyezApiConnectionError(OyezApiError):
    """Exception raised when connection to the Oyez API fails."""

    pass


class OyezApiResponseError(OyezApiError):
    """Exception raised when the Oyez API returns an unexpected response."""

    pass


class OyezResourceNotFoundError(OyezApiError):
    """Exception raised when a resource is not found in the Oyez API."""

    pass


class OyezDataConsistencyError(OyezApiError):
    """Exception raised when data across Oyez API endpoints is inconsistent."""

    pass


class NetworkError(OyezApiError):
    """Exception raised when there's a network-related error during API calls."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        """Initialize NetworkError.

        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error


class RateLimitError(OyezApiError):
    """Exception raised when the API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Initialize RateLimitError.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying (if provided by API)
        """
        super().__init__(message)
        self.retry_after = retry_after


class ResponseFormatError(OyezApiError):
    """Exception raised when the API response cannot be parsed as expected."""

    def __init__(self, message: str, response_text: str | None = None) -> None:
        """Initialize ResponseFormatError.

        Args:
            message: Error message
            response_text: The raw response text that couldn't be parsed
        """
        super().__init__(message)
        self.response_text = response_text


class AudioUrlError(OyezApiError):
    """Exception raised when audio URLs are missing or invalid in the API response."""

    def __init__(self, message: str, case_id: str | None = None) -> None:
        """Initialize AudioUrlError.

        Args:
            message: Error message
            case_id: ID of the case for which audio URLs are missing/invalid
        """
        super().__init__(message)
        self.case_id = case_id
