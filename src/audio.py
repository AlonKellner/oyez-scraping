"""Audio processing utilities for the Oyez scraper.

This module provides functions for processing and manipulating audio files
from the Oyez Supreme Court oral arguments.
"""

from pathlib import Path

import torchaudio

from src.models import Utterance


class AudioProcessor:
    """Audio processing functionality for oral arguments."""

    @staticmethod
    def extract_utterance_audio(
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
