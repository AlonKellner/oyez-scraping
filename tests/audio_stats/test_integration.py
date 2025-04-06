"""Unit tests for the audio_stats package."""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.audio_stats import AudioStatsCollector, AudioStatsReporter


class TestAudioStats(unittest.TestCase):
    """Test cases for the audio_stats package."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.collector = AudioStatsCollector()

        # Sample case data for mocking API responses
        self.mock_term_cases = [
            {
                "ID": "2022/21-1333",
                "name": "Test Case 1",
                "oral_argument_audio": ["audio1", "audio2"],
                "opinion_announcement": [],
                "term": "2022",
            },
            {
                "ID": "2022/21-1334",
                "name": "Test Case 2",
                "oral_argument_audio": [],
                "opinion_announcement": ["announcement1"],
                "term": "2022",
            },
        ]

        # Mock audio types
        self.mock_audio_types = {
            "oral-arguments": {
                "description": "Oral arguments before the Supreme Court",
            },
            "opinion-announcements": {
                "description": "Opinion announcements by the justices",
            },
        }

        # Mock terms list
        self.mock_terms = ["2022", "2021"]

    @pytest.mark.timeout(5)
    @patch("src.api.OyezAPI.get_audio_types")
    @patch("src.audio_stats.collector.requests.get")
    def test_simplified_flow(
        self,
        mock_requests_get: MagicMock,
        mock_get_audio_types: MagicMock,
    ) -> None:
        """Test a simplified flow of collecting and reporting stats."""
        # Configure mocks
        mock_get_audio_types.return_value = self.mock_audio_types

        # Mock the API responses
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_term_cases
        mock_requests_get.return_value = mock_response

        # Override the detailed case fetching to return our mock data
        with patch.object(
            self.collector, "_get_detailed_case", side_effect=self.mock_term_cases
        ):
            # Step 1: Collect stats for a term
            term_stats = self.collector.collect_stats_by_term(
                "2022", show_progress=False
            )

        # Verify we have the correct audio types
        self.assertIn("oral-arguments", term_stats)
        self.assertIn("opinion-announcements", term_stats)

        # Verify correct case counts
        self.assertEqual(len(term_stats["oral-arguments"]), 1)
        self.assertEqual(len(term_stats["opinion-announcements"]), 1)

        # Step 2: Generate a report
        reporter = AudioStatsReporter()
        report = reporter.format_report(
            {"oral-arguments": {"2022": term_stats["oral-arguments"]}}
        )

        # Check that the report contains key information
        self.assertIn("OYEZ LABELED AUDIO STATISTICS", report)
        self.assertIn("Test Case 1", report)

    @pytest.mark.timeout(5)
    def test_verify_case_has_audio(self) -> None:
        """Test verifying if a case has audio."""
        case_data = {
            "ID": "2022/21-1333",
            "name": "Test Case With Audio",
            "oral_argument_audio": ["audio1", "audio2"],
            "opinion_announcement": ["announcement1"],
        }

        # Mock the _get_detailed_case method
        with patch.object(self.collector, "_get_detailed_case", return_value=case_data):
            # Verify a case has audio
            audio_counts = self.collector.verify_case_has_audio("2022/21-1333")

        # Verify correct counts
        self.assertEqual(audio_counts["oral_arguments"], 2)
        self.assertEqual(audio_counts["opinion_announcements"], 1)


if __name__ == "__main__":
    unittest.main()
