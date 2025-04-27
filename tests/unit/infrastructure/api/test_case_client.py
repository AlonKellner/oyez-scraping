"""Unit tests for the OyezCaseClient class."""

import unittest
from unittest.mock import Mock, call, patch

import pytest

from oyez_scraping.infrastructure.api.case_client import OyezCaseClient
from oyez_scraping.infrastructure.exceptions.api_exceptions import (
    OyezApiResponseError,
)


class TestOyezCaseClientPagination(unittest.TestCase):
    """Test pagination functionality in the OyezCaseClient class."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.client = OyezCaseClient(base_url="https://api.oyez.org/")
        # Mock the get method to avoid actual API calls
        self.client.get = Mock()

    def test_get_all_cases_auto_paginate_true(self) -> None:
        """Test get_all_cases with auto_paginate=True uses iter_all_cases."""
        # Mock iter_all_cases to return a fixed list
        expected_cases = [{"id": 1}, {"id": 2}, {"id": 3}]

        with patch.object(self.client, "iter_all_cases") as mock_iter:
            # Set up the mock to return our test data
            mock_iter.return_value = iter(expected_cases)

            # Call the method with auto_paginate=True
            result = self.client.get_all_cases(auto_paginate=True)

            # Verify iter_all_cases was called with correct parameters
            mock_iter.assert_called_once_with(
                labels=False, per_page=self.client.MAX_PAGE_SIZE
            )

            # Verify the result is as expected
            self.assertEqual(result, expected_cases)

    def test_get_all_cases_auto_paginate_false(self) -> None:
        """Test get_all_cases with auto_paginate=False uses direct API call."""
        # Set up the mock to return test data
        expected_cases = [{"id": 1}, {"id": 2}]
        self.client.get.return_value = expected_cases

        # Call the method with auto_paginate=False
        result = self.client.get_all_cases(auto_paginate=False, page=0, per_page=2)

        # Verify get was called with correct parameters
        self.client.get.assert_called_once_with(
            "cases", params={"labels": "false", "page": "0", "per_page": "2"}
        )

        # Verify the result is as expected
        self.assertEqual(result, expected_cases)

    def test_iter_all_cases_single_page(self) -> None:
        """Test iter_all_cases when all results fit on a single page."""
        # Setup mock to return a single page of results
        expected_cases = [{"id": 1}, {"id": 2}]
        self.client.get.return_value = expected_cases

        # Call the generator and collect results
        result = list(self.client.iter_all_cases(per_page=10))

        # Verify get was called with correct parameters
        self.client.get.assert_called_once_with(
            "cases", params={"labels": "false", "per_page": "10", "page": "0"}
        )

        # Verify the result is as expected
        self.assertEqual(result, expected_cases)

    def test_iter_all_cases_multiple_pages(self) -> None:
        """Test iter_all_cases when results span multiple pages."""
        # Setup mock to return multiple pages of results
        page1 = [{"id": 1}, {"id": 2}]
        page2 = [{"id": 3}, {"id": 4}]
        page3 = []  # Empty page indicates end of results

        self.client.get.side_effect = [page1, page2, page3]

        # Call the generator and collect results
        result = list(self.client.iter_all_cases(per_page=2))

        # Verify get was called for each page with correct parameters
        expected_calls = [
            call("cases", params={"labels": "false", "per_page": "2", "page": "0"}),
            call("cases", params={"labels": "false", "per_page": "2", "page": "1"}),
            call("cases", params={"labels": "false", "per_page": "2", "page": "2"}),
        ]
        self.assertEqual(self.client.get.call_args_list, expected_calls)

        # Verify the result contains all items from all pages
        self.assertEqual(result, page1 + page2)

    def test_iter_all_cases_partial_last_page(self) -> None:
        """Test iter_all_cases when the last page is partially filled."""
        # Setup mock to return multiple pages with partial last page
        page1 = [{"id": 1}, {"id": 2}]  # Full page
        page2 = [{"id": 3}]  # Partial page (indicates end of results)

        self.client.get.side_effect = [page1, page2]

        # Call the generator and collect results
        result = list(self.client.iter_all_cases(per_page=2))

        # Verify get was called for each page with correct parameters
        expected_calls = [
            call("cases", params={"labels": "false", "per_page": "2", "page": "0"}),
            call("cases", params={"labels": "false", "per_page": "2", "page": "1"}),
        ]
        self.assertEqual(self.client.get.call_args_list, expected_calls)

        # Verify the result contains all items from all pages
        self.assertEqual(result, page1 + page2)

    def test_iter_all_cases_with_term_filter(self) -> None:
        """Test iter_all_cases with a term filter."""
        # Setup mock to return a single page of filtered results
        expected_cases = [{"id": 1, "term": "2021"}, {"id": 2, "term": "2021"}]
        self.client.get.return_value = expected_cases

        # Call the generator with a term filter and collect results
        result = list(self.client.iter_all_cases(term="2021", per_page=10))

        # Verify get was called with correct parameters including the term filter
        self.client.get.assert_called_once_with(
            "cases",
            params={
                "labels": "false",
                "per_page": "10",
                "page": "0",
                "filter": "term:2021",
            },
        )

        # Verify the result is as expected
        self.assertEqual(result, expected_cases)

    def test_iter_all_cases_error_handling(self) -> None:
        """Test iter_all_cases handles API errors properly."""
        # Setup mock to return a non-list response (error case)
        self.client.get.return_value = {"error": "Invalid response"}

        # Call the generator and verify it raises the expected exception
        with pytest.raises(OyezApiResponseError):
            list(self.client.iter_all_cases())

    def test_get_cases_by_term_auto_paginate(self) -> None:
        """Test get_cases_by_term with auto_paginate=True uses iter_all_cases."""
        term = "2022"
        expected_cases = [{"id": 1, "term": term}, {"id": 2, "term": term}]

        with patch.object(self.client, "iter_all_cases") as mock_iter:
            # Set up the mock to return our test data
            mock_iter.return_value = iter(expected_cases)

            # Call the method with auto_paginate=True
            result = self.client.get_cases_by_term(term=term, auto_paginate=True)

            # Verify iter_all_cases was called with correct parameters
            mock_iter.assert_called_once_with(
                labels=False, per_page=self.client.MAX_PAGE_SIZE, term=term
            )

            # Verify the result is as expected
            self.assertEqual(result, expected_cases)

    def test_get_cases_by_term_auto_paginate_false(self) -> None:
        """Test get_cases_by_term with auto_paginate=False uses direct API call."""
        term = "2022"
        expected_cases = [{"id": 1, "term": term}, {"id": 2, "term": term}]
        self.client.get.return_value = expected_cases

        # Call the method with auto_paginate=False
        result = self.client.get_cases_by_term(
            term=term, auto_paginate=False, per_page=10
        )

        # Verify get was called with correct parameters
        self.client.get.assert_called_once_with(
            "cases",
            params={"filter": f"term:{term}", "labels": "false", "per_page": "10"},
        )

        # Verify the result is as expected
        self.assertEqual(result, expected_cases)

    def test_get_all_values_respects_max_page_size(self) -> None:
        """Test that retrieving all values respects the MAX_PAGE_SIZE limit of 1000."""
        # Setup mock to return a page of results
        expected_cases = [{"id": i} for i in range(1, 101)]  # 100 cases
        self.client.get.return_value = expected_cases

        # Call the method to retrieve all values
        with patch.object(self.client, "iter_all_cases") as mock_iter:
            mock_iter.return_value = iter(expected_cases)
            self.client.get_all_cases(auto_paginate=True)

            # Verify iter_all_cases was called with per_page=1000 (MAX_PAGE_SIZE)
            mock_iter.assert_called_once_with(
                labels=False,
                per_page=1000,  # Hardcoded expected value
            )
            self.assertEqual(
                mock_iter.call_args[1]["per_page"], self.client.MAX_PAGE_SIZE
            )

    def test_get_all_values_overrides_smaller_per_page(self) -> None:
        """Test that when retrieving all values, a smaller per_page is ignored in favor of MAX_PAGE_SIZE."""
        # Setup mock to return a page of results
        expected_cases = [{"id": i} for i in range(1, 101)]  # 100 cases

        # Call the method with auto_paginate=True but a smaller per_page
        with patch.object(self.client, "iter_all_cases") as mock_iter:
            mock_iter.return_value = iter(expected_cases)
            self.client.get_all_cases(auto_paginate=True, per_page=50)

            # Verify iter_all_cases was still called with per_page=1000 (MAX_PAGE_SIZE)
            self.assertEqual(
                mock_iter.call_args[1]["per_page"], self.client.MAX_PAGE_SIZE
            )
