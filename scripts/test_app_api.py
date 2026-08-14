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
        payload = json.dumps(
            {
                "name": "Tanvi Gupta",
                "email": "tanvi.gupta31@example.com",
                "phone": "+91-9000000254",
                "city": "Bangalore",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8010/api/check-duplicate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
        assert result["duplicate"] is True
        assert result["match_type"] == "email_or_phone"
        print("App API test passed")
        print(json.dumps(result, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
