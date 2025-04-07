"""Filesystem storage implementation for the Oyez scraping project.

This module provides utilities for reading and writing files to the filesystem,
with a focus on JSON data handling and proper error handling.
"""

import json
import os
from pathlib import Path
from typing import Any, TypeVar

from ..exceptions.storage_exceptions import (
    DirectoryCreationError,
    FileReadError,
    FileWriteError,
)

# Type variable for generic JSON data
T = TypeVar("T", dict[str, Any], list[Any], str, int, float, bool, None)


class FilesystemStorage:
    """Filesystem storage implementation for reading and writing files."""

    @staticmethod
    def read_json(file_path: str | Path) -> Any:
        """Read JSON data from a file.

        Args:
            file_path: Path to the JSON file

        Returns
        -------
            The parsed JSON data

        Raises
        ------
            FileReadError: If the file cannot be read or parsed
        """
        try:
            file_path = Path(file_path)
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise FileReadError(
                f"Failed to parse JSON: {e}", file_path=str(file_path)
            ) from e
        except Exception as e:
            raise FileReadError(
                f"Failed to read file: {e}", file_path=str(file_path)
            ) from e

    @staticmethod
    def write_json(file_path: str | Path, data: Any, indent: int = 2) -> None:
        """Write data as JSON to a file.

        Args:
            file_path: Path where the JSON file will be written
            data: The data to serialize to JSON
            indent: Number of spaces for indentation (default: 2)

        Raises
        ------
            FileWriteError: If the file cannot be written
        """
        try:
            file_path = Path(file_path)

            # Ensure the parent directory exists
            os.makedirs(file_path.parent, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        except Exception as e:
            raise FileWriteError(
                f"Failed to write JSON file: {e}", file_path=str(file_path)
            ) from e

    @staticmethod
    def ensure_directory(directory_path: str | Path) -> Path:
        """Ensure a directory exists, creating it if necessary.

        Args:
            directory_path: Path to the directory to create

        Returns
        -------
            Path object for the created/existing directory

        Raises
        ------
            DirectoryCreationError: If the directory cannot be created
        """
        try:
            directory_path = Path(directory_path)
            os.makedirs(directory_path, exist_ok=True)
            return directory_path
        except Exception as e:
            raise DirectoryCreationError(
                f"Failed to create directory: {e}", dir_path=str(directory_path)
            ) from e

    @staticmethod
    def file_exists(file_path: str | Path) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to the file to check

        Returns
        -------
            True if the file exists, False otherwise
        """
        return Path(file_path).is_file()

    @staticmethod
    def directory_exists(directory_path: str | Path) -> bool:
        """Check if a directory exists.

        Args:
            directory_path: Path to the directory to check

        Returns
        -------
            True if the directory exists, False otherwise
        """
        return Path(directory_path).is_dir()

    @staticmethod
    def list_files(
        directory_path: str | Path, pattern: str | None = None
    ) -> list[Path]:
        """List files in a directory, optionally filtered by a glob pattern.

        Args:
            directory_path: Path to the directory
            pattern: Optional glob pattern to filter files (e.g., "*.json")

        Returns
        -------
            List of Path objects for the files

        Raises
        ------
            FileReadError: If the directory cannot be read
        """
        try:
            directory_path = Path(directory_path)

            if pattern:
                return list(directory_path.glob(pattern))
            else:
                return [p for p in directory_path.iterdir() if p.is_file()]
        except Exception as e:
            raise FileReadError(
                f"Failed to list files: {e}", file_path=str(directory_path)
            ) from e

    @staticmethod
    def read_bytes(file_path: str | Path) -> bytes:
        """Read binary data from a file.

        Args:
            file_path: Path to the file

        Returns
        -------
            The file contents as bytes

        Raises
        ------
            FileReadError: If the file cannot be read
        """
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            raise FileReadError(
                f"Failed to read binary file: {e}", file_path=str(file_path)
            ) from e

    @staticmethod
    def write_bytes(file_path: str | Path, data: bytes) -> None:
        """Write binary data to a file.

        Args:
            file_path: Path where the file will be written
            data: The binary data to write

        Raises
        ------
            FileWriteError: If the file cannot be written
        """
        try:
            file_path = Path(file_path)

            # Ensure the parent directory exists
            os.makedirs(file_path.parent, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(data)
        except Exception as e:
            raise FileWriteError(
                f"Failed to write binary file: {e}", file_path=str(file_path)
            ) from e
