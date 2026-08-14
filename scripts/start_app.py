from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

from database import DB_PATH, connect, init_db, USE_POSTGRES
import os
import ingest
import main as app_main

# Diagnostic (do not log secrets): check whether the process sees DATABASE_URL
print("DATABASE_URL present:", bool(os.environ.get("DATABASE_URL")))
print("USE_POSTGRES:", USE_POSTGRES)


if __name__ == "__main__":
    # PostgreSQL-aware startup: when DATABASE_URL is set, don't look for the
    # local database file. Instead, initialize schema and only run ingestion if
    # the database is empty.
    print("=== STARTUP DATABASE DIAGNOSTIC ===", flush=True)
    print("DATABASE_URL present:", bool(os.environ.get("DATABASE_URL")), flush=True)
    print("USE_POSTGRES:", USE_POSTGRES, flush=True)
    print("===================================", flush=True)

    if USE_POSTGRES:
        print("PostgreSQL configured — initializing schema and checking data...")
        # Use the shared connect/init_db abstraction. connect() ignores the path
        # when DATABASE_URL is set.
        with connect(DB_PATH) as conn:
            init_db(conn)
            try:
                row = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()
                count = int(row["c"]) if row and ("c" in row or 0) else (int(row[0]) if row else 0)
            except Exception:
                # If the table doesn't exist or query fails, treat as empty.
                count = 0
        if count == 0:
            print("No application data found in PostgreSQL — running initial ingestion...")
            ingest.main()
        else:
            print(f"PostgreSQL already contains data ({count} people). Skipping ingestion.")
    else:
        # SQLite path: preserve existing behavior
        if not DB_PATH.exists():
            print("Database not found, running initial ingestion...")
            ingest.main()
        else:
            print("Database found, initializing schema...")
            with connect(DB_PATH) as conn:
                init_db(conn)

    app_main.main()
