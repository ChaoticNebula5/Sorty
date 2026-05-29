# Manual Smoke Test

This walkthrough proves the backend flow before building a UI.

## 1. Start Services

```powershell
docker compose up --build
```

Run migrations in a second terminal:

```powershell
docker compose run --rm backend alembic upgrade head
```

Set a convenience variable:

```powershell
$API_KEY = "demo-secret"
```

## 2. Check Health

```powershell
curl.exe http://localhost:8000/api/health
curl.exe http://localhost:8000/api/ready
```

Expected:

- `/api/health` returns `status: ok`
- `/api/ready` returns `status: ready`

## 3. Create Event

```powershell
curl.exe -X POST http://localhost:8000/api/events `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"name":"Campus Fest 2026","event_type":"cultural","description":"Demo event"}'
```

Copy the returned `data.id` into:

```powershell
$EVENT_ID = "paste-event-id-here"
```

## 4. Upload Images

Put a few `.jpg`, `.jpeg`, `.png`, or `.webp` images in a local folder, then upload them:

```powershell
curl.exe -X POST "http://localhost:8000/api/events/$EVENT_ID/media/batch-upload" `
  -H "X-API-Key: $API_KEY" `
  -F "files=@C:\path\to\photo1.jpg" `
  -F "files=@C:\path\to\photo2.jpg"
```

Copy the returned `data.job_id` into:

```powershell
$JOB_ID = "paste-job-id-here"
```

## 5. Poll Job

```powershell
curl.exe "http://localhost:8000/api/jobs/$JOB_ID" -H "X-API-Key: $API_KEY"
```

The job should move through states such as:

- `queued`
- `processing`
- `waiting_for_review`
- `completed`
- `partial_failed`

## 6. Inspect Media

```powershell
curl.exe "http://localhost:8000/api/events/$EVENT_ID/media" -H "X-API-Key: $API_KEY"
```

Each item should expose backend URLs for:

- thumbnail
- original file
- quality signals when processed

Raw MinIO object keys should not be needed by the client.

## 7. Review Queue

```powershell
curl.exe "http://localhost:8000/api/events/$EVENT_ID/review-queue" -H "X-API-Key: $API_KEY"
```

If items need review, patch each media decision:

```powershell
$MEDIA_ID = "paste-media-id-here"

curl.exe -X PATCH "http://localhost:8000/api/media/$MEDIA_ID/review" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"status":"approved","final_primary_folder":"Highlights","final_sub_folder":"General","final_tags":["demo"],"include_in_export":true}'
```

For many pending items, use bulk approve:

```powershell
curl.exe -X POST "http://localhost:8000/api/events/$EVENT_ID/review/bulk-approve" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"media_ids":["paste-media-id-here"]}'
```

## 8. Resume Job

Run this only if the job status is `waiting_for_review` after review items are resolved.
If the job is already `completed`, skip this step.

```powershell
curl.exe -X POST "http://localhost:8000/api/jobs/$JOB_ID/resume" `
  -H "X-API-Key: $API_KEY"
```

This resumes the existing LangGraph thread.

## 9. Search

Default search returns export-ready media:

```powershell
curl.exe "http://localhost:8000/api/events/$EVENT_ID/search?q=stage" `
  -H "X-API-Key: $API_KEY"
```

Broader search:

```powershell
curl.exe "http://localhost:8000/api/events/$EVENT_ID/search?q=stage&export_ready_only=false&include_pending=true&include_duplicates=true" `
  -H "X-API-Key: $API_KEY"
```

## 10. Export

```powershell
curl.exe -X POST "http://localhost:8000/api/events/$EVENT_ID/export" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"include_duplicates":false,"include_blurry":true,"include_pending":false}'
```

Copy the returned `data.id`:

```powershell
$EXPORT_ID = "paste-export-id-here"
```

Poll status:

```powershell
curl.exe "http://localhost:8000/api/exports/$EXPORT_ID" -H "X-API-Key: $API_KEY"
```

Download when completed:

```powershell
curl.exe -L "http://localhost:8000/api/exports/$EXPORT_ID/download" `
  -H "X-API-Key: $API_KEY" `
  -o sorty-export.zip
```

## 11. Verify Export

Open the ZIP and confirm:

- organized folders exist
- `metadata.csv` exists
- `summary.md` exists
- rejected/duplicate media follows the selected export settings

## Troubleshooting

If readiness is degraded:

```powershell
docker compose ps
docker compose logs backend
docker compose logs worker
docker compose logs postgres
docker compose logs redis
docker compose logs minio
```

If migrations were not run, API calls that touch tables will fail. Run:

```powershell
docker compose run --rm backend alembic upgrade head
```
