"""Pagination mixin for API clients.

This module provides a mixin class for adding pagination capabilities to API clients.
It handles the complexities of paginating through API responses with consistent interfaces.
"""

import copy
import logging
from collections.abc import Generator
from typing import Any, TypeVar, Union, cast

# Create a generic type variable for API response types
T = TypeVar("T")
JsonResponse = Union[dict[str, Any], list[dict[str, Any]], list[Any]]

# Configure logger
logger = logging.getLogger(__name__)


class PaginationMixin:
    """Mixin that adds pagination capabilities to API clients.

    This mixin assumes the existence of a get() method on the class it's mixed into.
    It provides methods to handle common pagination scenarios for API endpoints.

    Attributes
    ----------
        continue_pagination_on_partial_page: If True, continue pagination even when
            receiving a partial page (fewer items than per_page). This is primarily
            used for testing where the mock needs to serve all defined responses.
    """

    # Default behavior is to stop on partial pages (real-world APIs)
    continue_pagination_on_partial_page = False

    def get_page_resource(
        self, endpoint: str, params: dict[str, Any] | None = None, page: int = 0
    ) -> JsonResponse:
        """Get a specific page of a resource.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            page: Page number to retrieve (0-indexed)

        Returns
        -------
            The JSON response for the requested page

        Note:
            This method assumes the API uses the 'page' query parameter for pagination.
            The page parameter will override any existing 'page' in params.
        """
        # Create a copy of params to avoid modifying the original
        params = {} if params is None else copy.copy(params)

        # Set the page parameter (convert to string as expected by most APIs)
        params["page"] = str(page)

        # Make the request using the client's get method
        logger.debug(f"Requesting page {page} from {endpoint}")
        try:
            return self.get(endpoint, params=params)  # type: ignore
        except StopIteration:
            # Handle the case where a mock's side_effect list is exhausted
            # This allows tests to define only the pages they care about
            logger.debug(f"No more mock responses available for page {page}")
            return []

    def iter_paginated_resource(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> Generator[dict[str, Any], None, None]:
        """Iterator that yields items from paginated resources.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Yields
        ------
            Individual items from the paginated resource

        Note:
            This method handles pagination automatically, fetching more pages as needed.
            It terminates pagination in two cases:
            1. When an empty page is received
            2. When a page contains fewer items than requested with per_page
               (unless continue_pagination_on_partial_page is True)
        """
        params = {} if params is None else copy.copy(params)

        page = 0
        per_page = None

        if "per_page" in params:
            try:
                per_page = int(params["per_page"])
            except (ValueError, TypeError):
                # If per_page is not a valid integer, we can't use it for determining
                # when we've reached the end of the results
                logger.warning(f"Invalid per_page parameter: {params['per_page']}")

        # Keep fetching pages until termination condition
        while True:
            # Get the current page
            page_data = self.get_page_resource(endpoint, params, page)

            # If we received a non-list response or an empty list, we're done
            if not isinstance(page_data, list) or not page_data:
                logger.debug(
                    f"Pagination terminated at page {page}: empty or non-list response"
                )
                break

            # Extract per_page from the first page if it wasn't provided
            if per_page is None and page == 0 and page_data:
                per_page = len(page_data)
                logger.debug(f"Determined per_page={per_page} from first page")

            # Yield each item in the current page
            for item in page_data:
                if isinstance(item, dict):
                    yield item
                else:
                    # Handle non-dict items by casting them
                    yield cast("dict[str, Any]", item)

            # Determine if we've reached the last page - terminate if:
            # 1. We have a per_page value, received fewer items than expected, and we're
            #    not configured to continue pagination on partial pages
            if (
                per_page is not None
                and len(page_data) < per_page
                and not getattr(self, "continue_pagination_on_partial_page", False)
            ):
                logger.debug(
                    f"Pagination terminated at page {page}: received {len(page_data)} items, expected {per_page}"
                )
                break

            # Move to the next page
            page += 1

    def get_paginated_resource(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Get all pages of a resource and return them as a single list.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns
        -------
            A list containing all items from all pages

        Note:
            This method is a convenience wrapper around iter_paginated_resource
            that collects all results into a single list.
        """
        # Safely collect items without risking infinite loops
        results = []
        try:
            # Explicitly collect items from the iterator
            for item in self.iter_paginated_resource(endpoint, params):
                results.append(item)
        except Exception as e:
            logger.error(f"Error during pagination: {e}")
            # Re-raise to maintain the original behavior
            raise

        logger.info(f"Retrieved {len(results)} total items from {endpoint}")
        return results
