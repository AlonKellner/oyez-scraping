"""Cache management for the Oyez scraping project.

This module provides a caching system for raw Oyez data to avoid
re-scraping already fetched content.
"""

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any

from ..exceptions.storage_exceptions import CacheError, StorageError
from .filesystem import FilesystemStorage

# Configure logger
logger = logging.getLogger(__name__)


class RawDataCache:
    """Cache manager for raw Oyez data.

    This class handles storing and retrieving raw data from the Oyez API,
    while maintaining a cache index to track what has been scraped.
    """

    def __init__(self, cache_dir: str | Path = ".app_cache") -> None:
        """Initialize the cache manager.

        Args:
            cache_dir: Directory where cache files will be stored
        """
        self.cache_dir = Path(cache_dir)
        self.storage = FilesystemStorage()

        # Create a lock for thread safety
        self.lock = threading.RLock()

        # Create cache directories
        self._create_cache_structure()

        # Cache index stores metadata about what's been cached
        self.index_path = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_or_create_index()

    def _create_cache_structure(self) -> None:
        """Create the cache directory structure.

        Raises
        ------
            CacheError: If directories cannot be created
        """
        try:
            # Main cache directory
            self.storage.ensure_directory(self.cache_dir)

            # Subdirectories for different types of data
            self.storage.ensure_directory(self.cache_dir / "cases")
            self.storage.ensure_directory(self.cache_dir / "audio")
            self.storage.ensure_directory(self.cache_dir / "metadata")
        except StorageError as e:
            raise CacheError(f"Failed to create cache directory structure: {e}") from e

    def _load_or_create_index(self) -> dict[str, Any]:
        """Load the cache index or create a new one if it doesn't exist.

        Returns
        -------
            Dict containing the cache index

        Raises
        ------
            CacheError: If the index file exists but cannot be loaded
        """
        if self.storage.file_exists(self.index_path):
            try:
                return self.storage.read_json(self.index_path)
            except StorageError as e:
                raise CacheError(f"Failed to load cache index: {e}") from e
        else:
            # Create a new index with basic structure
            index = {
                "metadata": {
                    "created_at": time.time(),
                    "last_updated": time.time(),
                    "version": "1.0",
                },
                "cases": {},
                "audio_files": {},
                "case_lists": {},
            }
            self._save_index(index)
            return index

    def _save_index(self, index: dict[str, Any] | None = None) -> None:
        """Save the cache index to disk.

        Args:
            index: Cache index to save (uses self.cache_index if None)

        Raises
        ------
            CacheError: If the index cannot be saved
        """
        try:
            with self.lock:
                index = index or self.cache_index
                index["metadata"]["last_updated"] = time.time()
                self.storage.write_json(self.index_path, index)
        except StorageError as e:
            raise CacheError(f"Failed to save cache index: {e}") from e

    def case_exists(self, case_id: str) -> bool:
        """Check if a case exists in the cache.

        Args:
            case_id: The ID of the case to check

        Returns
        -------
            True if the case is cached, False otherwise
        """
        with self.lock:
            return case_id in self.cache_index["cases"]

    def get_case_data(self, case_id: str) -> dict[str, Any]:
        """Get case data from the cache.

        Args:
            case_id: The ID of the case to retrieve

        Returns
        -------
            The case data as a dictionary

        Raises
        ------
            CacheError: If the case is not in the cache or cannot be loaded
        """
        if not self.case_exists(case_id):
            raise CacheError(f"Case {case_id} not found in cache")

        try:
            case_path = self._get_case_path(case_id)
            return self.storage.read_json(case_path)
        except StorageError as e:
            raise CacheError(f"Failed to read case data: {e}") from e

    def store_case_data(self, case_id: str, case_data: dict[str, Any]) -> None:
        """Store case data in the cache.

        Args:
            case_id: The ID of the case
            case_data: The case data to store

        Raises
        ------
            CacheError: If the case data cannot be stored
        """
        try:
            # Generate a safe filename from the case_id
            case_path = self._get_case_path(case_id)

            # Store the case data
            self.storage.write_json(case_path, case_data)

            # Update the cache index
            with self.lock:
                self.cache_index["cases"][case_id] = {
                    "path": str(case_path.relative_to(self.cache_dir)),
                    "cached_at": time.time(),
                    "has_audio": False,  # Initially no audio files are cached
                }

                # Save the updated index
                self._save_index()

            logger.info(f"Cached case data for {case_id}")
        except StorageError as e:
            raise CacheError(f"Failed to store case data: {e}") from e

    def audio_exists(self, audio_id: str) -> bool:
        """Check if an audio file exists in the cache.

        Args:
            audio_id: The ID of the audio to check

        Returns
        -------
            True if the audio is cached, False otherwise
        """
        with self.lock:
            return audio_id in self.cache_index["audio_files"]

    def get_audio_data(self, audio_id: str) -> bytes:
        """Get audio data from the cache.

        Args:
            audio_id: The ID of the audio to retrieve

        Returns
        -------
            The audio data as bytes

        Raises
        ------
            CacheError: If the audio is not in the cache or cannot be loaded
        """
        if not self.audio_exists(audio_id):
            raise CacheError(f"Audio {audio_id} not found in cache")

        try:
            with self.lock:
                audio_path = self._get_audio_path(audio_id)
            return self.storage.read_bytes(audio_path)
        except StorageError as e:
            raise CacheError(f"Failed to read audio data: {e}") from e

    def store_audio_data(
        self,
        audio_id: str,
        audio_data: bytes,
        case_id: str | None = None,
        media_type: str = "unknown",
    ) -> None:
        """Store audio data in the cache.

        Args:
            audio_id: The ID of the audio
            audio_data: The audio data to store as bytes
            case_id: Optional ID of the associated case
            media_type: Type of media (e.g., "mp3", "flac")

        Raises
        ------
            CacheError: If the audio data cannot be stored
        """
        try:
            # Generate a path for the audio file
            audio_path = self._get_audio_path(audio_id, media_type)

            # Store the audio data
            self.storage.write_bytes(audio_path, audio_data)

            # Update the cache index
            with self.lock:
                self.cache_index["audio_files"][audio_id] = {
                    "path": str(audio_path.relative_to(self.cache_dir)),
                    "cached_at": time.time(),
                    "media_type": media_type,
                    "case_id": case_id,
                }

                # Update the case entry if a case_id was provided
                if case_id and case_id in self.cache_index["cases"]:
                    self.cache_index["cases"][case_id]["has_audio"] = True

                # Save the updated index
                self._save_index()

            logger.info(f"Cached audio data for {audio_id}")
        except StorageError as e:
            raise CacheError(f"Failed to store audio data: {e}") from e

    def store_case_list(self, list_name: str, case_list: list[dict[str, Any]]) -> None:
        """Store a list of cases in the cache.

        Args:
            list_name: A name to identify this list (e.g., "term_2019")
            case_list: The list of cases to store

        Raises
        ------
            CacheError: If the case list cannot be stored
        """
        try:
            # Generate a path for the case list
            list_path = self.cache_dir / "metadata" / f"{list_name}.json"

            # Store the case list
            self.storage.write_json(list_path, case_list)

            # Update the cache index
            with self.lock:
                self.cache_index["case_lists"][list_name] = {
                    "path": str(list_path.relative_to(self.cache_dir)),
                    "cached_at": time.time(),
                    "count": len(case_list),
                }

                # Save the updated index
                self._save_index()

            logger.info(f"Cached case list {list_name} with {len(case_list)} cases")
        except StorageError as e:
            raise CacheError(f"Failed to store case list: {e}") from e

    def get_case_list(self, list_name: str) -> list[dict[str, Any]]:
        """Get a list of cases from the cache.

        Args:
            list_name: The name of the case list to retrieve

        Returns
        -------
            The list of cases

        Raises
        ------
            CacheError: If the case list is not in the cache or cannot be loaded
        """
        with self.lock:
            if list_name not in self.cache_index["case_lists"]:
                raise CacheError(f"Case list {list_name} not found in cache")

            try:
                list_path = (
                    self.cache_dir / self.cache_index["case_lists"][list_name]["path"]
                )
                return self.storage.read_json(list_path)
            except StorageError as e:
                raise CacheError(f"Failed to read case list: {e}") from e

    def case_list_exists(self, list_name: str) -> bool:
        """Check if a case list exists in the cache.

        Args:
            list_name: The name of the case list to check

        Returns
        -------
            True if the case list is cached, False otherwise
        """
        with self.lock:
            return list_name in self.cache_index["case_lists"]

    def _get_case_path(self, case_id: str) -> Path:
        """Generate a filesystem path for a case.

        Args:
            case_id: The ID of the case

        Returns
        -------
            Path object for the case file
        """
        # Replace slashes with dashes for safe filenames
        safe_id = case_id.replace("/", "-")
        return self.cache_dir / "cases" / f"{safe_id}.json"

    def _get_audio_path(self, audio_id: str, media_type: str = "mp3") -> Path:
        """Generate a filesystem path for an audio file.

        Args:
            audio_id: The ID of the audio
            media_type: The file extension for the audio

        Returns
        -------
            Path object for the audio file
        """
        # Generate a safe filename from the audio_id
        # Use a hash to ensure filename safety - SHA256 is used for security
        # (Though this is not for security purposes, just filename safety)
        hashed_id = hashlib.sha256(audio_id.encode()).hexdigest()
        safe_id = f"{hashed_id}"

        # Ensure the media_type doesn't include a leading dot
        if media_type.startswith("."):
            media_type = media_type[1:]

        return self.cache_dir / "audio" / f"{safe_id}.{media_type}"

    def get_all_cached_case_ids(self) -> set[str]:
        """Get the IDs of all cached cases.

        Returns
        -------
            Set of case IDs
        """
        with self.lock:
            return set(self.cache_index["cases"].keys())

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the cache.

        Returns
        -------
            Dictionary with cache statistics
        """
        with self.lock:
            return {
                "case_count": len(self.cache_index["cases"]),
                "audio_count": len(self.cache_index["audio_files"]),
                "case_list_count": len(self.cache_index["case_lists"]),
                "last_updated": self.cache_index["metadata"]["last_updated"],
            }

    def clear_cache(self) -> None:
        """Clear the entire cache.

        This removes all cached data but keeps the directory structure.

        Raises
        ------
            CacheError: If the cache cannot be cleared
        """
        try:
            with self.lock:
                # Create a fresh index
                self.cache_index = {
                    "metadata": {
                        "created_at": time.time(),
                        "last_updated": time.time(),
                        "version": "1.0",
                    },
                    "cases": {},
                    "audio_files": {},
                    "case_lists": {},
                }

                # Save the fresh index
                self._save_index()

            # Remove all files from case directory (outside lock to reduce lock time)
            for file_path in self.storage.list_files(self.cache_dir / "cases"):
                file_path.unlink()

            # Remove all files from audio directory
            for file_path in self.storage.list_files(self.cache_dir / "audio"):
                file_path.unlink()

            # Remove all files from metadata directory
            for file_path in self.storage.list_files(self.cache_dir / "metadata"):
                file_path.unlink()

            logger.info("Cache cleared")
        except Exception as e:
            raise CacheError(f"Failed to clear cache: {e}") from e
