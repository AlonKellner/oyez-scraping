"""Integration tests for the audio_io module.

These tests interact with the actual file system and test real audio file operations.
"""

import os
import tempfile

import pytest
import torch

from oyez_scraping.infrastructure.exceptions.audio_exceptions import (
    AudioProcessingError,
)
from oyez_scraping.infrastructure.processing import audio_io


@pytest.fixture
def sample_audio() -> tuple[torch.Tensor, int]:
    """Create a sample audio signal for testing."""
    sample_rate = 44100
    duration_seconds = 1.0
    t = torch.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    # Generate a 440 Hz sine wave
    samples = torch.sin(2 * torch.pi * 440 * t)
    return samples, sample_rate


class TestAudioSaveLoad:
    """Integration tests for saving and loading audio files."""

    def test_save_load_flac(self, sample_audio: tuple[torch.Tensor, int]) -> None:
        """Test saving and loading a FLAC file."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.flac")

            # Save the audio file
            audio_io.save(file_path, samples, sample_rate)

            # Verify the file exists
            assert os.path.exists(file_path)

            # Load the audio file
            loaded_samples, loaded_rate = audio_io.load(file_path, normalize=False)

            # Verify sample rate matches
            assert loaded_rate == sample_rate

            # Verify samples are similar (not exact due to compression)
            # Just check shape for now
            assert loaded_samples.shape[1] == samples.shape[0]

    def test_save_load_mp3(self, sample_audio: tuple[torch.Tensor, int]) -> None:
        """Test saving and loading an MP3 file."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.mp3")

            # Save the audio file
            audio_io.save(file_path, samples, sample_rate)

            # Verify the file exists
            assert os.path.exists(file_path)

            # Load the audio file
            loaded_samples, loaded_rate = audio_io.load(file_path, normalize=False)

            # Verify sample rate matches
            assert loaded_rate == sample_rate

            # Verify samples are similar (not exact due to compression)
            # Just check shape for now
            assert loaded_samples.shape[1] == samples.shape[0]

    def test_extract_segment(self, sample_audio: tuple[torch.Tensor, int]) -> None:
        """Test extracting a segment from an audio file."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.flac")
            output_path = os.path.join(temp_dir, "output.flac")

            # Save the full audio file
            audio_io.save(input_path, samples, sample_rate)

            # Extract a segment (0.2s to 0.5s)
            start_time = 0.2
            end_time = 0.5
            audio_io.extract_segment(input_path, output_path, start_time, end_time)

            # Verify the output file exists
            assert os.path.exists(output_path)

            # Load the segment
            segment, segment_rate = audio_io.load(output_path, normalize=False)

            # Verify sample rate
            assert segment_rate == sample_rate

            # Verify segment length (should be approximately (end-start) * sample_rate samples)
            expected_length = int((end_time - start_time) * sample_rate)
            # Allow for small differences due to encoding/decoding
            assert abs(segment.shape[1] - expected_length) <= 5

    def test_get_info(self, sample_audio: tuple[torch.Tensor, int]) -> None:
        """Test getting audio file metadata."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.flac")

            # Save the audio file
            audio_io.save(file_path, samples, sample_rate)

            # Get the file info
            info = audio_io.get_info(file_path)

            # Verify sample rate in metadata
            assert info.sample_rate == sample_rate

    def test_wav_to_flac_conversion(
        self, sample_audio: tuple[torch.Tensor, int]
    ) -> None:
        """Test conversion from WAV to FLAC and verify quality is preserved."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create paths for our test files
            wav_path = os.path.join(temp_dir, "test.wav")
            flac_path = os.path.join(temp_dir, "test.flac")

            # First save as WAV format
            audio_io.save(wav_path, samples, sample_rate)

            # Verify WAV file exists
            assert os.path.exists(wav_path)

            # Load the WAV file with normalization to standardize the audio
            # This helps ensure consistent comparison between formats
            wav_samples, wav_rate = audio_io.load(wav_path, normalize=True)

            # Now save as FLAC
            audio_io.save(flac_path, wav_samples, wav_rate)

            # Verify FLAC file exists
            assert os.path.exists(flac_path)

            # Load the FLAC file with normalization for consistent comparison
            flac_samples, flac_rate = audio_io.load(flac_path, normalize=True)

            # Verify sample rates match
            assert flac_rate == wav_rate

            # Verify sample shapes match
            assert flac_samples.shape == wav_samples.shape

            # Verify basic audio properties are preserved between formats
            # 1. Check if non-zero samples exist in both
            assert torch.sum(torch.abs(wav_samples)) > 0
            assert torch.sum(torch.abs(flac_samples)) > 0

            # 2. Verify both have similar energy profile (not empty/silent)
            wav_energy = torch.sum(wav_samples**2)
            flac_energy = torch.sum(flac_samples**2)
            assert wav_energy > 0
            assert flac_energy > 0

            # 3. Verify audio duration is preserved (sample count)
            assert wav_samples.shape[1] == flac_samples.shape[1]

            # Calculate maximum absolute difference between samples to verify
            # that normalization helps produce consistent results across formats
            max_diff = torch.max(torch.abs(flac_samples - wav_samples))

            # The difference should be minimal when both samples are normalized,
            # ensuring high-quality conversion between formats
            assert max_diff < 0.001, f"Max difference between WAV and FLAC: {max_diff}"


class TestErrorHandling:
    """Integration tests for error handling in audio_io."""

    def test_load_nonexistent_file(self) -> None:
        """Test loading a non-existent file raises appropriate error."""
        with pytest.raises(AudioProcessingError) as excinfo:
            audio_io.load("nonexistent_file.mp3")

        assert "Failed to load audio file" in str(excinfo.value)
        assert "nonexistent_file.mp3" in str(excinfo.value)

    def test_invalid_segment_extraction(
        self, sample_audio: tuple[torch.Tensor, int]
    ) -> None:
        """Test extracting an invalid segment raises appropriate error."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.flac")
            output_path = os.path.join(temp_dir, "output.flac")

            # Save the full audio file (1 second duration)
            audio_io.save(input_path, samples, sample_rate)

            # Try to extract beyond the file duration
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.extract_segment(input_path, output_path, 0.5, 1.5)

            assert "End time" in str(excinfo.value)
            assert "exceeds audio duration" in str(excinfo.value)

    def test_sample_rate_mismatch(self, sample_audio: tuple[torch.Tensor, int]) -> None:
        """Test that attempting to load with an incorrect sample rate raises an error."""
        samples, sample_rate = sample_audio

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.flac")

            # Save the audio file
            audio_io.save(file_path, samples, sample_rate)

            # Try to load with a different sample rate
            expected_rate = sample_rate * 2  # Deliberately wrong
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.load(file_path, sample_rate=expected_rate)

            assert "Sample rate mismatch" in str(excinfo.value)
            assert str(expected_rate) in str(excinfo.value)
            assert str(sample_rate) in str(excinfo.value)
