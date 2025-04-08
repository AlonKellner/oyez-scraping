"""Optimized service for downloading audio files from Oyez.

This module provides a high-performance service for downloading audio files
from the Oyez API, with support for concurrent downloading, streaming, and
effective caching.
"""

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..exceptions.audio_exceptions import AudioProcessingError
from ..storage.cache import RawDataCache

# Configure logger
logger = logging.getLogger(__name__)

# Chunk size for streaming downloads (bytes)
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB


class AudioDownloadError(AudioProcessingError):
    """Exception raised when there is an error downloading audio files."""

    pass


class AudioDownloader:
    """High-performance service for downloading audio files from Oyez.

    This service optimizes audio downloads through parallel processing,
    streaming, and effective caching strategies.
    """

    def __init__(
        self,
        cache: RawDataCache,
        max_workers: int = 4,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """Initialize the audio downloader.

        Args:
            cache: The cache service to use for storing audio files
            max_workers: Maximum number of concurrent download workers
            chunk_size: Size of chunks when streaming audio files (bytes)
            max_retries: Maximum number of retry attempts for failed downloads
            timeout: Request timeout in seconds
        """
        self.cache = cache
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.timeout = timeout

        # Create session with retry configuration
        self.session = self._create_session()

        # Lock for thread-safe access to shared resources
        self.lock = threading.Lock()

        # Track downloads in progress to avoid duplicates
        self.downloads_in_progress: dict[str, threading.Event] = {}

    def _create_session(self) -> requests.Session:
        """Create and configure a requests session with retry logic.

        Returns
        -------
            Configured requests session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )

        # Mount the adapter to the session
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent to avoid being blocked
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        return session

    def download_audio_files(
        self,
        audio_urls: list[tuple[str, dict[str, Any]]],
        case_id: str | None = None,
    ) -> list[str]:
        """Download multiple audio files concurrently.

        Args:
            audio_urls: List of tuples containing (url, content_data)
            case_id: Optional ID of the case for cache organization

        Returns
        -------
            List of content IDs for the downloaded files

        Raises
        ------
            AudioDownloadError: If there are errors downloading files
        """
        if not audio_urls:
            return []

        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all downloads to the executor, ignoring content_data
            future_to_url = {
                executor.submit(self.download_audio_file, url, case_id): url
                for url, _ in audio_urls
            }

            # Collect results as they complete
            content_ids = []
            errors = []

            for future, url in future_to_url.items():
                try:
                    content_id = future.result()
                    if content_id:
                        content_ids.append(content_id)
                except Exception as e:
                    errors.append(f"Error downloading {url}: {e}")

            # Log errors and raise if any
            if errors:
                for error in errors:
                    logger.error(error)
                if len(errors) == len(audio_urls):
                    raise AudioDownloadError(
                        f"Failed to download all {len(audio_urls)} audio files: {errors[0]}"
                    )

            return content_ids

    def download_audio_file(
        self,
        url: str,
        case_id: str | None = None,
    ) -> str | None:
        """Download a single audio file with streaming support.

        Args:
            url: URL of the audio file to download
            case_id: Optional ID of the case for cache organization

        Returns
        -------
            Content ID for the downloaded file, or None if already cached

        Raises
        ------
            AudioDownloadError: If there's an error downloading the file
        """
        try:
            # Generate content ID
            content_id = self._generate_content_id(url)

            # Check if already cached
            if self.cache.audio_exists(content_id):
                logger.debug(f"Audio for {content_id} already cached")
                return content_id

            # Check if download is already in progress by another thread
            with self.lock:
                if content_id in self.downloads_in_progress:
                    # Wait for the other thread to finish
                    download_event = self.downloads_in_progress[content_id]
                    logger.debug(f"Waiting for concurrent download of {content_id}")
                    download_event.wait()
                    return content_id

                # Mark this download as in progress
                self.downloads_in_progress[content_id] = threading.Event()

            try:
                # Determine media type
                media_type = self._get_media_type(url)

                # Verify the URL is accessible
                try:
                    # Use HEAD request to check URL without downloading
                    head_response = self.session.head(url, timeout=self.timeout)
                    head_response.raise_for_status()
                    logger.info(f"Audio URL {url} verified via HEAD request")
                except requests.RequestException as e:
                    raise AudioDownloadError(
                        f"Audio URL {url} is not accessible: {e}"
                    ) from e

                # Download with streaming
                try:
                    logger.info(f"Downloading audio from {url}")
                    with self.session.get(
                        url, stream=True, timeout=self.timeout
                    ) as response:
                        response.raise_for_status()

                        # Get content length if available
                        content_length = int(response.headers.get("content-length", 0))

                        # For small files, download all at once
                        if content_length and content_length < self.chunk_size:
                            audio_data = response.content
                        else:
                            # For larger files, stream in chunks
                            chunks = []
                            for chunk in response.iter_content(
                                chunk_size=self.chunk_size
                            ):
                                if chunk:
                                    chunks.append(chunk)
                            audio_data = b"".join(chunks)

                        # Store in cache
                        self.cache.store_audio_data(
                            content_id,
                            audio_data,
                            case_id=case_id,
                            media_type=media_type,
                        )

                        return content_id

                except requests.RequestException as e:
                    raise AudioDownloadError(
                        f"Failed to download audio from {url}: {e}"
                    ) from e

            finally:
                # Mark download as complete regardless of outcome
                with self.lock:
                    if content_id in self.downloads_in_progress:
                        self.downloads_in_progress[content_id].set()
                        del self.downloads_in_progress[content_id]

        except Exception as e:
            logger.error(f"Error downloading audio file {url}: {e}")
            raise AudioDownloadError(f"Failed to download audio: {e}") from e

    def _get_media_type(self, url: str) -> str:
        """Determine the media type from a URL.

        Args:
            url: The URL to analyze

        Returns
        -------
            The media type (file extension) or "mp3" as default
        """
        # Try to extract from URL path
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Check for file extension in the path
        import re

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
        # Create a hash of the URL to ensure uniqueness using SHA-256 for security
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]

        # Extract the path portion of the URL
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Remove any leading/trailing slashes and replace internal slashes with underscores
        path = path.strip("/").replace("/", "_")

        # Combine with the hash for uniqueness
        return f"{path}_{url_hash}"
