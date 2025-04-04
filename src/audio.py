"""Audio processing utilities for the Oyez scraper.

This module provides functions for processing and manipulating audio files
from the Oyez Supreme Court oral arguments.
"""

import json
from pathlib import Path

import torch
import torchaudio

from src.models import Utterance


class AudioProcessor:
    """Audio processing functionality for oral arguments."""

    def __init__(self) -> None:
        """Initialize the AudioProcessor."""
        self.waveform = None
        self.sample_rate = None
        self.audio_info = {}

    def load_audio(self, audio_path: Path) -> None:
        """Load the audio file into memory.

        Args:
            audio_path: Path to the audio file to load
        """
        # Get audio metadata using torchaudio.info
        info = torchaudio.info(audio_path)

        # Load the audio file
        self.waveform, self.sample_rate = torchaudio.load(audio_path)

        # Store audio metadata
        self.audio_info = {
            "file_path": str(audio_path),
            "file_format": audio_path.suffix[1:],  # Remove the dot from the extension
            "sample_rate": info.sample_rate,
            "channels": info.num_channels,
            "duration_seconds": info.num_frames / info.sample_rate,
            "total_samples": info.num_frames,
            "bits_per_sample": getattr(info, "bits_per_sample", None),
            "encoding": getattr(info, "encoding", None),
        }

        # Save audio metadata
        metadata_path = audio_path.parent / "audio_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self.audio_info, f, indent=2)

    def extract_utterance(self, utterance: Utterance, output_path: Path) -> None:
        """Extract utterance from the loaded audio and save to file.

        Args:
            utterance: Utterance to extract
            output_path: Where to save the audio segment
        """
        if self.waveform is None or self.sample_rate is None:
            raise ValueError("Audio not loaded. Call load_audio() first.")

        start_frame = int(utterance.start_time * self.sample_rate)
        end_frame = int(utterance.end_time * self.sample_rate)

        # Ensure frames are within bounds
        end_frame = min(end_frame, self.waveform.shape[1])

        if start_frame >= end_frame or start_frame >= self.waveform.shape[1]:
            # Create a silent segment if out of bounds
            segment = torch.zeros(1, self.sample_rate)  # 1 second of silence
        else:
            segment = self.waveform[:, start_frame:end_frame]

        # Save as FLAC format
        output_path = output_path.with_suffix(".flac")
        torchaudio.save(str(output_path), segment, self.sample_rate, format="flac")

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
        # Load audio with torchaudio
        waveform, sample_rate = torchaudio.load(audio_path)
        start_frame = int(utterance.start_time * sample_rate)
        end_frame = int(utterance.end_time * sample_rate)

        # Ensure frames are within bounds
        end_frame = min(end_frame, waveform.shape[1])

        if start_frame >= end_frame or start_frame >= waveform.shape[1]:
            # Create a silent segment if out of bounds
            segment = torch.zeros(1, sample_rate)  # 1 second of silence
        else:
            segment = waveform[:, start_frame:end_frame]

        # Save as FLAC format
        output_path = output_path.with_suffix(".flac")
        torchaudio.save(str(output_path), segment, sample_rate, format="flac")
