from __future__ import annotations

import math
import sqlite3
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audio_metadata import extract_audio_metadata
from database import DB_PATH, connect
from normalize import normalize_phone


def make_test_wav(path: Path) -> None:
    sample_rate = 16000
    duration = 2.2
    frames = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(frames):
            sample = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wav.writeframes(struct.pack("<h", sample))


def main() -> None:
    conn = connect(DB_PATH)
    people_count = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
    issues_count = conn.execute("SELECT COUNT(*) AS c FROM data_quality_issues").fetchone()["c"]
    assert people_count >= 50, f"expected merged people, found {people_count}"
    assert issues_count >= 3, f"expected logged data issues, found {issues_count}"

    row = conn.execute(
        """
        SELECT p.id
        FROM people p
        JOIN person_phones ph ON ph.person_id = p.id
        WHERE ph.normalized_phone = ?
        """,
        (normalize_phone("+91-9000000254"),),
    ).fetchone()
    assert row, "expected Tanvi Gupta phone to match a canonical person"

    test_audio = ROOT / "storage" / "audio" / "smoke_test.wav"
    test_audio.parent.mkdir(parents=True, exist_ok=True)
    make_test_wav(test_audio)
    metadata = extract_audio_metadata(test_audio)
    assert metadata["duration_seconds"] >= 2
    assert metadata["sample_rate_khz"] == 16
    assert metadata["bitrate_kbps"] == 256
    print("Smoke test passed")
    print(f"people={people_count} issues={issues_count} audio={metadata}")


if __name__ == "__main__":
    main()
