"""Raw data scraping service for Oyez project.

This module provides a service for scraping and caching raw data from the Oyez API,
including case metadata, audio files, and transcripts.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from ..infrastructure.api.case_client import AudioContentType, OyezCaseClient
from ..infrastructure.exceptions.api_exceptions import (
    OyezApiError,
)
from ..infrastructure.storage.cache import RawDataCache

# Configure logger
logger = logging.getLogger(__name__)


class RawDataScraperService:
    """Service for scraping and caching raw data from the Oyez API.

    This service handles fetching raw data from the Oyez API and storing it in a cache,
    including case information, audio files, transcripts, and metadata.
    """

    def __init__(
        self,
        cache_dir: str | Path = ".output",
        api_client: OyezCaseClient | None = None,
    ) -> None:
        """Initialize the raw data scraper service.

        Args:
            cache_dir: Directory where cache files will be stored
            api_client: Optional API client (creates a new one if not provided)
        """
        self.cache = RawDataCache(cache_dir)
        self.api_client = api_client or OyezCaseClient()

        # Request session for downloading audio files
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def scrape_term(
        self, term: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """Scrape all cases for a specific term.

        Args:
            term: The term to scrape (e.g., "2019")
            force_refresh: If True, re-scrape even if already cached

        Returns
        -------
            List of case data dictionaries

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        list_name = f"term_{term}"

        # Check if we already have this list cached
        if not force_refresh and self.cache.case_list_exists(list_name):
            logger.debug(f"Using cached case list for term {term}")
            return self.cache.get_case_list(list_name)

        try:
            # Fetch case list from API
            logger.info(f"Fetching cases for term {term}")
            cases = self.api_client.get_cases_by_term(term)

            # Store in cache
            self.cache.store_case_list(list_name, cases)

            return cases
        except OyezApiError as e:
            logger.error(f"Failed to fetch cases for term {term}: {e}")
            raise

    def scrape_all_cases(
        self,
        per_page: int = 100,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Scrape all cases available in the Oyez API.

        Args:
            per_page: Number of cases to fetch per page
            force_refresh: If True, re-scrape even if already cached

        Returns
        -------
            List of case data dictionaries

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        list_name = "all_cases"

        # Check if we already have this list cached
        if not force_refresh and self.cache.case_list_exists(list_name):
            logger.debug("Using cached all cases list")
            return self.cache.get_case_list(list_name)

        try:
            # Fetch all cases from API
            logger.info("Fetching all cases")
            cases = self.api_client.get_all_cases(per_page=per_page)

            # Store in cache
            self.cache.store_case_list(list_name, cases)

            return cases
        except OyezApiError as e:
            logger.error(f"Failed to fetch all cases: {e}")
            raise

    def scrape_case(
        self, term: str, docket: str, force_refresh: bool = False
    ) -> dict[str, Any]:
        """Scrape a specific case by term and docket number.

        Args:
            term: The term of the case (e.g., "2019")
            docket: The docket number of the case (e.g., "17-1618")
            force_refresh: If True, re-scrape even if already cached

        Returns
        -------
            Case data dictionary

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        case_id = f"{term}/{docket}"

        # Check if we already have this case cached
        if not force_refresh and self.cache.case_exists(case_id):
            logger.debug(f"Using cached case data for {case_id}")
            return self.cache.get_case_data(case_id)

        try:
            # Fetch case from API
            logger.info(f"Fetching case {case_id}")
            case_data = self.api_client.get_case_by_id(term, docket)

            # Store in cache
            self.cache.store_case_data(case_id, case_data)

            return case_data
        except OyezApiError as e:
            logger.error(f"Failed to fetch case {case_id}: {e}")
            raise

    def scrape_case_audio_content(
        self,
        case_data: dict[str, Any],
        download_audio: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        """Extract and scrape audio content from a case.

        Args:
            case_data: The case data dictionary
            download_audio: If True, download the audio files
            force_refresh: If True, re-scrape even if already cached

        Returns
        -------
            Dictionary mapping audio content types to lists of content

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        try:
            # Extract audio content from case data
            audio_content = self.api_client.get_case_audio_content(case_data)

            # For each type of audio content, scrape the detailed data
            for content_type, content_list in audio_content.items():
                for i, content in enumerate(content_list):
                    # Get the content URL
                    content_url = content.get("href")
                    if not content_url:
                        logger.warning(f"No URL for {content_type} item {i}")
                        continue

                    # Generate a unique ID for this content
                    content_id = self._generate_content_id(content_url)

                    # Skip if already cached and not forcing refresh
                    if not force_refresh and self._content_data_exists(content_id):
                        logger.debug(f"Using cached content data for {content_id}")
                        detailed_content = self._get_cached_content_data(content_id)
                    else:
                        # Fetch detailed content data based on type
                        logger.debug(f"Fetching {content_type} data from {content_url}")
                        if content_type == AudioContentType.ORAL_ARGUMENT:
                            detailed_content = self.api_client.get_oral_argument(
                                content_url
                            )
                        elif content_type == AudioContentType.OPINION_ANNOUNCEMENT:
                            detailed_content = self.api_client.get_opinion_announcement(
                                content_url
                            )
                        elif content_type == AudioContentType.DISSENTING_OPINION:
                            detailed_content = self.api_client.get_dissenting_opinion(
                                content_url
                            )
                        else:
                            # Unknown content type, just get as generic audio content
                            detailed_content = self.api_client.get_audio_content(
                                content_url
                            )

                        # Cache the detailed content data
                        self._cache_content_data(content_id, detailed_content)

                    # Update the content item with detailed data
                    content["detailed_data"] = detailed_content

                    # Download the audio file if requested
                    if download_audio:
                        self._download_audio_file(
                            detailed_content,
                            content_id,
                            case_id=f"{case_data.get('term', '')}/{case_data.get('docket_number', '')}",
                            force_refresh=force_refresh,
                        )

            return audio_content
        except OyezApiError as e:
            logger.error(f"Failed to scrape audio content: {e}")
            raise

    def _download_audio_file(
        self,
        content_data: dict[str, Any],
        content_id: str,
        case_id: str | None = None,
        force_refresh: bool = False,
    ) -> str | None:
        """Download an audio file from content data.

        Args:
            content_data: The detailed content data
            content_id: Unique ID for this content
            case_id: Optional ID of the case
            force_refresh: If True, download even if already cached

        Returns
        -------
            Path to the downloaded file or None if download failed

        Raises
        ------
            OyezApiError: If there's an error extracting or downloading the audio
        """
        try:
            # Skip if already cached and not forcing refresh
            if not force_refresh and self.cache.audio_exists(content_id):
                logger.debug(f"Audio for {content_id} already cached")
                return None

            # Extract audio URL
            audio_url = self.api_client.extract_audio_url(content_data)
            if not audio_url:
                logger.warning(f"No audio URL found in content {content_id}")
                return None

            # Verify the audio URL is accessible
            if not self.api_client.verify_audio_url(audio_url):
                logger.warning(f"Audio URL {audio_url} is not accessible")
                return None

            # Determine the media type from the URL or content-type
            media_type = self._get_media_type(audio_url)

            # Download the audio file
            logger.info(f"Downloading audio from {audio_url}")
            try:
                response = self.session.get(audio_url, stream=True, timeout=30)
                response.raise_for_status()

                audio_data = response.content

                # Store the audio data in the cache
                self.cache.store_audio_data(
                    content_id, audio_data, case_id=case_id, media_type=media_type
                )

                return content_id
            except requests.RequestException as e:
                logger.error(f"Failed to download audio from {audio_url}: {e}")
                return None
        except OyezApiError as e:
            logger.error(f"Failed to extract audio URL: {e}")
            raise

    def _get_media_type(self, url: str) -> str:
        """Determine the media type from a URL.

        Args:
            url: The URL to analyze

        Returns
        -------
            The media type (file extension) or "unknown"
        """
        # Try to extract from URL path
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Check for file extension in the path
        match = re.search(r"\.([a-zA-Z0-9]+)(?:\?|$)", path)
        if match:
            return match.group(1).lower()

        # If no extension found, check if it's a streaming URL
        if ".m3u8" in url:
            return "m3u8"
        elif ".mpd" in url:
            return "mpd"

        # Default to mp3 as it's common for Oyez
        return "mp3"

    def _generate_content_id(self, url: str) -> str:
        """Generate a unique ID for content based on its URL.

        Args:
            url: The content URL

        Returns
        -------
            A unique ID string
        """
        # Extract the path portion of the URL
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Remove any leading/trailing slashes and replace internal slashes with underscores
        path = path.strip("/").replace("/", "_")

        return path

    def _content_data_exists(self, content_id: str) -> bool:
        """Check if content data exists in the cache.

        Args:
            content_id: The content ID to check

        Returns
        -------
            True if the content data is cached, False otherwise
        """
        list_name = f"content_{content_id}"
        return self.cache.case_list_exists(list_name)

    def _get_cached_content_data(self, content_id: str) -> dict[str, Any]:
        """Get cached content data.

        Args:
            content_id: The content ID to retrieve

        Returns
        -------
            The content data dictionary

        Raises
        ------
            CacheError: If the content data is not cached
        """
        list_name = f"content_{content_id}"
        return self.cache.get_case_list(list_name)[0]  # Get first (and only) item

    def _cache_content_data(
        self, content_id: str, content_data: dict[str, Any]
    ) -> None:
        """Cache content data.

        Args:
            content_id: The content ID
            content_data: The content data to cache

        Raises
        ------
            CacheError: If the content data cannot be cached
        """
        list_name = f"content_{content_id}"
        self.cache.store_case_list(
            list_name, [content_data]
        )  # Store as a list with one item

    def scrape_and_download_all(self, terms: list[str] | None = None) -> dict[str, Any]:
        """Scrape and download all available data from the Oyez API.

        This is a high-level method that fetches case lists, case details,
        and audio content for all specified terms or all available cases.

        Args:
            terms: Optional list of terms to scrape (e.g., ["2019", "2020"])
                  If None, scrapes all available cases.

        Returns
        -------
            Statistics about the scraping process

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        start_time = time.time()
        stats: dict[str, Any] = {
            "cases_scraped": 0,
            "audio_files_downloaded": 0,
            "errors": 0,
        }

        try:
            if terms:
                # Scrape specific terms
                for term in terms:
                    try:
                        # Get case list for the term
                        case_list = self.scrape_term(term)

                        # Scrape each case
                        for case in case_list:
                            self._scrape_case_from_list(case, stats)
                    except Exception as e:
                        logger.error(f"Error scraping term {term}: {e}")
                        stats["errors"] += 1
            else:
                # Scrape all cases
                try:
                    # Get all cases
                    case_list = self.scrape_all_cases()

                    # Scrape each case
                    for case in case_list:
                        self._scrape_case_from_list(case, stats)
                except Exception as e:
                    logger.error(f"Error scraping all cases: {e}")
                    stats["errors"] += 1
        finally:
            # Add timing information
            stats["duration_seconds"] = time.time() - start_time
            stats["cache_stats"] = self.cache.get_cache_stats()

        return stats

    def _scrape_case_from_list(
        self, case: dict[str, Any], stats: dict[str, Any]
    ) -> None:
        """Scrape a case from a case list entry.

        Args:
            case: Case data from a case list
            stats: Statistics dictionary to update

        Raises
        ------
            OyezApiError: If there's an error fetching data from the API
        """
        try:
            # Extract term and docket
            term = case.get("term")
            docket = case.get("docket_number")

            if not term or not docket:
                logger.warning(f"Missing term or docket in case: {case}")
                return

            # Scrape the full case data
            case_data = self.scrape_case(term, docket)
            stats["cases_scraped"] += 1

            # Scrape audio content
            audio_content = self.scrape_case_audio_content(case_data)

            # Count audio files
            audio_count = 0
            for content_list in audio_content.values():
                audio_count += len(content_list)

            stats["audio_files_downloaded"] += audio_count

            logger.info(f"Scraped case {term}/{docket} with {audio_count} audio files")
        except Exception as e:
            logger.error(f"Error scraping case: {e}")
            stats["errors"] += 1
