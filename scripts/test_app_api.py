from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "app" / "main.py")],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PORT": "8010"},
    )
    try:
        time.sleep(2)
        
        # Test 1: Exact Duplicate Match
        payload_dup = json.dumps(
            {
                "name": "Tanvi Gupta",
                "email": "tanvi.gupta31@example.com",
                "phone": "+91-9000000254",
                "city": "Bangalore",
            }
        ).encode("utf-8")
        req1 = urllib.request.Request(
            "http://127.0.0.1:8010/api/check-duplicate",
            data=payload_dup,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req1, timeout=5) as response:
            res1 = json.loads(response.read().decode("utf-8"))
        assert res1["duplicate"] is True
        assert res1["match_type"] == "email_or_phone"
        assert res1["person"]["canonical_name"] == "Tanvi Gupta"
        print("[PASS] Test 1: Exact Duplicate Match Passed")

        # Test 2: Soft Candidate Match (Same Name & City, Different Email/Phone)
        payload_soft = json.dumps(
            {
                "name": "Arjun Mehta",
                "email": "arjun.newemail999@test.com",
                "phone": "+91-9999999999",
                "city": "Noida",
            }
        ).encode("utf-8")
        req2 = urllib.request.Request(
            "http://127.0.0.1:8010/api/check-duplicate",
            data=payload_soft,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as response:
            res2 = json.loads(response.read().decode("utf-8"))
        assert res2["duplicate"] is True
        assert res2["match_type"] == "name_city_candidate"
        assert len(res2["candidates"]) > 0
        print("[PASS] Test 2: Soft Candidate Match Passed")

        # Test 3: No Duplicate (New Person)
        payload_new = json.dumps(
            {
                "name": "Zoya Akhtar",
                "email": "zoya.akhtar99@example.com",
                "phone": "+91-9876543210",
                "city": "Mumbai",
            }
        ).encode("utf-8")
        req3 = urllib.request.Request(
            "http://127.0.0.1:8010/api/check-duplicate",
            data=payload_new,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req3, timeout=5) as response:
            res3 = json.loads(response.read().decode("utf-8"))
        assert res3["duplicate"] is False
        assert res3["match_type"] == "none"
        print("[PASS] Test 3: Brand New Person (No Duplicate) Passed")

        print("\nAll App API Tests Passed Successfully!")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
