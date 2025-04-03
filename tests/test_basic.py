"""Basic tests for the oyez-scraping project."""

import tempfile
from unittest.mock import Mock, patch

from src.scraper import OralArgument, OyezScraper

MOCK_CASE_DATA = {
    "name": "Brown v. Board of Education",
    "docket_number": "1-123",
    "oral_argument_audio": [{"href": "https://api.oyez.org/case/1234/argument/1"}],
}

MOCK_ARGUMENT_DATA = {
    "date": "1954-05-17",
    "duration": "3600",
    "media_file": {"href": "https://example.com/audio.mp3"},
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


@patch("src.scraper.requests.get")
def test_scrape_case(mock_get: Mock) -> None:
    """Test scraping a single case."""
    # Configure mock responses
    mock_responses = [
        type(
            "Response",
            (),
            {"json": lambda: MOCK_CASE_DATA, "raise_for_status": lambda: None},
        ),
        type(
            "Response",
            (),
            {"json": lambda: MOCK_ARGUMENT_DATA, "raise_for_status": lambda: None},
        ),
    ]
    mock_get.side_effect = mock_responses

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
