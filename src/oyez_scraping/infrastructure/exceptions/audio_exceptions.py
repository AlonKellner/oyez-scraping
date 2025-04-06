"""Custom exceptions for the infrastructure layer of the Oyez scraping project."""


class InfrastructureError(Exception):
    """Base exception for all infrastructure-related errors."""

    pass


class AudioProcessingError(InfrastructureError):
    """Exception raised for errors during audio processing operations."""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize the exception with context information.

        Args:
            message: The error message.
            file_path: Path to the audio file that caused the error.
            *args: Additional positional arguments passed to parent class.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        self.file_path = file_path
        self.message = f"{message}" + (f" File: {file_path}" if file_path else "")
        super().__init__(self.message, *args, **kwargs)
