"""API interaction with the Oyez project.

This module provides functions to interact with the Oyez API for fetching
Supreme Court case data and oral arguments.
"""

import contextlib

import requests


class OyezAPI:
    """Interface to the Oyez API."""

    BASE_URL = "https://api.oyez.org"

    @staticmethod
    def get_case_metadata(case_id: str) -> dict:
        """Fetch case metadata from Oyez API.

        Args:
            case_id: The Oyez case identifier

        Returns
        -------
            Dict containing case metadata
        """
        url = f"{OyezAPI.BASE_URL}/cases/{case_id}"
        response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_oral_argument_data(argument_url: str) -> dict:
        """Fetch oral argument data including transcript and timing info.

        Args:
            argument_url: URL to the oral argument JSON data

        Returns
        -------
            Dict containing oral argument data
        """
        # Get initial argument metadata
        response = requests.get(
            argument_url, headers={"Accept": "application/json"}, timeout=30
        )
        response.raise_for_status()
        arg_meta = response.json()

        # Get full transcript data
        transcript_url = (
            f"{OyezAPI.BASE_URL}/case_media/oral_argument_audio/{arg_meta.get('id')}"
        )
        response = requests.get(
            transcript_url, headers={"Accept": "application/json"}, timeout=30
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def find_audio_url(media_files: list) -> tuple[str, float]:
        """Find the best audio URL and duration from media files.

        Args:
            media_files: List of media file objects from the API

        Returns
        -------
            Tuple of (audio_url, duration)
        """
        audio_url = ""
        duration = 0.0

        # Make sure media_files is a list
        if not isinstance(media_files, list):
            media_files = [media_files] if media_files else []

        # Prefer MP3 format if available, otherwise try any audio format
        for media in media_files:
            if not isinstance(media, dict):
                continue

            mime = media.get("mime", "")
            href = media.get("href", "")

            # Look for MP3 or any audio format
            if "audio/mpeg" in mime or ".mp3" in href or "audio/" in mime:
                audio_url = href
                with contextlib.suppress(ValueError, TypeError):
                    if "size" in media:  # In some cases duration is labeled as size
                        duration = float(media.get("size", 0))
                    else:
                        duration = float(media.get("duration", 0))
                if audio_url:
                    break

        return audio_url, duration

    @staticmethod
    def download_audio(audio_url: str, output_path: str) -> None:
        """Download the oral argument audio file.

        Args:
            audio_url: URL to the audio file
            output_path: Where to save the audio file
        """
        response = requests.get(audio_url, stream=True, timeout=30)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
