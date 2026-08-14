from __future__ import annotations

import csv
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import DB_PATH, USE_POSTGRES, connect, init_db
from match_people import create_or_get_person, update_person_basics
from normalize import (
    name_key,
    normalize_city,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_status,
    parse_bool,
    parse_ctc_lpa,
    parse_date,
    parse_rate,
    skill_category,
    split_skills,
)


SOURCES = {
    "source1_naukri": ROOT / "data" / "raw" / "source1_naukri_applicants.csv",
    "source2_gig": ROOT / "data" / "raw" / "source2_gig_workers.csv",
    "source3_cbnexus": ROOT / "data" / "raw" / "source3_cbnexus_contacts.csv",
}


def log_issue(conn, source: str, row_number: int, issue_type: str, original, resolved, action: str) -> None:
    conn.execute(
        """
        INSERT INTO data_quality_issues
        (source_name, row_number, issue_type, original_value, resolved_value, action_taken)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source, row_number, issue_type, str(original) if original is not None else None, str(resolved) if resolved is not None else None, action),
    )


def add_email(conn, person_id: int, email: str, source: str) -> None:
    normalized = normalize_email(email)
    if normalized:
        conn.execute(
            "INSERT OR IGNORE INTO person_emails (person_id, email, normalized_email, source) VALUES (?, ?, ?, ?)",
            (person_id, email.strip(), normalized, source),
        )


def add_phone(conn, person_id: int, phone: str, source: str) -> None:
    normalized = normalize_phone(phone)
    if normalized:
        conn.execute(
            "INSERT OR IGNORE INTO person_phones (person_id, phone, normalized_phone, source) VALUES (?, ?, ?, ?)",
            (person_id, phone.strip(), normalized, source),
        )


def add_skills(conn, person_id: int, skills: list[str], source: str) -> None:
    for skill in skills:
        conn.execute(
            "INSERT OR IGNORE INTO person_skills (person_id, skill, source) VALUES (?, ?, ?)",
            (person_id, skill, source),
        )


def normalized_record(source: str, row: dict[str, str], row_number: int, conn) -> dict | None:
    if source == "source1_naukri":
        name = normalize_name(row.get("Full Name"))
        email = row.get("Email", "")
        phone = row.get("Phone", "")
        city = row.get("City", "")
        skills = split_skills(row.get("Skills"))
        applied_date = parse_date(row.get("Applied Date"))
        ctc_lpa = parse_ctc_lpa(row.get("Current CTC"))
        if row.get("Applied Date") and not applied_date:
            log_issue(conn, source, row_number, "unparsed_date", row.get("Applied Date"), None, "kept raw value in source_records")
        if row.get("Current CTC") and ctc_lpa is None:
            log_issue(conn, source, row_number, "unparsed_ctc", row.get("Current CTC"), None, "kept raw value in source_records")
        return {
            "name": name,
            "email": email,
            "phone": phone,
            "city": city,
            "skills": skills,
            "extra": {"experience_years": row.get("Experience (Years)"), "ctc_lpa": ctc_lpa, "applied_date": applied_date},
        }

    if source == "source2_gig":
        email = row.get("email_id", "")
        name = normalize_name(row.get("worker_name"))
        rate, unit = parse_rate(row.get("rate"))
        city = row.get("location", "")
        status = normalize_status(row.get("status"))
        skills = split_skills(row.get("skill_tags"))

        # Detect shifted row pattern (skills in email column, email with '@' in name column, etc.)
        if email and "@" not in email and "@" in row.get("worker_name", ""):
            repaired_email = row.get("worker_name", "").strip()
            repaired_name = row.get("rate", "").strip()
            repaired_rate_str = row.get("location", "").strip()
            repaired_city = row.get("status", "").strip()
            repaired_status_str = row.get("skill_tags", "").strip()
            repaired_skills_str = row.get("email_id", "").strip()

            rate, unit = parse_rate(repaired_rate_str)
            status = normalize_status(repaired_status_str)

            if "@" in repaired_email and rate is not None and repaired_name:
                repaired_dict = {
                    "email_id": repaired_email,
                    "worker_name": repaired_name,
                    "rate": repaired_rate_str,
                    "location": repaired_city,
                    "status": repaired_status_str,
                    "skill_tags": repaired_skills_str,
                }
                log_issue(
                    conn,
                    source,
                    row_number,
                    "repaired_shifted_row",
                    json.dumps(row),
                    json.dumps(repaired_dict),
                    "realigned shifted columns and imported",
                )
                return {
                    "name": normalize_name(repaired_name),
                    "email": repaired_email,
                    "phone": "",
                    "city": repaired_city,
                    "skills": split_skills(repaired_skills_str),
                    "extra": {"rate_amount": rate, "rate_unit": unit, "status": status},
                }
            else:
                log_issue(conn, source, row_number, "malformed_shifted_row", json.dumps(row), None, "skipped unrepairable shifted row")
                return None

        if email and "@" not in email:
            log_issue(conn, source, row_number, "malformed_row", json.dumps(row), None, "skipped malformed row without valid email")
            return None
        if row.get("rate") and rate is None:
            log_issue(conn, source, row_number, "unparsed_rate", row.get("rate"), None, "kept raw value in source_records")
        if row.get("status") and status is None:
            log_issue(conn, source, row_number, "unparsed_status", row.get("status"), None, "kept raw value in source_records")
        return {
            "name": name,
            "email": email,
            "phone": "",
            "city": city,
            "skills": skills,
            "extra": {"rate_amount": rate, "rate_unit": unit, "status": status},
        }

    if source == "source3_cbnexus":
        if row.get("Name") == "Name" and row.get("Phone Number") == "Phone Number":
            log_issue(conn, source, row_number, "repeated_header", json.dumps(row), None, "skipped repeated header row")
            return None
        verified = parse_bool(row.get("Verified"))
        projects = row.get("Projects Completed", "")
        if row.get("Verified") and verified is None:
            log_issue(conn, source, row_number, "unparsed_verified", row.get("Verified"), None, "kept raw value in source_records")
        return {
            "name": normalize_name(row.get("Name")),
            "email": "",
            "phone": row.get("Phone Number", ""),
            "city": row.get("City", ""),
            "skills": [],
            "extra": {"verified": verified, "projects_completed": projects},
        }
    raise ValueError(f"unknown source: {source}")


def import_source(conn, source: str, path: Path, batch_id: str) -> int:
    imported = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row_number, row in enumerate(csv.DictReader(f), start=2):
            record = normalized_record(source, row, row_number, conn)
            conn.execute(
                """
                INSERT INTO source_records (person_id, source_name, row_number, raw_json, import_batch_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (None, source, row_number, json.dumps(row, ensure_ascii=False), batch_id),
            )
            if not record:
                continue

            if not record["name"] and not record["email"] and not record["phone"]:
                log_issue(conn, source, row_number, "blank_identity", json.dumps(row), None, "skipped row with no usable identity")
                continue

            person_id = create_or_get_person(
                conn,
                name=record["name"] or "Unknown",
                email=record["email"],
                phone=record["phone"],
                city=record["city"],
            )
            update_person_basics(
                conn,
                person_id=person_id,
                name=record["name"] or "Unknown",
                email=record["email"],
                phone=record["phone"],
                city=record["city"],
            )
            add_email(conn, person_id, record["email"], source)
            add_phone(conn, person_id, record["phone"], source)
            add_skills(conn, person_id, record["skills"], source)
            conn.execute(
                "UPDATE source_records SET person_id = ? WHERE source_name = ? AND row_number = ? AND import_batch_id = ?",
                (person_id, source, row_number, batch_id),
            )
            imported += 1
    return imported


def record_match_candidates(conn) -> int:
    people = conn.execute("SELECT id, normalized_name, normalized_city FROM people").fetchall()
    inserted = 0
    for i, left in enumerate(people):
        for right in people[i + 1 :]:
            if (
                left["normalized_name"]
                and left["normalized_city"]
                and left["normalized_name"] == right["normalized_name"]
                and left["normalized_city"] == right["normalized_city"]
            ):
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO match_candidates
                    (left_person_id, right_person_id, reason, confidence)
                    VALUES (?, ?, ?, ?)
                    """,
                    (left["id"], right["id"], "same normalized name and city but no shared email/phone", "review"),
                )
                # Count successfully inserted rows
                try:
                    inserted += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 1
                except (AttributeError, TypeError):
                    inserted += 1
    return inserted


def refresh_skill_categories(conn) -> None:
    for row in conn.execute("SELECT id FROM people").fetchall():
        skills = [s["skill"] for s in conn.execute("SELECT skill FROM person_skills WHERE person_id = ?", (row["id"],))]
        conn.execute("UPDATE people SET skill_category = ? WHERE id = ?", (skill_category(skills), row["id"]))


def main() -> None:
    batch_id = str(uuid.uuid4())
    conn = connect(DB_PATH)
    init_db(conn)
    for table in (
        "match_candidates",
        "audio_submissions",
        "data_quality_issues",
        "source_records",
        "person_skills",
        "person_phones",
        "person_emails",
        "people",
    ):
        conn.execute(f"DELETE FROM {table}")
    if not USE_POSTGRES:
        conn.execute("DELETE FROM sqlite_sequence")
    totals = {}
    for source, path in SOURCES.items():
        totals[source] = import_source(conn, source, path, batch_id)
    refresh_skill_categories(conn)
    record_match_candidates(conn)
    conn.commit()

    people_count = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
    issue_count = conn.execute("SELECT COUNT(*) AS c FROM data_quality_issues").fetchone()["c"]
    candidate_count = conn.execute("SELECT COUNT(*) AS c FROM match_candidates").fetchone()["c"]
    print(f"Imported rows: {totals}")
    print(f"Canonical people: {people_count}")
    print(f"Data quality issues logged: {issue_count}")
    print(f"Review match candidates: {candidate_count}")
    print(f"Database: {'PostgreSQL' if USE_POSTGRES else DB_PATH}")


if __name__ == "__main__":
    main()
