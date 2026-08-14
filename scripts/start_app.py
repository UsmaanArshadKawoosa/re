from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

from database import DB_PATH, connect, init_db
import ingest
import main as app_main


if __name__ == "__main__":
    if not DB_PATH.exists():
        print("Database not found, running initial ingestion...")
        ingest.main()
    else:
        print("Database found, initializing schema...")
        with connect(DB_PATH) as conn:
            init_db(conn)
    app_main.main()
