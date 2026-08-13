from __future__ import annotations

import cgi
import html
import json
import mimetypes
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audio_metadata import extract_audio_metadata
from database import DB_PATH, connect, init_db
from match_people import create_or_get_person, find_existing_person, update_person_basics
from normalize import name_key, normalize_city, normalize_email, normalize_name, normalize_phone


HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
AUDIO_DIR = ROOT / "storage" / "audio"
TEMPLATE_DIR = ROOT / "app" / "templates"
STATIC_DIR = ROOT / "app" / "static"


def ensure_database() -> None:
    with connect(DB_PATH) as conn:
        init_db(conn)


def safe_filename(name: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", Path(name or "audio.wav").name)
    return f"{uuid.uuid4().hex}_{stem}"


def render_template(name: str, **context) -> bytes:
    content = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for key, value in context.items():
        content = content.replace("{{ " + key + " }}", str(value))
    return content.encode("utf-8")


def duplicate_check(payload: dict) -> dict:
    email = payload.get("email", "")
    phone = payload.get("phone", "")
    name = payload.get("name", "")
    city = payload.get("city", "")
    with connect(DB_PATH) as conn:
        init_db(conn)
        person_id = find_existing_person(conn, email=email, phone=phone)
        if person_id:
            row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
            return {
                "duplicate": True,
                "match_type": "email_or_phone",
                "person": dict(row),
            }

        normalized_name = name_key(name)
        normalized_city = normalize_city(city)
        candidates = []
        if normalized_name and normalized_city:
            candidates = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, canonical_name, primary_email, primary_phone, normalized_city, skill_category
                    FROM people
                    WHERE normalized_name = ? AND normalized_city = ?
                    LIMIT 10
                    """,
                    (normalized_name, normalized_city),
                )
            ]
        return {
            "duplicate": bool(candidates),
            "match_type": "name_city_candidate" if candidates else "none",
            "candidates": candidates,
            "normalized": {
                "email": normalize_email(email),
                "phone": normalize_phone(phone),
                "name": normalized_name,
                "city": normalized_city,
            },
        }


def submissions_table() -> str:
    with connect(DB_PATH) as conn:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT a.*, p.canonical_name
            FROM audio_submissions a
            LEFT JOIN people p ON p.id = a.person_id
            ORDER BY a.created_at DESC
            """
        ).fetchall()
    if not rows:
        return '<p class="empty">No submissions yet.</p>'
    parts = [
        "<table>",
        "<thead><tr><th>Name</th><th>Phone</th><th>Audio</th><th>Duration</th><th>Sample rate</th><th>Bitrate</th><th>Loudness</th><th>Quality</th><th>Created</th></tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        path = "/" + Path(row["audio_path"]).as_posix()
        parts.append(
            "<tr>"
            f"<td>{html.escape(row['submitter_name'])}</td>"
            f"<td>{html.escape(row['phone'])}</td>"
            f"<td><audio controls src='{html.escape(path)}'></audio></td>"
            f"<td>{row['duration_seconds'] if row['duration_seconds'] is not None else ''}</td>"
            f"<td>{row['sample_rate_khz'] if row['sample_rate_khz'] is not None else ''}</td>"
            f"<td>{row['bitrate_kbps'] if row['bitrate_kbps'] is not None else ''}</td>"
            f"<td>{row['loudness_db'] if row['loudness_db'] is not None else ''}</td>"
            f"<td>{html.escape(row['quality_estimate'] or '')}</td>"
            f"<td>{html.escape(row['created_at'])}</td>"
            "</tr>"
        )
    parts.extend(["</tbody>", "</table>"])
    return "".join(parts)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ConsultBaeAudio/1.0"

    def send_bytes(self, body: bytes, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/submissions"}:
            body = render_template("index.html", submissions=submissions_table(), message="")
            self.send_bytes(body)
            return
        if parsed.path == "/health":
            self.send_bytes(b'{"ok": true}', "application/json")
            return
        if parsed.path.startswith("/static/"):
            target = STATIC_DIR / parsed.path.removeprefix("/static/")
            if target.exists() and target.is_file():
                self.send_bytes(target.read_bytes(), mimetypes.guess_type(target)[0] or "application/octet-stream")
                return
        if parsed.path.startswith("/storage/audio/"):
            target = ROOT / parsed.path.lstrip("/")
            if target.exists() and target.is_file():
                self.send_bytes(target.read_bytes(), mimetypes.guess_type(target)[0] or "application/octet-stream")
                return
        self.send_bytes(b"Not found", "text/plain", 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/check-duplicate":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            body = json.dumps(duplicate_check(payload), indent=2).encode("utf-8")
            self.send_bytes(body, "application/json")
            return
        if parsed.path == "/submit":
            self.handle_submit()
            return
        self.send_bytes(b"Not found", "text/plain", 404)

    def handle_submit(self) -> None:
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
        name = normalize_name(form.getfirst("name", ""))
        phone = form.getfirst("phone", "")
        city = form.getfirst("city", "")
        audio_item = form["audio"] if "audio" in form else None
        if not name or not phone or audio_item is None or not getattr(audio_item, "filename", ""):
            body = render_template("index.html", submissions=submissions_table(), message="Name, phone, and audio are required.")
            self.send_bytes(body, status=400)
            return

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(audio_item.filename)
        audio_path = AUDIO_DIR / filename
        with audio_path.open("wb") as f:
            f.write(audio_item.file.read())

        metadata = extract_audio_metadata(audio_path)
        relative_audio_path = audio_path.relative_to(ROOT).as_posix()
        with connect(DB_PATH) as conn:
            init_db(conn)
            person_id = create_or_get_person(conn, name=name, email=None, phone=phone, city=city)
            update_person_basics(conn, person_id=person_id, name=name, email=None, phone=phone, city=city)
            conn.execute(
                """
                INSERT INTO audio_submissions
                (person_id, submitter_name, phone, audio_path, duration_seconds, sample_rate_khz, bitrate_kbps, loudness_db, quality_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    name,
                    normalize_phone(phone),
                    relative_audio_path,
                    metadata["duration_seconds"],
                    metadata["sample_rate_khz"],
                    metadata["bitrate_kbps"],
                    metadata["loudness_db"],
                    metadata["quality_estimate"],
                ),
            )
            conn.commit()

        body = render_template("index.html", submissions=submissions_table(), message="Submission saved.")
        self.send_bytes(body)


def main() -> None:
    ensure_database()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Audio app running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
