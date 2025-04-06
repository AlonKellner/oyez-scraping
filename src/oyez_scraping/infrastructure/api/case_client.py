"""Client for accessing Oyez API case data.

This module provides a client for interacting with the Oyez API to retrieve
case information, oral arguments, and associated media.
"""

import logging
from typing import Any

from oyez_scraping.infrastructure.api.client import OyezClient
from oyez_scraping.infrastructure.exceptions.api_exceptions import (
    OyezApiResponseError,
    OyezResourceNotFoundError,
)

# Configure logger
logger = logging.getLogger(__name__)


class OyezCaseClient(OyezClient):
    """Client for retrieving case data from the Oyez API.

    This class provides methods to fetch case information, oral arguments,
    and associated media from the Oyez API.
    """

    def get_cases_by_term(self, term: str) -> list[dict[str, Any]]:
        """Get list of cases for a specific Supreme Court term.

        Args:
            term: The Supreme Court term (year) to fetch cases for

        Returns
        -------
            A list of case data dictionaries

        Raises
        ------
            OyezApiConnectionError: If connection to the API fails
            OyezApiResponseError: If the API returns an unexpected response
            OyezResourceNotFoundError: If no cases are found for the term
        """
        endpoint = "cases"
        params = {"filter": f"term:{term}"}

        logger.debug(f"Getting cases for term {term}")
        response = self.get(endpoint, params=params)

        if not isinstance(response, list):
            raise OyezApiResponseError(f"Expected list of cases, got {type(response)}")

        if not response:
            raise OyezResourceNotFoundError(f"No cases found for term {term}")

        logger.info(f"Retrieved {len(response)} cases for term {term}")
        return response

    def get_case_by_id(self, term: str, docket: str) -> dict[str, Any]:
        """Get detailed information about a specific case.

        Args:
            term: The Supreme Court term (year)
            docket: The docket number of the case

        Returns
        -------
            A dictionary containing case details

        Raises
        ------
            OyezApiConnectionError: If connection to the API fails
            OyezApiResponseError: If the API returns an unexpected response
            OyezResourceNotFoundError: If the case is not found
        """
        case_id = f"{term}/{docket}"
        endpoint = f"cases/{case_id}"

        logger.debug(f"Getting case details for {case_id}")
        response = self.get(endpoint)

        # Handle case where API returns a list instead of a single object
        if isinstance(response, list):
            if not response:
                raise OyezResourceNotFoundError(f"No case found with ID {case_id}")
            return response[0]

        # Ensure we're returning a dictionary, not None
        if not isinstance(response, dict):
            raise OyezApiResponseError(f"Expected dictionary, got {type(response)}")

        logger.info(f"Retrieved case details for {case_id}")
        return response

    def get_oral_argument(self, url_or_path: str) -> dict[str, Any]:
        """Get oral argument data from the Oyez API.

        Args:
            url_or_path: The URL or path to the oral argument resource

        Returns
        -------
            A dictionary containing oral argument details

        Raises
        ------
            OyezApiConnectionError: If connection to the API fails
            OyezApiResponseError: If the API returns an unexpected response
            OyezResourceNotFoundError: If the oral argument is not found
        """
        logger.debug(f"Getting oral argument data from {url_or_path}")
        response = self.get(url_or_path)

        if not isinstance(response, dict):
            raise OyezApiResponseError(
                f"Expected dictionary for oral argument data, got {type(response)}"
            )

        logger.info(f"Retrieved oral argument data from {url_or_path}")
        return response

    def verify_audio_url(self, audio_url: str) -> bool:
        """Verify that an audio URL is accessible.

        Args:
            audio_url: The audio URL to verify

        Returns
        -------
            True if the URL is accessible, False otherwise
        """
        logger.debug(f"Verifying audio URL: {audio_url}")

        # Try a HEAD request first
        if self.head(audio_url):
            logger.info(f"Audio URL {audio_url} verified via HEAD request")
            return True

        # If HEAD failed, try a GET request with streaming
        try:
            get_response = self.session.get(
                audio_url, timeout=self.timeout, stream=True
            )
            # Close the connection immediately to avoid downloading the file
            get_response.close()
            result = get_response.status_code == 200

            if result:
                logger.info(f"Audio URL {audio_url} verified via GET request")
            else:
                logger.warning(
                    f"Audio URL {audio_url} verification failed: status code {get_response.status_code}"
                )

            return result
        except Exception as e:
            logger.warning(f"Audio URL {audio_url} verification failed: {e}")
            return False

    def extract_audio_url(self, oral_argument_data: dict[str, Any]) -> str:
        """Extract the best audio URL from oral argument data.

        Args:
            oral_argument_data: The oral argument data from the API

        Returns
        -------
            The best audio URL found

        Raises
        ------
            OyezResourceNotFoundError: If no audio URL can be found
        """
        # Check for media file information
        media_files = oral_argument_data.get("media_file", [])

        # Handle case where media_file is not a list
        if not isinstance(media_files, list):
            media_files = [media_files] if media_files else []

        if not media_files:
            raise OyezResourceNotFoundError(
                "No media files found for the oral argument"
            )

        # Look for audio URLs
        audio_url = None
        audio_formats = []

        for media in media_files:
            if not isinstance(media, dict):
                continue

            mime = media.get("mime", "")
            href = media.get("href", "")

            # Skip empty URLs
            if not href:
                continue

            # Track all found formats for debugging
            audio_formats.append(f"{mime} ({href})")

            # Accept various audio formats and streaming formats
            if (
                "audio" in mime.lower()
                or ".mp3" in href.lower()
                or ".m3u8" in href.lower()  # HLS streaming format
                or ".mpd" in href.lower()  # DASH streaming format
            ):
                audio_url = href
                if audio_url:
                    logger.debug(f"Found audio URL: {audio_url} ({mime})")
                    break

        if not audio_url:
            found_formats = ", ".join(audio_formats) if audio_formats else "none"
            logger.warning(
                f"No audio URL found in media files. Found formats: {found_formats}"
            )
            raise OyezResourceNotFoundError("No audio URL found in media files")

        return audio_url

    def extract_speakers(
        self, oral_argument_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract unique speakers from oral argument data.

        Args:
            oral_argument_data: The oral argument data from the API

        Returns
        -------
            A list of speaker dictionaries with identifier, name, and role

        Raises
        ------
            OyezResourceNotFoundError: If no speakers can be found
        """
        speakers = {}  # Dictionary to track unique speakers by identifier

        # Process sources of speaker information in order of preference
        self._extract_speakers_from_transcript(oral_argument_data, speakers)
        self._extract_speakers_from_sections(oral_argument_data, speakers)
        self._extract_speakers_from_root(oral_argument_data, speakers)

        # Convert dictionary to list
        speaker_list = list(speakers.values())

        if not speaker_list:
            raise OyezResourceNotFoundError("No speakers found in oral argument data")

        logger.info(f"Extracted {len(speaker_list)} speakers from oral argument data")
        return speaker_list

    def _extract_speakers_from_transcript(
        self, oral_argument_data: dict[str, Any], speakers: dict[str, dict[str, Any]]
    ) -> None:
        """Extract speakers from the transcript section of oral argument data.

        Args:
            oral_argument_data: The oral argument data
            speakers: Dictionary to populate with speakers
        """
        if "transcript" not in oral_argument_data or not isinstance(
            oral_argument_data["transcript"], dict
        ):
            return

        transcript = oral_argument_data["transcript"]

        # Check if speakers are directly in the transcript
        if "speakers" in transcript and isinstance(transcript["speakers"], list):
            for speaker in transcript["speakers"]:
                if isinstance(speaker, dict) and "identifier" in speaker:
                    speakers[speaker["identifier"]] = {
                        "identifier": speaker["identifier"],
                        "name": speaker.get("name", "Unknown"),
                        "role": speaker.get("role", ""),
                    }

        # Check in transcript sections
        if "sections" in transcript and isinstance(transcript["sections"], list):
            for section in transcript["sections"]:
                self._extract_speakers_from_turns(section.get("turns", []), speakers)

    def _extract_speakers_from_sections(
        self, oral_argument_data: dict[str, Any], speakers: dict[str, dict[str, Any]]
    ) -> None:
        """Extract speakers from top-level sections.

        Args:
            oral_argument_data: The oral argument data
            speakers: Dictionary to populate with speakers
        """
        if "sections" not in oral_argument_data or not isinstance(
            oral_argument_data["sections"], list
        ):
            return

        for section in oral_argument_data["sections"]:
            self._extract_speakers_from_turns(section.get("turns", []), speakers)

    def _extract_speakers_from_root(
        self, oral_argument_data: dict[str, Any], speakers: dict[str, dict[str, Any]]
    ) -> None:
        """Extract speakers from top-level data.

        Args:
            oral_argument_data: The oral argument data
            speakers: Dictionary to populate with speakers
        """
        # Extract from top-level speakers if available
        if "speakers" in oral_argument_data and isinstance(
            oral_argument_data["speakers"], list
        ):
            for speaker in oral_argument_data["speakers"]:
                if isinstance(speaker, dict) and "identifier" in speaker:
                    speakers[speaker["identifier"]] = {
                        "identifier": speaker["identifier"],
                        "name": speaker.get("name", "Unknown"),
                        "role": speaker.get("role", ""),
                    }

        # Extract from top-level turns if available
        if "turns" in oral_argument_data and isinstance(
            oral_argument_data["turns"], list
        ):
            self._extract_speakers_from_turns(oral_argument_data["turns"], speakers)

    def _extract_speakers_from_turns(
        self, turns: list[dict[str, Any]], speakers: dict[str, dict[str, Any]]
    ) -> None:
        """Extract speakers from a list of turns.

        Args:
            turns: List of turns from the transcript
            speakers: Dictionary to populate with unique speakers
        """
        for turn in turns:
            if not isinstance(turn, dict) or "speaker" not in turn:
                continue

            speaker = turn["speaker"]
            if not isinstance(speaker, dict) or "identifier" not in speaker:
                continue

            speaker_id = speaker["identifier"]
            if speaker_id not in speakers:
                speakers[speaker_id] = {
                    "identifier": speaker_id,
                    "name": speaker.get("name", "Unknown"),
                    "role": speaker.get("role", ""),
                }

    def extract_utterances(
        self, oral_argument_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract utterances with timing information from oral argument data.

        Args:
            oral_argument_data: The oral argument data from the API

        Returns
        -------
            A list of utterance dictionaries with speaker_id, start_time, end_time, and text

        Raises
        ------
            OyezResourceNotFoundError: If no utterances can be found
        """
        utterances = []

        # Process sources of utterances in order of preference
        self._extract_utterances_from_transcript(oral_argument_data, utterances)
        self._extract_utterances_from_root(oral_argument_data, utterances)

        if not utterances:
            raise OyezResourceNotFoundError("No utterances found in oral argument data")

        logger.info(f"Extracted {len(utterances)} utterances from oral argument data")
        return utterances

    def _extract_utterances_from_transcript(
        self, oral_argument_data: dict[str, Any], utterances: list[dict[str, Any]]
    ) -> None:
        """Extract utterances from the transcript section.

        Args:
            oral_argument_data: The oral argument data
            utterances: List to populate with utterances
        """
        if "transcript" not in oral_argument_data or not isinstance(
            oral_argument_data["transcript"], dict
        ):
            return

        transcript = oral_argument_data["transcript"]

        # Check in transcript sections
        if "sections" in transcript and isinstance(transcript["sections"], list):
            for section in transcript["sections"]:
                self._extract_utterances_from_turns(
                    section.get("turns", []), utterances
                )

        # Check directly in transcript turns
        if (
            not utterances
            and "turns" in transcript
            and isinstance(transcript["turns"], list)
        ):
            self._extract_utterances_from_turns(transcript["turns"], utterances)

        # Check in text_only format
        if (
            not utterances
            and "text_only" in transcript
            and isinstance(transcript["text_only"], list)
        ):
            self._extract_utterances_from_text_only(transcript["text_only"], utterances)

    def _extract_utterances_from_root(
        self, oral_argument_data: dict[str, Any], utterances: list[dict[str, Any]]
    ) -> None:
        """Extract utterances from root-level elements.

        Args:
            oral_argument_data: The oral argument data
            utterances: List to populate with utterances
        """
        # Extract from top-level sections if available
        if "sections" in oral_argument_data and isinstance(
            oral_argument_data["sections"], list
        ):
            for section in oral_argument_data["sections"]:
                self._extract_utterances_from_turns(
                    section.get("turns", []), utterances
                )

        # Extract from top-level turns if available
        if "turns" in oral_argument_data and isinstance(
            oral_argument_data["turns"], list
        ):
            self._extract_utterances_from_turns(oral_argument_data["turns"], utterances)

    def _extract_utterances_from_turns(
        self, turns: list[dict[str, Any]], utterances: list[dict[str, Any]]
    ) -> None:
        """Extract utterances from a list of turns.

        Args:
            turns: List of turns from the transcript
            utterances: List to append valid utterances to
        """
        for turn in turns:
            if not isinstance(turn, dict):
                continue

            speaker = turn.get("speaker", {})
            speaker_id = speaker.get("identifier", "")

            # If no identifier, try to use name as fallback
            if not speaker_id and isinstance(speaker, dict) and "name" in speaker:
                speaker_id = speaker.get("name", "")

            start_time = turn.get("start", None)
            end_time = turn.get("stop", None)  # API uses "stop" not "end"

            self._process_turn_content(
                turn, speaker_id, start_time, end_time, utterances
            )

    def _process_turn_content(
        self,
        turn: dict[str, Any],
        speaker_id: str,
        start_time: float | None,
        end_time: float | None,
        utterances: list[dict[str, Any]],
    ) -> None:
        """Process the content of a turn to extract utterances.

        Args:
            turn: The turn data dictionary
            speaker_id: The ID of the speaker
            start_time: The start time of the turn
            end_time: The end time of the turn
            utterances: List to append valid utterances to
        """
        # Check for segments (detailed utterances with timing)
        segments = turn.get("segments", [])
        if segments and isinstance(segments, list):
            self._process_segments(segments, speaker_id, utterances)
        # Check for text_blocks (another format used in the API)
        elif "text_blocks" in turn and isinstance(turn["text_blocks"], list):
            self._process_text_blocks(
                turn["text_blocks"], speaker_id, start_time, end_time, utterances
            )
        # If no segments or text_blocks, check for direct text on the turn
        elif "text" in turn:
            text = turn.get("text", "")

            if speaker_id and start_time is not None and end_time is not None and text:
                utterances.append(
                    {
                        "speaker_id": speaker_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "text": text,
                    }
                )

    def _process_segments(
        self,
        segments: list[dict[str, Any]],
        speaker_id: str,
        utterances: list[dict[str, Any]],
    ) -> None:
        """Process segments in a turn.

        Args:
            segments: List of segments
            speaker_id: The ID of the speaker
            utterances: List to append valid utterances to
        """
        for segment in segments:
            if not isinstance(segment, dict):
                continue

            segment_start_time = segment.get("start", None)
            segment_end_time = segment.get("stop", None)  # API uses "stop" not "end"
            text = segment.get("text", "")

            if (
                speaker_id
                and segment_start_time is not None
                and segment_end_time is not None
                and text
            ):
                utterances.append(
                    {
                        "speaker_id": speaker_id,
                        "start_time": segment_start_time,
                        "end_time": segment_end_time,
                        "text": text,
                    }
                )

    def _process_text_blocks(
        self,
        text_blocks: list[dict[str, Any]],
        speaker_id: str,
        start_time: float | None,
        end_time: float | None,
        utterances: list[dict[str, Any]],
    ) -> None:
        """Process text blocks in a turn.

        Args:
            text_blocks: List of text blocks
            speaker_id: The ID of the speaker
            start_time: Start time of the turn
            end_time: End time of the turn
            utterances: List to append valid utterances to
        """
        combined_text = ""

        # Combine all text blocks into a single utterance
        for block in text_blocks:
            if not isinstance(block, dict):
                continue

            block_text = block.get("text", "")
            if block_text:
                if combined_text:
                    combined_text += " "
                combined_text += block_text

        if (
            speaker_id
            and start_time is not None
            and end_time is not None
            and combined_text
        ):
            utterances.append(
                {
                    "speaker_id": speaker_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": combined_text,
                }
            )

    def _extract_utterances_from_text_only(
        self, text_only: list[dict[str, Any]], utterances: list[dict[str, Any]]
    ) -> None:
        """Extract utterances from text_only format.

        Args:
            text_only: List of text_only segments
            utterances: List to append valid utterances to
        """
        current_time = 0.0

        for segment in text_only:
            if not isinstance(segment, dict):
                continue

            speaker = segment.get("speaker", {})
            if not isinstance(speaker, dict):
                continue

            speaker_id = speaker.get("identifier", "")
            if not speaker_id and "name" in speaker:
                speaker_id = speaker.get("name", "")

            text = segment.get("text", "")

            if speaker_id and text:
                # Since there's no timing info, create synthetic timestamps
                # based on text length (roughly 3 chars per second)
                duration = max(1.0, len(text) / 3)
                end_time = current_time + duration

                utterances.append(
                    {
                        "speaker_id": speaker_id,
                        "start_time": current_time,
                        "end_time": end_time,
                        "text": text,
                    }
                )

                current_time = end_time
