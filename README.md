# Sorty AI

Sorty AI is a backend-first Event MediaOps system for turning messy event photo dumps into reviewed, searchable, export-ready archives.

It follows the locked PRD/TRD direction:

- FastAPI backend with API-key auth
- SQLAlchemy 2.0, Alembic, PostgreSQL, and pgvector
- Redis + RQ background processing
- MinIO object storage for originals, thumbnails, and export ZIPs
- LangGraph lifecycle checkpoint/resume workflow for human review
- Mock, Ollama, and Gemini vision providers
- Blur and duplicate detection
- pgvector-backed semantic search with sentence-transformers embeddings
- Organized ZIP export with metadata

No JWT/OAuth is used. No ChromaDB, Pinecone, or Weaviate is used.

## Current Status

Backend MVP supports upload, queued processing, AI analysis, review, graph resume,
semantic search, and organized ZIP export. Mock providers remain available for
tests and quick demos.

## Quick Start

From the repository root:

```powershell
docker compose up --build
```

In another terminal, run migrations:

```powershell
docker compose run --rm backend alembic upgrade head
```

The Compose stack starts the backend, worker, Postgres/pgvector, Redis, and MinIO.
The first sentence-transformers use may download
`sentence-transformers/all-MiniLM-L6-v2` into the container/cache.

Useful URLs:

- Backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

Default local credentials from `.env.example`:

- API key: `demo-secret`
- MinIO user: `sortyadmin`
- MinIO password: `sortypassword`

## Health Checks

Liveness:

```powershell
curl.exe http://localhost:8000/api/health
```

Readiness:

```powershell
curl.exe http://localhost:8000/api/ready
```

`/api/ready` checks database, Redis, storage, the selected vision provider, and
the selected embedding provider without exposing connection strings or secrets.
External AI providers are validated only when selected.

## Provider Modes

Mock vision demo mode:

```powershell
# .env or .env.example
VISION_PROVIDER=mock
EMBEDDING_PROVIDER=sentence-transformers
```

Mock vision requires no API keys. To avoid model downloads in a quick demo, set
`EMBEDDING_PROVIDER=mock`; keep `sentence-transformers` for functional search.

Ollama vision mode with host Ollama:

```powershell
ollama pull llava

# .env
VISION_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_VISION_MODEL=llava
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_DIMENSION=384
```

Use `http://localhost:11434` only when running the backend directly on the host.
The provided Compose file does not start an Ollama service.

Gemini vision mode:

```powershell
# .env
VISION_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_VISION_MODEL=gemini-2.0-flash
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_DIMENSION=384
```

Readiness checks only that `GEMINI_API_KEY` exists; it does not call Gemini.

## Test Suite

Use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/unit
```

Integration tests may require Docker services:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/integration
```

## Backend Smoke Test

With the backend, worker, Postgres, Redis, and MinIO running, use the reusable
smoke script to exercise the full HTTP flow: event creation, image upload,
worker processing, review/resume, semantic search, export generation, ZIP
download, and ZIP metadata validation.

Mock mode:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_backend.py `
  --mode mock `
  --base-url http://localhost:8000 `
  --api-key demo-secret
```

Ollama mode, after restarting backend and worker with `VISION_PROVIDER=ollama`:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_backend.py `
  --mode ollama `
  --base-url http://localhost:8000 `
  --api-key demo-secret `
  --image-count 1
```

Smoke artifacts are written under `.tmp/`, which is gitignored.

## Main Backend Flow

1. Create an event.
2. Upload a batch of images.
3. Backend stores originals and thumbnails in MinIO.
4. RQ worker processes the batch.
5. The selected vision provider generates AI metadata.
6. Quality service scores blur and duplicate candidates.
7. Clean images are auto-approved for export.
8. Low-confidence, blurry, or duplicate-like images go to review.
9. LangGraph checkpoints the lifecycle and interrupts if review is required.
10. Review decisions resolve pending items, then `/api/jobs/{job_id}/resume`
    continues the graph to finalized.
11. Search uses pgvector embeddings.
12. Export creates an organized ZIP in MinIO.

Typical API flow:

```powershell
$headers = @{ "X-API-Key" = "demo-secret" }

Invoke-RestMethod -Method Post http://localhost:8000/api/events `
  -Headers $headers -ContentType "application/json" `
  -Body '{"name":"Demo Event","event_type":"demo"}'

# Upload images with multipart/form-data to:
# POST /api/events/{event_id}/media

# Poll:
# GET /api/jobs/{job_id}
# GET /api/events/{event_id}/review

# After resolving review items:
# POST /api/jobs/{job_id}/resume

# Search and export:
# GET /api/events/{event_id}/search?q=stage
# POST /api/events/{event_id}/exports
```

See [docs/MANUAL_SMOKE_TEST.md](docs/MANUAL_SMOKE_TEST.md) for a command-level walkthrough.

## Architecture Notes

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how FastAPI, RQ, MinIO, Postgres, pgvector, and LangGraph fit together.
