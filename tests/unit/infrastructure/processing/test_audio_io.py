"""Unit tests for the audio_io module."""

import os
import tempfile
from unittest import mock

import pytest
import torch

from oyez_scraping.infrastructure.exceptions.audio_exceptions import (
    AudioProcessingError,
)
from oyez_scraping.infrastructure.processing import audio_io


class TestSaveFlac:
    """Tests for save_flac function."""

    def test_save_flac_normal_case(self) -> None:
        """Test normal operation of save_flac."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.flac")

            # Create a simple sine wave
            sample_rate = 44100
            samples = torch.sin(torch.linspace(0, 1000, sample_rate))

            # Mock torchaudio.save to prevent actual file writing in unit test
            with mock.patch("torchaudio.save") as mock_save:
                audio_io.save_flac(file_path, samples, sample_rate)

                # Verify the function was called with expected args
                mock_save.assert_called_once()
                # Verify that format is flac
                _, kwargs = mock_save.call_args
                assert kwargs["format"] == "flac"
                assert kwargs["bits_per_sample"] == 24

    def test_save_flac_exception_handling(self) -> None:
        """Test that exceptions are properly caught and converted to AudioProcessingError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.flac")
            samples = torch.zeros(1000)
            sample_rate = 44100

            # Mock torchaudio.save to raise an exception
            with mock.patch("torchaudio.save", side_effect=RuntimeError("Test error")):
                with pytest.raises(AudioProcessingError) as excinfo:
                    audio_io.save_flac(file_path, samples, sample_rate)

                # Verify the exception contains the file path and original error message
                assert "Failed to save FLAC file" in str(excinfo.value)
                assert "Test error" in str(excinfo.value)
                assert file_path in str(excinfo.value)


class TestLoadFlac:
    """Tests for load_flac function."""

    def test_load_flac_normal_case(self) -> None:
        """Test normal operation of load_flac."""
        # Mock torchaudio.load to return a known tensor and sample rate
        mock_samples = torch.zeros((1, 1000), dtype=torch.int32)
        mock_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, mock_sr)):
            samples, sr = audio_io.load_flac("test.flac")

            # Verify the return values
            assert sr == mock_sr
            assert samples.shape == mock_samples.shape
            assert samples.dtype == torch.float32  # Should convert to float32

    def test_load_flac_exception_handling(self) -> None:
        """Test that exceptions are properly caught and converted to AudioProcessingError."""
        # Mock torchaudio.load to raise an exception
        with mock.patch("torchaudio.load", side_effect=RuntimeError("Test error")):
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.load_flac("test.flac")

            # Verify the exception contains the file path and original error message
            assert "Failed to load FLAC file" in str(excinfo.value)
            assert "Test error" in str(excinfo.value)
            assert "test.flac" in str(excinfo.value)


class TestLoad:
    """Tests for the general load function."""

    def test_load_flac_file(self) -> None:
        """Test loading a FLAC file."""
        # Mock load_flac to return known values
        mock_samples = torch.zeros((1, 1000), dtype=torch.float32)
        mock_sr = 44100

        with mock.patch(
            "oyez_scraping.infrastructure.processing.audio_io.load_flac",
            return_value=(mock_samples, mock_sr),
        ):
            samples, sr = audio_io.load("test.flac", sample_rate=mock_sr)

            # Verify the return values
            assert sr == mock_sr
            assert samples.shape == mock_samples.shape

    def test_load_other_format(self) -> None:
        """Test loading a non-FLAC file."""
        # Mock torchaudio.load to return known values
        mock_samples = torch.zeros((1, 1000), dtype=torch.float32)
        mock_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, mock_sr)):
            samples, sr = audio_io.load("test.mp3", sample_rate=mock_sr)

            # Verify the return values
            assert sr == mock_sr
            assert samples.shape == mock_samples.shape

    def test_load_sample_rate_mismatch(self) -> None:
        """Test that an exception is raised when sample rate doesn't match expected."""
        # Mock torchaudio.load to return a different sample rate than expected
        mock_samples = torch.zeros((1, 1000), dtype=torch.float32)
        actual_sr = 22050
        expected_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, actual_sr)):
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.load("test.mp3", sample_rate=expected_sr)

            # Verify the exception message contains rate information
            assert "Sample rate mismatch" in str(excinfo.value)
            assert str(expected_sr) in str(excinfo.value)
            assert str(actual_sr) in str(excinfo.value)

    def test_load_multichannel_audio(self) -> None:
        """Test loading multi-channel audio to ensure it's converted to mono."""
        # Mock torchaudio.load to return a multi-channel audio
        mock_samples = torch.zeros((2, 1000), dtype=torch.float32)
        mock_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, mock_sr)):
            samples, sr = audio_io.load("test.mp3")

            # Verify the return values
            assert sr == mock_sr
            assert samples.shape[0] == 1  # Should be mono (single channel)
            assert samples.shape[1] == 1000  # Length should be unchanged

    def test_load_normalization(self) -> None:
        """Test that normalization is applied when requested."""
        # Create a simple tensor with non-zero mean and std
        mock_samples = torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0]])
        mock_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, mock_sr)):
            samples, _ = audio_io.load("test.mp3", normalize=True)

            # Verify normalization was applied (mean ≈ 0, std ≈ 1)
            assert torch.isclose(samples.mean(), torch.tensor(0.0), atol=1e-6)
            assert torch.isclose(samples.std(), torch.tensor(1.0), atol=1e-6)

    def test_load_no_normalization(self) -> None:
        """Test that normalization is not applied when not requested."""
        # Create a simple tensor
        mock_samples = torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0]])
        mock_sr = 44100

        with mock.patch("torchaudio.load", return_value=(mock_samples, mock_sr)):
            samples, _ = audio_io.load("test.mp3", normalize=False)

            # Verify normalization was not applied (original values preserved)
            assert torch.allclose(samples, mock_samples)


class TestSave:
    """Tests for the general save function."""

    def test_save_flac_file(self) -> None:
        """Test saving to a FLAC file calls save_flac."""
        with mock.patch(
            "oyez_scraping.infrastructure.processing.audio_io.save_flac"
        ) as mock_save_flac:
            samples = torch.zeros(1000)
            sample_rate = 44100
            audio_io.save("test.flac", samples, sample_rate)

            # Verify save_flac was called
            mock_save_flac.assert_called_once()

    def test_save_other_format(self) -> None:
        """Test saving to a non-FLAC file calls torchaudio.save."""
        with mock.patch("torchaudio.save") as mock_ta_save:
            samples = torch.zeros(1000)
            sample_rate = 44100
            audio_io.save("test.mp3", samples, sample_rate)

            # Verify torchaudio.save was called
            mock_ta_save.assert_called_once()

    def test_save_adds_channel_dimension(self) -> None:
        """Test that a channel dimension is added to 1D tensors."""
        with mock.patch("torchaudio.save") as mock_save:
            samples = torch.zeros(1000)  # 1D tensor
            sample_rate = 44100
            audio_io.save("test.mp3", samples, sample_rate)

            # Verify save was called with a 2D tensor
            args, _ = mock_save.call_args
            assert args[1].dim() == 2
            assert args[1].shape[0] == 1  # First dimension should be 1 (one channel)
            assert (
                args[1].shape[1] == 1000
            )  # Second dimension should be original length

    def test_save_exception_handling(self) -> None:
        """Test that exceptions are properly caught and converted to AudioProcessingError."""
        # Mock save_flac to raise an exception
        with mock.patch(
            "oyez_scraping.infrastructure.processing.audio_io.save_flac",
            side_effect=RuntimeError("Test error"),
        ):
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.save("test.flac", torch.zeros(1000), 44100)

            # Verify the exception contains the file path and original error message
            assert "Failed to save audio file" in str(excinfo.value)
            assert "Test error" in str(excinfo.value)
            assert "test.flac" in str(excinfo.value)


class TestGetInfo:
    """Tests for get_info function."""

    def test_get_info_normal_case(self) -> None:
        """Test normal operation of get_info."""
        # Mock torchaudio.info to return a mock object
        mock_metadata = mock.MagicMock()
        mock_metadata.sample_rate = 44100

        with mock.patch("torchaudio.info", return_value=mock_metadata):
            metadata = audio_io.get_info("test.mp3")

            # Verify the return value
            assert metadata == mock_metadata

    def test_get_info_exception_handling(self) -> None:
        """Test that exceptions are properly caught and converted to AudioProcessingError."""
        # Mock torchaudio.info to raise an exception
        with mock.patch("torchaudio.info", side_effect=RuntimeError("Test error")):
            with pytest.raises(AudioProcessingError) as excinfo:
                audio_io.get_info("test.mp3")

            # Verify the exception contains the file path and original error message
            assert "Failed to get audio file info" in str(excinfo.value)
            assert "Test error" in str(excinfo.value)
            assert "test.mp3" in str(excinfo.value)


class TestExtractSegment:
    """Tests for extract_segment function."""

    def test_extract_segment_normal_case(self) -> None:
        """Test normal operation of extract_segment."""
        # Mock load and save to avoid actual file operations
        mock_samples = torch.zeros((1, 44100))  # 1 second of audio
        mock_sr = 44100

        # Use a single with statement with multiple contexts instead of nested with statements
        with (
            mock.patch(
                "oyez_scraping.infrastructure.processing.audio_io.load",
                return_value=(mock_samples, mock_sr),
            ) as mock_load,
            mock.patch(
                "oyez_scraping.infrastructure.processing.audio_io.save"
            ) as mock_save,
        ):
            # Extract a 0.5 second segment
            audio_io.extract_segment("input.mp3", "output.mp3", 0.2, 0.7)

            # Verify load and save were called appropriately
            mock_load.assert_called_once()
            mock_save.assert_called_once()

            # Verify the segment passed to save has the correct length
            save_args, _ = mock_save.call_args
            segment = save_args[1]
            expected_length = int(0.5 * mock_sr)  # (0.7 - 0.2) * 44100

            # Allow for small differences due to floating point calculations
            # when converting times to sample indices
            assert abs(segment.shape[1] - expected_length) <= 1

    def test_extract_segment_invalid_start_time(self) -> None:
        """Test that an exception is raised for negative start time."""
        with pytest.raises(AudioProcessingError) as excinfo:
            audio_io.extract_segment("input.mp3", "output.mp3", -1.0, 0.5)

        # Verify the exception message
        assert "Invalid start time" in str(excinfo.value)

    def test_extract_segment_invalid_time_range(self) -> None:
        """Test that an exception is raised when end time <= start time."""
        with pytest.raises(AudioProcessingError) as excinfo:
            audio_io.extract_segment("input.mp3", "output.mp3", 0.5, 0.5)  # Equal times

        assert "Invalid time range" in str(excinfo.value)

        with pytest.raises(AudioProcessingError) as excinfo:
            audio_io.extract_segment("input.mp3", "output.mp3", 0.7, 0.5)  # End < start

        assert "Invalid time range" in str(excinfo.value)

    def test_extract_segment_exceeds_duration(self) -> None:
        """Test that an exception is raised when the segment exceeds audio duration."""
        # Mock load to return a 1-second audio
        mock_samples = torch.zeros((1, 44100))  # 1 second of audio
        mock_sr = 44100

        with mock.patch(
            "oyez_scraping.infrastructure.processing.audio_io.load",
            return_value=(mock_samples, mock_sr),
        ):
            with pytest.raises(AudioProcessingError) as excinfo:
                # Try to extract beyond the 1-second duration
                audio_io.extract_segment("input.mp3", "output.mp3", 0.5, 1.5)

            # Verify the exception message
            assert "End time" in str(excinfo.value)
            assert "exceeds audio duration" in str(excinfo.value)
