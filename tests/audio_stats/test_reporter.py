"""Unit tests for the AudioStatsReporter class."""

import unittest

from src.audio_stats.reporter import AudioStatsReporter


class TestAudioStatsReporter(unittest.TestCase):
    """Test cases for the AudioStatsReporter class."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Sample audio data for testing
        self.sample_audio_data = {
            "oral-arguments": {
                "2022": [
                    {"ID": "2022/21-1333", "name": "Test Case 1"},
                    {"ID": "2022/21-1334", "name": "Test Case 2"},
                ],
                "2021": [
                    {"ID": "2021/20-1001", "name": "Test Case 3"},
                ],
            },
            "opinion-announcements": {
                "2022": [
                    {"ID": "2022/21-1335", "name": "Test Case 4"},
                ],
                "2020": [
                    {"ID": "2020/19-1001", "name": "Test Case 5"},
                    {"ID": "2020/19-1002", "name": "Test Case 6"},
                ],
            },
        }

        # Empty data for edge case testing
        self.empty_audio_data = {
            "oral-arguments": {},
            "opinion-announcements": {},
        }

    def test_get_audio_counts(self) -> None:
        """Test calculating total counts for each audio type."""
        counts = AudioStatsReporter.get_audio_counts(self.sample_audio_data)

        self.assertEqual(counts["oral-arguments"], 3)
        self.assertEqual(counts["opinion-announcements"], 3)

        # Test with empty data
        empty_counts = AudioStatsReporter.get_audio_counts(self.empty_audio_data)
        self.assertEqual(empty_counts["oral-arguments"], 0)
        self.assertEqual(empty_counts["opinion-announcements"], 0)

    def test_get_term_counts(self) -> None:
        """Test calculating audio counts by term for each audio type."""
        term_counts = AudioStatsReporter.get_term_counts(self.sample_audio_data)

        self.assertEqual(term_counts["oral-arguments"]["2022"], 2)
        self.assertEqual(term_counts["oral-arguments"]["2021"], 1)
        self.assertEqual(term_counts["opinion-announcements"]["2022"], 1)
        self.assertEqual(term_counts["opinion-announcements"]["2020"], 2)

        # Test with empty data
        empty_term_counts = AudioStatsReporter.get_term_counts(self.empty_audio_data)
        self.assertEqual(empty_term_counts["oral-arguments"], {})
        self.assertEqual(empty_term_counts["opinion-announcements"], {})

    def test_get_unique_terms(self) -> None:
        """Test getting the set of unique terms across all audio types."""
        unique_terms = AudioStatsReporter.get_unique_terms(self.sample_audio_data)

        self.assertEqual(len(unique_terms), 3)
        self.assertIn("2022", unique_terms)
        self.assertIn("2021", unique_terms)
        self.assertIn("2020", unique_terms)

        # Test with empty data
        empty_unique_terms = AudioStatsReporter.get_unique_terms(self.empty_audio_data)
        self.assertEqual(len(empty_unique_terms), 0)

    def test_get_earliest_latest_terms(self) -> None:
        """Test getting the earliest and latest terms in the data."""
        earliest, latest = AudioStatsReporter.get_earliest_latest_terms(
            self.sample_audio_data
        )

        self.assertEqual(earliest, "2020")
        self.assertEqual(latest, "2022")

        # Test with empty data
        empty_earliest, empty_latest = AudioStatsReporter.get_earliest_latest_terms(
            self.empty_audio_data
        )
        self.assertEqual(empty_earliest, "")
        self.assertEqual(empty_latest, "")

        # Test with non-numeric terms
        non_numeric_data = {
            "oral-arguments": {
                "2022": [{"ID": "2022/21-1333", "name": "Test Case 1"}],
                "unknown": [{"ID": "unknown/21-1334", "name": "Test Case 2"}],
            },
            "opinion-announcements": {},
        }
        non_numeric_earliest, non_numeric_latest = (
            AudioStatsReporter.get_earliest_latest_terms(non_numeric_data)
        )
        self.assertEqual(non_numeric_earliest, "2022")
        self.assertEqual(non_numeric_latest, "2022")

    def test_format_report(self) -> None:
        """Test generating a formatted text report of audio statistics."""
        report = AudioStatsReporter.format_report(self.sample_audio_data)

        # Check that the report contains key information
        self.assertIn("OYEZ LABELED AUDIO STATISTICS", report)
        self.assertIn("Total labeled audio files: 6", report)
        self.assertIn("(2020 - 2022)", report)
        self.assertIn("oral-arguments: 3 files", report)
        self.assertIn("opinion-announcements: 3 files", report)

        # Test with empty data
        empty_report = AudioStatsReporter.format_report(self.empty_audio_data)
        self.assertIn("Total labeled audio files: 0", empty_report)
        self.assertIn("Total unique terms: 0", empty_report)


if __name__ == "__main__":
    unittest.main()
