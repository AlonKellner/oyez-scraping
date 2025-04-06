"""Basic tests for the oyez-scraping project."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.api import OyezAPI
from src.models import OralArgument
from src.scraper import OyezScraper

MOCK_CASE_DATA = {
    "name": "Brown v. Board of Education",
    "docket_number": "1-123",
    "oral_argument_audio": [{"href": "https://api.oyez.org/case/1234/argument/1"}],
}

MOCK_ARG_META = {
    "id": "1234",
}

MOCK_ARGUMENT_DATA = {
    "date": "1954-05-17",
    "duration": "3600",
    "media_file": [{"href": "https://example.com/audio.mp3"}],
    "sections": [
        {
            "name": "Introduction",
            "turns": [
                {
                    "speaker": {
                        "name": "Earl Warren",
                        "role": "Chief Justice",
                        "identifier": "warren",
                    },
                    "text_blocks": [
                        {
                            "text": "We'll hear arguments in case number...",
                            "start": 0,
                            "stop": 10,
                        }
                    ],
                }
            ],
        }
    ],
}

MOCK_TERM_LIST = [
    "2023",
    "2022",
    "2021",
]

MOCK_CASES_BY_TERM = {
    "2023": [
        {
            "ID": "2023/22-500",
            "name": "Case One",
            "oral_argument_audio": [{"href": "https://api.example.com/audio1"}],
        },
        {
            "ID": "2023/22-501",
            "name": "Case Two",
            "oral_argument_audio": [],  # No audio available
        },
    ],
    "2022": [
        {
            "ID": "2022/21-100",
            "name": "Case Three",
            "oral_argument_audio": [{"href": "https://api.example.com/audio3"}],
        }
    ],
}

MOCK_LABELED_AUDIO_TYPES = {
    "oral-arguments": {"description": "Oral arguments before the Supreme Court"},
    "opinion-announcements": {"description": "Opinion announcements by the justices"},
}


def test_environment() -> None:
    """Test that the test environment is properly set up."""
    assert True, "Basic assertion passes"


def test_version_import() -> None:
    """Test that we can import the version."""
    from src._version import __version__

    assert isinstance(__version__, str), "Version should be a string"
    assert len(__version__) > 0, "Version should not be empty"


@patch("src.api.OyezAPI.get_case_metadata")
@patch("src.api.OyezAPI.get_oral_argument_data")
@patch("src.api.OyezAPI.find_audio_url")
def test_scrape_case(
    mock_find_audio: Mock, mock_get_arg_data: Mock, mock_get_metadata: Mock
) -> None:
    """Test scraping a single case."""
    # Configure mock responses
    mock_get_metadata.return_value = MOCK_CASE_DATA
    mock_get_arg_data.return_value = MOCK_ARGUMENT_DATA
    mock_find_audio.return_value = ("https://example.com/audio.mp3", 3600.0)

    # Use Brown v. Board of Education (1954) as test case
    case_id = "brown-v-board-of-education"

    with tempfile.TemporaryDirectory() as temp_dir:
        scraper = OyezScraper(temp_dir)
        argument = scraper.scrape_case(case_id)

        assert isinstance(argument, OralArgument)
        assert argument.case_id == case_id
        assert "Brown" in argument.case_name
        assert argument.docket_number == "1-123"
        assert argument.transcript_url == "https://api.oyez.org/case/1234/argument/1"
        assert argument.audio_url == "https://example.com/audio.mp3"
        assert argument.duration == 3600.0
        assert len(argument.speakers) == 1
        assert argument.speakers[0].name == "Earl Warren"
        assert len(argument.utterances) == 1


@patch("src.api.OyezAPI.get_audio_types")
@patch("src.api.OyezAPI.get_term_list")
@patch("src.api.OyezAPI.get_cases_by_term")
def test_find_all_labeled_audio(
    mock_get_cases_by_term: Mock, mock_get_term_list: Mock, mock_get_audio_types: Mock
) -> None:
    """Test finding all available labeled audio files in Oyez."""
    # Configure mock responses
    mock_get_term_list.return_value = MOCK_TERM_LIST
    mock_get_cases_by_term.side_effect = lambda term: MOCK_CASES_BY_TERM.get(term, [])
    mock_get_audio_types.return_value = MOCK_LABELED_AUDIO_TYPES

    # Call the function to find all labeled audio
    all_audio_files = OyezAPI.find_all_labeled_audio()

    # Verify the results
    assert isinstance(all_audio_files, dict), (
        "Should return a dictionary of audio types"
    )
    assert "oral-arguments" in all_audio_files, "Should include oral arguments"
    assert "opinion-announcements" in all_audio_files, (
        "Should include opinion announcements"
    )

    # Verify the oral arguments section contains case data
    oral_args = all_audio_files["oral-arguments"]
    assert isinstance(oral_args, dict), (
        "Oral arguments should be a dictionary keyed by term"
    )
    assert "2023" in oral_args, "Should include 2023 term"
    assert "2022" in oral_args, "Should include 2022 term"

    # Verify the case data for the 2023 term
    term_2023 = oral_args["2023"]
    assert len(term_2023) == 1, "Should only include cases with available audio"
    assert term_2023[0]["ID"] == "2023/22-500", "Should include the first case"

    # Verify the case data for the 2022 term
    term_2022 = oral_args["2022"]
    assert len(term_2022) == 1, "Should only include cases with available audio"
    assert term_2022[0]["ID"] == "2022/21-100", (
        "Should include the case from the 2022 term"
    )


@pytest.mark.integration
def test_real_scraping() -> None:
    """Test scraping with actual API call to Oyez and process the case.

    This test performs a real API call to scrape a recent Supreme Court case and
    processes the full audio into segments. The outputs are saved to the .output
    directory.
    """
    # Use a relatively short and recent case
    case_id = "2022/21-1333"  # Gonzalez v. Google LLC (2023)

    # Create the output directory
    output_dir = Path(".output")
    output_dir.mkdir(exist_ok=True)

    # Create a scraper that outputs to .output directory
    scraper = OyezScraper(str(output_dir))

    # First scrape the case metadata
    argument = scraper.scrape_case(case_id)

    # Basic metadata checks
    assert isinstance(argument, OralArgument)
    assert argument.case_id == case_id
    assert "Gonzalez" in argument.case_name or "Google" in argument.case_name
    assert argument.transcript_url
    assert argument.audio_url
    assert argument.duration > 0
    assert len(argument.speakers) > 0

    # Verify there are utterances
    assert len(argument.utterances) > 0, "Should have extracted utterances"

    # Verify the date - should be February 21, 2023
    assert argument.argument_date.year == 2023
    assert argument.argument_date.month == 2
    assert argument.argument_date.day == 21

    # Process the case (download audio and extract segments)
    scraper.process_case(case_id)

    # Verify that the output files were created
    safe_case_id = case_id.replace("/", "-")
    case_dir = output_dir / safe_case_id

    # Check if full audio was downloaded
    assert (case_dir / "full_audio.mp3").exists(), "Full audio file should exist"

    # Check if metadata file was created
    metadata_path = case_dir / scraper.METADATA_FILE
    assert metadata_path.exists(), "Metadata file should exist"

    # Check if segments directory was created
    segments_dir = case_dir / scraper.AUDIO_SEGMENT_DIR
    assert segments_dir.exists(), "Segments directory should exist"

    # Verify segments were created in FLAC format
    flac_segments = list(segments_dir.glob("*.flac"))
    print(f"Found {len(flac_segments)} FLAC audio segments")
    assert len(flac_segments) > 0, "Should have at least one FLAC audio segment"

    # Verify that the metadata file contains utterance metrics
    with metadata_path.open("r") as f:
        metadata = json.loads(f.read())
        assert "utterance_metrics" in metadata, (
            "Metadata should include utterance metrics"
        )
        assert "total_utterance_time" in metadata["utterance_metrics"]
        assert "total_non_utterance_time" in metadata["utterance_metrics"]
        assert "utterance_time_percentage" in metadata["utterance_metrics"]
        assert "non_utterance_time_percentage" in metadata["utterance_metrics"]

        # Verify utterances have gap information
        if "utterances" in metadata and len(metadata["utterances"]) > 0:
            assert "gap_before" in metadata["utterances"][0], (
                "Utterances should include gap info"
            )
            if len(metadata["utterances"]) > 1:
                assert "gap_after" in metadata["utterances"][0], (
                    "Utterances should include gap_after info"
                )


@pytest.mark.integration
def test_find_all_labeled_audio_integration() -> None:
    """Test finding all available labeled audio files in Oyez with real API calls.

    This test performs actual API calls to Oyez to retrieve information about
    different types of available labeled audio files.
    """
    # Call the function to find all labeled audio without mocks
    all_audio_files = OyezAPI.find_all_labeled_audio()

    # Verify the basic structure of the response
    assert isinstance(all_audio_files, dict), (
        "Should return a dictionary of audio types"
    )

    # Check if we have some audio types
    assert len(all_audio_files) > 0, "Should have at least one audio type"

    # Since this is an integration test with real API calls,
    # we'll get different results depending on API availability.
    # Let's just verify the structure if data is present.

    print(f"Found audio types: {list(all_audio_files.keys())}")

    # If oral arguments are present, check their structure
    if "oral-arguments" in all_audio_files:
        oral_args = all_audio_files["oral-arguments"]
        assert isinstance(oral_args, dict), "Should be a dictionary"

        print(f"Found terms with oral arguments: {list(oral_args.keys())}")

        # Check any cases that may be available
        for term, cases in oral_args.items():
            if cases:
                assert isinstance(cases, list), "Cases should be a list"
                print(f"Term {term} has {len(cases)} cases with audio")

                # Check the first case has the expected fields
                first_case = cases[0]
                assert "ID" in first_case or "id" in first_case, (
                    "Case should have an ID"
                )
                assert "name" in first_case, "Case should have a name"

                # Print a sample case
                print(f"Sample case: {first_case.get('name')}")
                break

    # If opinion announcements are present, check their structure
    if "opinion-announcements" in all_audio_files:
        opinion_announcements = all_audio_files["opinion-announcements"]
        assert isinstance(opinion_announcements, dict), "Should be a dictionary"

        print(
            f"Found terms with opinion announcements: {list(opinion_announcements.keys())}"
        )

        # Check any available terms that have announcements
        for term, cases in opinion_announcements.items():
            if cases:
                assert isinstance(cases, list), "Cases should be a list"
                print(f"Term {term} has {len(cases)} cases with announcements")
                break
