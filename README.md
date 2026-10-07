# Bulk Certificate Generator

A compact FastAPI backend that accepts one bulk request containing multiple recipients, generates one PDF certificate per valid recipient from a single predefined design, persists job/item status in SQLite, and exposes status, result, and download endpoints.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for reproducible dependency installation from `uv.lock`

No external database, queue, browser runtime, or cloud service is required.

## Setup

```bash
git clone https://github.com/Suraj-H675/Bulk-Certificate-Generator.git
cd Bulk-Certificate-Generator
uv sync --group dev
```

## Run the API

```bash
uv run uvicorn bulk_certificate_generator.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`. FastAPI's interactive OpenAPI documentation is at `/docs`.

Runtime data is local by default:

- SQLite database: `var/bcg.db`
- generated PDFs: `var/certificates/<job-id>/<certificate-id>.pdf`

Both locations are ignored by Git. They can be changed with `BCG_DATABASE_URL` and `BCG_ARTIFACT_DIR`.

## Submit a bulk certificate job

`POST /api/jobs` accepts one certificate definition and a list of recipients:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "certificate": {
      "title": "Certificate of Completion",
      "event_name": "Backend Workshop",
      "issue_date": "2026-10-08"
    },
    "recipients": [
      {"name": "Alice Example", "email": "alice@example.com"},
      {"name": "Bob Example", "email": "bob@example.com"},
      {"name": "Charlie Example"}
    ]
  }'
```

The endpoint returns `202 Accepted` with a job ID and the current counts, for example:

```json
{
  "id": "<job-id>",
  "status": "PENDING",
  "total_count": 3,
  "processed_count": 0,
  "success_count": 0,
  "invalid_count": 0,
  "failed_count": 0
}
```

The exact status in the create response is the state at response creation. Processing is scheduled immediately in the application background.

## Check progress and results

Get aggregate job status and exact counts:

```bash
curl http://127.0.0.1:8000/api/jobs/<job-id>
```

Terminal jobs are `COMPLETED` when all recipients generate successfully, `COMPLETED_WITH_ERRORS` when one or more recipients are invalid or fail generation, and `FAILED` only for a job-level processing failure.

Get the per-recipient outcomes:

```bash
curl http://127.0.0.1:8000/api/jobs/<job-id>/certificates
```

Each item is independently reported as `PENDING`, `PROCESSING`, `INVALID`, `GENERATED`, or `FAILED`. Generated items include a `download_url`; invalid/failed items include a safe `error_message`.

## Retrieve a generated certificate

Use the `download_url` from the item results, or call:

```bash
curl -o certificate.pdf \
  http://127.0.0.1:8000/api/jobs/<job-id>/certificates/<certificate-id>/download
```

Only successfully generated items can be downloaded. Unknown resources return `404`; known items that are invalid, failed, or not yet generated return `409`.

## Run tests

```bash
uv run pytest -q
```

The focused suite covers the assignment's required areas: bulk job creation, top-level and recipient-level input validation, real PDF generation, status/progress counts, deliberate one-item generation failure with successful siblings, and real certificate retrieval. Tests use temporary SQLite databases and artifact directories and do not sleep, poll, or require network services.

## Design decisions and tradeoffs

### FastAPI + SQLAlchemy + SQLite

FastAPI keeps the HTTP contract typed and small. SQLAlchemy provides explicit relational persistence while SQLite makes reviewer setup zero-service. The persistence code is ordinary SQLAlchemy rather than SQLite-specific query logic, so moving to PostgreSQL later is localized, but this submission does not pretend SQLite is a high-concurrency production database.

### Background processing without queue infrastructure

The HTTP endpoint persists the job and all recipient items before scheduling `process_job(job_id)` with FastAPI's in-process background-task mechanism. The processor itself is framework-independent and owns state transitions, generation, storage, and progress updates.

This keeps bulk requests from holding the HTTP response open and makes progress/status meaningful without adding Redis/Celery solely for a take-home. The tradeoff is intentional: in-process background work is not durable across application crashes or suitable for arbitrary horizontal workers. A production deployment needing those properties would replace the scheduling boundary with a durable external queue while retaining the processor/service logic.

### Request-level vs recipient-level validation

Malformed top-level requests are rejected with `422`. Recipient entries are then validated individually. An invalid recipient becomes an `INVALID` item and counts as processed while valid siblings continue. This distinction is deliberate so a single bad recipient does not defeat the assignment's bulk/failure-isolation requirement.

### Failure isolation and progress

Recipients are processed sequentially. Each item has its own state transition and persistence step; one generation/storage failure is recorded as `FAILED` and processing continues with later recipients. Exact counts are persisted with the invariant:

```text
processed_count = success_count + invalid_count + failed_count
```

At a normal terminal state, `processed_count == total_count`.

Sequential processing is preferable here to premature parallel writes against SQLite. Parallelism can be introduced later if measured workload justifies the added coordination.

### PDF generation and local storage

ReportLab renders one predefined landscape A4 certificate design using built-in fonts. Long recipient names shrink within a bounded range rather than determining filenames or filesystem paths.

Artifacts are stored under generated job/certificate UUIDs and written through a temporary file plus atomic replace. The database stores a relative artifact key, not PDF blobs or user-provided paths.

## Repository shape

```text
src/bulk_certificate_generator/
  api.py        HTTP routes and response behavior
  app.py        application composition
  config.py     local runtime configuration
  db.py         SQLAlchemy engine/session setup
  generator.py  predefined PDF certificate renderer
  models.py     relational job/item state
  schemas.py    request/response contracts
  service.py    job creation and processing
  storage.py    local artifact storage boundary
tests/          focused required-behavior tests
```

The project intentionally does not include a frontend, template editor, authentication, email delivery, multiple certificate designs, cloud storage, or distributed queue infrastructure because none are required by the assignment.
