"""Exceptions related to storage operations.

This module provides custom exceptions for handling errors that occur
during storage operations like file reading, writing, and directory management.
"""


class StorageError(Exception):
    """Base exception for all storage-related errors."""

    pass


class FileReadError(StorageError):
    """Exception raised when reading from a file fails."""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize the exception with context information.

        Args:
            message: The error message
            file_path: Path to the file that caused the error
            *args: Additional positional arguments passed to parent class
            **kwargs: Additional keyword arguments passed to parent class
        """
        self.file_path = file_path
        self.message = f"{message}" + (f" File: {file_path}" if file_path else "")
        super().__init__(self.message, *args, **kwargs)


class FileWriteError(StorageError):
    """Exception raised when writing to a file fails."""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize the exception with context information.

        Args:
            message: The error message
            file_path: Path to the file that caused the error
            *args: Additional positional arguments passed to parent class
            **kwargs: Additional keyword arguments passed to parent class
        """
        self.file_path = file_path
        self.message = f"{message}" + (f" File: {file_path}" if file_path else "")
        super().__init__(self.message, *args, **kwargs)


class DirectoryCreationError(StorageError):
    """Exception raised when creating a directory fails."""

    def __init__(
        self,
        message: str,
        dir_path: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize the exception with context information.

        Args:
            message: The error message
            dir_path: Path to the directory that caused the error
            *args: Additional positional arguments passed to parent class
            **kwargs: Additional keyword arguments passed to parent class
        """
        self.dir_path = dir_path
        self.message = f"{message}" + (f" Directory: {dir_path}" if dir_path else "")
        super().__init__(self.message, *args, **kwargs)


class CacheError(StorageError):
    """Exception raised when an operation on the cache fails."""

    pass
