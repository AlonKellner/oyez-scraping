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
        (self.output_dir / self.AUDIO_SEGMENT_DIR).mkdir(exist_ok=True)

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
        print("DEBUG: Extracting speakers from:", json.dumps(arg_data, indent=2)[:1000])
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

        print(f"DEBUG: Found {len(speakers)} speakers")
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

        return utterances

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

        # Create OralArgument object
        argument = OralArgument(
            case_id=case_id,
            case_name=case_data.get("name", "Unknown"),
            docket_number=case_data.get("docket_number", "Unknown"),
            argument_date=parse_date(arg_data.get("date")),
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

        # Extract individual utterances
        segments_dir = case_dir / self.AUDIO_SEGMENT_DIR
        segments_dir.mkdir(exist_ok=True)

        for i, utterance in enumerate(argument.utterances):
            # Use segment number and speaker identifier in filename
            segment_path = segments_dir / f"{i:04d}_{utterance.speaker.identifier}.wav"
            AudioProcessor.extract_utterance_audio(audio_path, utterance, segment_path)

        # Save metadata
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
                "utterances": [
                    {
                        "start_time": u.start_time,
                        "end_time": u.end_time,
                        "speaker": u.speaker.identifier,
                        "text": u.text,
                        "section": u.section,
                        "speaker_turn": u.speaker_turn,
                        "audio_file": f"{i:04d}_{u.speaker.identifier}.wav",
                    }
                    for i, u in enumerate(argument.utterances)
                ],
            }
            json.dump(metadata, f, indent=2)
