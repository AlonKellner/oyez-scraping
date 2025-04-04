"""Basic tests for the oyez-scraping project."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

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
