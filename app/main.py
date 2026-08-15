from __future__ import annotations

import html
import json
import mimetypes
import os
import re
import sys
import uuid
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audio_metadata import extract_audio_metadata
from database import DB_PATH, connect, init_db, USE_POSTGRES
from match_people import create_or_get_person, find_existing_person, update_person_basics
from normalize import name_key, normalize_city, normalize_email, normalize_name, normalize_phone

HOST = os.environ.get("HOST", "0.0.0.0")
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


def parse_multipart_form(headers, rfile) -> tuple[dict[str, str], dict[str, dict]]:
    content_type = headers.get("Content-Type", "")
    content_length = int(headers.get("Content-Length", "0"))
    body = rfile.read(content_length) if content_length > 0 else b""

    fields: dict[str, str] = {}
    files: dict[str, dict] = {}

    if not content_type.startswith("multipart/form-data"):
        parsed = parse_qs(body.decode("utf-8", errors="replace"))
        for k, v in parsed.items():
            if v:
                fields[k] = v[0]
        return fields, files

    boundary_match = re.search(r"boundary=([^;]+)", content_type, re.IGNORECASE)
    if not boundary_match:
        return fields, files
    boundary = boundary_match.group(1).strip("\"'").encode("utf-8")
    delimiter = b"--" + boundary

    parts = body.split(delimiter)
    for part in parts:
        if not part or part in (b"--\r\n", b"--", b"\r\n"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        header_bytes = part[:header_end]
        data = part[header_end + 4 :]

        header_text = header_bytes.decode("utf-8", errors="replace")
        disp_match = re.search(
            r'Content-Disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]*)")?',
            header_text,
            re.IGNORECASE,
        )
        if not disp_match:
            continue
        field_name = disp_match.group(1)
        filename = disp_match.group(2)

        if filename is not None and filename != "":
            ct_match = re.search(r"Content-Type:\s*([^\r\n]+)", header_text, re.IGNORECASE)
            file_ct = ct_match.group(1).strip() if ct_match else "application/octet-stream"
            files[field_name] = {
                "filename": filename,
                "content_type": file_ct,
                "data": data,
            }
        else:
            fields[field_name] = data.decode("utf-8", errors="replace").strip()

    return fields, files


def duplicate_check(payload: dict) -> dict:
    """Return a JSON-safe duplicate-check response. Convert only date/time values to ISO strings
    while preserving numbers, booleans, arrays, and other JSON types.
    """
    email = payload.get("email", "")
    phone = payload.get("phone", "")
    name = payload.get("name", "")
    city = payload.get("city", "")

    def _convert_datetimes(obj):
        # Recursively convert datetime/date objects to ISO strings; leave other types intact
        if isinstance(obj, dict):
            return {k: _convert_datetimes(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert_datetimes(v) for v in obj]
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return obj

    with connect(DB_PATH) as conn:
        init_db(conn)
        person_id = find_existing_person(conn, email=email, phone=phone)
        if person_id:
            row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
            emails = [r["email"] for r in conn.execute("SELECT email FROM person_emails WHERE person_id = ?", (person_id,)).fetchall()]
            phones = [r["phone"] for r in conn.execute("SELECT phone FROM person_phones WHERE person_id = ?", (person_id,)).fetchall()]
            skills = [r["skill"] for r in conn.execute("SELECT skill FROM person_skills WHERE person_id = ?", (person_id,)).fetchall()]

            person_obj = {
                **dict(row),
                "emails": emails,
                "phones": phones,
                "skills": skills,
            }

            return {
                "duplicate": True,
                "match_type": "email_or_phone",
                "person": _convert_datetimes(person_obj),
                "normalized": {
                    "email": normalize_email(email),
                    "phone": normalize_phone(phone),
                    "name": name_key(name),
                    "city": normalize_city(city),
                },
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
            "candidates": _convert_datetimes(candidates),
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
            SELECT a.*, p.canonical_name, p.normalized_city
            FROM audio_submissions a
            LEFT JOIN people p ON p.id = a.person_id
            ORDER BY a.created_at DESC
            """
        ).fetchall()
    if not rows:
        return '<div class="empty-state"><p class="empty">No submissions yet. Record or upload an audio file above.</p></div>'

    parts = [
        '<div class="table-responsive">',
        '<table class="data-table">',
        "<thead><tr>"
        "<th>Submitter</th>"
        "<th>Phone</th>"
        "<th>Audio Playback</th>"
        "<th>Duration</th>"
        "<th>Sample Rate</th>"
        "<th>Bitrate</th>"
        "<th>Loudness</th>"
        "<th>Quality Rating</th>"
        "<th>Submitted</th>"
        "</tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        # For Postgres, serve audio via the persistent /api/audio/<id> endpoint.
        # For SQLite, continue to serve from the filesystem storage path.
        if USE_POSTGRES:
            path = f"/api/audio/{row['id']}"
        else:
            path = "/" + Path(row["audio_path"]).as_posix()
        quality = row["quality_estimate"] or "unknown"
        if "good" in quality.lower():
            badge_class = "badge badge-good"
        elif "poor" in quality.lower():
            badge_class = "badge badge-poor"
        else:
            badge_class = "badge badge-okay"

        duration = f"{row['duration_seconds']:.2f}s" if row["duration_seconds"] is not None else "—"
        sample_rate = f"{row['sample_rate_khz']:.1f} kHz" if row["sample_rate_khz"] is not None else "—"
        bitrate = f"{row['bitrate_kbps']:.0f} kbps" if row["bitrate_kbps"] is not None else "—"
        loudness = f"{row['loudness_db']:.1f} dB" if row["loudness_db"] is not None else "—"

        parts.append(
            "<tr>"
            f"<td class='fw-medium'>{html.escape(row['submitter_name'])}</td>"
            f"<td class='text-muted font-mono'>{html.escape(row['phone'])}</td>"
            f"<td><audio controls preload='none' src='{html.escape(path)}' class='table-audio'></audio></td>"
            f"<td>{duration}</td>"
            f"<td>{sample_rate}</td>"
            f"<td>{bitrate}</td>"
            f"<td>{loudness}</td>"
            f"<td><span class='{badge_class}'>{html.escape(quality)}</span></td>"
            f"<td class='text-muted text-sm'>{html.escape(str(row['created_at']))}</td>"
            "</tr>"
        )
    parts.extend(["</tbody>", "</table>", "</div>"])
    return "".join(parts)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ConsultBaeAudio/2.0"

    def send_bytes(self, body: bytes, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/submissions", "/submit"}:
            body = render_template("index.html", submissions=submissions_table(), message="", alert_class="")
            self.send_bytes(body)
            return
        if parsed.path == "/health":
            self.send_bytes(b'{"ok": true, "service": "consultbae-audio-app"}', "application/json")
            return
        if parsed.path.startswith("/static/"):
            target = STATIC_DIR / parsed.path.removeprefix("/static/")
            if target.exists() and target.is_file():
                self.send_bytes(target.read_bytes(), mimetypes.guess_type(target)[0] or "application/octet-stream")
                return
        if parsed.path.startswith("/api/audio/"):
            # Serve audio stored in the database by submission id
            try:
                sid = int(parsed.path.split("/api/audio/", 1)[1].split("/", 1)[0])
            except Exception:
                self.send_bytes(b"Not found", "text/plain", 404)
                return
            with connect(DB_PATH) as conn:
                init_db(conn)
                row = conn.execute("SELECT audio_data, content_type FROM audio_submissions WHERE id = ?", (sid,)).fetchone()
            if not row:
                self.send_bytes(b"Not found", "text/plain", 404)
                return
            audio_blob = row["audio_data"] if "audio_data" in row else row[0]
            content_type = row.get("content_type") if isinstance(row, dict) else (row[1] if len(row) > 1 else None)
            if not audio_blob:
                self.send_bytes(b"Not found", "text/plain", 404)
                return
            self.send_bytes(audio_blob, content_type or "application/octet-stream")
            return
        if parsed.path.startswith("/storage/audio/"):
            target = ROOT / parsed.path.lstrip("/")
            if target.exists() and target.is_file():
                self.send_bytes(target.read_bytes(), mimetypes.guess_type(target)[0] or "audio/wav")
                return
        self.send_bytes(b"Not found", "text/plain", 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/check-duplicate":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {}
            body = json.dumps(duplicate_check(payload), indent=2).encode("utf-8")
            self.send_bytes(body, "application/json")
            return
        if parsed.path == "/submit":
            self.handle_submit()
            return
        self.send_bytes(b"Not found", "text/plain", 404)

    def handle_submit(self) -> None:
        fields, files = parse_multipart_form(self.headers, self.rfile)
        name = normalize_name(fields.get("name", ""))
        phone = fields.get("phone", "")
        city = fields.get("city", "")
        audio_file = files.get("audio")

        if not name or not phone or not audio_file or not audio_file.get("data"):
            body = render_template(
                "index.html",
                submissions=submissions_table(),
                message="Name, phone, and audio file or recording are required.",
                alert_class="alert-error",
            )
            self.send_bytes(body, status=400)
            return

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(audio_file.get("filename", "recording.wav"))
        audio_path = AUDIO_DIR / filename
        with audio_path.open("wb") as f:
            f.write(audio_file["data"])

        metadata = extract_audio_metadata(audio_path)
        relative_audio_path = audio_path.relative_to(ROOT).as_posix()

        with connect(DB_PATH) as conn:
            init_db(conn)
            person_id = create_or_get_person(conn, name=name, email=None, phone=phone, city=city)
            update_person_basics(conn, person_id=person_id, name=name, email=None, phone=phone, city=city)

            # Read raw bytes for storage in Postgres when configured
            audio_bytes = audio_file["data"]
            content_type = audio_file.get("content_type") or "application/octet-stream"

            if USE_POSTGRES:
                # For Postgres, store audio bytes in audio_data column and content_type
                conn.execute(
                    """
                    INSERT INTO audio_submissions
                    (person_id, submitter_name, phone, audio_path, audio_data, content_type, duration_seconds, sample_rate_khz, bitrate_kbps, loudness_db, quality_estimate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        person_id,
                        name,
                        normalize_phone(phone),
                        relative_audio_path,
                        audio_bytes,
                        content_type,
                        metadata["duration_seconds"],
                        metadata["sample_rate_khz"],
                        metadata["bitrate_kbps"],
                        metadata["loudness_db"],
                        metadata["quality_estimate"],
                    ),
                )
            else:
                # SQLite / filesystem behavior unchanged
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

        body = render_template(
            "index.html",
            submissions=submissions_table(),
            message=f"Audio submission saved successfully! Quality rating: {metadata.get('quality_estimate', 'unknown')}.",
            alert_class="alert-success",
        )
        self.send_bytes(body)


def main() -> None:
    ensure_database()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"ConsultBae Audio App running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
