"""Command-line interface for the Oyez scraping project.

This module provides a command-line interface for downloading and managing
Oyez dataset content, including case metadata and audio files.
"""

import argparse
import datetime
import logging
import sys
from pathlib import Path

# Add the parent directory to the Python path if running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from oyez_scraping.infrastructure.storage.filesystem import FilesystemStorage
from oyez_scraping.services.download_service import DownloadService
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
        description="Download and manage Oyez dataset content"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".output",
        help="Directory where cache files will be stored (default: .output)",
    )

    parser.add_argument(
        "--terms",
        type=str,
        nargs="+",
        help="Specific terms to download (e.g., 2019 2020). If not specified, downloads all available cases.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually download, just show what would be downloaded",
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
        help="Download only the N most recent terms (e.g., --recent-terms 5)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads for parallel processing (default: 4)",
    )

    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip downloading audio files (metadata only)",
    )

    parser.add_argument(
        "--retry-limit",
        type=int,
        default=3,
        help="Maximum number of retry attempts for failed downloads (default: 3)",
    )

    return parser.parse_args()


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

    current_year = datetime.datetime.now().year

    # Supreme Court terms typically start in October and are numbered by the year they start
    # So the 2019 term starts in October 2019 and runs to June/July 2020
    terms = []
    for i in range(num_terms):
        term_year = current_year - i - 1
        terms.append(str(term_year))

    return terms


def handle_dry_run(
    scraper: RawDataScraperService, terms: list[str] | None = None
) -> None:
    """Process a dry run, showing what would be downloaded without actually downloading.

    Args:
        scraper: The RawDataScraperService instance
        terms: Optional list of term years to download
    """
    logger = logging.getLogger(__name__)

    logger.info("Dry run mode - would download the following:")
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
        try:
            case_list = scraper.scrape_all_cases()
            logger.info(f"  - Total: {len(case_list)} cases")
        except Exception as e:
            logger.error(f"Error fetching all cases: {e}")


def main() -> None:
    """Run the Oyez dataset download tool."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Create base components
    cache_dir = Path(args.cache_dir)
    filesystem_storage = FilesystemStorage()
    scraper = RawDataScraperService(cache_dir=cache_dir)

    # Process recent terms if specified
    terms = args.terms
    if args.recent_terms > 0:
        if terms:
            logger.warning(
                "Both --terms and --recent-terms specified; using --recent-terms"
            )
        terms = generate_recent_terms(args.recent_terms)
        logger.info(
            f"Will download {args.recent_terms} recent terms: {', '.join(terms)}"
        )

    # Handle dry run mode
    if args.dry_run:
        handle_dry_run(scraper, terms)
        return

    # Create the download service
    download_service = DownloadService(
        scraper=scraper,
        filesystem_storage=filesystem_storage,
        cache_dir=cache_dir,
        max_workers=args.workers,
        max_retry_attempts=args.retry_limit,
        status_interval=args.status_interval,
    )

    # Show info about what we're about to do
    logger.info("Starting Oyez dataset download")
    logger.info(f"Cache directory: {cache_dir.resolve()}")
    logger.info(f"Workers: {args.workers}")

    if args.skip_audio:
        logger.info("Skipping audio downloads (metadata only)")

    try:
        # Download the data
        if terms:
            download_service.download_multiple_terms(terms, skip_audio=args.skip_audio)
        else:
            logger.info("Downloading all available cases (this may take a LONG time)")
            download_service.download_all_cases(skip_audio=args.skip_audio)

        logger.info("Download completed successfully")

    except KeyboardInterrupt:
        logger.warning("Download interrupted by user")
    except Exception as e:
        logger.error(f"Error during download: {e}", exc_info=True)


if __name__ == "__main__":
    main()
