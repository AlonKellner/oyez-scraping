"""Oyez Supreme Court oral arguments scraper.

This module provides functionality to scrape oral arguments from the Oyez project website
and create an ASR (Automatic Speech Recognition) dataset.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
import torchaudio


@dataclass
class Speaker:
    """Represents a speaker in an oral argument."""

    name: str
    role: str
    identifier: str


@dataclass
class Utterance:
    """Represents a single utterance in an oral argument."""

    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    speaker: Speaker
    text: str
    section: str | None = None  # E.g., "Opening", "Rebuttal", etc.
    speaker_turn: int | None = None  # Sequential turn number for the speaker


@dataclass
class OralArgument:
    """Represents a complete oral argument session."""

    case_id: str
    case_name: str
    docket_number: str
    argument_date: datetime
    transcript_url: str
    audio_url: str
    duration: float  # Duration in seconds
    speakers: list[Speaker]
    utterances: list[Utterance]
    term: str | None = None
    description: str | None = None


class OyezScraper:
    """Scraper for Oyez Supreme Court oral arguments."""

    BASE_URL = "https://api.oyez.org/cases"
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

    def _get_case_metadata(self, case_id: str) -> dict:
        """Fetch case metadata from Oyez API.

        Args:
            case_id: The Oyez case identifier

        Returns
        -------
            Dict containing case metadata
        """
        url = f"{self.BASE_URL}/{case_id}"
        response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get_oral_argument_data(self, argument_url: str) -> dict:
        """Fetch oral argument data including transcript and timing info.

        Args:
            argument_url: URL to the oral argument JSON data

        Returns
        -------
            Dict containing oral argument data
        """
        response = requests.get(
            argument_url, headers={"Accept": "application/json"}, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _download_audio(self, audio_url: str, output_path: Path) -> None:
        """Download the oral argument audio file.

        Args:
            audio_url: URL to the audio file
            output_path: Where to save the audio file
        """
        response = requests.get(audio_url, stream=True, timeout=30)
        response.raise_for_status()

        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def _extract_utterance_audio(
        self,
        audio_path: Path,
        utterance: Utterance,
        output_path: Path,
    ) -> None:
        """Extract utterance audio segment and save to file.

        Args:
            audio_path: Path to the complete audio file
            utterance: Utterance to extract
            output_path: Where to save the audio segment
        """
        waveform, sample_rate = torchaudio.load(audio_path)
        start_frame = int(utterance.start_time * sample_rate)
        end_frame = int(utterance.end_time * sample_rate)
        segment = waveform[:, start_frame:end_frame]
        torchaudio.save(str(output_path), segment, sample_rate)

    def scrape_case(self, case_id: str) -> OralArgument:
        """Scrape a single case's oral argument.

        Args:
            case_id: The Oyez case identifier

        Returns
        -------
            OralArgument object containing all extracted data
        """
        # Get case metadata
        case_data = self._get_case_metadata(case_id)
        if isinstance(case_data, list):
            if not case_data:
                raise ValueError(f"No case data found for case {case_id}")
            case_data = case_data[0]  # Take the first case if multiple returned

        # Get oral argument data
        oral_args = case_data.get("oral_argument_audio", [])
        if not oral_args:
            raise ValueError(f"No oral argument found for case {case_id}")

        # For this implementation, we'll use the first oral argument
        arg_data = self._get_oral_argument_data(oral_args[0]["href"])

        # Extract speakers
        speakers = []
        speaker_map = {}
        for section in arg_data.get("sections", []):
            for turn in section.get("turns", []):
                spk = turn.get("speaker", {})
                if spk.get("identifier") not in speaker_map:
                    speaker = Speaker(
                        name=spk.get("name", "Unknown"),
                        role=spk.get("role", "Unknown"),
                        identifier=spk.get("identifier", "unknown"),
                    )
                    speakers.append(speaker)
                    speaker_map[speaker.identifier] = speaker

        # Extract utterances
        utterances = []
        for section in arg_data.get("sections", []):
            section_name = section.get("name")
            for turn in section.get("turns", []):
                spk = turn.get("speaker", {})
                speaker = speaker_map[spk.get("identifier")]

                for text_segment in turn.get("text_blocks", []):
                    if text := text_segment.get("text"):
                        start = float(text_segment.get("start", 0))
                        end = float(text_segment.get("stop", 0))
                        utterance = Utterance(
                            start_time=start,
                            end_time=end,
                            speaker=speaker,
                            text=text,
                            section=section_name,
                        )
                        utterances.append(utterance)

        # Create OralArgument object
        argument = OralArgument(
            case_id=case_id,
            case_name=case_data.get("name", "Unknown"),
            docket_number=case_data.get("docket_number", "Unknown"),
            argument_date=datetime.fromisoformat(arg_data.get("date", "1970-01-01")),
            transcript_url=oral_args[0]["href"],
            audio_url=arg_data.get("media_file", {}).get("href", ""),
            duration=float(arg_data.get("duration", 0)),
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

        # Create case directory
        case_dir = self.output_dir / case_id
        case_dir.mkdir(exist_ok=True)

        # Download full audio
        audio_path = case_dir / "full_audio.mp3"
        self._download_audio(argument.audio_url, audio_path)

        # Extract individual utterances
        segments_dir = case_dir / self.AUDIO_SEGMENT_DIR
        segments_dir.mkdir(exist_ok=True)

        for i, utterance in enumerate(argument.utterances):
            segment_path = segments_dir / f"segment_{i:04d}.wav"
            self._extract_utterance_audio(audio_path, utterance, segment_path)

        # Save metadata
        metadata = {
            "case_id": argument.case_id,
            "case_name": argument.case_name,
            "docket_number": argument.docket_number,
            "argument_date": argument.argument_date.isoformat(),
            "duration": argument.duration,
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
                    "audio_file": f"segments/segment_{i:04d}.wav",
                }
                for i, u in enumerate(argument.utterances)
            ],
        }

        with (case_dir / self.METADATA_FILE).open("w") as f:
            json.dump(metadata, f, indent=2)
