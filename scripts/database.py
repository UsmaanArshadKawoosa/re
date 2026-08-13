from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database.sqlite"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    primary_email TEXT,
    primary_phone TEXT,
    normalized_city TEXT,
    skill_category TEXT DEFAULT 'uncategorized',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS person_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    email TEXT NOT NULL,
    normalized_email TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, normalized_email)
);

CREATE TABLE IF NOT EXISTS person_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    phone TEXT NOT NULL,
    normalized_phone TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, normalized_phone)
);

CREATE TABLE IF NOT EXISTS person_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    skill TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, skill)
);

CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES people(id),
    source_name TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    issue_type TEXT NOT NULL,
    original_value TEXT,
    resolved_value TEXT,
    action_taken TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_person_id INTEGER NOT NULL REFERENCES people(id),
    right_person_id INTEGER NOT NULL REFERENCES people(id),
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(left_person_id, right_person_id, reason)
);

CREATE TABLE IF NOT EXISTS audio_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES people(id),
    submitter_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    duration_seconds REAL,
    sample_rate_khz REAL,
    bitrate_kbps REAL,
    loudness_db REAL,
    quality_estimate TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
