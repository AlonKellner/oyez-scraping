"""Integration tests for the raw data scraper service.

These tests verify that the raw data scraper service can fetch data from
the Oyez API and properly store it in the cache.
"""

import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from oyez_scraping.infrastructure.api.case_client import OyezCaseClient
from oyez_scraping.services.raw_data_scraper import RawDataScraperService

# Constants for test cases based on the API tests
TEST_TERM = "1971"
TEST_DOCKET = "70-18"
TEST_CASE_ID = f"{TEST_TERM}/{TEST_DOCKET}"


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client for testing."""
    mock_client = MagicMock(spec=OyezCaseClient)

    # Setup mock responses
    mock_client.get_cases_by_term.return_value = [
        {
            "ID": "1",
            "term": TEST_TERM,
            "docket_number": TEST_DOCKET,
            "name": "Test Case",
        }
    ]

    mock_client.get_case_by_id.return_value = {
        "ID": "1",
        "term": TEST_TERM,
        "docket_number": TEST_DOCKET,
        "name": "Test Case",
        "oral_argument_audio": [
            {"href": "api/cases/1971/70-18/oral-argument/1", "title": "Oral Argument"}
        ],
    }

    mock_client.get_case_audio_content.return_value = {
        "oral_argument": [
            {
                "href": "api/cases/1971/70-18/oral-argument/1",
                "title": "Oral Argument",
                "type": "oral_argument",
            }
        ]
    }

    mock_client.get_oral_argument.return_value = {
        "id": "oral-argument-1",
        "title": "Oral Argument",
        "media_file": [{"mime": "audio/mp3", "href": "http://example.com/audio.mp3"}],
        "transcript": {
            "sections": [
                {
                    "turns": [
                        {
                            "speaker": {"name": "Speaker 1", "identifier": "speaker-1"},
                            "text": "Test transcript",
                        }
                    ]
                }
            ]
        },
    }

    mock_client.extract_audio_url.return_value = "http://example.com/audio.mp3"
    mock_client.verify_audio_url.return_value = True

    return mock_client


@pytest.fixture
def temp_cache_dir() -> Generator[str, None, None]:
    """Create a temporary directory for the cache."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def scraper_service(
    temp_cache_dir: str, mock_api_client: MagicMock
) -> RawDataScraperService:
    """Create a scraper service for testing with a mock API client."""
    return RawDataScraperService(cache_dir=temp_cache_dir, api_client=mock_api_client)


class TestRawDataScraperService:
    """Integration tests for the RawDataScraperService."""

    def test_scrape_term(
        self, scraper_service: RawDataScraperService, mock_api_client: MagicMock
    ) -> None:
        """Test scraping a term."""
        # Scrape the test term
        cases = scraper_service.scrape_term(TEST_TERM)

        # Verify results
        assert len(cases) == 1
        assert cases[0]["term"] == TEST_TERM
        assert cases[0]["docket_number"] == TEST_DOCKET

        # Verify the API client was called correctly
        mock_api_client.get_cases_by_term.assert_called_once_with(TEST_TERM)

        # Verify the case list was cached
        assert scraper_service.cache.case_list_exists(f"term_{TEST_TERM}")

        # Scrape again to test cache
        mock_api_client.get_cases_by_term.reset_mock()
        cases_from_cache = scraper_service.scrape_term(TEST_TERM)

        # Verify results from cache
        assert cases_from_cache == cases

        # Verify the API client was not called again
        mock_api_client.get_cases_by_term.assert_not_called()

    def test_scrape_case(
        self, scraper_service: RawDataScraperService, mock_api_client: MagicMock
    ) -> None:
        """Test scraping a case."""
        # Scrape the test case
        case = scraper_service.scrape_case(TEST_TERM, TEST_DOCKET)

        # Verify results
        assert case["term"] == TEST_TERM
        assert case["docket_number"] == TEST_DOCKET

        # Verify the API client was called correctly
        mock_api_client.get_case_by_id.assert_called_once_with(TEST_TERM, TEST_DOCKET)

        # Verify the case was cached
        assert scraper_service.cache.case_exists(TEST_CASE_ID)

        # Scrape again to test cache
        mock_api_client.get_case_by_id.reset_mock()
        case_from_cache = scraper_service.scrape_case(TEST_TERM, TEST_DOCKET)

        # Verify results from cache
        assert case_from_cache == case

        # Verify the API client was not called again
        mock_api_client.get_case_by_id.assert_not_called()

    def test_scrape_case_audio_content(
        self, scraper_service: RawDataScraperService, mock_api_client: MagicMock
    ) -> None:
        """Test scraping audio content from a case."""
        # First get the case data
        case_data = scraper_service.scrape_case(TEST_TERM, TEST_DOCKET)

        # Reset the mock to clear the call history
        mock_api_client.reset_mock()

        # Mock the requests session to avoid real HTTP requests
        with patch("requests.Session.get") as mock_get:
            # Setup mock response for audio download
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"mock audio data"
            mock_get.return_value = mock_response

            # Scrape audio content
            audio_content = scraper_service.scrape_case_audio_content(case_data)

        # Verify results
        assert "oral_argument" in audio_content
        assert len(audio_content["oral_argument"]) == 1
        assert audio_content["oral_argument"][0]["title"] == "Oral Argument"
        assert "detailed_data" in audio_content["oral_argument"][0]

        # Verify the API client was called correctly
        mock_api_client.get_case_audio_content.assert_called_once_with(case_data)
        mock_api_client.get_oral_argument.assert_called_once()
        mock_api_client.extract_audio_url.assert_called_once()

        # Verify the audio content and audio file were cached
        content_id = scraper_service._generate_content_id(
            audio_content["oral_argument"][0]["href"]
        )
        assert scraper_service._content_data_exists(content_id)
        assert scraper_service.cache.audio_exists(content_id)

        # Test caching by scraping again
        mock_api_client.reset_mock()
        with patch("requests.Session.get") as mock_get:
            # We shouldn't reach this but set it up anyway
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"mock audio data"
            mock_get.return_value = mock_response

            # Scrape audio content again
            audio_content_from_cache = scraper_service.scrape_case_audio_content(
                case_data
            )

        # Verify results from cache
        assert audio_content_from_cache == audio_content

        # Verify API methods for content data were not called again
        mock_api_client.get_oral_argument.assert_not_called()

    def test_scrape_and_download_all(
        self, scraper_service: RawDataScraperService
    ) -> None:
        """Test the high-level scrape_and_download_all method."""
        # Mock the requests session to avoid real HTTP requests
        with patch("requests.Session.get") as mock_get:
            # Setup mock response for audio download
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"mock audio data"
            mock_get.return_value = mock_response

            # Scrape all data for a specific term
            stats = scraper_service.scrape_and_download_all(terms=[TEST_TERM])

        # Verify results
        assert stats["cases_scraped"] == 1
        assert stats["audio_files_downloaded"] == 1
        assert stats["errors"] == 0
        assert "duration_seconds" in stats
        assert "cache_stats" in stats

        # Verify cache stats
        cache_stats = stats["cache_stats"]
        assert cache_stats["case_count"] == 1
        assert cache_stats["audio_count"] == 1
        assert cache_stats["case_list_count"] > 0  # At least the term list


class TestRawDataScraperServiceWithRealAPI:
    """Integration tests for the RawDataScraperService with the real API.

    These tests are marked as slow and will be skipped by default.
    To run them, use pytest with the --run-slow flag.
    """

    @pytest.mark.skip(reason="Slow test that uses the real API")
    def test_scrape_term_real_api(self, temp_cache_dir: str) -> None:
        """Test scraping a term using the real API."""
        # Create a scraper with a real API client
        scraper = RawDataScraperService(cache_dir=temp_cache_dir)

        # Scrape a term with a small number of cases
        cases = scraper.scrape_term(TEST_TERM)

        # Basic validation
        assert isinstance(cases, list)
        assert len(cases) > 0

        # Verify cache
        assert scraper.cache.case_list_exists(f"term_{TEST_TERM}")

        # Detailed validation of first case
        first_case = cases[0]
        assert "term" in first_case
        assert "docket_number" in first_case
        assert "name" in first_case

    @pytest.mark.skip(reason="Slow test that uses the real API")
    def test_scrape_case_real_api(self, temp_cache_dir: str) -> None:
        """Test scraping a case using the real API."""
        # Create a scraper with a real API client
        scraper = RawDataScraperService(cache_dir=temp_cache_dir)

        # Scrape a specific case
        case = scraper.scrape_case(TEST_TERM, TEST_DOCKET)

        # Verify data
        assert case["term"] == TEST_TERM
        assert case["docket_number"] == TEST_DOCKET
        assert "name" in case
        assert "oral_argument_audio" in case

        # Verify cache
        assert scraper.cache.case_exists(TEST_CASE_ID)

    @pytest.mark.skip(reason="Very slow test that downloads audio files")
    def test_download_audio_real_api(self, temp_cache_dir: str) -> None:
        """Test downloading audio files using the real API."""
        # Create a scraper with a real API client
        scraper = RawDataScraperService(cache_dir=temp_cache_dir)

        # Scrape case data first
        case_data = scraper.scrape_case(TEST_TERM, TEST_DOCKET)

        # Scrape audio content
        audio_content = scraper.scrape_case_audio_content(case_data)

        # Verify we got audio content
        assert audio_content
        assert any(content_list for content_list in audio_content.values())
