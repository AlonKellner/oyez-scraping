#!/usr/bin/env python
"""Script to scrape the entire Oyez dataset.

This script uses the RawDataScraperService to fetch and cache all available
data from the Oyez API, including case metadata, audio files, and transcripts.
"""

import argparse
import concurrent.futures
import logging
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oyez_scraping.services.raw_data_scraper import RawDataScraperService


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration.

    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Scrape the entire Oyez dataset or specific terms"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".app_cache",
        help="Directory where cache files will be stored (default: .app_cache)",
    )

    parser.add_argument(
        "--terms",
        type=str,
        nargs="+",
        help="Specific terms to scrape (e.g., 2019 2020). If not specified, scrapes all available cases.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually scrape, just show what would be scraped",
    )

    parser.add_argument(
        "--status-interval",
        type=int,
        default=30,
        help="Interval in seconds between status updates (default: 30)",
    )

    parser.add_argument(
        "--recent-terms",
        type=int,
        default=0,
        help="Scrape only the N most recent terms (e.g., --recent-terms 5)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,  # Set to 4 workers as requested for better performance
        help="Number of worker threads for parallel processing (default: 4)",
    )

    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip downloading audio files (metadata only)",
    )

    parser.add_argument(
        "--audio-format",
        type=str,
        choices=["all", "mp3", "m3u8"],
        default="all",
        help="Audio format to download (default: all)",
    )

    parser.add_argument(
        "--retry-limit",
        type=int,
        default=10,  # Increased from 5 to handle rate limiting better
        help="Maximum number of retries for failed requests (default: 10)",
    )

    parser.add_argument(
        "--retry-delay",
        type=int,
        default=30,
        help="Delay in seconds between retries (default: 30)",
    )

    return parser.parse_args()


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable time string.

    Args:
        seconds: Time in seconds

    Returns
    -------
        Human-readable time string
    """
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if td.days > 0:
        return f"{td.days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif minutes > 0:
        return f"{minutes:02d}m {seconds:02d}s"
    else:
        return f"{seconds:02d}s"


def generate_recent_terms(num_terms: int) -> list[str]:
    """Generate a list of the most recent Supreme Court terms.

    Args:
        num_terms: Number of recent terms to generate

    Returns
    -------
        List of term years as strings
    """
    if num_terms <= 0:
        return []

    import datetime

    current_year = datetime.datetime.now().year

    # Supreme Court terms typically start in October and are numbered by the year they start
    # So the 2019 term starts in October 2019 and runs to June/July 2020
    terms = []
    for i in range(num_terms):
        term_year = current_year - i - 1
        terms.append(str(term_year))

    return terms


def progress_monitor(
    scraper: RawDataScraperService,
    interval: int,
    stop_event: threading.Event,
    stats: dict[str, Any],
) -> None:
    """Monitor progress and print status updates at regular intervals.

    Args:
        scraper: The RawDataScraperService instance to monitor
        interval: Time in seconds between status updates
        stop_event: Threading event to signal when to stop monitoring
        stats: Shared statistics dictionary to track progress
    """
    logger = logging.getLogger(__name__)
    start_time = time.time()
    last_stats = scraper.cache.get_cache_stats()
    last_update_time = start_time

    while not stop_event.is_set():
        time.sleep(0.5)  # Check frequently but update based on interval

        current_time = time.time()
        if current_time - last_update_time >= interval:
            # Get current statistics
            current_stats = scraper.cache.get_cache_stats()
            elapsed = current_time - start_time

            # Calculate rates
            time_diff = current_time - last_update_time
            case_diff = current_stats["case_count"] - last_stats["case_count"]
            audio_diff = current_stats["audio_count"] - last_stats["audio_count"]

            case_rate = (
                case_diff / time_diff * 60 if time_diff > 0 else 0
            )  # cases per minute
            audio_rate = (
                audio_diff / time_diff * 60 if time_diff > 0 else 0
            )  # audio files per minute

            # Update shared stats dict with current values
            with stats["lock"]:
                stats["current_case_rate"] = case_rate
                stats["current_audio_rate"] = audio_rate
                stats["last_case_count"] = current_stats["case_count"]
                stats["last_audio_count"] = current_stats["audio_count"]

            # Print status update
            logger.info("=" * 40)
            logger.info(f"Progress after {format_time(elapsed)}:")
            logger.info(
                f"Cases: {current_stats['case_count']} (+{case_diff}, {case_rate:.1f}/min)"
            )
            logger.info(
                f"Audio files: {current_stats['audio_count']} (+{audio_diff}, {audio_rate:.1f}/min)"
            )

            # Estimate cache size
            try:
                cache_dir = scraper.cache.cache_dir
                cache_size_mb = sum(
                    f.stat().st_size for f in cache_dir.glob("**/*") if f.is_file()
                ) / (1024 * 1024)
                logger.info(f"Cache size: {cache_size_mb:.2f} MB")

                # Update shared stats dict with cache size
                with stats["lock"]:
                    stats["cache_size_mb"] = cache_size_mb

            except Exception as e:
                # Log the exception instead of silently ignoring it
                logger.debug(f"Unable to calculate cache size: {e}")

            logger.info("=" * 40)

            # Update for next iteration
            last_stats = current_stats
            last_update_time = current_time


def process_case(
    case: dict[str, Any],
    scraper: RawDataScraperService,
    skip_audio: bool = False,
    processed_cases: set[str] | None = None,
) -> tuple[bool, int]:
    """Process a single case from the case list.

    Args:
        case: Case data dictionary from a case list
        scraper: RawDataScraperService instance to use for scraping
        skip_audio: If True, don't download audio files
        processed_cases: Set of already processed case IDs (to avoid duplicates)

    Returns
    -------
        Tuple of (success, audio_count) where success is True if the case was scraped
        successfully and audio_count is the number of audio files downloaded
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract term and docket
        term = case.get("term")
        docket = case.get("docket_number")

        if not term or not docket:
            logger.warning(f"Missing term or docket in case: {case}")
            return False, 0

        case_id = f"{term}/{docket}"

        # Skip if already processed (for parallel processing)
        if processed_cases is not None and case_id in processed_cases:
            logger.debug(f"Skipping already processed case {case_id}")
            return True, 0

        # Add to processed set if tracking
        if processed_cases is not None:
            processed_cases.add(case_id)

        # Scrape the full case data
        case_data = scraper.scrape_case(term, docket)

        # Skip audio if requested
        if skip_audio:
            return True, 0

        # Scrape audio content
        audio_content = scraper.scrape_case_audio_content(case_data)

        # Count audio files
        audio_count = 0
        for content_list in audio_content.values():
            audio_count += len(content_list)

        logger.info(f"Scraped case {term}/{docket} with {audio_count} audio files")
        return True, audio_count

    except Exception as e:
        logger.error(f"Error scraping case: {e}")
        return False, 0


def parallel_scrape_term(
    term: str,
    scraper: RawDataScraperService,
    max_workers: int,
    stats: dict[str, Any],
    skip_audio: bool = False,
) -> None:
    """Scrape all cases for a term in parallel.

    Args:
        term: Term to scrape
        scraper: RawDataScraperService instance
        max_workers: Maximum number of worker threads
        stats: Shared statistics dictionary
        skip_audio: If True, skip downloading audio files
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Scraping term {term} with {max_workers} workers")

    # Get case list for the term
    case_list = scraper.scrape_term(term)

    # Keep track of processed cases (to avoid duplicates)
    processed_cases = set()

    # Use thread pool for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all cases to the executor
        future_to_case = {
            executor.submit(
                process_case, case, scraper, skip_audio, processed_cases
            ): case
            for case in case_list
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_case):
            future_to_case[future]
            try:
                success, audio_count = future.result()

                # Update stats
                with stats["lock"]:
                    if success:
                        stats["cases_scraped"] += 1
                    else:
                        stats["errors"] += 1
                    stats["audio_files_downloaded"] += audio_count

            except Exception as e:
                logger.error(f"Exception processing case: {e}")
                with stats["lock"]:
                    stats["errors"] += 1


def scrape_specific_terms(
    terms: list[str],
    scraper: RawDataScraperService,
    workers: int,
    stats: dict[str, Any],
    skip_audio: bool = False,
) -> None:
    """Process a list of specific court terms.

    Args:
        terms: List of term years to process
        scraper: The RawDataScraperService instance
        workers: Number of worker threads
        stats: Statistics dictionary for tracking progress
        skip_audio: If True, skip audio file downloads
    """
    logger = logging.getLogger(__name__)

    # Process terms in sequence (could be parallelized further if needed)
    for term in terms:
        try:
            parallel_scrape_term(term, scraper, workers, stats, skip_audio)
        except Exception as e:
            logger.error(f"Failed to scrape term {term}: {e}")
            with stats["lock"]:
                stats["errors"] += 1


def scrape_all_available_cases(
    scraper: RawDataScraperService,
    workers: int,
    stats: dict[str, Any],
    skip_audio: bool = False,
) -> None:
    """Process all available cases in the Oyez database.

    Args:
        scraper: The RawDataScraperService instance
        workers: Number of worker threads
        stats: Statistics dictionary for tracking progress
        skip_audio: If True, skip audio file downloads
    """
    logger = logging.getLogger(__name__)

    # Get case list for all cases
    case_list = scraper.scrape_all_cases()
    logger.info(f"Found {len(case_list)} cases to scrape")

    # Keep track of processed cases (to avoid duplicates)
    processed_cases = set()

    # Use thread pool for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all cases to the executor
        future_to_case = {
            executor.submit(
                process_case, case, scraper, skip_audio, processed_cases
            ): case
            for case in case_list
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_case):
            future_to_case[future]
            try:
                success, audio_count = future.result()

                # Update stats
                with stats["lock"]:
                    if success:
                        stats["cases_scraped"] += 1
                    else:
                        stats["errors"] += 1
                    stats["audio_files_downloaded"] += audio_count

            except Exception as e:
                logger.error(f"Exception processing case: {e}")
                with stats["lock"]:
                    stats["errors"] += 1


def print_final_statistics(
    scraper: RawDataScraperService,
    stats: dict[str, Any],
    start_time: float,
    cache_dir: Path,
) -> None:
    """Print final statistics after scraping is complete.

    Args:
        scraper: The RawDataScraperService instance
        stats: Statistics dictionary with scraping results
        start_time: Timestamp when scraping started
        cache_dir: Directory where cache files are stored
    """
    logger = logging.getLogger(__name__)

    elapsed_time = time.time() - start_time
    logger.info("=" * 50)
    logger.info("Scraping completed successfully!")
    logger.info(f"Total cases scraped: {stats['cases_scraped']}")
    logger.info(f"Total audio files downloaded: {stats['audio_files_downloaded']}")
    logger.info(f"Total errors encountered: {stats['errors']}")
    logger.info(f"Total time: {format_time(elapsed_time)}")

    # Get cache size
    try:
        cache_size_mb = sum(
            f.stat().st_size for f in cache_dir.glob("**/*") if f.is_file()
        ) / (1024 * 1024)
        logger.info(f"Total cache size: {cache_size_mb:.2f} MB")
    except Exception as e:
        logger.debug(f"Unable to calculate total cache size: {e}")

    # Get final cache stats
    cache_stats = scraper.cache.get_cache_stats()
    logger.info("Final cache statistics:")
    logger.info(f"  - Cases: {cache_stats['case_count']}")
    logger.info(f"  - Audio files: {cache_stats['audio_count']}")
    logger.info(f"  - Case lists: {cache_stats['case_list_count']}")


def handle_dry_run(scraper: RawDataScraperService, terms: list[str] | None) -> None:
    """Process a dry run, showing what would be scraped without actually scraping.

    Args:
        scraper: The RawDataScraperService instance
        terms: Optional list of term years to scrape
    """
    logger = logging.getLogger(__name__)

    logger.info("Dry run mode - would scrape the following:")
    if terms:
        logger.info(f"Terms: {', '.join(terms)}")
        for term in terms:
            try:
                case_list = scraper.scrape_term(term)
                logger.info(f"  - Term {term}: {len(case_list)} cases")
            except Exception as e:
                logger.error(f"Error fetching case list for term {term}: {e}")
    else:
        logger.info("All available cases")


def init_stats() -> dict[str, Any]:
    """Initialize the statistics tracking dictionary.

    Returns
    -------
        New statistics dictionary with required fields
    """
    return {
        "cases_scraped": 0,
        "audio_files_downloaded": 0,
        "errors": 0,
        "lock": threading.Lock(),
        "current_case_rate": 0,
        "current_audio_rate": 0,
        "last_case_count": 0,
        "last_audio_count": 0,
        "cache_size_mb": 0,
    }


def setup_monitoring(
    scraper: RawDataScraperService,
    interval: int,
    stats: dict[str, Any],
) -> tuple[threading.Event, threading.Thread]:
    """Set up and start the progress monitoring thread.

    Args:
        scraper: The RawDataScraperService instance to monitor
        interval: Time in seconds between status updates
        stats: Statistics dictionary for tracking progress

    Returns
    -------
        Tuple containing the stop event and monitor thread
    """
    # Start progress monitoring in a separate thread
    stop_monitor = threading.Event()
    monitor_thread = threading.Thread(
        target=progress_monitor,
        args=(scraper, interval, stop_monitor, stats),
        daemon=True,
    )
    monitor_thread.start()
    return stop_monitor, monitor_thread


def cleanup_monitoring(
    stop_monitor: threading.Event, monitor_thread: threading.Thread
) -> None:
    """Clean up monitoring thread resources.

    Args:
        stop_monitor: Event to signal the monitoring thread to stop
        monitor_thread: The monitoring thread to join
    """
    stop_monitor.set()
    monitor_thread.join(timeout=1.0)


def print_interrupted_statistics(
    scraper: RawDataScraperService, start_time: float
) -> None:
    """Print statistics after scraping is interrupted.

    Args:
        scraper: The RawDataScraperService instance
        start_time: Timestamp when scraping started
    """
    logger = logging.getLogger(__name__)

    elapsed_time = time.time() - start_time
    logger.warning("Scraping interrupted by user after %s", format_time(elapsed_time))
    # Get current cache stats
    cache_stats = scraper.cache.get_cache_stats()
    logger.info("Current cache statistics:")
    logger.info(f"  - Cases: {cache_stats['case_count']}")
    logger.info(f"  - Audio files: {cache_stats['audio_count']}")
    logger.info(f"  - Case lists: {cache_stats['case_list_count']}")


def main() -> None:
    """Run the Oyez scraper to download all available data."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Initialize the scraper service
    cache_dir = Path(args.cache_dir)
    scraper = RawDataScraperService(cache_dir=cache_dir)

    # Process recent terms if specified
    terms = args.terms
    if args.recent_terms > 0:
        if terms:
            logger.warning(
                "Both --terms and --recent-terms specified; using --recent-terms"
            )
        terms = generate_recent_terms(args.recent_terms)
        logger.info(f"Will scrape {args.recent_terms} recent terms: {', '.join(terms)}")

    # Handle dry run mode
    if args.dry_run:
        handle_dry_run(scraper, terms)
        return

    # Show info about what we're about to do
    logger.info("Starting Oyez dataset scraping")
    logger.info(f"Cache directory: {cache_dir.resolve()}")
    logger.info(f"Workers: {args.workers}")

    if args.skip_audio:
        logger.info("Skipping audio downloads (metadata only)")

    if terms:
        logger.info(f"Scraping specific terms: {', '.join(terms)}")
    else:
        logger.info("Scraping all available cases (this may take a LONG time)")

    # Initialize shared statistics dictionary
    stats = init_stats()

    # Set up monitoring
    stop_monitor, monitor_thread = setup_monitoring(
        scraper, args.status_interval, stats
    )

    start_time = time.time()

    try:
        if terms:
            scrape_specific_terms(terms, scraper, args.workers, stats, args.skip_audio)
        else:
            scrape_all_available_cases(scraper, args.workers, stats, args.skip_audio)

        # Stop the monitoring thread
        cleanup_monitoring(stop_monitor, monitor_thread)

        # Print final statistics
        print_final_statistics(scraper, stats, start_time, cache_dir)

    except KeyboardInterrupt:
        cleanup_monitoring(stop_monitor, monitor_thread)
        print_interrupted_statistics(scraper, start_time)
    except Exception as e:
        cleanup_monitoring(stop_monitor, monitor_thread)
        logger.error(f"Error during scraping: {e}", exc_info=True)


if __name__ == "__main__":
    main()
