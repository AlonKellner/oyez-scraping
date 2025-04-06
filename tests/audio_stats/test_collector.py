"""Tests for the collector module."""

import unittest
from unittest.mock import MagicMock, patch

from src.audio_stats.collector import AudioStatsCollector


class TestAudioStatsCollector(unittest.TestCase):
    """Test cases for the AudioStatsCollector class."""

    def setUp(self) -> None:
        """Set up test cases."""
        self.collector = AudioStatsCollector()

        # Sample audio types
        self.mock_audio_types = {
            "oral-arguments": {
                "description": "Oral arguments before the Supreme Court",
            },
            "opinion-announcements": {
                "description": "Opinion announcements by the justices",
            },
        }

        # Sample case data
        self.mock_cases = [
            {
                "ID": "2022/21-1333",
                "name": "Case 1",
                "oral_argument_audio": ["audio1", "audio2"],
                "opinion_announcement": [],
            },
            {
                "ID": "2022/21-404",
                "name": "Case 2",
                "oral_argument_audio": [],
                "opinion_announcement": ["announcement1"],
            },
        ]

    @patch("src.audio_stats.collector.requests.get")
    @patch("src.api.OyezAPI.get_audio_types")
    def test_collect_stats_by_term(
        self, mock_get_audio_types: MagicMock, mock_requests_get: MagicMock
    ) -> None:
        """Test collecting stats for a specific term."""
        # Configure mocks
        mock_get_audio_types.return_value = self.mock_audio_types

        # Mock the response for the term request
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_cases
        mock_requests_get.return_value = mock_response

        # For the detailed case data, we'll patch _get_detailed_case
        with patch.object(
            self.collector, "_get_detailed_case", side_effect=self.mock_cases
        ):
            # Call the method with max_cases=2 to limit processing
            result = self.collector.collect_stats_by_term(
                "2022", max_cases=2, show_progress=False
            )

        # Verify we got the right audio types in the result
        self.assertIn("oral-arguments", result)
        self.assertIn("opinion-announcements", result)

        # Verify the right cases were added to the right categories
        self.assertEqual(len(result["oral-arguments"]), 1)
        self.assertEqual(len(result["opinion-announcements"]), 1)
        self.assertEqual(result["oral-arguments"][0]["name"], "Case 1")
        self.assertEqual(result["opinion-announcements"][0]["name"], "Case 2")

    @patch("src.api.OyezAPI.get_case_metadata")
    def test_verify_case_has_audio(self, mock_get_case: MagicMock) -> None:
        """Test verifying if a case has audio."""
        # Configure mock
        case_data = {
            "ID": "2022/21-1333",
            "name": "Case With Audio",
            "oral_argument_audio": ["audio1", "audio2"],
            "opinion_announcement": ["announcement1"],
        }
        mock_get_case.return_value = case_data

        # Override the retry behavior for this test
        with patch.object(self.collector, "_get_detailed_case", return_value=case_data):
            # Call the method
            result = self.collector.verify_case_has_audio("2022/21-1333")

        # Verify the counts
        self.assertEqual(result["oral_arguments"], 2)
        self.assertEqual(result["opinion_announcements"], 1)

    @patch("src.audio_stats.collector.AudioStatsCollector._get_detailed_case")
    def test_verify_case_has_audio_error(
        self, mock_get_detailed_case: MagicMock
    ) -> None:
        """Test verifying if a case has audio when an error occurs."""
        # Configure mock to raise an exception
        mock_get_detailed_case.return_value = {}

        # Call the method
        result = self.collector.verify_case_has_audio("2022/21-1333")

        # Verify the counts are zero
        self.assertEqual(result["oral_arguments"], 0)
        self.assertEqual(result["opinion_announcements"], 0)

        # Verify the call
        mock_get_detailed_case.assert_called_once_with("2022/21-1333")

    @patch("src.audio_stats.collector.requests.get")
    def test_get_detailed_case_retry_logic(self, mock_requests_get: MagicMock) -> None:
        """Test retry logic in _get_detailed_case method."""
        # Create a collector with shorter delay times for testing
        collector = AudioStatsCollector(max_retries=2, request_delay=0.01)

        # First call fails, second succeeds
        mock_response1 = MagicMock()
        mock_response1.raise_for_status.side_effect = Exception("API error")

        mock_response2 = MagicMock()
        mock_response2.json.return_value = {"name": "Test Case"}

        mock_requests_get.side_effect = [mock_response1, mock_response2]

        # Mock time.sleep to speed up the test
        with patch("time.sleep"):
            result = collector._get_detailed_case("2022/test-case")

        # Verify the result
        self.assertEqual(result, {"name": "Test Case"})

        # Verify requests.get was called twice
        self.assertEqual(mock_requests_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
