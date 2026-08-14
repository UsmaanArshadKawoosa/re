import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database.sqlite"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 65)
    print(" 1. AUDIO SUBMISSIONS IN DATABASE")
    print("=" * 65)
    submissions = conn.execute(
        """
        SELECT a.*, p.canonical_name 
        FROM audio_submissions a 
        LEFT JOIN people p ON p.id = a.person_id 
        ORDER BY a.created_at DESC
        """
    ).fetchall()
    if not submissions:
        print("  No audio submissions recorded yet.")
    else:
        for r in submissions:
            print(f"Submission #{r['id']} - Submitter: {r['submitter_name']} ({r['phone']})")
            print(f"  Person ID: {r['person_id']} | Canonical Name: {r['canonical_name']}")
            print(f"  Audio Path: {r['audio_path']}")
            print(f"  Duration: {r['duration_seconds']}s | Sample Rate: {r['sample_rate_khz']} kHz | Bitrate: {r['bitrate_kbps']} kbps")
            print(f"  Loudness: {r['loudness_db']} dB | Quality: {r['quality_estimate']}")
            print(f"  Created At: {r['created_at']}")
            print("-" * 45)

    print("\n" + "=" * 65)
    print(" 2. DATA QUALITY ISSUES LOGGED")
    print("=" * 65)
    issues = conn.execute("SELECT * FROM data_quality_issues").fetchall()
    for r in issues:
        print(f"Issue #{r['id']}: {r['issue_type']}")
        print(f"  Source: {r['source_name']} (Row {r['row_number']})")
        print(f"  Action: {r['action_taken']}")
        print(f"  Original: {r['original_value']}")
        if r['resolved_value']:
            print(f"  Resolved: {r['resolved_value']}")
        print("-" * 45)

    print("\n" + "=" * 65)
    print(" 3. CITY NORMALIZATION BREAKDOWN")
    print("=" * 65)
    cities = conn.execute("SELECT normalized_city, count(*) as c FROM people GROUP BY normalized_city").fetchall()
    for r in cities:
        print(f"  - {r['normalized_city']}: {r['c']} profiles")

    print("\n" + "=" * 65)
    print(" 4. REVIEW MATCH CANDIDATES (SOFT MATCHES)")
    print("=" * 65)
    candidates = conn.execute("SELECT * FROM match_candidates").fetchall()
    for r in candidates:
        left = conn.execute("SELECT canonical_name, primary_email, primary_phone, normalized_city FROM people WHERE id = ?", (r['left_person_id'],)).fetchone()
        right = conn.execute("SELECT canonical_name, primary_email, primary_phone, normalized_city FROM people WHERE id = ?", (r['right_person_id'],)).fetchone()
        print(f"Candidate Pair #{r['id']} ({r['confidence']} confidence):")
        print(f"  Left:  {left['canonical_name']} | Email: {left['primary_email']} | Phone: {left['primary_phone']} | City: {left['normalized_city']}")
        print(f"  Right: {right['canonical_name']} | Email: {right['primary_email']} | Phone: {right['primary_phone']} | City: {right['normalized_city']}")
        print(f"  Reason: {r['reason']}")
        print("-" * 45)

if __name__ == "__main__":
    main()
