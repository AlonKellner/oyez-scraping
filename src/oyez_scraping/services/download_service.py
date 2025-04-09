"""Download management service for the Oyez scraping project.

This module provides services for managing large download operations, including
parallel processing, progress tracking, and automatic retrying of failed downloads.
"""

import concurrent.futures
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

from ..infrastructure.monitoring.progress import ProgressMonitor, format_time
from ..infrastructure.storage.download_tracker import DownloadTracker
from ..infrastructure.storage.filesystem import FilesystemStorage
from ..services.raw_data_scraper import RawDataScraperService

# Type variable for self-referential type hints
T = TypeVar("T", bound="DownloadService")


class DownloadService:
    """Service for managing large download operations.

    This service provides high-level functionality for downloading and tracking
    large datasets, with support for parallel processing, progress monitoring,
    and automatic retrying of failed downloads.
    """

    def __init__(
        self,
        scraper: RawDataScraperService,
        filesystem_storage: FilesystemStorage,
        cache_dir: Path,
        max_workers: int = 4,
        max_retry_attempts: int = 3,
        status_interval: int = 30,
    ) -> None:
        """Initialize the download service.

        Args:
            scraper: RawDataScraperService instance for API interactions
            filesystem_storage: FilesystemStorage instance for file operations
            cache_dir: Directory where downloaded data and state will be stored
            max_workers: Maximum number of worker threads for parallel processing
            max_retry_attempts: Maximum number of retry attempts for failed downloads
            status_interval: Interval in seconds between status updates

        Raises
        ------
            DirectoryCreationError: If the cache directory cannot be created
        """
        self.scraper = scraper
        self.storage = filesystem_storage
        self.cache_dir = filesystem_storage.ensure_directory(cache_dir)
        self.max_workers = max_workers
        self.max_retry_attempts = max_retry_attempts
        self.status_interval = status_interval
        self.logger = logging.getLogger(__name__)

        # Initialize the download tracker
        self.download_tracker = DownloadTracker(
            storage=filesystem_storage,
            cache_dir=cache_dir,
            max_retry_attempts=max_retry_attempts,
        )

        # Initialize shared statistics
        self.stats: dict[str, Any] = {
            "items_processed": 0,
            "audio_files_downloaded": 0,
            "errors": 0,
            "lock": threading.Lock(),
        }

        # Progress monitor will be initialized when needed
        self.progress_monitor: ProgressMonitor | None = None

    def _get_current_stats(self) -> dict[str, Any]:
        """Get current statistics for progress monitoring.

        Returns
        -------
            Dictionary with current statistics
        """
        stats: dict[str, Any] = {}

        # Get cache stats from the scraper
        cache_stats = self.scraper.cache.get_cache_stats()

        # Add stats from cache
        stats["item_count"] = cache_stats.get("case_count", 0)
        stats["audio_count"] = cache_stats.get("audio_count", 0)
        stats["case_list_count"] = cache_stats.get("case_list_count", 0)

        # Calculate cache size
        try:
            cache_size_mb = sum(
                f.stat().st_size for f in self.cache_dir.glob("**/*") if f.is_file()
            ) / (1024 * 1024)
            stats["cache_size_mb"] = cache_size_mb
        except Exception as e:
            self.logger.debug(f"Unable to calculate cache size: {e}")
            stats["cache_size_mb"] = 0.0

        # Add stats from our internal tracking
        with self.stats["lock"]:
            stats["items_processed"] = self.stats["items_processed"]
            stats["audio_files_downloaded"] = self.stats["audio_files_downloaded"]
            stats["errors"] = self.stats["errors"]

        # Add download tracker stats
        tracker_stats = self.download_tracker.get_stats()
        stats["failed_items"] = tracker_stats["total_failed"]
        stats["retriable_items"] = tracker_stats["retriable"]
        stats["permanent_failures"] = tracker_stats["permanent_failures"]

        return stats

    def _start_progress_monitoring(self) -> dict[str, Any]:
        """Start progress monitoring in a background thread.

        Returns
        -------
            Shared statistics dictionary
        """
        if self.progress_monitor is None:
            self.progress_monitor = ProgressMonitor(
                stats_callback=self._get_current_stats,
                update_interval=self.status_interval,
                logger=self.logger,
            )
            shared_stats = self.progress_monitor.start()
            return shared_stats
        else:
            return self.progress_monitor.shared_stats

    def _stop_progress_monitoring(self) -> None:
        """Stop progress monitoring."""
        if self.progress_monitor is not None:
            self.progress_monitor.stop()
            self.progress_monitor = None

    def _process_case(
        self,
        case: dict[str, Any],
        skip_audio: bool = False,
        processed_cases: set[str] | None = None,
    ) -> tuple[bool, int]:
        """Process a single case with download tracking.

        Args:
            case: Case data dictionary
            skip_audio: If True, skip audio file downloads
            processed_cases: Optional set of already processed case IDs to avoid duplicates

        Returns
        -------
            Tuple of (success, audio_count) where success is True if the case was
            scraped successfully and audio_count is the number of audio files downloaded
        """
        # Extract term and docket
        term = case.get("term")
        docket = case.get("docket_number")

        if not term or not docket:
            self.logger.warning(f"Missing term or docket in case: {case}")
            return False, 0

        case_id = f"{term}/{docket}"

        # Skip if already processed (for parallel processing)
        if processed_cases is not None and case_id in processed_cases:
            self.logger.debug(f"Skipping already processed case {case_id}")
            return True, 0

        # Add to processed set if tracking
        if processed_cases is not None:
            processed_cases.add(case_id)

        try:
            # Scrape the full case data
            case_data = self.scraper.scrape_case(term, docket)

            # Skip audio if requested
            if skip_audio:
                self.download_tracker.mark_successful(case_id)
                return True, 0

            # Scrape audio content
            audio_content = self.scraper.scrape_case_audio_content(case_data)

            # Count audio files
            audio_count = 0
            for content_list in audio_content.values():
                audio_count += len(content_list)

            self.logger.info(
                f"Scraped case {term}/{docket} with {audio_count} audio files"
            )

            # Mark as successful in the tracker
            self.download_tracker.mark_successful(case_id)
            return True, audio_count

        except Exception as e:
            self.logger.error(f"Error scraping case {case_id}: {e}")
            # Mark the case as failed in the tracker for later retry
            self.download_tracker.mark_failed(case_id, case)
            return False, 0

    def download_term(self, term: str, *, skip_audio: bool = False) -> dict[str, Any]:
        """Download all cases for a specific term.

        Args:
            term: The term to download cases for (e.g., "2022").
            skip_audio: If True, skips downloading audio files.

        Returns
        -------
            A dictionary with stats about the download operation.

        Raises
        ------
            Exception: If an error occurs during the term download.
        """
        self._start_progress_monitoring()
        try:
            self.logger.info(f"Downloading term {term}")

            # Get all cases for the term
            cases = self.scraper.scrape_term(term)

            # Process each case in the term
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                futures = []
                for case in cases:
                    futures.append(
                        executor.submit(self._process_case, case, skip_audio=skip_audio)
                    )

                # Wait for all futures to complete and update stats
                results = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)

                        # Update stats
                        success, audio_count = result
                        with self.stats["lock"]:
                            if success:
                                self.stats["items_processed"] += 1
                            else:
                                self.stats["errors"] += 1
                            self.stats["audio_files_downloaded"] += audio_count
                    except Exception as e:
                        self.logger.error(f"Exception in worker thread: {e}")
                        with self.stats["lock"]:
                            self.stats["errors"] += 1

            # Count successes for reporting
            successes = sum(1 for success, _ in results if success)
            documents = sum(docs for _, docs in results)

            self.logger.info(
                f"Term {term}: Downloaded {successes}/{len(cases)} cases with {documents} documents"
            )

            return {
                "term": term,
                "total_cases": len(cases),
                "successful_cases": successes,
                "documents_downloaded": documents,
            }
        except Exception as e:
            self.logger.error(f"Failed to download term {term}: {e!s}")
            self.stats["errors"] += 1
            raise
        finally:
            self._stop_progress_monitoring()

    def download_multiple_terms(
        self, terms: list[str], *, skip_audio: bool = False
    ) -> dict[str, Any]:
        """Download cases for multiple terms.

        Args:
            terms: List of term years to download
            skip_audio: If True, skip audio file downloads

        Returns
        -------
            Dictionary with download statistics
        """
        self.logger.info(f"Downloading {len(terms)} terms: {', '.join(terms)}")

        # Start progress monitoring
        self._start_progress_monitoring()
        start_time = time.time()

        try:
            # Process each term sequentially
            for term in terms:
                try:
                    self.download_term(term, skip_audio=skip_audio)
                except Exception as e:
                    self.logger.error(f"Failed to download term {term}: {e}")
                    with self.stats["lock"]:
                        self.stats["errors"] += 1

            # After all terms have been processed, retry any failed cases
            self._retry_failed_cases(skip_audio=skip_audio)

            # Get final statistics
            final_stats = self._get_current_stats()

            # Add elapsed time
            elapsed_time = time.time() - start_time
            final_stats["elapsed_time"] = elapsed_time
            final_stats["elapsed_time_formatted"] = format_time(elapsed_time)

            self.logger.info(
                f"Multi-term download completed in {format_time(elapsed_time)}: "
                f"{final_stats['items_processed']} cases processed, "
                f"{final_stats['audio_files_downloaded']} audio files downloaded, "
                f"{final_stats['errors']} errors"
            )

            return final_stats

        finally:
            # Ensure progress monitoring is stopped
            self._stop_progress_monitoring()

    def download_all_cases(self, *, skip_audio: bool = False) -> dict[str, Any]:
        """Download all available cases.

        Args:
            skip_audio: If True, skip audio file downloads

        Returns
        -------
            Dictionary with download statistics
        """
        self.logger.info("Downloading all available cases")

        # Start progress monitoring
        self._start_progress_monitoring()
        start_time = time.time()

        try:
            # Get case list for all cases
            case_list = self.scraper.scrape_all_cases()
            self.logger.info(f"Found {len(case_list)} cases to download")

            # Keep track of processed cases (to avoid duplicates)
            processed_cases: set[str] = set()

            # Use thread pool for parallel processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all cases to the executor
                futures = {
                    executor.submit(
                        self._process_case,
                        case,
                        skip_audio=skip_audio,
                        processed_cases=processed_cases,
                    ): case
                    for case in case_list
                }

                # Process results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success, audio_count = future.result()

                        # Update stats
                        with self.stats["lock"]:
                            if success:
                                self.stats["items_processed"] += 1
                            else:
                                self.stats["errors"] += 1
                            self.stats["audio_files_downloaded"] += audio_count

                    except Exception as e:
                        self.logger.error(f"Exception in worker thread: {e}")
                        with self.stats["lock"]:
                            self.stats["errors"] += 1

            # After all cases have been processed, retry any failed cases
            self._retry_failed_cases(skip_audio=skip_audio)

            # Get final statistics
            final_stats = self._get_current_stats()

            # Add elapsed time
            elapsed_time = time.time() - start_time
            final_stats["elapsed_time"] = elapsed_time
            final_stats["elapsed_time_formatted"] = format_time(elapsed_time)

            self.logger.info(
                f"All cases download completed in {format_time(elapsed_time)}: "
                f"{final_stats['items_processed']} cases processed, "
                f"{final_stats['audio_files_downloaded']} audio files downloaded, "
                f"{final_stats['errors']} errors"
            )

            return final_stats

        finally:
            # Ensure progress monitoring is stopped
            self._stop_progress_monitoring()

    def _retry_failed_cases(
        self, *, skip_audio: bool = False, max_retries: int = 3
    ) -> None:
        """Retry failed cases with exponential backoff.

        Args:
            skip_audio: If True, skip audio file downloads
            max_retries: Maximum number of retry rounds to attempt
        """
        if not hasattr(self.download_tracker, "has_failed_items_for_retry"):
            self.logger.warning("Download tracker does not support failed item retry")
            return

        retry_round = 0
        retry_wait = 60  # Start with 60 second wait

        # Initial check if there are items to retry
        if not self.download_tracker.has_failed_items_for_retry():
            self.logger.info("No failed items to retry")
            return

        # Continue retrying until max_retries is reached
        while retry_round < max_retries:
            retry_round += 1
            self.logger.info(f"Starting retry round {retry_round}/{max_retries}")

            # Get list of failed items to retry
            failed_items = self.download_tracker.get_failed_items_for_retry()
            if not failed_items:
                self.logger.info("No failed items returned for retry")
                break

            self.logger.info(f"Retrying {len(failed_items)} failed items")

            # Process each failed item
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for _item_id, case in failed_items:
                    futures.append(
                        executor.submit(self._process_case, case, skip_audio=skip_audio)
                    )

                # Wait for all futures to complete and update stats
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success, audio_count = future.result()

                        # Update stats
                        with self.stats["lock"]:
                            if success:
                                self.stats["items_processed"] += 1
                            else:
                                self.stats["errors"] += 1
                            self.stats["audio_files_downloaded"] += audio_count
                    except Exception as e:
                        self.logger.error(f"Exception in worker thread: {e}")
                        with self.stats["lock"]:
                            self.stats["errors"] += 1

            # Check if we should continue to the next round
            if (
                retry_round < max_retries
                and self.download_tracker.has_failed_items_for_retry()
            ):
                wait_time = retry_wait * retry_round
                self.logger.info(f"Waiting {wait_time} seconds before next retry round")
                time.sleep(wait_time)
            else:
                break
