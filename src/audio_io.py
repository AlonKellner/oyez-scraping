"""Legacy audio input/output module (DEPRECATED).

This module is deprecated and has been replaced by
oyez_scraping.infrastructure.processing.audio_io module.

This module provided basic audio loading and saving functionality using torchaudio.
It is kept for reference purposes only and should not be used in new code.
"""

from pathlib import Path

import torch
import torchaudio as ta


def ta_save_flac(flac_path: str, samples: torch.Tensor, sample_rate: int) -> None:
    """Save audio samples to a FLAC file with appropriate normalization.

    Args:
        flac_path: Path where the FLAC file will be saved.
        samples: Audio samples tensor.
        sample_rate: Sampling rate of the audio.
    """
    samples = samples - samples.min()
    samples = samples / samples.max()
    samples = (samples * (2**31 - 2**24)).to(torch.int32)
    ta.save(
        str(flac_path),
        samples[None, :],
        sample_rate,
        format="flac",
        bits_per_sample=24,
        encoding="PCM_S",
    )


def ta_load_flac(flac_path: str) -> tuple[torch.Tensor, int]:
    """Load audio samples from a FLAC file with appropriate denormalization.

    Args:
        flac_path: Path to the FLAC file to load.

    Returns
    -------
        Tuple containing audio samples tensor and sampling rate.
    """
    samples, sr = ta.load(flac_path, normalize=False, format="flac")
    samples = (samples / (2**30 - 2**24)).to(torch.float32)
    return samples, sr


def load(audio_path: str, sample_rate: int) -> torch.Tensor:
    """Load audio samples from a file with verification of the sampling rate.

    Args:
        audio_path: Path to the audio file to load.
        sample_rate: Expected sampling rate for verification.

    Returns
    -------
        Normalized audio samples tensor.

    Raises
    ------
        AssertionError: If the sampling rate doesn't match the expected value or
            if the audio is not mono.
    """
    if Path(audio_path).suffix == ".flac":
        samples, sr = ta_load_flac(audio_path)
    else:
        samples, sr = ta.load(audio_path)
    assert sr == sample_rate
    assert samples.shape[0] == 1
    samples = samples[0, :]
    samples = samples - samples.mean()
    samples = samples / samples.std()
    return samples


def save(audio_path: str, samples: torch.Tensor, sample_rate: int) -> None:
    """Save audio samples to a file with format detection based on file extension.

    Args:
        audio_path: Path where the audio file will be saved.
        samples: Audio samples tensor.
        sample_rate: Sampling rate of the audio.
    """
    if Path(audio_path).suffix == ".flac":
        ta_save_flac(audio_path, samples, sample_rate)
    else:
        ta.save(audio_path, samples[None, :], sample_rate)


def info(audio_path: str) -> ta.AudioMetaData:
    """Get metadata information about an audio file.

    Args:
        audio_path: Path to the audio file.

    Returns
    -------
        AudioMetaData object containing file metadata.
    """
    return ta.info(audio_path)
