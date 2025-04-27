"""Request logger module for tracking API requests.

This module provides functionality to log API request metadata to files,
maintaining a parallel directory structure matching the data files.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from oyez_scraping.infrastructure.monitoring.request_metadata import RequestMetadata


class RequestLogger:
    """Logs API request metadata to files.

    This class handles logging request metadata to files with a consistent naming convention,
    maintaining a parallel directory structure to the data files.

    Attributes
    ----------
        log_dir: Base directory for request logs
    """

    def __init__(self, log_dir: Path) -> None:
        """Initialize the request logger.

        Args:
            log_dir: Directory where request logs will be stored
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_request(
        self, metadata: RequestMetadata, data_type: str, data_filename: str
    ) -> str:
        """Log request metadata to a file.

        Args:
            metadata: The request metadata to log
            data_type: Type of data (audio, cases, case_list, etc.)
            data_filename: The filename of the corresponding data file

        Returns
        -------
            The request ID

        Raises
        ------
            OSError: If there's an error creating directories or writing to the log file
        """
        # Extract the base filename without extension
        base_filename = Path(data_filename).stem

        # Create the request log filename with .request.json extension
        request_filename = f"{base_filename}.request.json"

        # Ensure the directory exists
        log_dir = self.log_dir / data_type
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create log directory {log_dir}: {e!s}") from e

        # Update related_file in metadata
        metadata.related_file = f"{data_type}/{data_filename}"

        # Save the request metadata
        log_path = log_dir / request_filename
        try:
            with open(log_path, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2, default=self._json_serialize)
        except OSError as e:
            raise OSError(f"Failed to write request log to {log_path}: {e!s}") from e

        return metadata.request_id

    def find_request_log_for_data_file(self, data_file_path: Path) -> Path | None:
        """Find the request log file for a data file.

        Args:
            data_file_path: Path to the data file

        Returns
        -------
            Path to the request log file, or None if not found
        """
        # Extract data type from parent directory name
        data_type = data_file_path.parent.name

        # Extract base filename
        base_filename = data_file_path.stem

        # Construct path to request log
        request_log_path = self.log_dir / data_type / f"{base_filename}.request.json"

        return request_log_path if request_log_path.exists() else None

    def _json_serialize(self, obj: Any) -> Any:
        """Handle serialization of special types.

        Args:
            obj: Object to serialize

        Returns
        -------
            JSON serializable representation of the object

        Raises
        ------
            TypeError: If the object is not serializable
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
