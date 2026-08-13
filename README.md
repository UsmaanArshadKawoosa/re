# ConsultBae AI Automation Assignment

This repo contains a working SQLite merge pipeline, a no-code n8n duplicate-check workflow export, and a miniature audio collection app.

## Setup

Use Python 3.11+.

```bash
python scripts/ingest.py
python scripts/smoke_test.py
python app/main.py
```

Open the app at:

```text
http://127.0.0.1:8000
```

The project uses only the Python standard library for the core demo. The browser recorder creates WAV files, so the app can extract duration, sample rate, bitrate, loudness, and a simple quality estimate without ffmpeg. If you upload MP3/WebM manually, install ffmpeg so `ffprobe` is available on PATH.

## What Is Implemented

- Imports all three CSV files from `data/raw/`.
- Preserves raw rows in `source_records`.
- Logs cleanup decisions in `data_quality_issues`.
- Merges people by normalized email and normalized phone.
- Keeps name + city matches as review candidates instead of blindly merging them.
- Provides `/api/check-duplicate` for n8n.
- Provides audio upload/browser recording, metadata extraction, database insert, listing, and playback.

## Database

The SQLite database is created at `database.sqlite`.

Important tables:

- `people`
- `person_emails`
- `person_phones`
- `person_skills`
- `source_records`
- `data_quality_issues`
- `match_candidates`
- `audio_submissions`

## Matching Logic

Automatic merge rules:

- Same normalized email means same person.
- Same normalized phone means same person.

Candidate-only rule:

- Same normalized name + normalized city is recorded in `match_candidates` for review.

I avoided automatic name-only matching because the source files contain common Indian names, abbreviations, alternate emails, missing phones, and at least one case where the same name/city appears with different contact information.

## n8n Automation

Import:

```text
automations/n8n_duplicate_alert.json
```

Expected demo flow:

1. Start the Python app locally.
2. Import the n8n JSON.
3. Send this JSON to the webhook:

```json
{
  "name": "Tanvi Gupta",
  "email": "tanvi.gupta31@example.com",
  "phone": "+91-9000000254",
  "city": "Bangalore"
}
```

4. n8n calls:

```text
http://host.docker.internal:8000/api/check-duplicate
```

If n8n is not running in Docker, change the URL to:

```text
http://127.0.0.1:8000/api/check-duplicate
```

The response includes `duplicate`, `match_type`, and matched person details.

## Data Issues Report

Issues found and handling:

- Mixed phone formats: removed non-digits and normalized Indian 10-digit/leading-zero numbers into `91xxxxxxxxxx`.
- Mixed email casing: lowercased emails before matching.
- Mixed city spelling/casing: normalized known aliases such as `Gurgaon -> gurugram`, `Bangalore -> bengaluru`, `New Delhi/Delhi NCR -> delhi`.
- Multiple date formats in Naukri source: parsed known formats into ISO dates where possible.
- CTC inconsistency: values above 1000 treated as rupees per year and converted to LPA; smaller decimal values treated as already LPA.
- Gig worker rate inconsistency: parsed `1415/hr` and `15k/month` into amount + unit.
- Status inconsistency: normalized `Active`, `active`, `ACTIVE`, `Inactive`, and `paused`.
- Verified inconsistency: normalized `Y`, `yes`, `Yes`, `No`, `N`.
- Repeated header row in CBNexus source: skipped and logged.
- Malformed shifted row in gig worker source: skipped and logged instead of guessing a risky repair.
- Blank identity fields: skipped if a row has no usable name, email, or phone.
- Duplicate rows inside source1: merged by email/phone.
- Name abbreviations such as `R. Verma`: merged only when email/phone matched.

Current ingestion result:

- Raw rows read: 105
- Usable imported rows: 102
- Canonical people after strong-key merge: 60
- Logged data-quality issues: 3
- Review match candidates: 7

## Stuck Log

1. The gig worker file had one row shifted left, where the skill list appeared in the email column. I first considered repairing it positionally, but rejected that because it could hide a real corruption. I logged and skipped it instead.

2. City aliases were tricky because `Delhi`, `New Delhi`, and `Delhi NCR` can mean different operational areas. For this assignment I normalized them to `delhi` for matching, but documented the choice because a real CRM may need a richer location model.

3. Audio metadata looked like it needed ffmpeg, but ffmpeg was not guaranteed locally. I avoided making the demo fragile by recording WAV in the browser and using Python's standard `wave` module. I left optional ffprobe support for non-WAV uploads.

## Stretch: 5,000 Workers In One Weekend

What breaks first:

- Local disk fills with audio uploads.
- Synchronous audio processing slows form submission.
- Users retry uploads and create duplicates.
- Large files cause timeouts.
- Server memory and bandwidth become bottlenecks.
- No monitoring means failures are discovered late.

Before launch:

- Store audio in S3/R2/GCS instead of local disk.
- Process metadata asynchronously with a queue.
- Add file size and duration limits.
- Add resumable/retry-safe uploads.
- Use phone-based duplicate prevention before accepting audio.
- Add worker-facing upload status.
- Add monitoring for upload failures, queue delay, and storage cost.
- Put the app behind a production server and database backups.

## Video Checklist

Show these in the screen recording:

1. Run `python scripts/ingest.py`.
2. Run `python scripts/smoke_test.py`.
3. Import or show the n8n workflow JSON.
4. Trigger duplicate check with a known person.
5. Open the audio app.
6. Record or upload audio.
7. Submit and show the extracted metadata plus playback.
8. Explain the matching rules and the malformed rows.
