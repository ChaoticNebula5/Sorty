# Sorty AI Handoff For Next Agent

## Current State

Sorty AI is a backend-first Event MediaOps project. The backend MVP is now working through the main local Docker smoke path.

Locked technical direction:

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL with pgvector
- Redis + RQ
- MinIO as the source of truth for binary files
- LangGraph for review workflow checkpoints
- Pydantic v2
- API-key auth only
- MockVisionProvider first
- No frontend-first work
- No JWT/OAuth
- No ChromaDB/Pinecone/Weaviate

Important context files:

- `START_HERE.md`
- `CODING_AGENT_PROMPT.md`
- `Sorty_AI_FULL_BUILD_CONTEXT_PACK.md`
- `docs/ARCHITECTURE.md`
- `docs/MANUAL_SMOKE_TEST.md`
- `README.md`

The user wants teaching-style collaboration, not blind code generation. Explain design choices clearly and keep the user involved.

## Recent Fixes

Recent commits:

```text
768f43a fix: manage LangGraph checkpoint schema with Alembic
d2ce73b fix: reuse quality signal during duplicate detection
452a690 fix: support alembic imports in docker
```

### Quality Signal Duplicate Fix

The worker was creating a pending `QualitySignal`, then duplicate detection queried for the same row before flush/commit and created a second row. PostgreSQL rejected it with:

```text
duplicate key value violates unique constraint "uq_quality_signals_media_id"
```

Fix:

- `quality_service.detect_duplicate_for_media()` now accepts an optional existing `quality_signal`.
- `worker/tasks.py` passes the already-created object into duplicate detection.
- Worker counters now increment only after `db.commit()` succeeds.
- `MediaAssetRead` exposes `processing_error`.

### LangGraph Checkpoint Fix

LangGraph `PostgresSaver.setup()` was running inside the RQ worker job. That caused a 180 second timeout during checkpoint table/index setup.

Fix:

- Added Alembic migrations for LangGraph checkpoint tables:
  - `alembic/versions/002_langgraph_checkpoints.py`
  - `alembic/versions/003_repair_langgraph_checkpoint_schema.py`
- Set `LANGGRAPH_AUTO_SETUP_CHECKPOINTER=false` in `.env.example`.
- Set `langgraph_auto_setup_checkpointer=False` by default in config.
- Runtime checkpointer setup is still available if explicitly enabled, but normal Docker/local flow uses Alembic.

## Verified Smoke Test

The full local Docker smoke path has been verified after both fixes.

Fresh successful media job:

```text
event_id: ba85657b-d069-40e9-afe3-5b108a7d0e4f
job_id: 44a3fa7c-6b69-4226-9044-718532cd8625
job status: completed
processed_files: 2
failed_files: 0
needs_review_count: 0
```

Worker logs showed:

```text
process_batch_job ... Job OK ... 2.889s
generate_export_job ... Job OK ... 2.514s
```

Export smoke also passed:

```text
export_id: a782201b-2329-438d-902c-a2f8621be056
status: completed
included_count: 2
```

Export ZIP contained:

- both uploaded screenshots
- `metadata.csv`
- `summary.md`

Unit test count after the latest fix:

```text
191 passed
```

## Known Docs Cleanup

`README.md` and `docs/MANUAL_SMOKE_TEST.md` now reflect the verified Docker smoke test
and `191 passed` unit tests. If any other docs still sound pre-verification, update them.

## Suggested Next Steps

1. Add one or two integration tests using Docker services or testcontainers-style infrastructure if desired:
   - upload -> worker -> media processed
   - export -> ZIP generated
2. Add Gemini as an optional `VisionProvider`, behind config, without replacing MockVisionProvider as default.
3. Build a minimal UI only after backend verification:
   - event list/create
   - batch upload
   - job polling
   - media grid
   - review queue
   - search
   - export/download
4. Resume teaching mode when implementing UI. Explain routes, schemas, services, state management, and API calls clearly.

## Prompt For The Next AI Agent

```text
You are continuing work on Sorty AI in C:\ProgrammingAndCoding\Sorty.

Read these first:
- START_HERE.md
- CODING_AGENT_PROMPT.md
- Sorty_AI_FULL_BUILD_CONTEXT_PACK.md
- docs/ARCHITECTURE.md
- docs/MANUAL_SMOKE_TEST.md
- docs/HANDOFF_NEXT_AGENT.md

Follow the locked constraints:
- Backend-first.
- Use MinIO as final source of truth.
- Use FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL + pgvector, Redis + RQ, MinIO, LangGraph, Pydantic v2.
- API-key auth only.
- Do not add JWT/OAuth.
- Do not add ChromaDB/Pinecone/Weaviate.
- MockVisionProvider remains default.
- Do not build frontend before backend flow is understood and verified.

Current backend status:
- Main Docker smoke test passed.
- Unit tests: 191 passed.
- Quality signal duplicate creation bug is fixed.
- LangGraph checkpoint schema is managed through Alembic and no longer times out in the worker.
- Export ZIP smoke test passed.

User preference:
- Teach as you code.
- Explain what each file does and why.
- Show reasoning and design choices.
- Keep changes small and commit-worthy.
- Use a reviewer/code-quality agent for meaningful code slices when available.

Start by checking:
- git status --short
- latest docs for stale smoke-test/test-count wording

Recommended immediate task:
Plan and implement a small integration test (upload->worker->processed or export->ZIP) or add Gemini as an optional provider, then confirm next steps with the user.
```
