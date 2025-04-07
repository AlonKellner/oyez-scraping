"""Unit tests for the filesystem storage module."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from oyez_scraping.infrastructure.exceptions.storage_exceptions import (
    DirectoryCreationError,
    FileReadError,
    FileWriteError,
)
from oyez_scraping.infrastructure.storage.filesystem import FilesystemStorage


class TestFilesystemStorage:
    """Tests for the FilesystemStorage class."""

    def test_read_json_normal_case(self) -> None:
        """Test normal operation of read_json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.json")
            test_data = {"key": "value", "list": [1, 2, 3]}

            # Write test data
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(test_data, f)

            # Read using filesystemstorage
            storage = FilesystemStorage()
            result = storage.read_json(file_path)

            # Verify result
            assert result == test_data

    def test_read_json_nonexistent_file(self) -> None:
        """Test read_json with a non-existent file."""
        storage = FilesystemStorage()
        with pytest.raises(FileReadError) as excinfo:
            storage.read_json("nonexistent_file.json")

        assert "Failed to read file" in str(excinfo.value)
        assert "nonexistent_file.json" in str(excinfo.value)

    def test_read_json_invalid_json(self) -> None:
        """Test read_json with invalid JSON content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "invalid.json")

            # Write invalid JSON
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("{invalid: json")

            # Attempt to read
            storage = FilesystemStorage()
            with pytest.raises(FileReadError) as excinfo:
                storage.read_json(file_path)

            assert "Failed to parse JSON" in str(excinfo.value)
            assert file_path in str(excinfo.value)

    def test_write_json_normal_case(self) -> None:
        """Test normal operation of write_json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.json")
            test_data = {"key": "value", "list": [1, 2, 3]}

            # Write using filesystemstorage
            storage = FilesystemStorage()
            storage.write_json(file_path, test_data)

            # Verify file exists
            assert os.path.exists(file_path)

            # Read back and verify content
            with open(file_path, encoding="utf-8") as f:
                result = json.load(f)

            assert result == test_data

    def test_write_json_invalid_permission(self) -> None:
        """Test write_json with invalid permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory with the same name to cause a write error
            file_path = os.path.join(temp_dir, "test_dir")
            os.makedirs(file_path)

            # Attempt to write to the directory as a file
            storage = FilesystemStorage()
            with pytest.raises(FileWriteError) as excinfo:
                storage.write_json(file_path, {"key": "value"})

            assert "Failed to write JSON file" in str(excinfo.value)
            assert file_path in str(excinfo.value)

    def test_ensure_directory_normal_case(self) -> None:
        """Test normal operation of ensure_directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = os.path.join(temp_dir, "test_dir")

            # Ensure directory exists
            storage = FilesystemStorage()
            result = storage.ensure_directory(test_dir)

            # Verify directory exists
            assert os.path.isdir(test_dir)
            assert result == Path(test_dir)

            # Call again on existing directory
            result2 = storage.ensure_directory(test_dir)
            assert result2 == Path(test_dir)

    def test_ensure_directory_error(self) -> None:
        """Test ensure_directory with an error."""
        with mock.patch("os.makedirs", side_effect=PermissionError("Mock error")):
            storage = FilesystemStorage()
            with pytest.raises(DirectoryCreationError) as excinfo:
                storage.ensure_directory("/some/path")

            assert "Failed to create directory" in str(excinfo.value)
            assert "Mock error" in str(excinfo.value)

    def test_file_exists(self) -> None:
        """Test file_exists method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("test")

            storage = FilesystemStorage()

            # Test existing file
            assert storage.file_exists(file_path) is True

            # Test non-existent file
            assert (
                storage.file_exists(os.path.join(temp_dir, "nonexistent.txt")) is False
            )

    def test_directory_exists(self) -> None:
        """Test directory_exists method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test directory
            dir_path = os.path.join(temp_dir, "test_dir")
            os.makedirs(dir_path)

            storage = FilesystemStorage()

            # Test existing directory
            assert storage.directory_exists(dir_path) is True

            # Test non-existent directory
            assert (
                storage.directory_exists(os.path.join(temp_dir, "nonexistent_dir"))
                is False
            )

    def test_list_files(self) -> None:
        """Test list_files method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            file1 = os.path.join(temp_dir, "test1.txt")
            file2 = os.path.join(temp_dir, "test2.txt")
            file3 = os.path.join(temp_dir, "test3.json")

            for file_path in [file1, file2, file3]:
                with open(file_path, "w") as f:
                    f.write("test")

            # Create a subdirectory
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)

            storage = FilesystemStorage()

            # Test listing all files
            files = storage.list_files(temp_dir)
            assert len(files) == 3
            assert all(f.is_file() for f in files)

            # Test listing with pattern
            json_files = storage.list_files(temp_dir, "*.json")
            assert len(json_files) == 1
            assert json_files[0].name == "test3.json"

    def test_list_files_nonexistent_dir(self) -> None:
        """Test list_files with a non-existent directory."""
        storage = FilesystemStorage()
        with pytest.raises(FileReadError) as excinfo:
            storage.list_files("/nonexistent/directory")

        assert "Failed to list files" in str(excinfo.value)

    def test_read_write_bytes(self) -> None:
        """Test read_bytes and write_bytes methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.bin")
            test_data = b"binary data \x00\x01\x02"

            storage = FilesystemStorage()

            # Write binary data
            storage.write_bytes(file_path, test_data)

            # Verify file exists
            assert os.path.exists(file_path)

            # Read binary data
            result = storage.read_bytes(file_path)

            # Verify content
            assert result == test_data

    def test_write_bytes_creates_parent_dirs(self) -> None:
        """Test that write_bytes creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "nested", "dir", "test.bin")
            test_data = b"binary data"

            storage = FilesystemStorage()

            # Write binary data
            storage.write_bytes(file_path, test_data)

            # Verify file exists
            assert os.path.exists(file_path)

            # Verify parent directories were created
            assert os.path.isdir(os.path.join(temp_dir, "nested"))
            assert os.path.isdir(os.path.join(temp_dir, "nested", "dir"))

    def test_read_bytes_nonexistent_file(self) -> None:
        """Test read_bytes with a non-existent file."""
        storage = FilesystemStorage()
        with pytest.raises(FileReadError) as excinfo:
            storage.read_bytes("nonexistent_file.bin")

        assert "Failed to read binary file" in str(excinfo.value)
        assert "nonexistent_file.bin" in str(excinfo.value)
