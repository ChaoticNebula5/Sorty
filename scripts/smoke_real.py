"""Create a disposable event and verify real vision, embeddings, search and export.

Sends one repository sample image to Gemini. Reads credentials from .env.
Run after starting scripts/run_local.py api and worker.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main() -> None:
    import os
    from dotenv import load_dotenv
    import httpx
    from sqlalchemy import select

    os.chdir(ROOT)
    load_dotenv(ROOT / ".env")
    from app.core.config import get_settings
    from app.db.models import AIAnalysis, MediaEmbedding, MediaVisualEmbedding
    from app.db.session import SessionLocal
    from scripts.smoke_backend import poll_job, create_and_download_export

    settings = get_settings()
    if settings.vision_provider != "gemini" or settings.embedding_provider != "sentence-transformers" or not settings.visual_search_enabled:
        raise SystemExit("This check requires Gemini and real text/visual embeddings.")
    artifacts = ROOT / ".tmp" / "real-smoke"
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "vision_model": settings.gemini_vision_model}
    image = ROOT / "frontend/public/events/speaker-portrait.png"
    with httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {settings.admin_token}"}, timeout=180) as client:
        response = client.post("/api/events", json={"name": f"Real Gemini Final Test {uuid.uuid4().hex[:8]}", "event_type": "conference"})
        response.raise_for_status()
        event_id = response.json()["data"]["id"]
        report["event_id"] = event_id
        print("EVENT_ID", event_id, flush=True)
        with image.open("rb") as stream:
            response = client.post(f"/api/events/{event_id}/media/batch-upload", files={"files": (image.name, stream, "image/png")})
        response.raise_for_status()
        upload = response.json()["data"]
        assert upload["accepted_count"] == 1 and upload["rejected_count"] == 0, upload
        job_id = upload["job_id"]
        media_id = uuid.UUID(upload["media_ids"][0])
        job = poll_job(client, job_id, timeout_seconds=240, label="REAL")
        assert job["failed_files"] == 0, job
        with SessionLocal() as db:
            analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.media_id == media_id))
            text = db.scalar(select(MediaEmbedding).where(MediaEmbedding.media_id == media_id))
            visual = db.scalar(select(MediaVisualEmbedding).where(MediaVisualEmbedding.media_id == media_id))
            assert analysis is not None and analysis.model_provider == "gemini", "Real Gemini analysis missing; inspect quota and review reasons."
            assert text is not None and not text.embedding_model.startswith("mock:"), "Real text embedding missing."
            assert visual is not None, "CLIP embedding missing; worker suppresses visual embedding errors."
            assert len(text.embedding) == 384 and len(visual.embedding) == 512
            report.update(caption=analysis.caption, text_model=text.embedding_model, visual_model=visual.embedding_model, text_dimensions=len(text.embedding), visual_dimensions=len(visual.embedding))
            print("VERIFIED_REAL_MODELS", report, flush=True)
        if job["status"] == "waiting_for_review":
            response = client.get(f"/api/events/{event_id}/review-queue")
            response.raise_for_status()
            for item in response.json()["data"]:
                assert "vision_analysis_failed" not in item["review_reasons"]
                response = client.patch(f"/api/media/{item['media_id']}/review", json={"status": "approved", "final_primary_folder": "Speakers", "final_tags": ["speaker", "microphone"], "include_in_export": True})
                response.raise_for_status()
            client.post(f"/api/jobs/{job_id}/resume").raise_for_status()
            job = poll_job(client, job_id, timeout_seconds=60, label="RESUME")
        assert job["status"] == "completed", job
        response = client.get(f"/api/events/{event_id}/search", params={"q": "woman speaking into a microphone", "include_blurry": True})
        response.raise_for_status()
        matches = response.json()["data"]
        assert matches, "Real-model search returned no expected result."
        report["search_matches"] = len(matches)
        export, archive, names = create_and_download_export(client, event_id, artifacts, 90)
        assert len([n for n in names if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]) == 1
        report.update(export_status=export["status"], archive=str(archive), archive_entries=names)
        response = client.patch(f"/api/events/{event_id}/public", json={"is_public": True})
        response.raise_for_status()
        slug = response.json()["data"]["public_slug"]
        try:
            with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as public:
                response = public.get(f"/api/public/events/{slug}/media")
                response.raise_for_status()
                public_items = response.json()["data"]
                assert len(public_items) == 1
                response = public.get(public_items[0]["thumbnail_url"])
                response.raise_for_status()
                assert response.headers["content-type"].startswith("image/")
                report["anonymous_thumbnail_status"] = response.status_code
        finally:
            client.patch(f"/api/events/{event_id}/public", json={"is_public": False}).raise_for_status()
        assert httpx.get(f"http://127.0.0.1:8000/api/public/events/{slug}").status_code == 404
        report.update(unpublish_verified=True, status="passed")
    (artifacts / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("REAL_SMOKE_PASSED", artifacts / "report.json", flush=True)


if __name__ == "__main__":
    main()
