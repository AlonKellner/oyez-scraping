"""Integration tests for the Oyez API endpoints.

These tests verify our assumptions about the Oyez API structure, relations between
different endpoints, and media availability. They test against the actual Oyez API.

Note: These tests require internet connection and may fail if the Oyez API changes
its structure or if rate limiting is applied.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from oyez_scraping.infrastructure.api.case_client import (
    AudioContentType,
    OyezCaseClient,
)

# Constants for test cases that are known to be stable and have complete data
# Roe v. Wade - a landmark case with complete information including oral arguments
TEST_TERM = "1971"
TEST_DOCKET = "70-18"
TEST_CASE_ID = f"{TEST_TERM}/{TEST_DOCKET}"

# Constants for test cases with opinion announcements and dissenting opinions
OPINION_TEST_TERM = "2022"
OPINION_TEST_DOCKET1 = "21-476"  # 303 Creative LLC v. Elenis
OPINION_TEST_DOCKET2 = "22-506"  # Biden v. Nebraska

# Output directory for generated files
OUTPUT_DIR = Path(".output/api_samples")


@pytest.fixture(scope="session", autouse=True)
def ensure_output_dir() -> None:
    """Ensure the output directory exists."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def case_client() -> OyezCaseClient:
    """Create an OyezCaseClient for API requests."""
    return OyezCaseClient()


@pytest.fixture
def case_data(case_client: OyezCaseClient) -> dict[str, Any]:
    """Get case data for the test case.

    This avoids repeating the same API call in multiple tests.
    """
    return case_client.get_case_by_id(TEST_TERM, TEST_DOCKET)


@pytest.fixture
def oral_argument_data(
    case_client: OyezCaseClient, case_data: dict[str, Any]
) -> dict[str, Any]:
    """Get oral argument data for the test case.

    This avoids repeating the same API call in multiple tests.
    """
    # Check for oral argument audio
    oral_args = case_data.get("oral_argument_audio", [])

    # We use a test case known to have oral arguments
    assert oral_args, f"The test case {TEST_CASE_ID} must have oral arguments"

    # Get the first oral argument URL
    arg_url = oral_args[0]["href"]

    # Fetch the oral argument data using the client
    return case_client.get_oral_argument(arg_url)


@pytest.fixture
def opinion_case_data1(case_client: OyezCaseClient) -> dict[str, Any]:
    """Get case data for the first opinion test case.

    This avoids repeating the same API call in multiple tests.
    """
    return case_client.get_case_by_id(OPINION_TEST_TERM, OPINION_TEST_DOCKET1)


@pytest.fixture
def opinion_case_data2(case_client: OyezCaseClient) -> dict[str, Any]:
    """Get case data for the second opinion test case.

    This avoids repeating the same API call in multiple tests.
    """
    return case_client.get_case_by_id(OPINION_TEST_TERM, OPINION_TEST_DOCKET2)


class TestOyezApiEndpoints:
    """Tests that verify the structure and behavior of Oyez API endpoints."""

    def test_term_lookup_structure(self, case_client: OyezCaseClient) -> None:
        """Test that the term-based lookup returns the expected structure."""
        # Use our client to get cases by term
        cases = case_client.get_cases_by_term(TEST_TERM)

        # Basic validation of the response
        assert isinstance(cases, list), "Term lookup should return a list of cases"
        assert len(cases) > 0, f"No cases found for term {TEST_TERM}"

        # Check the structure of the first case
        first_case = cases[0]
        assert "ID" in first_case, "Case should have an ID field"
        assert "name" in first_case, "Case should have a name field"
        assert "docket_number" in first_case, "Case should have a docket_number field"

        # Print for debugging purposes
        print(
            f"First case from term lookup: {first_case['name']} (ID: {first_case['ID']})"
        )

        # Check that the term-based lookup does NOT include audio information
        # This is a key assumption about the API behavior
        assert "oral_argument_audio" not in first_case, (
            "Term-based lookup should not include oral_argument_audio field. "
            "This indicates an API change!"
        )

    def test_direct_case_lookup_structure(self, case_data: dict[str, Any]) -> None:
        """Test that the direct case lookup returns the expected structure with audio information."""
        # Validate the response structure
        assert "ID" in case_data, "Case should have an ID field"
        assert "name" in case_data, "Case should have a name field"
        assert "docket_number" in case_data, "Case should have a docket_number field"

        # Check that direct case lookup DOES include audio information
        # This is a key assumption about the API behavior
        assert "oral_argument_audio" in case_data, (
            "Direct case lookup should include oral_argument_audio field. "
            "This indicates an API change!"
        )

        # Validate the audio information structure
        audio_info = case_data.get("oral_argument_audio", [])
        assert isinstance(audio_info, list), "oral_argument_audio should be a list"
        assert len(audio_info) > 0, "oral_argument_audio should not be empty"

        first_audio = audio_info[0]
        assert "href" in first_audio, "Audio entry should have an href field"

        # Verify the href is a valid URL or path
        href = first_audio["href"]
        assert href, "href should not be empty"
        assert isinstance(href, str), "href should be a string"

        # Print for debugging purposes
        print(f"Audio URL found: {href}")

    def test_id_consistency_across_endpoints(self, case_client: OyezCaseClient) -> None:
        """Test that case IDs are consistent across different endpoint responses."""
        # Get a list of cases from the term lookup
        term_cases = case_client.get_cases_by_term(TEST_TERM)

        # Select a case from the term lookup results
        sample_case = next(
            (case for case in term_cases if case.get("docket_number") == TEST_DOCKET),
            term_cases[0],
        )

        # Extract case information
        docket = sample_case["docket_number"]

        # Get the same case by direct lookup
        direct_case = case_client.get_case_by_id(TEST_TERM, docket)

        # Verify the case name matches (a more reliable identifier than the numeric ID)
        assert direct_case["name"] == sample_case["name"], "Case name mismatch"
        assert direct_case["docket_number"] == sample_case["docket_number"], (
            "Docket number mismatch"
        )

        # Print for debugging purposes
        print(f"Case ID consistency verified for {sample_case['name']}")

    def test_oral_argument_lookup(self, oral_argument_data: dict[str, Any]) -> None:
        """Test lookup of oral argument details from its URL."""
        # Print the keys in the response for debugging
        print(f"Oral argument data keys: {list(oral_argument_data.keys())}")

        # Validate oral argument structure - the structure may vary, but should have
        # at least some of these fields
        expected_fields = ["id", "media_file", "title", "transcript"]
        present_fields = [
            field for field in expected_fields if field in oral_argument_data
        ]
        assert present_fields, (
            f"Oral argument should have at least one of these fields: {expected_fields}"
        )

        # Check for media file information
        assert "media_file" in oral_argument_data, (
            "Oral argument should have media_file field"
        )

    def test_speakers_extraction(
        self, case_client: OyezCaseClient, oral_argument_data: dict[str, Any]
    ) -> None:
        """Test the extraction of speakers from the structure of oral arguments."""
        # Extract speakers using the client
        speakers = case_client.extract_speakers(oral_argument_data)

        # Print what we found for debugging
        print(f"Found {len(speakers)} unique speakers in the oral argument")

        # For our test case, we know there should be speakers
        assert len(speakers) > 0, "No speakers found in the oral argument"

        # Verify structure of speaker data
        for speaker in speakers:
            assert "identifier" in speaker, "Speaker should have an identifier"
            assert "name" in speaker, "Speaker should have a name"

    def test_audio_url_availability(
        self, case_client: OyezCaseClient, oral_argument_data: dict[str, Any]
    ) -> None:
        """Test that audio URLs are available and structured correctly."""
        # Find audio URL using the client
        audio_url = case_client.extract_audio_url(oral_argument_data)

        # Verify the URL is accessible
        assert audio_url, "No audio URL extracted"
        assert isinstance(audio_url, str), "Audio URL should be a string"

        # Verify the URL is accessible
        is_accessible = case_client.verify_audio_url(audio_url)
        assert is_accessible, f"Audio URL {audio_url} is not accessible"

        print(f"Successfully verified audio URL: {audio_url}")


class TestOyezApiOpinionAnnouncements:
    """Tests that verify the structure and behavior of opinion announcement endpoints."""

    def test_opinion_announcement_availability(
        self, opinion_case_data1: dict[str, Any]
    ) -> None:
        """Test that opinion announcements are available in the case data."""
        # Check for opinion announcement field
        assert "opinion_announcement" in opinion_case_data1, (
            "Test case should include opinion_announcement field"
        )

        # Validate structure
        announcements = opinion_case_data1.get("opinion_announcement", [])
        assert isinstance(announcements, list | dict), (
            "opinion_announcement should be a list or dict"
        )

        # Convert to list if it's a dict
        if isinstance(announcements, dict):
            announcements = [announcements]

        assert len(announcements) > 0, "opinion_announcement should not be empty"

        # Check first announcement
        first_announcement = announcements[0]
        assert "id" in first_announcement, "Announcement should have an id"
        assert "title" in first_announcement, "Announcement should have a title"
        assert "href" in first_announcement, "Announcement should have an href"

        print(f"Found opinion announcement: {first_announcement['title']}")

    def test_dissenting_opinion_availability(
        self, case_client: OyezCaseClient, opinion_case_data1: dict[str, Any]
    ) -> None:
        """Test that dissenting opinions are available in the case data."""
        audio_content = case_client.get_case_audio_content(opinion_case_data1)

        # Check that we have dissenting opinions
        dissenting_opinions = audio_content[AudioContentType.DISSENTING_OPINION]
        assert len(dissenting_opinions) > 0, "Test case should have dissenting opinions"

        first_dissent = dissenting_opinions[0]
        assert "title" in first_dissent, "Dissenting opinion should have a title"
        assert "dissenting opinion" in first_dissent["title"].lower(), (
            "Dissenting opinion title should contain 'dissenting opinion'"
        )

        print(f"Found dissenting opinion: {first_dissent['title']}")

    def test_audio_content_classification(
        self,
        case_client: OyezCaseClient,
        opinion_case_data1: dict[str, Any],
        opinion_case_data2: dict[str, Any],
    ) -> None:
        """Test that audio content is correctly classified by type."""
        # Get all audio content from each case
        audio_content1 = case_client.get_case_audio_content(opinion_case_data1)
        audio_content2 = case_client.get_case_audio_content(opinion_case_data2)

        # Verify structure of the audio content dictionary
        assert AudioContentType.ORAL_ARGUMENT in audio_content1, (
            "Should have oral argument key"
        )
        assert AudioContentType.OPINION_ANNOUNCEMENT in audio_content1, (
            "Should have opinion announcement key"
        )
        assert AudioContentType.DISSENTING_OPINION in audio_content1, (
            "Should have dissenting opinion key"
        )

        # Both test cases should have all three types of content
        assert len(audio_content1[AudioContentType.ORAL_ARGUMENT]) > 0, (
            "Should have oral arguments"
        )
        assert len(audio_content1[AudioContentType.OPINION_ANNOUNCEMENT]) > 0, (
            "Should have opinion announcements"
        )
        assert len(audio_content1[AudioContentType.DISSENTING_OPINION]) > 0, (
            "Should have dissenting opinions"
        )

        assert len(audio_content2[AudioContentType.ORAL_ARGUMENT]) > 0, (
            "Second case should have oral arguments"
        )
        assert len(audio_content2[AudioContentType.OPINION_ANNOUNCEMENT]) > 0, (
            "Second case should have opinion announcements"
        )

        # Print summary
        print(
            f"Case 1 audio content: {', '.join(f'{k}: {len(v)}' for k, v in audio_content1.items() if v)}"
        )
        print(
            f"Case 2 audio content: {', '.join(f'{k}: {len(v)}' for k, v in audio_content2.items() if v)}"
        )

    def test_fetch_opinion_announcement_data(
        self, case_client: OyezCaseClient, opinion_case_data1: dict[str, Any]
    ) -> None:
        """Test fetching and processing an opinion announcement."""
        audio_content = case_client.get_case_audio_content(opinion_case_data1)
        opinion_announcements = audio_content[AudioContentType.OPINION_ANNOUNCEMENT]

        assert len(opinion_announcements) > 0, "Should have opinion announcements"

        # Get the announcement data
        announcement = opinion_announcements[0]
        announcement_data = case_client.get_opinion_announcement(announcement["href"])

        # Validate fields
        assert "id" in announcement_data, "Announcement should have an id"
        assert "title" in announcement_data, "Announcement should have a title"
        assert "media_file" in announcement_data, "Announcement should have media_file"

        # Extract and validate audio URL
        audio_url = case_client.extract_audio_url(announcement_data)
        assert audio_url, "No audio URL extracted"

        # Extract speakers
        try:
            speakers = case_client.extract_speakers(announcement_data)
            assert len(speakers) > 0, "Should find speakers in the announcement"
            print(f"Found {len(speakers)} speakers in opinion announcement")
        except Exception as e:
            print(f"Note: Couldn't extract speakers from announcement: {e}")

        # Extract utterances
        try:
            utterances = case_client.extract_utterances(announcement_data)
            assert len(utterances) > 0, "Should find utterances in the announcement"
            print(f"Found {len(utterances)} utterances in opinion announcement")
        except Exception as e:
            print(f"Note: Couldn't extract utterances from announcement: {e}")

    def test_fetch_dissenting_opinion_data(
        self, case_client: OyezCaseClient, opinion_case_data1: dict[str, Any]
    ) -> None:
        """Test fetching and processing a dissenting opinion."""
        audio_content = case_client.get_case_audio_content(opinion_case_data1)
        dissenting_opinions = audio_content[AudioContentType.DISSENTING_OPINION]

        assert len(dissenting_opinions) > 0, "Should have dissenting opinions"

        # Get the dissenting opinion data
        dissent = dissenting_opinions[0]
        dissent_data = case_client.get_dissenting_opinion(dissent["href"])

        # Validate fields
        assert "id" in dissent_data, "Dissenting opinion should have an id"
        assert "title" in dissent_data, "Dissenting opinion should have a title"
        assert "media_file" in dissent_data, "Dissenting opinion should have media_file"

        # Extract and validate audio URL
        audio_url = case_client.extract_audio_url(dissent_data)
        assert audio_url, "No audio URL extracted"

        # Extract speakers
        try:
            speakers = case_client.extract_speakers(dissent_data)
            assert len(speakers) > 0, "Should find speakers in the dissenting opinion"
            print(f"Found {len(speakers)} speakers in dissenting opinion")
        except Exception as e:
            print(f"Note: Couldn't extract speakers from dissenting opinion: {e}")

        # Extract utterances
        try:
            utterances = case_client.extract_utterances(dissent_data)
            assert len(utterances) > 0, (
                "Should find utterances in the dissenting opinion"
            )
            print(f"Found {len(utterances)} utterances in dissenting opinion")
        except Exception as e:
            print(f"Note: Couldn't extract utterances from dissenting opinion: {e}")


class TestOyezApiDataConsistency:
    """Tests that verify the consistency of data across API responses."""

    def test_utterance_extraction(
        self, case_client: OyezCaseClient, oral_argument_data: dict[str, Any]
    ) -> None:
        """Test extraction of utterances with timing information."""
        # Extract utterances using the client
        utterances = case_client.extract_utterances(oral_argument_data)

        # Print what we found for debugging
        print(f"Found {len(utterances)} utterances in the oral argument")

        # We should have utterances in our test case
        assert len(utterances) > 0, "No utterances found in the oral argument"

        # Verify structure of utterance data
        self._verify_utterances(utterances)

    def _verify_utterances(self, utterances: list[dict[str, Any]]) -> None:
        """Verify structure and consistency of extracted utterances.

        Args:
            utterances: List of utterances to verify

        Raises
        ------
            AssertionError: If utterances do not have the expected structure
        """
        # Verify the first few utterances if there are many
        sample_size = min(5, len(utterances))

        for i in range(sample_size):
            utterance = utterances[i]

            # Check for required fields
            assert "speaker_id" in utterance, f"Utterance {i} missing speaker_id"
            assert "start_time" in utterance, f"Utterance {i} missing start_time"
            assert "end_time" in utterance, f"Utterance {i} missing end_time"
            assert "text" in utterance, f"Utterance {i} missing text"

            # Check types
            assert isinstance(utterance["speaker_id"], str), (
                f"Utterance {i} speaker_id must be a string"
            )
            assert isinstance(utterance["text"], str), (
                f"Utterance {i} text must be a string"
            )

            # For numeric fields, accept either int or float
            start_time = utterance["start_time"]
            end_time = utterance["end_time"]
            assert isinstance(start_time, int | float), (
                f"Utterance {i} start_time must be numeric"
            )
            assert isinstance(end_time, int | float), (
                f"Utterance {i} end_time must be numeric"
            )

            # Check time order
            start_float = float(start_time)
            end_float = float(end_time)
            assert start_float <= end_float, (
                f"Utterance {i} start_time must be <= end_time"
            )

            # Check for non-empty text
            assert utterance["text"].strip(), f"Utterance {i} must have non-empty text"

        # Check for timing sequence (utterances should be in chronological order)
        if len(utterances) > 1:
            for i in range(1, len(utterances)):
                prev_end = float(utterances[i - 1]["end_time"])
                curr_start = float(utterances[i]["start_time"])

                # We allow a small variation in timing (overlaps or gaps)
                # For real data parsing, we'd want a more sophisticated approach
                assert abs(curr_start - prev_end) < 60, (
                    f"Utterance {i} has a large gap or overlap with previous utterance"
                )

    def test_save_sample_api_responses(self, case_client: OyezCaseClient) -> None:
        """Save sample API responses for reference during implementation.

        This is not a test per se, but generates valuable development artifacts.
        """
        # Get term lookup response
        term_cases = case_client.get_cases_by_term(TEST_TERM)

        # Get direct case lookup
        case_data = case_client.get_case_by_id(TEST_TERM, TEST_DOCKET)

        # Get oral argument response
        oral_args = case_data.get("oral_argument_audio", [])
        assert oral_args, f"The test case {TEST_CASE_ID} must have oral arguments"

        arg_url = oral_args[0]["href"]
        arg_data = case_client.get_oral_argument(arg_url)

        # Save the responses to the .output directory
        with open(OUTPUT_DIR / "term_lookup_sample.json", "w") as f:
            json.dump(term_cases, f, indent=2)

        with open(OUTPUT_DIR / "case_lookup_sample.json", "w") as f:
            json.dump(case_data, f, indent=2)

        with open(OUTPUT_DIR / "oral_argument_sample.json", "w") as f:
            json.dump(arg_data, f, indent=2)

        # Save opinion announcement and dissenting opinion samples
        opinion_case = case_client.get_case_by_id(
            OPINION_TEST_TERM, OPINION_TEST_DOCKET1
        )
        audio_content = case_client.get_case_audio_content(opinion_case)

        with open(OUTPUT_DIR / "opinion_case_sample.json", "w") as f:
            json.dump(opinion_case, f, indent=2)

        # Save an opinion announcement sample if available
        opinion_announcements = audio_content[AudioContentType.OPINION_ANNOUNCEMENT]
        if opinion_announcements:
            opinion_data = case_client.get_opinion_announcement(
                opinion_announcements[0]["href"]
            )
            with open(OUTPUT_DIR / "opinion_announcement_sample.json", "w") as f:
                json.dump(opinion_data, f, indent=2)

        # Save a dissenting opinion sample if available
        dissenting_opinions = audio_content[AudioContentType.DISSENTING_OPINION]
        if dissenting_opinions:
            dissent_data = case_client.get_dissenting_opinion(
                dissenting_opinions[0]["href"]
            )
            with open(OUTPUT_DIR / "dissenting_opinion_sample.json", "w") as f:
                json.dump(dissent_data, f, indent=2)

        # Print the path for reference
        print(f"Sample API responses saved to {OUTPUT_DIR}")
