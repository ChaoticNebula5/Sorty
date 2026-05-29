# Sorty AI

Sorty AI is a backend-first Event MediaOps system for turning messy event photo dumps into reviewed, searchable, export-ready archives.

It follows the locked PRD/TRD direction:

- FastAPI backend with API-key auth
- SQLAlchemy 2.0, Alembic, PostgreSQL, and pgvector
- Redis + RQ background processing
- MinIO object storage for originals, thumbnails, and export ZIPs
- LangGraph checkpoint/resume workflow for human review
- MockVisionProvider as the default AI provider
- Blur and duplicate detection
- pgvector-backed semantic search
- Organized ZIP export with metadata

No JWT/OAuth is used. No ChromaDB, Pinecone, or Weaviate is used.

## Current Status

Backend MVP is smoke-verified via the Docker-backed manual smoke test.
The next work before a basic UI is:

- add a few integration tests around Postgres, MinIO, Redis/RQ, and export
- optionally add Gemini behind the existing `VisionProvider`
- build a minimal UI after backend flow is proven

## Quick Start

From the repository root:

```powershell
docker compose up --build
```

In another terminal, run migrations:

```powershell
docker compose run --rm backend alembic upgrade head
```

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

`/api/ready` checks database, Redis, and storage reachability without exposing connection strings or secrets.

## Test Suite

Use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/unit
```

At the time of writing, the unit suite has 191 passing tests.

## Main Backend Flow

1. Create an event.
2. Upload a batch of images.
3. Backend stores originals and thumbnails in MinIO.
4. RQ worker processes the batch.
5. MockVisionProvider generates AI metadata.
6. Quality service scores blur and duplicate candidates.
7. Clean images are auto-approved for export.
8. Low-confidence, blurry, or duplicate-like images go to review.
9. Review decisions resume the LangGraph workflow.
10. Search uses pgvector embeddings.
11. Export creates an organized ZIP in MinIO.

See [docs/MANUAL_SMOKE_TEST.md](docs/MANUAL_SMOKE_TEST.md) for a command-level walkthrough.

## Architecture Notes

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how FastAPI, RQ, MinIO, Postgres, pgvector, and LangGraph fit together.
