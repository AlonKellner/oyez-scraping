"""API client module for Oyez scraping.

This package provides clients for interacting with the Oyez API, including
base client functionality, pagination, rate limiting, and specialized clients
for different types of API resources.
"""

from oyez_scraping.infrastructure.api.case_client import (
    AudioContentType,
    OyezCaseClient,
)
from oyez_scraping.infrastructure.api.client import OyezClient
from oyez_scraping.infrastructure.api.pagination_mixin import PaginationMixin
from oyez_scraping.infrastructure.api.rate_limiter import AdaptiveRateLimiter
from oyez_scraping.infrastructure.api.tracked_client import TrackedOyezClient

__all__ = [
    "AdaptiveRateLimiter",
    "AudioContentType",
    "OyezCaseClient",
    "OyezClient",
    "PaginationMixin",
    "TrackedOyezClient",
]
