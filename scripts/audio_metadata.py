from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from pathlib import Path


def _quality(duration: float | None, sample_rate_hz: int | None, loudness_db: float | None) -> str:
    if duration is None or sample_rate_hz is None:
        return "unknown"
    if duration < 2:
        return "poor - too short"
    if sample_rate_hz < 16000:
        return "poor - low sample rate"
    if loudness_db is not None and loudness_db < -45:
        return "poor - very quiet"
    if loudness_db is not None and loudness_db > -3:
        return "poor - likely clipped"
    if loudness_db is not None and loudness_db < -35:
        return "okay - quiet"
    return "good"


def _wav_metadata(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
        duration = frames / sample_rate if sample_rate else None
        raw = wav.readframes(frames)

    max_value = float(2 ** (sample_width * 8 - 1))
    sample_count = len(raw) // sample_width if sample_width else 0
    loudness_db = None
    if sample_width == 2 and sample_count:
        total = 0.0
        for i in range(0, len(raw), 2):
            sample = int.from_bytes(raw[i : i + 2], "little", signed=True)
            total += sample * sample
        rms = math.sqrt(total / sample_count)
        loudness_db = round(20 * math.log10(max(rms / max_value, 1e-12)), 2)

    bitrate = round((sample_rate * channels * sample_width * 8) / 1000, 2) if sample_rate else None
    return {
        "duration_seconds": round(duration, 2) if duration is not None else None,
        "sample_rate_khz": round(sample_rate / 1000, 2) if sample_rate else None,
        "bitrate_kbps": bitrate,
        "loudness_db": loudness_db,
        "quality_estimate": _quality(duration, sample_rate, loudness_db),
    }


def _ffprobe_metadata(path: Path) -> dict | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    duration = float(data.get("format", {}).get("duration") or audio_stream.get("duration") or 0) or None
    sample_rate = int(audio_stream.get("sample_rate") or 0) or None
    bitrate = int(data.get("format", {}).get("bit_rate") or audio_stream.get("bit_rate") or 0) / 1000 or None
    return {
        "duration_seconds": round(duration, 2) if duration else None,
        "sample_rate_khz": round(sample_rate / 1000, 2) if sample_rate else None,
        "bitrate_kbps": round(bitrate, 2) if bitrate else None,
        "loudness_db": None,
        "quality_estimate": _quality(duration, sample_rate, None),
    }


def extract_audio_metadata(path: str | Path) -> dict:
    audio_path = Path(path)
    try:
        return _wav_metadata(audio_path)
    except wave.Error:
        probed = _ffprobe_metadata(audio_path)
        if probed:
            return probed
        return {
            "duration_seconds": None,
            "sample_rate_khz": None,
            "bitrate_kbps": None,
            "loudness_db": None,
            "quality_estimate": "unknown - upload WAV or install ffmpeg for this format",
        }
