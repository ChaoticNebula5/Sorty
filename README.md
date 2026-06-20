# Sorty AI

Sorty AI is an AI-powered event media management backend that helps event teams upload, process, review, search, and export large batches of event photos.

It is designed for college societies, hackathon teams, cultural fest teams, and social media teams that need to quickly organize raw event photos into clean, usable folders.

## Features

* Batch image upload for event-based media libraries
* AI-generated captions, tags, and folder suggestions
* Blur and image quality detection
* Duplicate photo detection using perceptual hashing
* Human review workflow for blurry, duplicate, or uncertain images
* Semantic media search using PostgreSQL and pgvector
* ZIP export with organized folders, metadata CSV, and summary file
* Background processing with Redis and RQ workers
* Object storage using MinIO
* LangGraph lifecycle checkpoint/resume workflow for human review
* Mock, Ollama, and Gemini vision providers
* Sentence-transformers embeddings for functional local search
* Dockerized local development setup
* Unit and integration test coverage

Backend MVP supports upload, queued processing, AI analysis, review, graph resume, semantic search, and organized ZIP export. Mock providers remain available for tests and quick demos.

## Tech Stack

* **Backend:** FastAPI, Python, SQLAlchemy, Pydantic
* **Database:** PostgreSQL, pgvector, Alembic
* **Queue:** Redis, RQ
* **Storage:** MinIO
* **AI Workflow:** LangGraph
* **AI Providers:** Mock, Ollama, Gemini
* **Testing:** Pytest
* **Deployment:** Docker, Docker Compose

## System Flow

```text
Create Event
  -> Upload Photos
  -> Background AI Processing
  -> Quality + Duplicate Detection
  -> Human Review
  -> Search / Browse Media
  -> Export Organized ZIP
```

## Architecture

```text
FastAPI Backend
  |-- PostgreSQL + pgvector
  |-- Redis / RQ Worker
  |-- MinIO Object Storage
  `-- LangGraph Review Workflow
```

The backend processes uploaded images asynchronously. Media files are stored in MinIO, metadata and embeddings are stored in PostgreSQL, and Redis/RQ handles background jobs.

LangGraph records lifecycle checkpoint/resume state around the worker flow. It pauses when human review is required and resumes after review decisions are completed.

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/ChaoticNebula5/Sorty.git
cd Sorty
```

### 2. Create Environment File

```bash
cp .env.example .env
```

For Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

### 3. Start the Docker Stack

```bash
docker compose up --build
```

### 4. Run Database Migrations

In another terminal:

```bash
docker compose run --rm backend alembic upgrade head
```

The Compose stack starts the backend, worker, Postgres/pgvector, Redis, and MinIO. The first sentence-transformers use may download `sentence-transformers/all-MiniLM-L6-v2` into the container/cache.

### 5. Open API Docs

```text
http://localhost:8000/docs
```

Useful local URLs:

* Backend API: `http://localhost:8000`
* OpenAPI docs: `http://localhost:8000/docs`
* MinIO console: `http://localhost:9001`

Default local credentials from `.env.example`:

* API key: `demo-secret`
* MinIO user: `sortyadmin`
* MinIO password: `sortypassword`

## Health Checks

Liveness:

```powershell
curl.exe http://localhost:8000/api/health
```

Readiness:

```powershell
curl.exe http://localhost:8000/api/ready
```

`/api/ready` checks database, Redis, storage, the selected vision provider, and the selected embedding provider without exposing connection strings or secrets. External AI providers are validated only when selected.

## Provider Modes

Mock vision demo mode:

```powershell
# .env or .env.example
VISION_PROVIDER=mock
EMBEDDING_PROVIDER=sentence-transformers
```

Mock vision requires no API keys. To avoid model downloads in a quick demo, set `EMBEDDING_PROVIDER=mock`; keep `sentence-transformers` for functional search.

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

Use `http://localhost:11434` only when running the backend directly on the host. The provided Compose file does not start an Ollama service.

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

## Running Tests

### Unit Tests

Use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/unit
```

Or, if your shell is already using the project environment:

```bash
python -m pytest backend/app/tests/unit
```

### Integration Tests

Integration tests may require Docker services:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/app/tests/integration
```

For Windows users, if pytest faces temp/cache permission issues, run tests with a local temp directory:

```powershell
New-Item -ItemType Directory -Force .\.tmp\pytest | Out-Null
$env:TEMP=".tmp"
$env:TMP=".tmp"

python -m pytest backend/app/tests/unit `
  --basetemp=.tmp\pytest `
  -p no:cacheprovider
```

## Backend Smoke Test

With the backend, worker, Postgres, Redis, and MinIO running, use the reusable smoke script to exercise the full HTTP flow: event creation, image upload, worker processing, review/resume, semantic search, export generation, ZIP download, and ZIP metadata validation.

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
10. Review decisions resolve pending items, then `/api/jobs/{job_id}/resume` continues the graph to finalized.
11. Search uses pgvector embeddings.
12. Export creates an organized ZIP in MinIO.

Typical API flow:

```powershell
$headers = @{ "X-API-Key" = "demo-secret" }

Invoke-RestMethod -Method Post http://localhost:8000/api/events `
  -Headers $headers -ContentType "application/json" `
  -Body '{"name":"Demo Event","event_type":"demo"}'

# Upload images with multipart/form-data to:
# POST /api/events/{event_id}/media/batch-upload

# Poll:
# GET /api/jobs/{job_id}
# GET /api/events/{event_id}/review-queue

# After resolving review items:
# POST /api/jobs/{job_id}/resume

# Search and export:
# GET /api/events/{event_id}/search?q=stage
# POST /api/events/{event_id}/export
```

## Main API Flow

```text
POST /api/events
POST /api/events/{event_id}/media/batch-upload
GET  /api/jobs/{job_id}
GET  /api/events/{event_id}/review-queue
PATCH /api/media/{media_id}/review
POST /api/jobs/{job_id}/resume
GET  /api/events/{event_id}/search
POST /api/events/{event_id}/export
GET  /api/exports/{export_id}/download
```

## Project Status

* Backend MVP completed
* Docker-based local setup completed
* Worker-based media processing completed
* Human review and resume workflow completed
* Search and export workflow completed
* Unit tests passing
* Integration tests passing
* Frontend pending

## Future Improvements

* Build a minimal frontend dashboard
* Add user authentication and role-based access
* Improve AI folder classification
* Add cloud deployment support
* Add bulk actions for review and export workflows
* Add deployment-ready observability and monitoring

## License

This project is currently intended for learning, experimentation, and portfolio demonstration.
