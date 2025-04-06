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

    @staticmethod
    def get_audio_types() -> dict:
        """Get available types of audio content from Oyez.

        This method retrieves the different types of audio content available
        on Oyez, such as oral arguments and opinion announcements.

        Returns
        -------
            Dict mapping audio type identifiers to their descriptions
        """
        # Define known audio types directly since the base endpoint doesn't return API structure
        audio_types = {
            "oral-arguments": {
                "description": "Oral arguments before the Supreme Court",
                "href": f"{OyezAPI.BASE_URL}/case_media/oral_argument_audio",
            },
            "opinion-announcements": {
                "description": "Opinion announcements by the justices",
                "href": f"{OyezAPI.BASE_URL}/case_media/opinion_announcement",
            },
        }

        return audio_types

    @staticmethod
    def get_term_list() -> list[str]:
        """Get a list of available court terms.

        This method retrieves a list of available Supreme Court terms
        from the Oyez API.

        Returns
        -------
            List of term identifiers (years) as strings
        """
        try:
            # Try the terms endpoint first
            response = requests.get(
                f"{OyezAPI.BASE_URL}/terms",
                headers={"Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            terms_data = response.json()

            # Extract term identifiers
            terms = []
            for term in terms_data:
                if isinstance(term, dict) and "term" in term:
                    terms.append(str(term["term"]))

            # Sort terms newest to oldest
            terms.sort(reverse=True)
            return terms
        except Exception:
            # Fallback to hard-coded recent terms
            current_year = 2023  # As of now, this is the most recent completed term

            # Generate a list of the last 20 terms
            terms = [str(year) for year in range(current_year, current_year - 20, -1)]

            return terms

    @staticmethod
    def get_cases_by_term(term: str) -> list[dict]:
        """Get all cases for a specific Supreme Court term.

        Args:
            term: The term identifier (year) as a string

        Returns
        -------
            List of case data dictionaries
        """
        response = requests.get(
            f"{OyezAPI.BASE_URL}/terms/{term}",
            headers={"Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        term_data = response.json()

        # Extract cases
        cases = []
        if isinstance(term_data, list) and len(term_data) > 0:
            if "cases" in term_data[0]:
                cases = term_data[0]["cases"]
        elif isinstance(term_data, dict) and "cases" in term_data:
            cases = term_data["cases"]

        return cases

    @staticmethod
    def find_all_labeled_audio() -> dict:
        """Find all available labeled audio files in Oyez.

        This method retrieves information about all available audio files
        in Oyez that have associated labels (transcripts), categorized by
        audio type and term.

        Returns
        -------
            Dict mapping audio types to terms and cases with labeled audio
        """
        # Get available audio types
        audio_types = OyezAPI.get_audio_types()

        # Get available terms
        terms = OyezAPI.get_term_list()

        # Prepare result structure
        all_audio = {}
        for audio_type in audio_types:
            all_audio[audio_type] = {}

        # Process each audio type
        if "oral-arguments" in all_audio:
            OyezAPI._process_audio_type(
                all_audio, "oral-arguments", "oral_argument_audio", terms
            )

        if "opinion-announcements" in all_audio:
            OyezAPI._process_audio_type(
                all_audio, "opinion-announcements", "opinion_announcement", terms
            )

        return all_audio

    @staticmethod
    def _process_audio_type(
        all_audio: dict, audio_type: str, audio_field: str, terms: list[str]
    ) -> None:
        """Process a specific audio type to find cases with available audio.

        Args:
            all_audio: Dictionary to store results
            audio_type: Type of audio (e.g., 'oral-arguments')
            audio_field: Field name to check for audio availability in case data
            terms: List of Supreme Court terms to process
        """
        for term in terms:
            try:
                cases = OyezAPI.get_cases_by_term(term)
                cases_with_audio = []

                for case in cases:
                    # Only include cases that have audio available
                    if case.get(audio_field):
                        cases_with_audio.append(case)

                if cases_with_audio:
                    all_audio[audio_type][term] = cases_with_audio
            except requests.RequestException:
                # Skip this term if there's an API error
                continue
