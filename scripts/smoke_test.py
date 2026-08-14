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
from normalize import normalize_city, normalize_phone


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
    assert people_count == 60, f"expected exactly 60 merged people, found {people_count}"
    assert issues_count >= 3, f"expected at least 3 logged data issues, found {issues_count}"

    # Check repaired shifted row
    repaired_issue = conn.execute(
        "SELECT * FROM data_quality_issues WHERE issue_type = 'repaired_shifted_row'"
    ).fetchone()
    assert repaired_issue, "expected repaired_shifted_row to be logged in data_quality_issues"

    # Check city normalization
    assert normalize_city("Delhi") == "delhi"
    assert normalize_city("New Delhi") == "delhi"
    assert normalize_city("Delhi NCR") == "ncr"
    assert normalize_city("Gurgaon") == "gurugram"
    assert normalize_city("Bangalore") == "bengaluru"

    delhi_count = conn.execute("SELECT COUNT(*) AS c FROM people WHERE normalized_city = 'delhi'").fetchone()["c"]
    ncr_count = conn.execute("SELECT COUNT(*) AS c FROM people WHERE normalized_city = 'ncr'").fetchone()["c"]
    assert delhi_count == 10, f"expected 10 people in delhi, found {delhi_count}"
    assert ncr_count == 2, f"expected 2 people in ncr, found {ncr_count}"

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
    assert metadata["quality_estimate"] == "good"
    print("Smoke test passed successfully!")
    print(f"people={people_count} issues={issues_count} delhi_count={delhi_count} ncr_count={ncr_count}")
    print(f"audio_metadata={metadata}")


if __name__ == "__main__":
    main()
