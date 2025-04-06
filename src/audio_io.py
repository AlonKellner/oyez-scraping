from pathlib import Path
import torch
import torchaudio as ta


def ta_save_flac(flac_path: str, samples: torch.Tensor, sample_rate: int) -> None:
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
    samples, sr = ta.load(flac_path, normalize=False, format="flac")
    samples = (samples / (2**30 - 2**24)).to(torch.float32)
    return samples, sr


def load(audio_path: str, sample_rate: int) -> torch.Tensor:
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
    if Path(audio_path).suffix == ".flac":
        ta_save_flac(audio_path, samples, sample_rate)
    else:
        ta.save(audio_path, samples[None, :], sample_rate)


def info(audio_path: str) -> ta.AudioMetaData:
    return ta.info(audio_path)
