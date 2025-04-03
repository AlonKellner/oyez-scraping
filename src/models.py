"""Data models for the Oyez scraper.

This module contains data classes representing the structure of oral arguments
from the Oyez Supreme Court database.
"""

from dataclasses import dataclass
from datetime import datetime


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
