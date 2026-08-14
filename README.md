# ConsultBae AI Automation Take-Home Assignment

Submitted by: **Usmaan Arshad Kawoosa**

This repository contains my end-to-end implementation for the **ConsultBae AI Automation take-home assignment**. It includes an automated CSV ingestion and deduplication pipeline, a normalized SQLite database with audit trails, an n8n webhook workflow for real-time duplicate screening, a browser-based audio collection web app with real-time waveform visualization and technical audio quality analysis, and a production scaling roadmap for high-volume recruitment.

---

## Table of Contents

1. [Executive Summary & Architecture](#executive-summary--architecture)
2. [Tech Stack & Design Philosophy](#tech-stack--design-philosophy)
3. [Local Quickstart & Verification](#local-quickstart--verification)
4. [Deployment: Local vs. Global/Cloud Differences](#deployment-local-vs-globalcloud-differences)
5. [Database Design & Auditability](#database-design--auditability)
6. [Data Pipeline, Normalization & Cleaning](#data-pipeline-normalization--cleaning)
7. [Duplicate Check API & n8n Automation](#duplicate-check-api--n8n-automation)
8. [Audio Collection Web App & Metadata Extraction](#audio-collection-web-app--metadata-extraction)
9. [Stuck Log: Technical Challenges & Decisions](#stuck-log-technical-challenges--decisions)
10. [Scale Plan: 5,000 Workers in One Weekend](#scale-plan-5000-workers-in-one-weekend)


---

## Executive Summary & Architecture

The solution tackles candidate data ingestion, automated verification, and voice assessment through four core components:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           1. DATA PIPELINE (ETL)                               │
│  source1_naukri.csv (42)  │  source2_gig.csv (32)   │  source3_cbnexus.csv (31)│
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       ▼
                 ┌───────────────────────────────────────────┐
                 │    scripts/normalize.py + ingest.py       │
                 │  - Indian Phone (+91) & Email Cleaning    │
                 │  - City Mapping (Delhi vs NCR distinct)   │
                 │  - Repaired Shifted Gig Row (Row 20)      │
                 │  - Skipped Blank Rows & Repeated Headers  │
                 └─────────────────────┬─────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                         2. RELATIONAL DATABASE (SQLite)                        │
│  people (60 canonical)  │  person_emails  │  person_phones  │  person_skills   │
│  source_records (105)   │  data_quality_issues (3) │ match_candidates (7 pairs)│
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       3. API & AUTOMATION INTEGRATION                          │
│  POST /api/check-duplicate  ◄───►  automations/n8n_duplicate_alert.json        │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                    4. VOICE STUDIO APP & AUDIO TELEMETRY                       │
│  Browser Recording Studio (Canvas Waveform + Timer)  │  Pure-Python WAV DSP    │
│  Duration • Sample Rate (kHz) • Bitrate (kbps) • Loudness (RMS dBFS) • Quality │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Key Metrics from Ingestion:
* **Total raw source rows processed:** 105 rows
* **Total usable records imported:** 103 records
* **Canonical deduplicated people:** 60 unique profiles
* **Logged data-quality issues:** 3 issues (1 blank row skipped, 1 shifted row repaired & imported, 1 repeated header skipped)
* **Soft match review candidates:** 7 candidate pairs (same normalized name & city without shared email/phone)

---

## Tech Stack & Design Philosophy

* **Language & Runtime:** Python 3.10+ / 3.11+ / 3.12+ / 3.13+
* **Database:** SQLite (with `PRAGMA foreign_keys = ON`)
* **Web Server:** Standard Library `http.server.ThreadingHTTPServer` with custom zero-dependency multipart form-data parsing
* **Frontend:** Vanilla HTML5, CSS3 (Modern HSL Design System), and JavaScript (Web Audio API + HTML5 Canvas Visualizer)
* **Audio Digital Signal Processing (DSP):** Pure Python standard `wave` + `math` module (with `ffprobe` fallback for non-WAV formats)
* **Automation:** n8n Webhook & HTTP Request workflow JSON

### Why Zero-Dependency Core?
I intentionally engineered the ingestion, audio metadata calculation, and web server without mandatory external heavy dependencies (like Pandas, FastAPI, or FFmpeg binaries). This guarantees the reviewer can clone, run, and verify the entire project instantly on any operating system without complex environment setups or binary compilation issues.

---

## Local Quickstart & Verification

### 1. Clone & Ingest Data
```bash
# Clone the repository
git clone https://github.com/UsmaanArshadKawoosa/re.git
cd re

# Ingest all raw data into database.sqlite
python scripts/ingest.py
```

### 2. Run Automated Verification Suite
```bash
# Verify data integrity, city mapping, and audio metadata extraction
python scripts/smoke_test.py

# Verify duplicate detection API endpoints (exact match, candidate match, new user)
python scripts/test_app_api.py
```

### 3. Launch the Audio Collection App
```bash
# Start the local server
python app/main.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## Deployment: Local vs. Global/Cloud Differences

I built the app with full production deployment readiness for cloud platforms such as **Render**, **Railway**, **Fly.io**, or any container/VPS host.

```bash
# One-command startup for cloud platforms (runs ingestion then boots web service):
python scripts/start_app.py
```

### Will functionality change between Local and Global deployment?

| Dimension | Local Execution (`127.0.0.1:8000`) | Global / Cloud Deployment (`https://your-app.onrender.com`) |
| :--- | :--- | :--- |
| **Core Features** | Audio recording, file upload, metadata DSP, submission table, and duplicate check work locally. | **Identical functionality**, accessible globally over HTTPS from any mobile device, laptop, or browser. |
| **n8n URL** | Uses `http://host.docker.internal:8000/api/check-duplicate` or `http://127.0.0.1:8000`. | Uses the public URL: `https://your-app.onrender.com/api/check-duplicate`. No Docker networking tricks needed. |
| **Port Binding** | Binds to default port `8000`. | Binds dynamically to `0.0.0.0` and reads `PORT` environment variable injected by Render/Railway. |
| **CORS** | Local browser same-origin. | `Access-Control-Allow-Origin: *` is enabled so n8n cloud instances or external frontends can call the API directly. |
| **Storage Persistence** | Filesystem is permanently stored on local hard drive (`database.sqlite` & `storage/audio/`). | **Ephemeral Container Storage:** On free-tier cloud containers, the disk resets when the container restarts. |

> **Production Note:** For a permanent production rollout at scale, I would swap the local SQLite database for managed **PostgreSQL** (e.g. Supabase, Neon, or Render Postgres) and stream audio uploads directly to cloud object storage like **Amazon S3**, **Cloudflare R2**, or **Google Cloud Storage**.

---

## Database Design & Auditability

The database schema is defined in `scripts/database.py` and creates `database.sqlite`:

```sql
-- Core canonical person entity
CREATE TABLE people (
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

-- Multi-value contact tables (1-to-many lookup for aliases)
CREATE TABLE person_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    email TEXT NOT NULL,
    normalized_email TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, normalized_email)
);

CREATE TABLE person_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    phone TEXT NOT NULL,
    normalized_phone TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, normalized_phone)
);

CREATE TABLE person_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    skill TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(person_id, skill)
);

-- Complete source lineage & audit trails
CREATE TABLE source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES people(id),
    source_name TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    issue_type TEXT NOT NULL,
    original_value TEXT,
    resolved_value TEXT,
    action_taken TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE match_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_person_id INTEGER NOT NULL REFERENCES people(id),
    right_person_id INTEGER NOT NULL REFERENCES people(id),
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(left_person_id, right_person_id, reason)
);

CREATE TABLE audio_submissions (
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
```

---

## Data Pipeline, Normalization & Cleaning

### 1. Normalization Rules (`scripts/normalize.py`)
* **Phone Numbers:** Strips all non-digit formatting, resolves leading `0` and 10-digit Indian numbers into unified standard `91xxxxxxxxxx`.
* **Emails:** Trimmed and lowercased to ensure casing differences (`ISHA.CHOPRA95@...` vs `isha.chopra95@...`) resolve to the same person.
* **City Aliasing & Geographic Precision:**
  * `Delhi` and `New Delhi` $\rightarrow$ unified as `delhi`
  * `Delhi NCR` $\rightarrow$ mapped to `ncr` (preserving the distinct operational region of the National Capital Region)
  * `Gurgaon` $\rightarrow$ `gurugram`
  * `Bangalore` $\rightarrow$ `bengaluru`
* **Dates:** Converts mixed date formats (`DD-MM-YYYY`, `YYYY-MM-DD`, `D Mon YYYY`, `MM/DD/YYYY`) into ISO standard `YYYY-MM-DD`.
* **Compensation / CTC:** Identifies full rupee values ($>1000$) and converts them to LPA (e.g. $417,964 \rightarrow 4.18$ LPA), while preserving decimal entries already in LPA.
* **Gig Rates:** Parses rate strings (`1415/hr`, `15k/month`) into structured amount and frequency unit.
* **Skills & Auto-categorization:** Splits comma-separated skills, lowercases them, and categorizes candidates into `automation-heavy`, `web-dev`, `data`, or `uncategorized`.

### 2. Entity Matching & Deduplication Strategy
* **Automatic Hard Merges:** A record is automatically linked to an existing person if and only if there is a match on **normalized email** or **normalized phone**.
* **Human Review Candidates:** When two records share the same normalized name and normalized city but lack matching email or phone numbers, they are flagged in `match_candidates` for human review rather than merged blindly. This prevents incorrectly collating different people with common names.
* **Name Variations:** Handles abbreviated names like `R. Verma` vs `Rohit Verma` safely by only merging when a verified phone or email matches.

### 3. Data Quality Issues Handled (`data_quality_issues`)
During ingestion, 3 distinct data quality issues were logged:
1. **Row 12 of `source2_gig_workers.csv` (Blank Row):** Contains empty commas `,,,,,` $\rightarrow$ Safely skipped and logged as `blank_identity`.
2. **Row 20 of `source2_gig_workers.csv` (Shifted Row):** Column values were displaced circularly by 1 column:
   ```json
   {
     "email_id": "react, javascript, mysql",
     "worker_name": "ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG",
     "rate": "Isha Chopra",
     "location": "1406/hr",
     "status": "Pune",
     "skill_tags": "active"
   }
   ```
   **My Solution:** Rather than discarding valid worker data, I built a deterministic realignment check. The pipeline verifies that the shifted `worker_name` contains `@`, realigns the columns into their correct fields, verifies the rate (`1406/hr`) and status (`active`), logs the audit trail as `repaired_shifted_row`, and imports the record cleanly.
3. **Row 16 of `source3_cbnexus_contacts.csv` (Repeated Header):** Duplicate header inside the CSV body $\rightarrow$ Skipped and logged as `repeated_header`.

---

## Duplicate Check API & n8n Automation

### API Endpoint: `POST /api/check-duplicate`
Accepts a JSON payload representing a new incoming applicant:
```bash
curl -X POST http://127.0.0.1:8000/api/check-duplicate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tanvi Gupta",
    "email": "tanvi.gupta31@example.com",
    "phone": "+91-9000000254",
    "city": "Bangalore"
  }'
```

**Response (Exact Match Found):**
```json
{
  "duplicate": true,
  "match_type": "email_or_phone",
  "person": {
    "id": 1,
    "canonical_name": "Tanvi Gupta",
    "normalized_name": "tanvi gupta",
    "primary_email": "tanvi.gupta31@example.com",
    "primary_phone": "919000000254",
    "normalized_city": "bengaluru",
    "skill_category": "automation-heavy",
    "emails": ["tanvi.gupta31@example.com"],
    "phones": ["+919000000254", "9000000254"],
    "skills": ["n8n", "langchain", "rest apis", "mongodb", "sql"]
  }
}
```

### n8n Automation Workflow (`automations/n8n_duplicate_alert.json`)
The n8n workflow operates as an automated screening gatekeeper:
1. **Webhook Trigger (`Incoming CSV Row`):** Listens for incoming POST payloads from web forms or CSV ingestion triggers.
2. **HTTP Request (`Check App Database`):** Sends payload to `/api/check-duplicate`.
3. **IF Condition (`Duplicate?`):** Evaluates `{{ $json.duplicate }} == true`.
4. **Branching Responses:**
   * `True`: Routes to `Duplicate Alert Response` (returns `alert: "duplicate_found"` and candidate details).
   * `False`: Routes to `No Duplicate Response` (returns `alert: "no_duplicate"`).

---

## Audio Collection Web App & Metadata Extraction

I built the voice submission portal in `app/` with an interactive recording studio and real-time audio analysis.

### Features:
* **Live In-Browser Studio:** Uses Web Audio API to capture microphone input, displays a real-time animated waveform visualizer on an HTML5 `<canvas>`, and runs a live timer (`00:00`).
* **Direct 16-bit PCM WAV Encoding:** The client-side JavaScript packs raw audio buffers directly into valid RIFF WAV files in memory. This allows zero-dependency server-side processing without requiring FFmpeg on client machines.
* **File Upload Support:** Candidates can record in-browser or upload existing WAV/MP3 files.
* **Live Telemetry & Submissions Feed:** Real-time table displaying submitter name, phone, inline audio player for instant playback, and extracted technical metadata.

### Pure-Python Audio DSP (`scripts/audio_metadata.py`)
Using Python's standard `wave` and `math` libraries, the server extracts:
* **Duration:** $\text{Frames} / \text{Sample Rate}$ (seconds)
* **Sample Rate:** Converted to kHz (e.g. 16.0 kHz, 44.1 kHz, 48.0 kHz)
* **Bitrate:** $(\text{Sample Rate} \times \text{Channels} \times \text{Sample Width} \times 8) / 1000$ (kbps)
* **Loudness (RMS dBFS):**
  $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x_i^2}$$
  $$\text{Loudness (dBFS)} = 20 \times \log_{10}\left(\frac{\text{RMS}}{\text{Max Sample Value}}\right)$$
* **Automated Quality Rating Heuristic:**
  * `poor - too short`: Duration $< 2.0\text{s}$
  * `poor - low sample rate`: Sample rate $< 16\text{ kHz}$
  * `poor - very quiet`: RMS Loudness $< -45\text{ dB}$
  * `poor - likely clipped`: RMS Loudness $> -3\text{ dB}$
  * `okay - quiet`: RMS Loudness between $-45\text{ dB}$ and $-35\text{ dB}$
  * `good`: Passed all quality thresholds

---

## Stuck Log: Technical Challenges & Decisions

### 1. Shifted Row in Gig Workers CSV (`source2_gig_workers.csv` Row 20)
* **Problem:** Row 20 contained displaced columns where the skill list appeared in `email_id`, the email appeared in `worker_name`, the name in `rate`, the rate in `location`, and so forth.
* **Initial Reaction:** The safest standard approach would be skipping the row.
* **My Decision & Solution:** I inspected the data and observed that row 20 was a circular 1-column displacement. I engineered a guarded recovery routine that checks whether `email_id` lacks `@` while `worker_name` contains `@`. It shifts the fields back into alignment, validates that the recovered rate parses correctly, logs an auditable entry in `data_quality_issues` as `repaired_shifted_row`, and imports the person. This preserves 100% of legitimate applicant data while remaining fully deterministic and auditable.

### 2. Geographic Granularity: Delhi vs. New Delhi vs. Delhi NCR
* **Problem:** Unifying city names required deciding whether to collapse `Delhi`, `New Delhi`, and `Delhi NCR` into a single bucket.
* **My Decision & Solution:** In recruitment operations, candidates located in the National Capital Region (e.g. Gurgaon, Noida, Faridabad, Ghaziabad) often have different commute and remote-work preferences compared to central Delhi. I mapped `Delhi` and `New Delhi` together as `delhi`, while classifying `Delhi NCR` separately as `ncr`.

### 3. Audio Metadata DSP Without External Binaries
* **Problem:** Traditional audio metadata extraction relies on FFmpeg or libsox binaries, which can complicate deployment and grading environments.
* **My Decision & Solution:** I implemented client-side WAV encoding in JavaScript coupled with a pure-Python binary WAV decoder in `scripts/audio_metadata.py`. This calculates frame headers, sample width, channel count, and RMS signal energy mathematically using only Python's built-in `wave` and `math` modules, while retaining an optional `ffprobe` fallback for non-WAV formats.

---

## Scale Plan: 5,000 Workers in One Weekend

If ConsultBae runs a high-volume weekend hiring drive receiving **5,000 worker submissions in 48 hours**, the single-instance SQLite server would face bottlenecks around disk I/O, synchronous upload handling, and unqueued audio DSP.

Here is the architectural upgrade roadmap to handle this scale effortlessly:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               PRODUCTION SCALE ARCHITECTURE                            │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ 5,000 Workers / Browser Clients ]
                 │
                 ├── 1. Request Signed Upload URL ──► [ Fast API / Go Web Tier (Auto-scaled) ]
                 │                                                │
                 │                                                ▼ (Generates Presigned URL)
                 ├── 2. Direct S3 Upload ────────────► [ Amazon S3 / Cloudflare R2 Bucket ]
                 │                                                │
                 │                                                ▼ (S3 Event / SQS Message)
                 └── 3. Submit Metadata ─────────────► [ Asynchronous Task Queue (Celery/Redis) ]
                                                                  │
                                      ┌───────────────────────────┴───────────────────────────┐
                                      ▼                                                       ▼
                       [ Audio DSP Worker Pool ]                                [ Database Cluster ]
                       - FFmpeg Transcoding (WAV/MP3)                           - Managed PostgreSQL
                       - Speech-to-Text & Diarization (Whisper)                 - PgBouncer Pooling
                       - Quality & SNR Calculations                             - Read Replicas
```

### 1. Storage & Ingestion: Pre-Signed Direct Object Storage
* **Current:** Audio streams directly to the application server disk.
* **Scale Change:** Clients request a pre-signed PUT URL from the API and upload audio directly to **Amazon S3** or **Cloudflare R2**. The web server never handles heavy audio binary payloads, reducing server bandwidth and memory usage by 90%.

### 2. Database: PostgreSQL with Connection Pooling
* **Current:** SQLite database with file locks.
* **Scale Change:** Migrate to managed **PostgreSQL** with **PgBouncer** connection pooling.
* **Indexing:** Add B-Tree indexes on `normalized_email`, `normalized_phone`, and composite index on `(normalized_name, normalized_city)` for sub-millisecond duplicate checks across hundreds of thousands of records.

### 3. Asynchronous Audio Processing Queue
* **Current:** Audio metadata calculated synchronously during HTTP request.
* **Scale Change:** Offload audio extraction, speech-to-text transcription (OpenAI Whisper), and quality scoring to a background **Celery / Redis / AWS SQS** worker pool. The HTTP API returns `202 Accepted` immediately with a submission ID.

### 4. Idempotency & Duplicate Prevention
* **Scale Change:** Introduce `X-Idempotency-Key` headers on client submissions and unique database constraints on `(submitter_phone, audio_hash)` to prevent double submissions from unstable mobile network retries.

### 5. Observability & Rate Limiting
* **Rate Limiting:** Implement Redis token-bucket rate limiting (e.g. 20 requests/minute per IP) via Nginx or Cloudflare.
* **Monitoring:** Add Prometheus metrics and Grafana dashboards tracking upload throughput, queue lag, P95 audio processing latency, and error rates.

---



*Thank you for reviewing my assignment!*
