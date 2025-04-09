"""Integration tests for the CLI module."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest

from oyez_scraping.cli.download_cli import generate_recent_terms, handle_dry_run, main
from oyez_scraping.infrastructure.storage.filesystem import FilesystemStorage
from oyez_scraping.services.download_service import DownloadService
from oyez_scraping.services.raw_data_scraper import RawDataScraperService


class TestCliIntegration:
    """Integration tests for the CLI module."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Fixture providing a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_generate_recent_terms(self) -> None:
        """Test generating recent terms."""
        # Test with 0 terms
        terms_0 = generate_recent_terms(0)
        assert terms_0 == []

        # Test with 3 terms
        terms_3 = generate_recent_terms(3)
        assert len(terms_3) == 3

        # Test that terms are in descending order
        assert int(terms_3[0]) > int(terms_3[1]) > int(terms_3[2])

    def test_handle_dry_run_with_terms(self) -> None:
        """Test handling dry run with specific terms."""
        mock_scraper = mock.MagicMock(spec=RawDataScraperService)
        mock_scraper.scrape_term.side_effect = [
            [{"term": "2020", "docket_number": "123-45"}],
            [
                {"term": "2019", "docket_number": "234-56"},
                {"term": "2019", "docket_number": "345-67"},
            ],
        ]

        terms = ["2020", "2019"]

        with mock.patch("logging.Logger.info") as mock_info:
            handle_dry_run(mock_scraper, terms)

            # Should have logged info about terms and case counts
            mock_info.assert_any_call("Dry run mode - would download the following:")
            mock_info.assert_any_call("Terms: 2020, 2019")
            mock_info.assert_any_call("  - Term 2020: 1 cases")
            mock_info.assert_any_call("  - Term 2019: 2 cases")

            # Should have called scrape_term for each term
            mock_scraper.scrape_term.assert_any_call("2020")
            mock_scraper.scrape_term.assert_any_call("2019")

    def test_handle_dry_run_all_cases(self) -> None:
        """Test handling dry run with all cases."""
        mock_scraper = mock.MagicMock(spec=RawDataScraperService)
        mock_scraper.scrape_all_cases.return_value = [
            {"term": "2020", "docket_number": "123-45"},
            {"term": "2019", "docket_number": "234-56"},
        ]

        with mock.patch("logging.Logger.info") as mock_info:
            handle_dry_run(mock_scraper)

            # Should have logged info about all cases
            mock_info.assert_any_call("Dry run mode - would download the following:")
            mock_info.assert_any_call("All available cases")
            mock_info.assert_any_call("  - Total: 2 cases")

            # Should have called scrape_all_cases
            mock_scraper.scrape_all_cases.assert_called_once()

    def test_handle_dry_run_error_handling(self) -> None:
        """Test error handling in dry run."""
        mock_scraper = mock.MagicMock(spec=RawDataScraperService)
        mock_scraper.scrape_term.side_effect = Exception("API error")

        terms = ["2020"]

        with (
            mock.patch("logging.Logger.info"),
            mock.patch("logging.Logger.error") as mock_error,
        ):
            handle_dry_run(mock_scraper, terms)

            # Should have logged the error
            mock_error.assert_called_with(
                "Error fetching case list for term 2020: API error"
            )

    def test_main_with_mock_services(self, temp_dir: Path) -> None:
        """Test main function with mocked services."""
        # Mock command line arguments
        test_args = [
            "--cache-dir",
            str(temp_dir),
            "--terms",
            "2020",
            "2019",
            "--verbose",
            "--workers",
            "2",
        ]

        # Mock FilesystemStorage
        mock_storage = mock.MagicMock(spec=FilesystemStorage)

        # Mock RawDataScraperService
        mock_scraper = mock.MagicMock(spec=RawDataScraperService)

        # Mock DownloadService
        mock_download_service = mock.MagicMock(spec=DownloadService)
        mock_download_service.download_multiple_terms.return_value = {
            "items_processed": 3,
            "audio_files_downloaded": 10,
            "errors": 0,
        }

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.FilesystemStorage",
                return_value=mock_storage,
            ),
            mock.patch(
                "oyez_scraping.cli.download_cli.RawDataScraperService",
                return_value=mock_scraper,
            ),
            mock.patch(
                "oyez_scraping.cli.download_cli.DownloadService",
                return_value=mock_download_service,
            ),
            mock.patch("logging.Logger.info") as mock_info,
        ):
            # Run main
            main()

            # Verify log messages
            mock_info.assert_any_call("Starting Oyez dataset download")
            mock_info.assert_any_call(f"Cache directory: {temp_dir.resolve()}")
            mock_info.assert_any_call("Workers: 2")
            mock_info.assert_any_call("Download completed successfully")

            # Verify service interaction
            mock_download_service.download_multiple_terms.assert_called_once_with(
                ["2020", "2019"], skip_audio=False
            )

    def test_main_with_dry_run(self, temp_dir: Path) -> None:
        """Test main function with dry run option."""
        # Mock command line arguments
        test_args = ["--cache-dir", str(temp_dir), "--terms", "2020", "--dry-run"]

        # Mock handle_dry_run
        mock_handle_dry_run = mock.MagicMock()

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.RawDataScraperService"
            ) as mock_scraper_cls,
            mock.patch(
                "oyez_scraping.cli.download_cli.handle_dry_run", mock_handle_dry_run
            ),
        ):
            mock_scraper = mock.MagicMock()
            mock_scraper_cls.return_value = mock_scraper

            # Run main
            main()

            # Verify handle_dry_run was called with expected args
            mock_handle_dry_run.assert_called_once_with(mock_scraper, ["2020"])

    def test_main_with_recent_terms(self, temp_dir: Path) -> None:
        """Test main function with recent terms option."""
        # Mock command line arguments
        test_args = ["--cache-dir", str(temp_dir), "--recent-terms", "3"]

        # Mock generate_recent_terms
        mock_generate_recent_terms = mock.MagicMock(
            return_value=["2022", "2021", "2020"]
        )

        # Mock DownloadService
        mock_download_service = mock.MagicMock(spec=DownloadService)

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.generate_recent_terms",
                mock_generate_recent_terms,
            ),
            mock.patch(
                "oyez_scraping.cli.download_cli.DownloadService",
                return_value=mock_download_service,
            ),
            mock.patch("logging.Logger.info") as mock_info,
        ):
            # Run main
            main()

            # Verify generate_recent_terms was called
            mock_generate_recent_terms.assert_called_once_with(3)

            # Verify log message about recent terms
            mock_info.assert_any_call("Will download 3 recent terms: 2022, 2021, 2020")

            # Verify download service was called with generated terms
            mock_download_service.download_multiple_terms.assert_called_once_with(
                ["2022", "2021", "2020"], skip_audio=False
            )

    def test_main_with_skip_audio(self, temp_dir: Path) -> None:
        """Test main function with skip_audio option."""
        # Mock command line arguments
        test_args = ["--cache-dir", str(temp_dir), "--skip-audio"]

        # Mock DownloadService
        mock_download_service = mock.MagicMock(spec=DownloadService)

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.DownloadService",
                return_value=mock_download_service,
            ),
            mock.patch("logging.Logger.info") as mock_info,
        ):
            # Run main
            main()

            # Verify log message about skipping audio
            mock_info.assert_any_call("Skipping audio downloads (metadata only)")

            # Verify download service was called with skip_audio=True
            mock_download_service.download_all_cases.assert_called_once_with(
                skip_audio=True
            )

    def test_main_with_exception(self, temp_dir: Path) -> None:
        """Test main function with an exception in download service."""
        # Mock command line arguments
        test_args = [
            "--cache-dir",
            str(temp_dir),
        ]

        # Mock DownloadService
        mock_download_service = mock.MagicMock(spec=DownloadService)
        mock_download_service.download_all_cases.side_effect = Exception("Test error")

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.DownloadService",
                return_value=mock_download_service,
            ),
            mock.patch("logging.Logger.error") as mock_error,
        ):
            # Run main
            main()

            # Verify error was logged
            mock_error.assert_called_once()
            assert "Test error" in mock_error.call_args[0][0]

    def test_main_with_keyboard_interrupt(self, temp_dir: Path) -> None:
        """Test main function with keyboard interrupt."""
        # Mock command line arguments
        test_args = [
            "--cache-dir",
            str(temp_dir),
        ]

        # Mock DownloadService
        mock_download_service = mock.MagicMock(spec=DownloadService)
        mock_download_service.download_all_cases.side_effect = KeyboardInterrupt()

        # Apply mocks
        with (
            mock.patch("sys.argv", ["download_cli.py", *test_args]),
            mock.patch(
                "oyez_scraping.cli.download_cli.DownloadService",
                return_value=mock_download_service,
            ),
            mock.patch("logging.Logger.warning") as mock_warning,
        ):
            # Run main
            main()

            # Verify warning was logged
            mock_warning.assert_called_once_with("Download interrupted by user")
