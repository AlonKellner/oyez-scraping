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
