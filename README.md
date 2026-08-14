# ConsultBae AI Automation Assignment

This project is my submission for the ConsultBae AI Automation take-home assignment. It includes a CSV merge pipeline, a SQLite database, an n8n duplicate-check workflow, and a small audio collection web app.

## Overview

The solution covers the required tasks:

- Merge three messy CSV sources into one clean database.
- Deduplicate people using normalized email and phone values.
- Preserve raw source rows and log data-quality decisions.
- Provide an n8n workflow that checks new records for duplicates.
- Provide a browser-based audio submission app with metadata extraction.
- Document data issues, implementation choices, stuck points, and scale considerations.

## Tech Stack

- Python 3.11+
- SQLite
- Standard-library HTTP server
- Browser JavaScript for WAV audio recording
- n8n for the no-code automation

The core project intentionally avoids heavy dependencies so it is easy to run and review.

## Local Setup

From the project root:

```bash
python scripts/ingest.py
python scripts/smoke_test.py
python app/main.py
```

Open:

```text
http://127.0.0.1:8000
```

Useful verification commands:

```bash
python scripts/ingest.py
python scripts/smoke_test.py
python scripts/test_app_api.py
```

## Deployment

The app can run outside my local machine on a service such as Render, Railway, or any host that supports Python web services.

The deployed functionality is the same as the local functionality:

- the audio form works from a public URL;
- `/api/check-duplicate` is available to n8n or other tools;
- the app still writes people and audio submission rows to SQLite;
- uploaded audio is still stored on the server filesystem.

The important difference is persistence. On many free hosting plans, the server filesystem is temporary. That is fine for a short demo, but for a production launch I would move the database to Postgres and audio files to object storage such as S3, Cloudflare R2, or Google Cloud Storage.

Deployment start command:

```bash
python scripts/start_app.py
```

`scripts/start_app.py` runs ingestion first, creates `database.sqlite`, and then starts the app. The app reads the platform `PORT` environment variable and binds to `0.0.0.0`, which is required by most web service hosts.

Suggested deployment steps:

1. Push this repository to GitHub.
2. Create a new Python web service on Render or Railway.
3. Connect the GitHub repository.
4. Use this build command:

```bash
pip install -r requirements.txt
```

5. Use this start command:

```bash
python scripts/start_app.py
```

6. Open the public URL provided by the host.

## Project Structure

```text
app/
  main.py
  static/
  templates/
automations/
  n8n_duplicate_alert.json
data/
  raw/
scripts/
  audio_metadata.py
  database.py
  ingest.py
  match_people.py
  normalize.py
  smoke_test.py
  start_app.py
  test_app_api.py
storage/
  audio/
```

## Database Design

The SQLite database is created at:

```text
database.sqlite
```

Main tables:

- `people`
- `person_emails`
- `person_phones`
- `person_skills`
- `source_records`
- `data_quality_issues`
- `match_candidates`
- `audio_submissions`

I kept source-level traceability through `source_records` so the cleaned database can always be audited against the original CSV rows.

## Matching Logic

Automatic merges:

- same normalized email;
- same normalized phone.

Review candidates:

- same normalized name and normalized city without a shared email or phone.

I did not merge on name alone because the data has repeated names, missing fields, initials, alternate emails, and common city values. A conservative merge is better here than incorrectly combining two different people.

## Normalization Rules

Emails:

- trim spaces;
- lowercase before matching.

Phones:

- remove non-digit characters;
- convert Indian 10-digit and leading-zero formats into `91xxxxxxxxxx`.

Cities:

- `Gurgaon` -> `gurugram`
- `Bangalore` -> `bengaluru`
- `New Delhi` -> `delhi`
- `Delhi` -> `delhi`
- `Delhi NCR` -> `ncr`

Dates:

- parse known formats into ISO date format where possible.

CTC:

- large numeric values are treated as annual rupee values and converted to LPA;
- small decimal values are treated as already being LPA.

Gig rates:

- `1415/hr` is parsed as hourly;
- `15k/month` is parsed as monthly.

## n8n Automation

Workflow file:

```text
automations/n8n_duplicate_alert.json
```

Demo payload:

```json
{
  "name": "Tanvi Gupta",
  "email": "tanvi.gupta31@example.com",
  "phone": "+91-9000000254",
  "city": "Bangalore"
}
```

The workflow calls:

```text
http://host.docker.internal:8000/api/check-duplicate
```

If n8n is not running in Docker, I would change that URL to:

```text
http://127.0.0.1:8000/api/check-duplicate
```

The API returns whether a duplicate was found, the match type, and the matched person details.

## Audio App

The app supports:

- name and phone entry;
- optional city entry;
- browser recording;
- audio file upload;
- database insert;
- listing of all submissions;
- playback from the submissions table.

For WAV files, the app extracts:

- duration;
- sample rate in kHz;
- bitrate in kbps;
- loudness in dB;
- simple quality estimate.

The browser recorder creates WAV files directly, so the demo does not depend on ffmpeg. If I wanted broader upload support for MP3 or WebM in production, I would install ffmpeg and use `ffprobe` for all formats.

## Data Issues Report

Current ingestion result:

- raw rows read: 105
- usable imported rows: 103
- canonical people after email/phone merge: 60
- logged data-quality issues: 3
- review match candidates: 7

Issues found and handled:

- Mixed phone formats were normalized into one Indian phone format.
- Email casing differences were normalized by lowercasing.
- City casing and aliases were normalized, with `Delhi` and `New Delhi` grouped as `delhi`, and `Delhi NCR` kept separately as `ncr`.
- Naukri applied dates appeared in multiple formats and were parsed into ISO dates where possible.
- CTC values used mixed units, so annual rupee values were converted to LPA and small decimals were treated as LPA.
- Gig rates used hourly and monthly formats, both of which are parsed into amount and unit.
- Worker status values had case differences and were normalized.
- CBNexus verified values used `Y`, `yes`, `Yes`, `No`, and `N`, which were normalized to booleans.
- CBNexus contained a repeated header row inside the file; I skipped and logged it.
- The gig-worker file contained one shifted row; I repaired it by shifting values back into their expected columns after validating the recovered email and rate.
- One row had no usable identity and was skipped with a logged issue.
- Duplicate rows and duplicate people across sources were merged through email and phone keys.
- Name abbreviations such as `R. Verma` were only merged when a stronger email or phone key matched.

## Stuck Log

1. The hardest data issue was the shifted gig-worker row. At first it looked unsafe because the skill list appeared in the email column and every later value was displaced. I inspected the row manually, found that the values were consistently shifted left, then added a guarded repair that only runs when the recovered email contains `@` and the recovered rate parses correctly. I chose this over skipping the row because the repair was deterministic and auditable.

2. City normalization needed judgment. I initially considered grouping `Delhi`, `New Delhi`, and `Delhi NCR` together, but that would hide a useful operational distinction. I now map `Delhi` and `New Delhi` to `delhi`, while keeping `Delhi NCR` as `ncr`.

3. Audio metadata was unfamiliar territory. My first assumption was that the demo would require ffmpeg everywhere. I avoided making the app fragile by recording WAV directly in the browser and extracting WAV metadata with Python's standard `wave` module. I kept optional `ffprobe` support for non-WAV uploads.

## Scale Plan: 5,000 Workers In One Weekend

The first likely bottlenecks would be uploads, local disk storage, duplicate submissions, synchronous audio processing, and lack of retry visibility.

Before launching at that scale, I would change:

- move audio storage to S3, R2, or GCS;
- move the database from SQLite to Postgres;
- process audio metadata asynchronously through a queue;
- add upload size and duration limits;
- add duplicate checks before accepting audio;
- make uploads retry-safe;
- add monitoring for upload failure rate, queue lag, storage usage, and API errors;
- add backups and a basic admin review page.

## Video Walkthrough Checklist

In the screen recording I would show:

1. Running `python scripts/ingest.py`.
2. Running `python scripts/smoke_test.py`.
3. The merged database result.
4. The n8n workflow JSON.
5. A duplicate-check API call.
6. The audio app recording or uploading a file.
7. The submission list with playback and extracted metadata.
8. The matching decisions and data-quality issues.
