"""Oyez Supreme Court oral arguments scraper.

This module provides functionality to scrape oral arguments from the Oyez project website
and create an ASR (Automatic Speech Recognition) dataset.
"""

import contextlib
import json
from pathlib import Path

from src.api import OyezAPI
from src.audio import AudioProcessor
from src.models import OralArgument, Speaker, Utterance
from src.utils import parse_date


class OyezScraper:
    """Scraper for Oyez Supreme Court oral arguments."""

    AUDIO_SEGMENT_DIR = "segments"
    METADATA_FILE = "metadata.json"

    def __init__(self, output_dir: str) -> None:
        """Initialize the scraper.

        Args:
            output_dir: Directory where the dataset will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _extract_speakers(
        self, arg_data: dict
    ) -> tuple[list[Speaker], dict[str, Speaker]]:
        """Extract speakers from argument data.

        Args:
            arg_data: Argument data from API

        Returns
        -------
            Tuple of (speaker_list, speaker_map)
        """
        speakers = []
        speaker_map = {}

        # Look in sections first
        for section in arg_data.get("sections", []):
            for turn in section.get("turns", []):
                spk = turn.get("speaker", {})
                if not spk or "identifier" not in spk:
                    continue

                if spk["identifier"] not in speaker_map:
                    speaker = Speaker(
                        name=spk.get("name", "Unknown"),
                        role=spk.get("roles", [{}])[0].get("role_title", "Unknown")
                        if spk.get("roles")
                        else "Unknown",
                        identifier=spk["identifier"],
                    )
                    speakers.append(speaker)
                    speaker_map[speaker.identifier] = speaker

        # Also check transcript section if available
        if "transcript" in arg_data and isinstance(arg_data["transcript"], dict):
            for section in arg_data["transcript"].get("sections", []):
                for turn in section.get("turns", []):
                    spk = turn.get("speaker", {})
                    if not spk or "identifier" not in spk:
                        continue

                    if spk["identifier"] not in speaker_map:
                        speaker = Speaker(
                            name=spk.get("name", "Unknown"),
                            role=spk.get("roles", [{}])[0].get("role_title", "Unknown")
                            if spk.get("roles")
                            else "Unknown",
                            identifier=spk["identifier"],
                        )
                        speakers.append(speaker)
                        speaker_map[speaker.identifier] = speaker

        return speakers, speaker_map

    def _extract_utterances(
        self, arg_data: dict, speaker_map: dict[str, Speaker]
    ) -> list[Utterance]:
        """Extract utterances from argument data.

        Args:
            arg_data: Argument data from API
            speaker_map: Map of speaker identifiers to Speaker objects

        Returns
        -------
            List of utterances
        """
        utterances = []
        turn_counts = {}  # Track turn counts per speaker

        # Process regular sections
        self._process_standard_sections(arg_data, speaker_map, turn_counts, utterances)

        # Process transcript sections if available
        self._process_transcript_sections(
            arg_data, speaker_map, turn_counts, utterances
        )

        # Sort utterances by start time
        utterances.sort(key=lambda u: u.start_time)

        return utterances

    def _process_standard_sections(
        self,
        arg_data: dict,
        speaker_map: dict[str, Speaker],
        turn_counts: dict[str, int],
        utterances: list[Utterance],
    ) -> None:
        """Process standard sections in the argument data.

        Args:
            arg_data: Argument data from API
            speaker_map: Map of speaker identifiers to Speaker objects
            turn_counts: Dictionary to track turn counts per speaker
            utterances: List to append extracted utterances to
        """
        for section in arg_data.get("sections", []):
            for turn in section.get("turns", []):
                spk = turn.get("speaker", {})
                if not spk or "identifier" not in spk:
                    continue

                speaker = speaker_map[spk["identifier"]]
                # Update turn count for this speaker
                turn_counts[speaker.identifier] = (
                    turn_counts.get(speaker.identifier, 0) + 1
                )

                for text_segment in turn.get("text_blocks", []):
                    if text := text_segment.get("text"):
                        with contextlib.suppress(ValueError, TypeError):
                            start_time = float(text_segment.get("start", 0))
                            end_time = float(text_segment.get("stop", 0))
                            if end_time > start_time:  # Only add valid segments
                                utterance = Utterance(
                                    start_time=start_time,
                                    end_time=end_time,
                                    speaker=speaker,
                                    text=text,
                                    section=section.get("name"),
                                    speaker_turn=turn_counts[speaker.identifier],
                                )
                                utterances.append(utterance)

    def _process_transcript_sections(
        self,
        arg_data: dict,
        speaker_map: dict[str, Speaker],
        turn_counts: dict[str, int],
        utterances: list[Utterance],
    ) -> None:
        """Process transcript sections in the argument data.

        Args:
            arg_data: Argument data from API
            speaker_map: Map of speaker identifiers to Speaker objects
            turn_counts: Dictionary to track turn counts per speaker
            utterances: List to append extracted utterances to
        """
        if "transcript" not in arg_data or not isinstance(arg_data["transcript"], dict):
            return

        for section in arg_data["transcript"].get("sections", []):
            section_name = section.get("title", "Unknown Section")
            for turn in section.get("turns", []):
                spk = turn.get("speaker", {})
                if not spk or "identifier" not in spk:
                    continue

                if spk["identifier"] not in speaker_map:
                    # Skip if speaker not in speaker_map
                    continue

                speaker = speaker_map[spk["identifier"]]
                # Update turn count for this speaker
                turn_counts[speaker.identifier] = (
                    turn_counts.get(speaker.identifier, 0) + 1
                )

                # Extract text and timing information
                start_time = float(turn.get("start", 0))
                end_time = float(turn.get("stop", 0))

                # Get text from either text_blocks or directly
                text = self._extract_text_from_turn(turn)

                if text and end_time > start_time:
                    utterance = Utterance(
                        start_time=start_time,
                        end_time=end_time,
                        speaker=speaker,
                        text=text,
                        section=section_name,
                        speaker_turn=turn_counts[speaker.identifier],
                    )
                    utterances.append(utterance)

    def _extract_text_from_turn(self, turn: dict) -> str:
        """Extract text from a turn, handling different formats.

        Args:
            turn: Turn data from the API

        Returns
        -------
            Extracted text
        """
        text = ""
        if "text_blocks" in turn:
            for block in turn.get("text_blocks", []):
                if block_text := block.get("text", ""):
                    text += block_text + " "
            text = text.strip()
        elif "text" in turn:
            text = turn["text"]

        return text

    def _calculate_utterance_metrics(
        self, utterances: list[Utterance], total_duration: float
    ) -> tuple[dict, list[dict]]:
        """Calculate metrics about utterances including gaps between them.

        Args:
            utterances: List of utterances sorted by start time
            total_duration: Total duration of the audio in seconds

        Returns
        -------
            Tuple of (metrics_dict, utterances_with_gaps)
        """
        # Ensure total_duration is in seconds
        # In some cases the API returns duration in milliseconds or bytes
        if (
            total_duration > 100000
        ):  # If duration is unreasonably large, assume it's not in seconds
            # Try to estimate a more reasonable duration using utterances or default to 0
            total_duration = max(u.end_time for u in utterances) if utterances else 0.0

        metrics = {
            "total_duration_seconds": total_duration,
            "total_utterance_time": 0.0,
            "total_non_utterance_time": 0.0,
            "utterance_count": len(utterances),
        }

        # Create a list of utterances with gap information
        utterances_with_gaps = []

        if not utterances:
            metrics["total_non_utterance_time"] = total_duration
            return metrics, utterances_with_gaps

        # Calculate total utterance time and gaps
        prev_end = 0.0
        for i, utterance in enumerate(utterances):
            # Calculate time since previous utterance ended (gap)
            gap_before = max(0.0, utterance.start_time - prev_end)

            # Time for this utterance
            utterance_duration = utterance.end_time - utterance.start_time
            metrics["total_utterance_time"] += utterance_duration

            # Store the gap information with the utterance
            utterance_data = {
                "start_time": utterance.start_time,
                "end_time": utterance.end_time,
                "duration": utterance_duration,
                "speaker": utterance.speaker.identifier,
                "text": utterance.text,
                "section": utterance.section,
                "speaker_turn": utterance.speaker_turn,
                "gap_before": gap_before,
            }

            # Calculate gap after (only for non-last utterances)
            if i < len(utterances) - 1:
                gap_after = max(0.0, utterances[i + 1].start_time - utterance.end_time)
                utterance_data["gap_after"] = gap_after
            else:
                # For the last utterance, calculate gap to the end of the audio
                gap_after = max(0.0, total_duration - utterance.end_time)
                utterance_data["gap_after"] = gap_after

            utterances_with_gaps.append(utterance_data)
            prev_end = utterance.end_time

        # Calculate total non-utterance time
        metrics["total_non_utterance_time"] = (
            total_duration - metrics["total_utterance_time"]
        )

        # Add percentage metrics
        if total_duration > 0:
            metrics["utterance_time_percentage"] = (
                metrics["total_utterance_time"] / total_duration
            ) * 100
            metrics["non_utterance_time_percentage"] = (
                metrics["total_non_utterance_time"] / total_duration
            ) * 100

        return metrics, utterances_with_gaps

    def scrape_case(self, case_id: str) -> OralArgument:
        """Scrape a single case's oral argument.

        Args:
            case_id: The Oyez case identifier

        Returns
        -------
            OralArgument object containing all extracted data
        """
        # Get case metadata
        case_data = OyezAPI.get_case_metadata(case_id)
        if isinstance(case_data, list):
            if not case_data:
                raise ValueError(f"No case data found for case {case_id}")
            case_data = case_data[0]  # Take the first case if multiple returned

        # Get oral argument data
        oral_args = case_data.get("oral_argument_audio", [])
        if not oral_args:
            raise ValueError(f"No oral argument found for case {case_id}")

        # Get full argument data
        arg_data = OyezAPI.get_oral_argument_data(oral_args[0]["href"])

        # Extract speakers and utterances
        speakers, speaker_map = self._extract_speakers(arg_data)
        utterances = self._extract_utterances(arg_data, speaker_map)

        # Get media URL and duration
        audio_url, duration = OyezAPI.find_audio_url(arg_data.get("media_file", []))

        # Use fallback duration if not found in media_file
        if duration == 0.0 and "duration" in arg_data:
            with contextlib.suppress(ValueError, TypeError):
                duration = float(arg_data["duration"])

        # Calculate duration from transcript timestamps if available
        if duration == 0.0 and utterances:
            duration = max(u.end_time for u in utterances)

        if not audio_url:
            raise ValueError(f"Could not find valid audio URL for case {case_id}")

        # Try to get the date from the title field if available
        argument_date = parse_date(arg_data.get("date"))
        if argument_date.year < 1971 and "title" in arg_data:
            # If we have a default date and a title, try to extract from title
            argument_date = parse_date(arg_data.get("title"))

        # Create OralArgument object
        argument = OralArgument(
            case_id=case_id,
            case_name=case_data.get("name", "Unknown"),
            docket_number=case_data.get("docket_number", "Unknown"),
            argument_date=argument_date,
            transcript_url=oral_args[0]["href"],
            audio_url=audio_url,
            duration=duration,
            speakers=speakers,
            utterances=utterances,
            term=case_data.get("term"),
            description=case_data.get("description"),
        )

        return argument

    def process_case(self, case_id: str) -> None:
        """Process a case by downloading audio and extracting utterance segments.

        Args:
            case_id: The Oyez case identifier
        """
        # Scrape the case data
        argument = self.scrape_case(case_id)

        # Create case directory (handle slashes in case IDs)
        safe_case_id = case_id.replace("/", "-")
        case_dir = self.output_dir / safe_case_id
        case_dir.mkdir(exist_ok=True)

        # Download full audio
        audio_path = case_dir / "full_audio.mp3"
        OyezAPI.download_audio(argument.audio_url, str(audio_path))

        # Create segments directory
        segments_dir = case_dir / self.AUDIO_SEGMENT_DIR
        segments_dir.mkdir(exist_ok=True)

        # Calculate utterance metrics
        utterance_metrics, utterances_with_gaps = self._calculate_utterance_metrics(
            argument.utterances, argument.duration
        )

        # Save metadata first, before processing audio segments
        metadata_path = case_dir / self.METADATA_FILE
        with metadata_path.open("w") as f:
            # Convert OralArgument to dict for JSON serialization
            metadata = {
                "case_id": argument.case_id,
                "case_name": argument.case_name,
                "docket_number": argument.docket_number,
                "argument_date": argument.argument_date.isoformat(),
                "transcript_url": argument.transcript_url,
                "audio_url": argument.audio_url,
                "duration": argument.duration,
                "term": argument.term,
                "description": argument.description,
                "speakers": [
                    {
                        "name": s.name,
                        "role": s.role,
                        "identifier": s.identifier,
                    }
                    for s in argument.speakers
                ],
                "utterance_metrics": utterance_metrics,
                "utterances": [
                    {
                        **u,
                        "audio_file": f"{i:04d}_{u['speaker']}.flac",
                    }
                    for i, u in enumerate(utterances_with_gaps)
                ],
            }
            json.dump(metadata, f, indent=2)

        # Now load audio and process segments after metadata is saved
        audio_processor = AudioProcessor()
        audio_processor.load_audio(audio_path)

        # Process each utterance with the loaded audio
        for i, utterance in enumerate(argument.utterances):
            # Use segment number and speaker identifier in filename
            segment_path = segments_dir / f"{i:04d}_{utterance.speaker.identifier}.flac"
            audio_processor.extract_utterance(utterance, segment_path)
