#!/usr/bin/env python3
"""Demonstrates auto-pagination functionality of the Oyez API client.

This script shows how the auto-pagination feature works, ensuring that
when auto_paginate=True, the maximum page size (1000) is always used
regardless of any provided per_page value.
"""

import logging
from pathlib import Path

from oyez_scraping.infrastructure.api.case_client import OyezCaseClient
from oyez_scraping.infrastructure.api.rate_limiter import AdaptiveRateLimiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Set up request logs directory
APP_CACHE_DIR = Path(".app_cache")
REQUEST_LOGS_DIR = APP_CACHE_DIR / "request_logs"
REQUEST_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def test_autopagination() -> None:
    """Test that auto-pagination always uses MAX_PAGE_SIZE."""
    logger.info("Testing auto-pagination functionality")

    # Create a rate limiter with adaptive parameters
    rate_limiter = AdaptiveRateLimiter(
        min_delay=0.5,
        max_delay=5.0,
        backoff_factor=1.5,
        jitter=0.25,
    )

    # Create the client
    client = OyezCaseClient(
        timeout=30,
        rate_limiter=rate_limiter,
    )

    # Get the maximum page size from the client
    max_page_size = client.MAX_PAGE_SIZE
    logger.info(f"MAX_PAGE_SIZE is configured as: {max_page_size}")

    # Test cases to demonstrate that auto-pagination always uses MAX_PAGE_SIZE
    test_cases = [
        {
            "per_page": None,
            "auto_paginate": True,
            "term": "2015",  # Using a term filter to limit the number of results for testing
            "description": "auto-pagination with default per_page",
        },
        {
            "per_page": 30,
            "auto_paginate": True,
            "term": "2015",
            "description": "auto-pagination with per_page=30",
        },
        {
            "per_page": 100,
            "auto_paginate": True,
            "term": "2015",
            "description": "auto-pagination with per_page=100",
        },
        {
            "per_page": 50,
            "auto_paginate": False,
            "term": "2015",
            "description": "no auto-pagination with per_page=50 (for comparison)",
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        per_page = test_case["per_page"]
        auto_paginate = test_case["auto_paginate"]
        term = test_case["term"]
        description = test_case["description"]

        logger.info(f"\nRunning test {i}: {description}")
        try:
            # Enable debug logging just for this test
            logging.getLogger("oyez_scraping").setLevel(logging.DEBUG)

            # Use get_cases_by_term to demonstrate the functionality
            cases = client.get_cases_by_term(
                term=term,
                per_page=per_page,
                auto_paginate=auto_paginate,
            )

            # Reset logging level
            logging.getLogger("oyez_scraping").setLevel(logging.INFO)

            # Record results
            result = {
                "test_id": i,
                "description": description,
                "per_page_requested": per_page,
                "auto_paginate": auto_paginate,
                "term": term,
                "cases_returned": len(cases),
            }
            results.append(result)

            logger.info(f"Test {i} returned {len(cases)} cases")

        except Exception as e:
            logger.error(f"Test {i} failed with error: {e}")

    # Print summary
    logger.info("\nTest Results Summary:")
    for result in results:
        logger.info(
            f"Test {result['test_id']}: {result['description']} -> "
            f"{result['cases_returned']} cases"
        )


def test_get_all_cases_autopagination() -> None:
    """Test auto-pagination with get_all_cases method."""
    logger.info("\nTesting get_all_cases auto-pagination functionality")

    # Create a rate limiter with adaptive parameters
    rate_limiter = AdaptiveRateLimiter(
        min_delay=0.5,
        max_delay=5.0,
        backoff_factor=1.5,
        jitter=0.25,
    )

    # Create the client
    client = OyezCaseClient(
        timeout=30,
        rate_limiter=rate_limiter,
    )

    # Test cases to demonstrate that auto-pagination always uses MAX_PAGE_SIZE
    test_cases = [
        {
            "per_page": None,
            "auto_paginate": True,
            "labels": False,
            "description": "get_all_cases - auto-pagination with default per_page",
        },
        {
            "per_page": 30,
            "auto_paginate": True,
            "labels": False,
            "description": "get_all_cases - auto-pagination with per_page=30",
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        per_page = test_case["per_page"]
        auto_paginate = test_case["auto_paginate"]
        labels = test_case["labels"]
        description = test_case["description"]

        logger.info(f"\nRunning test {i}: {description}")
        try:
            # Enable debug logging just for this test
            logging.getLogger("oyez_scraping").setLevel(logging.DEBUG)

            # Get cases
            cases = client.get_all_cases(
                labels=labels,
                per_page=per_page,
                auto_paginate=auto_paginate,
            )

            # Reset logging level
            logging.getLogger("oyez_scraping").setLevel(logging.INFO)

            # Record results
            result = {
                "test_id": i,
                "description": description,
                "per_page_requested": per_page,
                "auto_paginate": auto_paginate,
                "cases_returned": len(cases),
            }
            results.append(result)

            logger.info(f"Test {i} returned {len(cases)} cases")

        except Exception as e:
            logger.error(f"Test {i} failed with error: {e}")

    # Print summary
    logger.info("\nTest Results Summary:")
    for result in results:
        logger.info(
            f"Test {result['test_id']}: {result['description']} -> "
            f"{result['cases_returned']} cases"
        )


if __name__ == "__main__":
    logger.info("Starting pagination demonstration")
    test_autopagination()
    test_get_all_cases_autopagination()
    logger.info("Demonstration complete")
