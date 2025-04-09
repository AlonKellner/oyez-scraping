"""Unit tests for the download service module."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from oyez_scraping.infrastructure.monitoring.progress import ProgressMonitor
from oyez_scraping.infrastructure.storage.download_tracker import DownloadTracker
from oyez_scraping.infrastructure.storage.filesystem import FilesystemStorage
from oyez_scraping.services.download_service import DownloadService
from oyez_scraping.services.raw_data_scraper import RawDataScraperService


class TestDownloadService:
    """Test cases for the DownloadService class."""

    @pytest.fixture
    def mock_scraper(self) -> mock.MagicMock:
        """Fixture providing a mock RawDataScraperService."""
        scraper_mock = mock.MagicMock(spec=RawDataScraperService)
        # Set up cache stats
        cache_mock = mock.MagicMock()
        cache_mock.get_cache_stats.return_value = {
            "case_count": 10,
            "audio_count": 5,
            "case_list_count": 2,
        }
        scraper_mock.cache = cache_mock
        return scraper_mock

    @pytest.fixture
    def mock_storage(self) -> mock.MagicMock:
        """Fixture providing a mock FilesystemStorage."""
        storage_mock = mock.MagicMock(spec=FilesystemStorage)
        # Mock ensure_directory to return the provided path
        storage_mock.ensure_directory.side_effect = lambda path: path
        return storage_mock

    @pytest.fixture
    def mock_tracker(self) -> mock.MagicMock:
        """Fixture providing a mock DownloadTracker."""
        tracker_mock = mock.MagicMock(spec=DownloadTracker)
        tracker_mock.get_stats.return_value = {
            "total_failed": 2,
            "retriable": 1,
            "permanent_failures": 1,
        }
        return tracker_mock

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Fixture providing a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def download_service(
        self,
        mock_scraper: mock.MagicMock,
        mock_storage: mock.MagicMock,
        temp_dir: Path,
        mock_tracker: mock.MagicMock,
    ) -> DownloadService:
        """Fixture providing a DownloadService instance for testing with mocked dependencies."""
        with mock.patch(
            "oyez_scraping.services.download_service.DownloadTracker",
            return_value=mock_tracker,
        ):
            service = DownloadService(
                scraper=mock_scraper,
                filesystem_storage=mock_storage,
                cache_dir=temp_dir,
                max_workers=2,  # Use fewer workers for testing
                max_retry_attempts=2,
                status_interval=1,  # Integer value for testing
            )

            # Ensure the service is using our mock_tracker
            assert service.download_tracker is mock_tracker

            return service

    def test_init(
        self,
        download_service: DownloadService,
        mock_scraper: mock.MagicMock,
        mock_storage: mock.MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test initializing a DownloadService."""
        assert download_service.scraper == mock_scraper
        assert download_service.storage == mock_storage
        assert download_service.cache_dir == temp_dir
        assert download_service.max_workers == 2
        assert download_service.max_retry_attempts == 2
        assert download_service.status_interval == 1  # Updated to match fixture value
        assert isinstance(download_service.stats, dict)
        assert download_service.progress_monitor is None

    def test_get_current_stats(self, download_service: DownloadService) -> None:
        """Test getting current statistics."""
        # Mock the cache_dir glob to return a list of mock files
        with mock.patch("pathlib.Path.glob") as mock_glob:
            mock_files = [
                mock.MagicMock(stat=lambda: mock.MagicMock(st_size=1024 * 1024))
                for _ in range(3)
            ]
            mock_glob.return_value = mock_files

            # Get stats
            stats = download_service._get_current_stats()

            # Verify expected stats are present
            assert stats["item_count"] == 10
            assert stats["audio_count"] == 5
            assert stats["case_list_count"] == 2
            assert stats["cache_size_mb"] == 3.0  # 3 files at 1MB each
            assert stats["items_processed"] == 0
            assert stats["audio_files_downloaded"] == 0
            assert stats["errors"] == 0
            assert stats["failed_items"] == 2
            assert stats["retriable_items"] == 1
            assert stats["permanent_failures"] == 1

    def test_get_current_stats_handles_exceptions(
        self, download_service: DownloadService
    ) -> None:
        """Test that _get_current_stats handles exceptions when calculating cache size."""
        # Mock the glob to raise an exception
        with mock.patch("pathlib.Path.glob", side_effect=Exception("Test exception")):
            stats = download_service._get_current_stats()

            # Should still return stats with cache_size_mb set to 0
            assert stats["cache_size_mb"] == 0.0

    def test_start_stop_progress_monitoring(
        self, download_service: DownloadService
    ) -> None:
        """Test starting and stopping progress monitoring."""
        with mock.patch(
            "oyez_scraping.services.download_service.ProgressMonitor"
        ) as mock_monitor_cls:
            mock_monitor = mock.MagicMock(spec=ProgressMonitor)
            mock_monitor_cls.return_value = mock_monitor

            # Start monitoring
            download_service._start_progress_monitoring()

            # Should have created a ProgressMonitor
            mock_monitor_cls.assert_called_once()
            # Should have started the monitor
            mock_monitor.start.assert_called_once()

            # Stop monitoring
            download_service._stop_progress_monitoring()

            # Should have stopped the monitor
            mock_monitor.stop.assert_called_once()

    def test_process_case_successful(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test processing a case successfully."""
        # Set up mock case data
        case = {"term": "2020", "docket_number": "123-45"}

        # Set up mock return values
        mock_scraper.scrape_case.return_value = {"full_case_data": "sample"}
        mock_scraper.scrape_case_audio_content.return_value = {
            "section1": ["audio1.mp3", "audio2.mp3"],
            "section2": ["audio3.mp3"],
        }

        # Create mock for download_tracker.mark_successful
        mark_successful_mock = mock.MagicMock()
        download_service.download_tracker.mark_successful = mark_successful_mock

        # Process the case
        result_success, result_audio_count = download_service._process_case(case)

        # Check results
        assert result_success is True
        assert result_audio_count == 3

        # Verify expected method calls
        mock_scraper.scrape_case.assert_called_once_with("2020", "123-45")
        mock_scraper.scrape_case_audio_content.assert_called_once()
        mark_successful_mock.assert_called_once_with("2020/123-45")

    def test_process_case_with_skip_audio(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test processing a case with skip_audio=True."""
        # Set up mock case data
        case = {"term": "2020", "docket_number": "123-45"}

        # Create mock for download_tracker.mark_successful
        mark_successful_mock = mock.MagicMock()
        download_service.download_tracker.mark_successful = mark_successful_mock

        # Process the case with skip_audio=True
        result_success, result_audio_count = download_service._process_case(
            case, skip_audio=True
        )

        # Check results
        assert result_success is True
        assert result_audio_count == 0

        # Verify expected method calls
        mock_scraper.scrape_case.assert_called_once_with("2020", "123-45")
        mock_scraper.scrape_case_audio_content.assert_not_called()
        mark_successful_mock.assert_called_once_with("2020/123-45")

    def test_process_case_with_processed_cases(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test processing a case with a processed_cases set."""
        # Set up mock case data
        case = {"term": "2020", "docket_number": "123-45"}

        # Set up processed cases set
        processed_cases: set[str] = set()

        # Process the case
        first_result = download_service._process_case(
            case, processed_cases=processed_cases
        )
        # Use the result to avoid unused variable warnings
        assert first_result[0] is True  # success
        assert first_result[1] >= 0  # audio_count

        # Check that the case was added to processed_cases
        assert "2020/123-45" in processed_cases

        # Process the same case again
        second_result = download_service._process_case(
            case, processed_cases=processed_cases
        )
        # Should be skipped and return True, 0
        assert second_result[0] is True  # success
        assert second_result[1] == 0  # audio_count

        # Scrape_case should only have been called once
        assert mock_scraper.scrape_case.call_count == 1

    def test_process_case_with_missing_data(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test processing a case with missing term or docket."""
        # Case with missing term
        case1 = {"docket_number": "123-45"}
        success1, audio_count1 = download_service._process_case(case1)
        assert success1 is False
        assert audio_count1 == 0

        # Case with missing docket
        case2 = {"term": "2020"}
        success2, audio_count2 = download_service._process_case(case2)
        assert success2 is False
        assert audio_count2 == 0

        # Verify scrape_case was not called for either case
        mock_scraper.scrape_case.assert_not_called()

    def test_process_case_with_error(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test processing a case that raises an error."""
        # Set up mock case data
        case = {"term": "2020", "docket_number": "123-45"}

        # Make scrape_case raise an exception
        mock_scraper.scrape_case.side_effect = Exception("Test error")

        # Create mock for download_tracker.mark_failed
        mark_failed_mock = mock.MagicMock()
        download_service.download_tracker.mark_failed = mark_failed_mock

        # Process the case
        result_success, result_audio_count = download_service._process_case(case)

        # Should have failed
        assert result_success is False
        assert result_audio_count == 0

        # Should have marked the case as failed
        mark_failed_mock.assert_called_once_with("2020/123-45", case)

    def test_download_term(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test downloading a term."""
        # Set up mock case list
        mock_cases = [
            {"term": "2020", "docket_number": "123-45"},
            {"term": "2020", "docket_number": "234-56"},
        ]
        mock_scraper.scrape_term.return_value = mock_cases

        # Mock _process_case to return success
        with (
            mock.patch.object(
                download_service, "_process_case", return_value=(True, 2)
            ) as mock_process,
            mock.patch.object(
                download_service, "_start_progress_monitoring"
            ) as mock_start_monitor,
            mock.patch.object(
                download_service, "_stop_progress_monitoring"
            ) as mock_stop_monitor,
        ):
            # Download the term
            download_service.download_term("2020")

            # Verify progress monitoring was started and stopped
            mock_start_monitor.assert_called_once()
            mock_stop_monitor.assert_called_once()

            # Verify term was scraped
            mock_scraper.scrape_term.assert_called_once_with("2020")

            # Verify each case was processed
            assert mock_process.call_count == 2

            # Check stats were updated correctly
            assert download_service.stats["items_processed"] == 2
            assert download_service.stats["audio_files_downloaded"] == 4

    def test_download_term_with_exception(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test downloading a term that raises an exception."""
        # Make scrape_term raise an exception
        mock_scraper.scrape_term.side_effect = Exception("Test error")

        # Mock progress monitoring
        with (
            mock.patch.object(
                download_service, "_start_progress_monitoring"
            ) as mock_start_monitor,
            mock.patch.object(
                download_service, "_stop_progress_monitoring"
            ) as mock_stop_monitor,
        ):
            # Should raise the exception
            with pytest.raises(Exception, match="Test error"):
                download_service.download_term("2020")

            # Verify progress monitoring was started and stopped despite the exception
            mock_start_monitor.assert_called_once()
            mock_stop_monitor.assert_called_once()

    def test_download_multiple_terms(self, download_service: DownloadService) -> None:
        """Test downloading multiple terms."""
        # Mock download_term method
        with (
            mock.patch.object(download_service, "download_term") as mock_download_term,
            mock.patch.object(download_service, "_retry_failed_cases") as mock_retry,
            mock.patch.object(download_service, "_start_progress_monitoring"),
            mock.patch.object(download_service, "_stop_progress_monitoring"),
        ):
            # Download multiple terms
            stats = download_service.download_multiple_terms(
                ["2019", "2020"], skip_audio=True
            )

            # Verify each term was downloaded
            assert mock_download_term.call_count == 2
            mock_download_term.assert_any_call("2019", skip_audio=True)
            mock_download_term.assert_any_call("2020", skip_audio=True)

            # Verify retry was called
            mock_retry.assert_called_once_with(skip_audio=True)

            # Check stats includes elapsed time
            assert "elapsed_time" in stats
            assert "elapsed_time_formatted" in stats

    def test_download_multiple_terms_with_term_error(
        self, download_service: DownloadService
    ) -> None:
        """Test downloading multiple terms where one term fails."""
        # Create a mock for download_term
        mock_download_term = mock.MagicMock()

        # Define the side effect function
        def mock_download_side_effect(term: str, **_: Any) -> None:
            """Mock side effect function that raises an error for 2020 term."""
            if term == "2020":
                raise Exception("Test error")

        # Set the side effect on the mock
        mock_download_term.side_effect = mock_download_side_effect

        with (
            mock.patch.object(download_service, "download_term", mock_download_term),
            mock.patch.object(download_service, "_retry_failed_cases") as mock_retry,
            mock.patch.object(download_service, "_start_progress_monitoring"),
            mock.patch.object(download_service, "_stop_progress_monitoring"),
        ):
            # Download multiple terms
            download_service.download_multiple_terms(["2019", "2020"], skip_audio=True)

            # Verify each term was attempted
            assert mock_download_term.call_count == 2

            # Verify retry was still called
            mock_retry.assert_called_once()

            # Check stats
            assert download_service.stats["errors"] == 1

    def test_download_all_cases(
        self, download_service: DownloadService, mock_scraper: mock.MagicMock
    ) -> None:
        """Test downloading all cases."""
        # Set up mock case list
        mock_cases = [
            {"term": "2019", "docket_number": "123-45"},
            {"term": "2020", "docket_number": "234-56"},
        ]
        mock_scraper.scrape_all_cases.return_value = mock_cases

        # Mock _process_case to return success
        with (
            mock.patch.object(
                download_service, "_process_case", return_value=(True, 2)
            ) as mock_process,
            mock.patch.object(download_service, "_retry_failed_cases") as mock_retry,
            mock.patch.object(download_service, "_start_progress_monitoring"),
            mock.patch.object(download_service, "_stop_progress_monitoring"),
        ):
            # Download all cases
            stats = download_service.download_all_cases()

            # Verify all cases were scraped
            mock_scraper.scrape_all_cases.assert_called_once()

            # Verify each case was processed
            assert mock_process.call_count == 2

            # Verify retry was called
            mock_retry.assert_called_once_with(skip_audio=False)

            # Check stats
            assert download_service.stats["items_processed"] == 2
            assert download_service.stats["audio_files_downloaded"] == 4
            assert "elapsed_time" in stats

    def test_retry_failed_cases(self, download_service: DownloadService) -> None:
        """Test retrying failed cases."""
        # Mock failed cases
        failed_items = [
            ("2019/123-45", {"term": "2019", "docket_number": "123-45"}),
            ("2020/234-56", {"term": "2020", "docket_number": "234-56"}),
        ]

        # Create proper mocks for the download_tracker methods
        get_failed_items_mock = mock.MagicMock(return_value=failed_items)
        has_failed_items_mock = mock.MagicMock(side_effect=[True, False])

        # Replace the tracker methods with our mocks
        download_service.download_tracker.get_failed_items_for_retry = (
            get_failed_items_mock
        )
        download_service.download_tracker.has_failed_items_for_retry = (
            has_failed_items_mock
        )

        # Create a proper mock for _process_case
        process_mock = mock.MagicMock(return_value=(True, 2))

        # Create a proper mock for time.sleep
        sleep_mock = mock.MagicMock()

        # Apply the patches
        with (
            mock.patch.object(download_service, "_process_case", process_mock),
            mock.patch("time.sleep", sleep_mock),
        ):
            # Retry failed cases
            download_service._retry_failed_cases()

            # Verify items were retried
            assert process_mock.call_count == 2

            # Verify we didn't need to sleep (only one retry round)
            assert not sleep_mock.called

    def test_retry_failed_cases_multiple_rounds(
        self, download_service: DownloadService
    ) -> None:
        """Test retrying failed cases with multiple retry rounds."""
        # Mock failed cases
        failed_items_round1 = [
            ("2019/123-45", {"term": "2019", "docket_number": "123-45"}),
            ("2020/234-56", {"term": "2020", "docket_number": "234-56"}),
        ]
        failed_items_round2 = [
            ("2020/234-56", {"term": "2020", "docket_number": "234-56"})
        ]

        # Create proper mocks for the download_tracker methods
        get_failed_items_mock = mock.MagicMock(
            side_effect=[
                failed_items_round1,
                failed_items_round2,
            ]
        )
        has_failed_items_mock = mock.MagicMock(
            side_effect=[
                True,
                True,
                False,
            ]
        )

        # Replace the tracker methods with our mocks
        download_service.download_tracker.get_failed_items_for_retry = (
            get_failed_items_mock
        )
        download_service.download_tracker.has_failed_items_for_retry = (
            has_failed_items_mock
        )

        # Create a mock function for _process_case
        mock_process = mock.MagicMock()

        # Define the side effect function
        def mock_process_side_effect(
            case: dict[str, Any], **_: Any
        ) -> tuple[bool, int]:
            """Mock side effect function that succeeds for item 123-45 and fails for other items."""
            if case.get("docket_number") == "123-45":
                return True, 2
            return False, 0

        # Set the side effect on the mock
        mock_process.side_effect = mock_process_side_effect

        # Apply the patch
        with (
            mock.patch.object(download_service, "_process_case", mock_process),
            mock.patch("time.sleep") as mock_sleep,
        ):
            # Retry failed cases
            download_service._retry_failed_cases()

            # Verify retry was attempted for each item
            assert mock_process.call_count == 3  # 2 in first round, 1 in second

            # Verify sleep was called between retry rounds
            mock_sleep.assert_called_once_with(60)  # 60 * retry_round (which is 1)
