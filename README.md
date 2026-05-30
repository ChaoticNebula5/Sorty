# Sorty AI

Sorty AI is an AI-powered event media management backend that helps event teams upload, process, review, search, and export large batches of event photos.

It is designed for college societies, hackathon teams, cultural fest teams, and social media teams that need to quickly organize raw event photos into clean, usable folders.

---

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
* Dockerized local development setup
* Unit and integration test coverage

---

## Tech Stack

* **Backend:** FastAPI, Python, SQLAlchemy, Pydantic
* **Database:** PostgreSQL, pgvector, Alembic
* **Queue:** Redis, RQ
* **Storage:** MinIO
* **AI Workflow:** LangGraph
* **AI Providers:** Mock Vision Provider, Gemini Vision Provider
* **Testing:** Pytest
* **Deployment:** Docker, Docker Compose

---

## System Flow

```text
Create Event
   ↓
Upload Photos
   ↓
Background AI Processing
   ↓
Quality + Duplicate Detection
   ↓
Human Review
   ↓
Search / Browse Media
   ↓
Export Organized ZIP
```

---

## Architecture

```text
FastAPI Backend
   ├── PostgreSQL + pgvector
   ├── Redis / RQ Worker
   ├── MinIO Object Storage
   └── LangGraph Review Workflow
```

The backend processes uploaded images asynchronously. Media files are stored in MinIO, metadata and embeddings are stored in PostgreSQL, and Redis/RQ handles background jobs.

LangGraph is used to pause processing when human review is required and resume the workflow after review decisions are completed.

---

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

### 5. Open API Docs

```text
http://localhost:8000/docs
```

---

## Running Tests

### Unit Tests

```bash
python -m pytest backend/app/tests/unit
```

### Integration Tests

Start Docker services first, then run:

```bash
python -m pytest backend/app/tests/integration -m integration
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

---

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

---

## Project Status

* Backend MVP completed
* Docker-based local setup completed
* Worker-based media processing completed
* Human review and resume workflow completed
* Search and export workflow completed
* Unit tests passing
* Integration tests passing
* Frontend pending

---

## Future Improvements

* Build a minimal frontend dashboard
* Add user authentication and role-based access
* Improve AI folder classification
* Add cloud deployment support
* Add bulk actions for review and export workflows
* Add deployment-ready observability and monitoring

---

## License

This project is currently intended for learning, experimentation, and portfolio demonstration.
