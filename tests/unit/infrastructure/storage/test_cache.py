"""Unit tests for the cache module."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from oyez_scraping.infrastructure.exceptions.storage_exceptions import (
    CacheError,
    StorageError,
)
from oyez_scraping.infrastructure.storage.cache import RawDataCache


class TestRawDataCache:
    """Tests for the RawDataCache class."""

    def test_initialization(self) -> None:
        """Test that initialization creates the cache directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            RawDataCache(temp_dir)

            # Verify that the cache directories were created
            assert os.path.isdir(os.path.join(temp_dir, "cases"))
            assert os.path.isdir(os.path.join(temp_dir, "audio"))
            assert os.path.isdir(os.path.join(temp_dir, "metadata"))

            # Verify that the cache index was created
            assert os.path.isfile(os.path.join(temp_dir, "cache_index.json"))

    def test_store_and_retrieve_case_data(self) -> None:
        """Test storing and retrieving case data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            case_id = "2019/17-1618"
            case_data = {
                "id": case_id,
                "name": "Test Case",
                "term": "2019",
                "docket_number": "17-1618",
            }

            # Store case data
            cache.store_case_data(case_id, case_data)

            # Verify case exists in cache
            assert cache.case_exists(case_id)

            # Retrieve case data
            retrieved_data = cache.get_case_data(case_id)

            # Verify retrieved data matches original
            assert retrieved_data == case_data

            # Verify case file exists
            case_file = os.path.join(temp_dir, "cases", "2019-17-1618.json")
            assert os.path.isfile(case_file)

    def test_get_nonexistent_case(self) -> None:
        """Test retrieving a non-existent case."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Verify non-existent case
            assert not cache.case_exists("nonexistent_case")

            # Attempt to retrieve non-existent case
            with pytest.raises(CacheError) as excinfo:
                cache.get_case_data("nonexistent_case")

            assert "not found in cache" in str(excinfo.value)

    def test_store_and_retrieve_audio_data(self) -> None:
        """Test storing and retrieving audio data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            audio_id = "test_audio_id"
            audio_data = b"test audio binary data"
            case_id = "2019/17-1618"
            media_type = "mp3"

            # Store audio data
            cache.store_audio_data(audio_id, audio_data, case_id, media_type)

            # Verify audio exists in cache
            assert cache.audio_exists(audio_id)

            # Retrieve audio data
            retrieved_data = cache.get_audio_data(audio_id)

            # Verify retrieved data matches original
            assert retrieved_data == audio_data

    def test_get_nonexistent_audio(self) -> None:
        """Test retrieving non-existent audio data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Verify non-existent audio
            assert not cache.audio_exists("nonexistent_audio")

            # Attempt to retrieve non-existent audio
            with pytest.raises(CacheError) as excinfo:
                cache.get_audio_data("nonexistent_audio")

            assert "not found in cache" in str(excinfo.value)

    def test_store_and_retrieve_case_list(self) -> None:
        """Test storing and retrieving a case list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            list_name = "term_2019"
            case_list = [
                {"id": "case1", "name": "Case 1"},
                {"id": "case2", "name": "Case 2"},
            ]

            # Store case list
            cache.store_case_list(list_name, case_list)

            # Verify case list exists in cache
            assert cache.case_list_exists(list_name)

            # Retrieve case list
            retrieved_list = cache.get_case_list(list_name)

            # Verify retrieved list matches original
            assert retrieved_list == case_list

            # Verify case list file exists
            list_file = os.path.join(temp_dir, "metadata", f"{list_name}.json")
            assert os.path.isfile(list_file)

    def test_get_nonexistent_case_list(self) -> None:
        """Test retrieving a non-existent case list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Verify non-existent case list
            assert not cache.case_list_exists("nonexistent_list")

            # Attempt to retrieve non-existent case list
            with pytest.raises(CacheError) as excinfo:
                cache.get_case_list("nonexistent_list")

            assert "not found in cache" in str(excinfo.value)

    def test_get_all_cached_case_ids(self) -> None:
        """Test getting all cached case IDs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Store some test cases
            test_cases = {
                "2019/1": {"id": "2019/1", "name": "Case 1"},
                "2019/2": {"id": "2019/2", "name": "Case 2"},
                "2020/1": {"id": "2020/1", "name": "Case 3"},
            }

            for case_id, case_data in test_cases.items():
                cache.store_case_data(case_id, case_data)

            # Get all cached case IDs
            case_ids = cache.get_all_cached_case_ids()

            # Verify all test case IDs are present
            assert case_ids == set(test_cases.keys())

    def test_get_cache_stats(self) -> None:
        """Test getting cache statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Store some test data
            cache.store_case_data("case1", {"id": "case1"})
            cache.store_case_data("case2", {"id": "case2"})
            cache.store_audio_data("audio1", b"data", "case1")
            cache.store_case_list("list1", [{"id": "case1"}])

            # Get cache stats
            stats = cache.get_cache_stats()

            # Verify stats
            assert stats["case_count"] == 2
            assert stats["audio_count"] == 1
            assert stats["case_list_count"] == 1
            assert "last_updated" in stats

    def test_clear_cache(self) -> None:
        """Test clearing the cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Store some test data
            cache.store_case_data("case1", {"id": "case1"})
            cache.store_audio_data("audio1", b"data", "case1")
            cache.store_case_list("list1", [{"id": "case1"}])

            # Verify data exists
            assert cache.case_exists("case1")
            assert cache.audio_exists("audio1")
            assert cache.case_list_exists("list1")

            # Clear the cache
            cache.clear_cache()

            # Verify data was cleared
            assert not cache.case_exists("case1")
            assert not cache.audio_exists("audio1")
            assert not cache.case_list_exists("list1")

            # Verify directory structure still exists
            assert os.path.isdir(os.path.join(temp_dir, "cases"))
            assert os.path.isdir(os.path.join(temp_dir, "audio"))
            assert os.path.isdir(os.path.join(temp_dir, "metadata"))

    def test_handle_cache_initialization_error(self) -> None:
        """Test handling errors during cache initialization."""
        with mock.patch(
            "oyez_scraping.infrastructure.storage.filesystem.FilesystemStorage.ensure_directory",
            side_effect=StorageError("Mock error"),
        ):
            with pytest.raises(CacheError) as excinfo:
                RawDataCache("/temp/nonexistent")

            assert "Failed to create cache directory structure" in str(excinfo.value)

    def test_cache_path_generation(self) -> None:
        """Test the path generation for case and audio files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = RawDataCache(temp_dir)

            # Test case path
            case_path = cache._get_case_path("2019/17-1618")
            expected_case_path = Path(temp_dir) / "cases" / "2019-17-1618.json"
            assert case_path == expected_case_path

            # Test audio path with default media type
            audio_path = cache._get_audio_path("test_audio_id")
            # We can't assert the exact path since it uses a hash, but we can check the structure
            assert audio_path.parent == Path(temp_dir) / "audio"
            assert audio_path.suffix == ".mp3"

            # Test audio path with custom media type
            audio_path = cache._get_audio_path("test_audio_id", "flac")
            assert audio_path.suffix == ".flac"
