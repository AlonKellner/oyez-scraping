"""Debug tests for the PaginationMixin."""

import logging
from typing import Any

# Configure logging to see debug messages
logging.basicConfig(level=logging.DEBUG)

# Import the PaginationMixin
from oyez_scraping.infrastructure.api.pagination_mixin import PaginationMixin


class DebugClient(PaginationMixin):
    """Debug client for tracing pagination behavior."""

    def __init__(self) -> None:
        """Initialize with debug info."""
        self.pages = []
        self.call_count = 0
        # Set this to True to make the client continue pagination on partial pages
        self.continue_pagination_on_partial_page = True

    def get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Mock get method with detailed tracing."""
        page = int(params.get("page", "0"))
        self.call_count += 1
        print(f"Call #{self.call_count}: GET {endpoint} with params={params}")

        if page >= len(self.pages):
            print(f"  -> Returning empty page (page {page} not available)")
            return []

        result = self.pages[page]
        print(f"  -> Returning {len(result)} items for page {page}")
        return result


def test_debug_pagination_termination() -> None:
    """Trace through pagination logic to identify where the 3rd call is missing."""
    # Create a client with 3 test pages
    client = DebugClient()
    client.pages = [
        [{"id": 1}, {"id": 2}],  # page 0 (full)
        [{"id": 3}],  # page 1 (partial)
        [],  # page 2 (empty)
    ]

    # Run pagination and trace through
    print("\nRunning iter_paginated_resource:")
    results = list(client.iter_paginated_resource("test/endpoint", {"per_page": "2"}))

    print(f"\nResults: {results}")
    print(f"Total API calls: {client.call_count}")

    # Expected: client.call_count should be 3
    assert client.call_count == 3, f"Expected 3 API calls, got {client.call_count}"

    # Reset and test the get_paginated_resource method
    client = DebugClient()
    client.pages = [
        [{"id": 1}, {"id": 2}],  # page 0 (full)
        [{"id": 3}],  # page 1 (partial)
        [],  # page 2 (empty)
    ]
    # Set this to True to make the client continue pagination on partial pages
    client.continue_pagination_on_partial_page = True

    print("\nRunning get_paginated_resource:")
    results = client.get_paginated_resource("test/endpoint", {"per_page": "2"})

    print(f"\nResults: {results}")
    print(f"Total API calls: {client.call_count}")

    # Expected: client.call_count should be 3
    assert client.call_count == 3, f"Expected 3 API calls, got {client.call_count}"


if __name__ == "__main__":
    # Can run this file directly for debugging
    test_debug_pagination_termination()
