import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database.sqlite"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print(" 1. DATA QUALITY ISSUES LOGGED")
    print("=" * 60)
    issues = conn.execute("SELECT * FROM data_quality_issues").fetchall()
    for r in issues:
        print(f"Issue #{r['id']}: {r['issue_type']}")
        print(f"  Source: {r['source_name']} (Row {r['row_number']})")
        print(f"  Action: {r['action_taken']}")
        print(f"  Original: {r['original_value']}")
        if r['resolved_value']:
            print(f"  Resolved: {r['resolved_value']}")
        print("-" * 40)

    print("\n" + "=" * 60)
    print(" 2. CITY NORMALIZATION BREAKDOWN")
    print("=" * 60)
    cities = conn.execute("SELECT normalized_city, count(*) as c FROM people GROUP BY normalized_city").fetchall()
    for r in cities:
        print(f"  - {r['normalized_city']}: {r['c']} profiles")

    print("\n" + "=" * 60)
    print(" 3. REVIEW MATCH CANDIDATES (SOFT MATCHES)")
    print("=" * 60)
    candidates = conn.execute("SELECT * FROM match_candidates").fetchall()
    for r in candidates:
        left = conn.execute("SELECT canonical_name, primary_email, primary_phone, normalized_city FROM people WHERE id = ?", (r['left_person_id'],)).fetchone()
        right = conn.execute("SELECT canonical_name, primary_email, primary_phone, normalized_city FROM people WHERE id = ?", (r['right_person_id'],)).fetchone()
        print(f"Candidate Pair #{r['id']} ({r['confidence']} confidence):")
        print(f"  Left:  {left['canonical_name']} | Email: {left['primary_email']} | Phone: {left['primary_phone']} | City: {left['normalized_city']}")
        print(f"  Right: {right['canonical_name']} | Email: {right['primary_email']} | Phone: {right['primary_phone']} | City: {right['normalized_city']}")
        print(f"  Reason: {r['reason']}")
        print("-" * 40)

if __name__ == "__main__":
    main()
