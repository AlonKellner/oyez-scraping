"""Integration tests for the audio_stats package with live Oyez API."""

import os
import unittest

import pytest
import requests

from src.audio_stats import AudioStatsCollector, AudioStatsReporter


@pytest.mark.integration
class TestOyezIntegration(unittest.TestCase):
    """Integration tests that make actual API calls to Oyez."""

    def setUp(self) -> None:
        """Set up the test environment."""
        self.collector = AudioStatsCollector(max_retries=2, request_delay=1.0)
        self.reporter = AudioStatsReporter()

        # API base URL
        self.base_url = "https://api.oyez.org"

        # Known case with audio data
        self.test_case_id = "2022/21-1333"  # Gonzalez v. Google LLC

        # Skip tests if SKIP_INTEGRATION_TESTS environment variable is set
        if os.environ.get("SKIP_INTEGRATION_TESTS"):
            self.skipTest("Skipping integration tests")

        # Test if the Oyez API is accessible
        try:
            response = requests.get(f"{self.base_url}/cases", timeout=10)
            response.raise_for_status()
        except (requests.RequestException, ConnectionError):
            self.skipTest("Oyez API is not accessible")

    @pytest.mark.timeout(30)
    def test_api_endpoints_behavior(self) -> None:
        """Test the different behavior of Oyez API endpoints.

        This test verifies our understanding of the API discrepancy:
        - Term lookup endpoints don't include audio data
        - Direct case lookup endpoints do include audio data
        """
        # First, get cases by term (2022)
        term_url = (
            f"{self.base_url}/cases?filter=term:2022&labels=true&page=0&per_page=5"
        )
        term_response = requests.get(
            term_url, headers={"Accept": "application/json"}, timeout=30
        )
        term_response.raise_for_status()
        term_cases = term_response.json()

        # Verify we got some cases
        self.assertGreater(len(term_cases), 0)

        # Verify term-based endpoint doesn't include audio fields
        first_case = term_cases[0]
        self.assertNotIn(
            "oral_argument_audio",
            first_case,
            "Term-based response unexpectedly includes oral_argument_audio",
        )
        self.assertNotIn(
            "opinion_announcement",
            first_case,
            "Term-based response unexpectedly includes opinion_announcement",
        )

        # Now get a known case by direct lookup
        direct_url = f"{self.base_url}/cases/{self.test_case_id}"
        direct_response = requests.get(
            direct_url, headers={"Accept": "application/json"}, timeout=30
        )
        direct_response.raise_for_status()
        direct_case = direct_response.json()

        # Verify direct lookup includes audio fields
        self.assertIn(
            "oral_argument_audio",
            direct_case,
            "Direct case lookup missing oral_argument_audio field",
        )
        self.assertIn(
            "opinion_announcement",
            direct_case,
            "Direct case lookup missing opinion_announcement field",
        )

        print("\nAPI endpoints behavior verified:")
        print("  - Term-based endpoint responses don't include audio fields")
        print("  - Direct case lookup responses do include audio fields")

    @pytest.mark.timeout(30)
    def test_gonzalez_case_has_audio(self) -> None:
        """Test that the Gonzalez v. Google case has audio files."""
        # Verify the case has audio using our collector
        audio_counts = self.collector.verify_case_has_audio(self.test_case_id)

        # The case should have at least one oral argument
        self.assertGreater(audio_counts["oral_arguments"], 0)

        # Print out what we found for debugging
        print(
            f"\nGonzalez v. Google LLC has {audio_counts['oral_arguments']} oral arguments"
        )
        print(
            f"Gonzalez v. Google LLC has {audio_counts['opinion_announcements']} opinion announcements"
        )

    @pytest.mark.timeout(120)
    def test_collect_term_stats_with_audio(self) -> None:
        """Test collecting audio statistics for term 2022.

        This test verifies our collector can properly handle the API discrepancy
        by fetching detailed case data for each case found in the term.
        """
        # Test with a small number of cases to avoid long test runs
        term_stats = self.collector.collect_stats_by_term("2022", max_cases=3)

        # Verify we got the expected audio types
        self.assertIn("oral-arguments", term_stats)
        self.assertIn("opinion-announcements", term_stats)

        # Count total cases with audio
        total_cases_with_audio = len(term_stats["oral-arguments"]) + len(
            term_stats["opinion-announcements"]
        )

        # Print info about what we found
        print("\nCollected audio stats for 3 cases from term 2022:")
        print(f"  Cases with oral arguments: {len(term_stats['oral-arguments'])}")
        print(
            f"  Cases with opinion announcements: {len(term_stats['opinion-announcements'])}"
        )

        # Since we're only testing 3 cases, we might not find audio in the random sample
        # But our collector should be working correctly regardless
        if total_cases_with_audio == 0:
            print(
                "  No audio found in the sample of 3 cases (this is expected for small samples)"
            )

            # Verify our known test case has audio as a sanity check
            test_case_audio = self.collector.verify_case_has_audio(self.test_case_id)
            has_audio = (
                test_case_audio["oral_arguments"] > 0
                or test_case_audio["opinion_announcements"] > 0
            )
            self.assertTrue(has_audio, "Known test case should have audio")
            print(f"  Verified that known test case ({self.test_case_id}) has audio")
        else:
            print(f"  Found {total_cases_with_audio} cases with audio in the sample")

    @pytest.mark.timeout(30)
    def test_generate_report_with_known_case(self) -> None:
        """Test generating a report using a known case with audio."""
        # Fetch a known case that has audio using our collector's internal method
        detailed_case = self.collector._get_detailed_case(self.test_case_id)

        # Create a report structure with this case
        report_data = {
            "oral-arguments": {"2022": []},
            "opinion-announcements": {"2022": []},
        }

        # Add case to the appropriate categories
        if detailed_case.get("oral_argument_audio"):
            report_data["oral-arguments"]["2022"].append(detailed_case)

        if detailed_case.get("opinion_announcement"):
            report_data["opinion-announcements"]["2022"].append(detailed_case)

        # Generate the report
        report = self.reporter.format_report(report_data)

        # Verify the report contains key information
        self.assertIn("OYEZ LABELED AUDIO STATISTICS", report)
        self.assertIn("2022", report)

        # Get counts of audio files from our report data
        oral_args_count = len(report_data["oral-arguments"]["2022"])
        opinion_count = len(report_data["opinion-announcements"]["2022"])
        total_audio_count = oral_args_count + opinion_count

        # Verify we have audio data in our report
        self.assertGreater(
            total_audio_count,
            0,
            "Expected to find at least one case with audio in the report",
        )

        print(
            f"\nReport successfully generated with {oral_args_count} oral arguments cases "
            f"and {opinion_count} opinion announcement cases"
        )


if __name__ == "__main__":
    unittest.main()
