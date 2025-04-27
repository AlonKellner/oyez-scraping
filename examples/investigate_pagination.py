#!/usr/bin/env python3
"""Investigates the pagination issue with the Oyez API.

This script uses the request tracking system to investigate why only 30 cases
are being returned from the Oyez API when there should be more.
"""

import json
import logging
from pathlib import Path

from oyez_scraping.infrastructure.api.rate_limiter import AdaptiveRateLimiter
from oyez_scraping.infrastructure.api.tracked_client import TrackedOyezClient
from oyez_scraping.infrastructure.monitoring.request_logger import RequestLogger

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


def test_different_pagination_values() -> None:
    """Test different pagination values to see what works best."""
    logger.info("Testing different pagination values")

    # Create a rate limiter with adaptive parameters
    rate_limiter = AdaptiveRateLimiter(
        min_delay=0.5,
        max_delay=5.0,
        backoff_factor=1.5,
        jitter=0.25,
    )

    # Create the tracked client with request logging
    client = TrackedOyezClient(
        timeout=30,  # Updated to match new constructor
        rate_limiter=rate_limiter,
        log_dir=REQUEST_LOGS_DIR,
    )

    # Test with different per_page values
    test_cases = [
        {
            "per_page": None,
            "term": None,
            "description": "default pagination, no filters",
        },
        {"per_page": 30, "term": None, "description": "30 per page, no filters"},
        {"per_page": 50, "term": None, "description": "50 per page, no filters"},
        {"per_page": 100, "term": None, "description": "100 per page, no filters"},
        {
            "per_page": None,
            "term": "2015",
            "description": "default pagination, 2015 term filter",
        },
        {
            "per_page": 50,
            "term": "2015",
            "description": "50 per page, 2015 term filter",
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        per_page = test_case["per_page"]
        term = test_case["term"]
        description = test_case["description"]

        data_filename = f"pagination_test_{i}.json"

        logger.info(f"Running test {i}: {description}")
        try:
            cases = client.get_all_cases(
                term=term,
                per_page=per_page,
                data_filename=data_filename,
            )

            # Record results
            result = {
                "test_id": i,
                "description": description,
                "per_page": per_page,
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

    # Save results to a file
    results_file = REQUEST_LOGS_DIR / "pagination_test_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to {results_file}")

    # Examine request logs
    examine_request_logs(results)


def examine_request_logs(results) -> None:
    """Examine the request logs for the pagination tests."""
    logger.info("\nExamining request logs:")

    request_logger = RequestLogger(REQUEST_LOGS_DIR)

    for result in results:
        test_id = result["test_id"]
        data_filename = f"pagination_test_{test_id}.json"

        # Construct a mock data file path
        data_file_path = Path(".app_cache/raw/case_lists") / data_filename

        # Find the request log for this file
        log_file = request_logger.find_request_log_for_data_file(data_file_path)

        if log_file and log_file.exists():
            with open(log_file) as f:
                log_data = json.load(f)

            # Extract pagination info
            pagination_info = log_data.get("pagination_info", {})
            params = log_data.get("params", {})

            logger.info(f"\nTest {test_id}:")
            logger.info(f"  URL: {log_data['url']}")
            logger.info(f"  Request parameters: {params}")
            logger.info(
                f"  Requested per_page: {pagination_info.get('requested_per_page')}"
            )
            logger.info(f"  Returned count: {pagination_info.get('returned_count')}")
        else:
            logger.warning(f"Request log for test {test_id} not found")


if __name__ == "__main__":
    logger.info("Starting pagination investigation")
    test_different_pagination_values()
    logger.info("Investigation complete")
