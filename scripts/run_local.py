"""Run Sorty's API or Windows-compatible worker using the root .env file.

Infrastructure remains in Docker: docker compose up -d postgres redis minio minio-init
Usage: python scripts/run_local.py api | worker
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT), str(PROJECT_ROOT / "backend")]


def main() -> None:
    import os
    from dotenv import load_dotenv

    if len(sys.argv) != 2 or sys.argv[1] not in {"api", "worker"}:
        raise SystemExit("Usage: python scripts/run_local.py api | worker")
    os.chdir(PROJECT_ROOT)
    load_dotenv(PROJECT_ROOT / ".env")

    from app.core.config import get_settings

    settings = get_settings()
    if settings.vision_provider != "gemini" or not settings.gemini_api_key.strip():
        raise SystemExit("Real-provider testing requires VISION_PROVIDER=gemini and GEMINI_API_KEY in .env.")
    if settings.embedding_provider != "sentence-transformers" or not settings.visual_search_enabled:
        raise SystemExit("Real-provider testing requires sentence-transformers and VISUAL_SEARCH_ENABLED=true.")

    if sys.argv[1] == "api":
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=settings.backend_port)
    else:
        import redis
        from rq import SimpleWorker, Worker
        from rq.timeouts import TimerDeathPenalty

        class WindowsWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        worker_class = WindowsWorker if os.name == "nt" else Worker
        worker_class(
            [settings.rq_queue_name], connection=redis.from_url(settings.redis_url)
        ).work()


if __name__ == "__main__":
    main()
