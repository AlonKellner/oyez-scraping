"""Audio input/output operations for the Oyez scraping project.

This module provides utilities for loading and saving audio files with a focus on
FLAC format. It wraps torchaudio functionality with appropriate error handling and
normalization.
"""

from pathlib import Path

import torch
import torchaudio
from torchaudio.backend.common import AudioMetaData

from oyez_scraping.infrastructure.exceptions.audio_exceptions import (
    AudioProcessingError,
)


def save_flac(
    file_path: str | Path,
    samples: torch.Tensor,
    sample_rate: int,
    bits_per_sample: int = 24,
) -> None:
    """Save audio data to a FLAC file with appropriate normalization.

    Args:
        file_path: Path where the FLAC file will be saved.
        samples: Audio samples tensor of shape [C] or [T].
        sample_rate: Sampling rate of the audio.
        bits_per_sample: Bit depth for the FLAC encoding (default: 24).

    Raises
    ------
        AudioProcessingError: If there's an error during the save operation.
    """
    try:
        # Normalize samples to the range [0, 1]
        samples = samples - samples.min()
        max_val = samples.max()
        # Avoid division by zero if all samples are the same
        if max_val > 0:
            samples = samples / max_val

        # Scale to the appropriate bit depth for FLAC
        max_int_value = 2 ** (bits_per_sample - 1) - 1
        samples = (samples * max_int_value).to(torch.int32)

        # Ensure the path is a string as required by torchaudio
        str_path = str(file_path)

        # Add a channel dimension if not present
        if samples.dim() == 1:
            samples = samples.unsqueeze(0)

        torchaudio.save(
            str_path,
            samples,
            sample_rate,
            format="flac",
            bits_per_sample=bits_per_sample,
            encoding="PCM_S",
        )
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to save FLAC file: {e!s}", file_path=str(file_path)
        ) from e


def load_flac(file_path: str | Path) -> tuple[torch.Tensor, int]:
    """Load audio data from a FLAC file with appropriate denormalization.

    Args:
        file_path: Path to the FLAC file to load.

    Returns
    -------
        Tuple containing:
            - Audio samples tensor
            - Sampling rate

    Raises
    ------
        AudioProcessingError: If there's an error during the load operation.
    """
    try:
        # Ensure the path is a string as required by torchaudio
        str_path = str(file_path)

        # Load the audio without normalization to preserve bit depth
        samples, sample_rate = torchaudio.load(str_path, normalize=False, format="flac")

        # Normalize the samples to float32 in the range [-1, 1]
        # We use a conservative divisor to avoid clipping
        samples = (samples / (2**30)).to(torch.float32)

        return samples, sample_rate
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to load FLAC file: {e!s}", file_path=str(file_path)
        ) from e


def load(
    file_path: str | Path, sample_rate: int | None = None, normalize: bool = True
) -> tuple[torch.Tensor, int]:
    """Load audio data from various audio formats.

    Args:
        file_path: Path to the audio file to load.
        sample_rate: Expected sampling rate. If provided, the function will verify
            that the loaded audio matches this rate.
        normalize: Whether to normalize the audio samples (default: True).

    Returns
    -------
        Tuple containing:
            - Audio samples tensor of shape [1, T] (mono)
            - Sampling rate

    Raises
    ------
        AudioProcessingError: If there's an error during loading or if the sample rate
            doesn't match the expected value.
    """
    try:
        file_path = Path(file_path)

        # Use the appropriate loading method based on file extension
        if file_path.suffix.lower() == ".flac":
            samples, sr = load_flac(file_path)
        else:
            # For other formats, use the standard torchaudio loader
            samples, sr = torchaudio.load(str(file_path))

        # Verify sample rate if expected rate is provided
        if sample_rate is not None and sr != sample_rate:
            raise AudioProcessingError(
                f"Sample rate mismatch. Expected {sample_rate}Hz, got {sr}Hz",
                file_path=str(file_path),
            )

        # Ensure mono audio (take first channel if multi-channel)
        if samples.shape[0] > 1:
            samples = samples[0:1, :]  # Keep dimension for consistency

        # Apply normalization if requested
        if normalize:
            # Z-score normalization
            samples = samples - samples.mean()
            std = samples.std()
            if std > 0:  # Avoid division by zero
                samples = samples / std

        return samples, sr
    except AudioProcessingError:
        # Re-raise AudioProcessingError exceptions directly
        raise
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to load audio file: {e!s}", file_path=str(file_path)
        ) from e


def save(file_path: str | Path, samples: torch.Tensor, sample_rate: int) -> None:
    """Save audio data to various audio formats.

    Args:
        file_path: Path where the audio file will be saved.
        samples: Audio samples tensor.
        sample_rate: Sampling rate of the audio.

    Raises
    ------
        AudioProcessingError: If there's an error during the save operation.
    """
    try:
        file_path = Path(file_path)

        # Add a channel dimension if not present
        if samples.dim() == 1:
            samples = samples.unsqueeze(0)

        # Use the appropriate saving method based on file extension
        if file_path.suffix.lower() == ".flac":
            save_flac(file_path, samples, sample_rate)
        else:
            # For other formats, use the standard torchaudio saver
            torchaudio.save(str(file_path), samples, sample_rate)
    except AudioProcessingError:
        # Re-raise AudioProcessingError exceptions directly
        raise
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to save audio file: {e!s}", file_path=str(file_path)
        ) from e


def get_info(file_path: str | Path) -> AudioMetaData:
    """Get metadata information about an audio file.

    Args:
        file_path: Path to the audio file.

    Returns
    -------
        AudioMetaData object containing file metadata.

    Raises
    ------
        AudioProcessingError: If there's an error retrieving file information.
    """
    try:
        return torchaudio.info(str(file_path))
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to get audio file info: {e!s}", file_path=str(file_path)
        ) from e


def extract_segment(
    file_path: str | Path,
    output_path: str | Path,
    start_time: float,
    end_time: float,
    sample_rate: int | None = None,
) -> None:
    """Extract a segment from an audio file and save it to a new file.

    Args:
        file_path: Path to the source audio file.
        output_path: Path where the segment will be saved.
        start_time: Start time of the segment in seconds.
        end_time: End time of the segment in seconds.
        sample_rate: Optional sample rate override for the output file.

    Raises
    ------
        AudioProcessingError: If there's an error during extraction or if the
            specified time range is invalid.
    """
    if start_time < 0:
        raise AudioProcessingError(
            f"Invalid start time: {start_time}. Must be >= 0", file_path=str(file_path)
        )

    if end_time <= start_time:
        raise AudioProcessingError(
            f"Invalid time range: end time ({end_time}) must be > start time ({start_time})",
            file_path=str(file_path),
        )

    try:
        # Load the audio file
        samples, sr = load(file_path, sample_rate=sample_rate, normalize=False)

        # Calculate sample indices for the segment
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)

        # Validate sample indices
        if end_sample > samples.shape[1]:
            raise AudioProcessingError(
                f"End time ({end_time}s) exceeds audio duration ({samples.shape[1] / sr:.2f}s)",
                file_path=str(file_path),
            )

        # Extract the segment
        segment = samples[:, start_sample:end_sample]

        # Save the segment
        save(output_path, segment, sr)
    except AudioProcessingError:
        # Re-raise AudioProcessingError exceptions directly
        raise
    except Exception as e:
        raise AudioProcessingError(
            f"Failed to extract audio segment: {e!s}", file_path=str(file_path)
        ) from e
