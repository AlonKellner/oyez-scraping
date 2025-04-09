#!/usr/bin/env python
"""Demonstration of the raw data scraper feature.

This script shows how to use the RawDataScraperService to fetch and cache
raw data from the Oyez API.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oyez_scraping.services.raw_data_scraper import RawDataScraperService


def setup_logging() -> None:
    """Set up basic logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
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
        description="Fetch and cache raw data from the Oyez API"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".output",
        help="Directory where cache files will be stored (default: .output)",
    )

    parser.add_argument(
        "--term",
        type=str,
        help="Specific term to scrape (e.g., '2019')",
    )

    parser.add_argument(
        "--docket",
        type=str,
        help="Specific docket number to scrape (requires --term)",
    )

    parser.add_argument(
        "--list-terms",
        type=int,
        default=5,
        help="List the latest N Supreme Court terms (default: 5)",
    )

    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Show cache statistics",
    )

    parser.add_argument(
        "--list-cached",
        action="store_true",
        help="List all cached cases",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh of cached data",
    )

    return parser.parse_args()


def show_cache_statistics(scraper: RawDataScraperService) -> None:
    """Display cache statistics.

    Args:
        scraper: The RawDataScraperService instance
    """
    stats = scraper.cache.get_cache_stats()
    print("\nCache Statistics:")
    print(f"  Case count: {stats['case_count']}")
    print(f"  Audio count: {stats['audio_count']}")
    print(f"  Case list count: {stats['case_list_count']}")
    print()


def list_cached_cases(scraper: RawDataScraperService) -> None:
    """List all cases in the cache.

    Args:
        scraper: The RawDataScraperService instance
    """
    case_ids = scraper.cache.get_all_cached_case_ids()
    if case_ids:
        print("\nCached Cases:")
        for case_id in sorted(case_ids):
            print(f"  {case_id}")
        print()
    else:
        print("\nNo cases in cache\n")


def scrape_specific_case(
    scraper: RawDataScraperService, term: str, docket: str, force_refresh: bool
) -> None:
    """Scrape a specific case and its audio content.

    Args:
        scraper: The RawDataScraperService instance
        term: The term of the case
        docket: The docket number of the case
        force_refresh: Whether to force refresh cached data
    """
    print(f"\nScraping case {term}/{docket}...")
    case_data = scraper.scrape_case(term, docket, force_refresh=force_refresh)
    print(f"Scraped case: {case_data.get('name', 'Unknown')}")

    # Scrape audio content
    print("Scraping audio content...")
    audio_content = scraper.scrape_case_audio_content(
        case_data, force_refresh=force_refresh
    )

    # Count audio files
    audio_count = sum(len(content_list) for content_list in audio_content.values())
    print(f"Downloaded {audio_count} audio files")

    # Show the audio content types
    for content_type, content_list in audio_content.items():
        if content_list:
            print(f"  {content_type}: {len(content_list)} files")


def scrape_term(scraper: RawDataScraperService, term: str, force_refresh: bool) -> None:
    """Scrape all cases for a specific term.

    Args:
        scraper: The RawDataScraperService instance
        term: The term to scrape
        force_refresh: Whether to force refresh cached data
    """
    print(f"\nScraping cases from term {term}...")
    cases = scraper.scrape_term(term, force_refresh=force_refresh)
    print(f"Found {len(cases)} cases for term {term}")

    # Show case names
    for case in cases[:5]:  # Show only the first 5 cases
        print(f"  {case.get('name', 'Unknown')}")

    if len(cases) > 5:
        print(f"  ...and {len(cases) - 5} more")


def list_recent_terms(num_terms: int) -> None:
    """List recent Supreme Court terms.

    Args:
        num_terms: Number of recent terms to list
    """
    # Get current year for calculating terms
    import datetime

    current_year = datetime.datetime.now().year

    # Supreme Court terms typically start in October and are numbered by the year they start
    # So the 2019 term starts in October 2019 and runs to June/July 2020
    print(f"\nLatest {num_terms} Supreme Court terms:")
    for i in range(num_terms):
        term_year = current_year - i - 1
        print(f"  {term_year}")


def show_final_cache_info(scraper: RawDataScraperService, cache_dir: str) -> None:
    """Show updated cache statistics and location.

    Args:
        scraper: The RawDataScraperService instance
        cache_dir: Path to the cache directory
    """
    stats = scraper.cache.get_cache_stats()
    print("\nUpdated Cache Statistics:")
    print(f"  Case count: {stats['case_count']}")
    print(f"  Audio count: {stats['audio_count']}")
    print(f"  Case list count: {stats['case_list_count']}")
    print()

    # Show cache location
    cache_dir_path = Path(cache_dir).resolve()
    print(f"Cache location: {cache_dir_path}")
    print(f"Cache size: {get_directory_size(cache_dir_path)} MB")


def get_directory_size(directory: Path) -> float:
    """Calculate the total size of a directory in megabytes.

    Args:
        directory: Path to the directory

    Returns
    -------
        Size in megabytes
    """
    total_size = 0

    for path in directory.glob("**/*"):
        if path.is_file():
            total_size += path.stat().st_size

    return total_size / (1024 * 1024)  # Convert bytes to MB


def main() -> None:
    """Run the demonstration."""
    # Set up logging
    setup_logging()

    # Parse command-line arguments
    args = parse_args()

    # Initialize the scraper service
    scraper = RawDataScraperService(cache_dir=args.cache_dir)

    # Show cache statistics if requested
    if args.show_stats:
        show_cache_statistics(scraper)

    # List cached cases if requested
    if args.list_cached:
        list_cached_cases(scraper)

    # Process based on arguments
    if args.term and args.docket:
        scrape_specific_case(scraper, args.term, args.docket, args.force)
    elif args.term:
        scrape_term(scraper, args.term, args.force)
    elif args.list_terms > 0:
        list_recent_terms(args.list_terms)

    # Show final cache statistics
    if args.term or args.docket:
        show_final_cache_info(scraper, args.cache_dir)


if __name__ == "__main__":
    main()
