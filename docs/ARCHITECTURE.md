# Architecture

Sorty AI is intentionally backend-heavy. The frontend is expected to be thin and should not know about storage keys, embeddings, provider internals, or LangGraph checkpoint details.

## Components

FastAPI owns the public HTTP contract:

- event APIs
- media upload/read APIs
- job status and resume APIs
- review APIs
- search APIs
- export APIs
- health/readiness APIs

PostgreSQL owns durable application state:

- events
- media assets
- batch jobs
- AI analyses
- quality signals
- duplicate groups
- review decisions
- media embeddings
- export jobs

pgvector stores semantic media embeddings inside PostgreSQL. This keeps search in the primary database and avoids external vector databases.

MinIO owns binary objects:

- uploaded originals
- generated thumbnails
- export ZIP archives

Redis + RQ own background execution:

- batch media processing
- graph resume jobs
- export generation

LangGraph owns workflow checkpointing and human-review interrupt/resume behavior. The worker creates or resumes the existing graph thread; resume must not create a new thread.

## Processing Flow

```text
POST /api/events/{event_id}/media/batch-upload
  -> validate image
  -> create media_assets rows
  -> store originals/thumbnails in MinIO
  -> create batch_jobs row
  -> enqueue RQ processing job

RQ worker
  -> download original from MinIO
  -> MockVisionProvider analysis
  -> save ai_analyses
  -> score quality
  -> detect duplicates
  -> create pending review or auto-approved review decision
  -> index media embedding
  -> update job status
  -> create LangGraph checkpoint/interruption if review is needed
```

## Review And Resume

Pending review rows are the API-facing human checkpoint.

```text
GET /api/events/{event_id}/review-queue
PATCH /api/media/{media_id}/review
POST /api/jobs/{job_id}/resume
```

The resume API validates that:

- the job exists
- all pending reviews are resolved
- resolved review decisions are valid
- the same LangGraph thread is resumed

## Export

Export reads reviewed media and storage objects, creates an organized ZIP, then stores that ZIP in MinIO.

```text
POST /api/events/{event_id}/export
GET /api/exports/{export_id}
GET /api/exports/{export_id}/download
```

Exports exclude rejected media and duplicates by default. Pending media can be blocked or included based on the export request.

## Source Of Truth

- PostgreSQL owns metadata, workflow state, review state, embeddings, and export state.
- MinIO owns binary media and generated archives.
- LangGraph owns checkpoint data for workflow resume.
- The frontend is only a client of backend APIs.
