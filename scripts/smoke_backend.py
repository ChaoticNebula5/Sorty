import argparse
import json
import os
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw


TERMINAL_JOB_STATUSES = {
    "completed",
    "waiting_for_review",
    "reviewed",
    "failed",
    "partial_failed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Sorty backend HTTP smoke flow end to end.",
    )
    parser.add_argument(
        "--mode",
        choices=("mock", "ollama"),
        required=True,
        help="Expected vision provider mode for readiness validation.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend API base URL.",
    )
    parser.add_argument(
        "--api-key",
        default="demo-secret",
        help="Deprecated local API key sent as X-API-Key when no admin token is provided.",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_TOKEN"),
        help="Admin token sent as Authorization: Bearer <token>.",
    )
    parser.add_argument(
        "--image-count",
        type=int,
        default=None,
        help="Number of generated test images. Defaults to 3 for mock, 1 for Ollama.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Directory for generated images and downloaded ZIP.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=360,
        help="Maximum seconds to wait for background jobs.",
    )
    return parser.parse_args()


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = client.request(method, url, **kwargs)
    print(f"{method.upper()} {url} -> {response.status_code}")
    response.raise_for_status()
    return response.json()


def expect_status(
    client: httpx.Client,
    method: str,
    url: str,
    expected_status: int,
    **kwargs: Any,
) -> httpx.Response:
    response = client.request(method, url, **kwargs)
    print(f"{method.upper()} {url} -> {response.status_code}")
    if response.status_code != expected_status:
        raise RuntimeError(
            f"Expected {expected_status} for {method.upper()} {url}, "
            f"got {response.status_code}: {response.text}",
        )
    return response


def require_ready(client: httpx.Client, mode: str) -> None:
    health = request_json(client, "GET", "/api/health")
    if health["data"]["status"] != "ok":
        raise RuntimeError(f"Unexpected health response: {health}")

    ready = request_json(client, "GET", "/api/ready")
    if ready["data"]["status"] != "ready":
        raise RuntimeError(f"Backend readiness is not ready: {ready}")

    components = {
        component["name"]: component
        for component in ready["data"]["components"]
    }
    vision = components.get("vision_provider")
    if vision is None or vision["status"] != "ok":
        raise RuntimeError(f"Vision provider is not ready: {vision}")
    detail = str(vision.get("detail") or "").lower()
    if mode not in detail:
        raise RuntimeError(
            f"Smoke mode {mode!r} does not match readiness detail: {vision}",
        )


def generate_images(artifact_dir: Path, mode: str, image_count: int) -> list[Path]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    colors = [
        (220, 40, 40),
        (40, 150, 220),
        (60, 190, 90),
        (230, 170, 40),
        (140, 80, 210),
    ]
    image_paths: list[Path] = []
    for index in range(1, image_count + 1):
        path = artifact_dir / f"{mode}_photo_{index}.jpg"
        image = Image.new("RGB", (220, 160), color=colors[(index - 1) % len(colors)])
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 200, 140), outline=(255, 255, 255), width=4)
        draw.text((36, 68), f"Sorty {mode} {index}", fill=(255, 255, 255))
        image.save(path, format="JPEG", quality=88)
        image_paths.append(path)
    return image_paths


def create_event(client: httpx.Client, mode: str) -> str:
    body = request_json(
        client,
        "POST",
        "/api/events",
        json={
            "name": f"Smoke {mode.title()} {uuid.uuid4().hex[:8]}",
            "event_type": "smoke-test",
            "description": f"Runtime smoke test in {mode} mode.",
        },
    )
    return body["data"]["id"]


def upload_images(
    client: httpx.Client,
    event_id: str,
    image_paths: list[Path],
) -> dict[str, Any]:
    opened = []
    files = []
    try:
        for path in image_paths:
            handle = path.open("rb")
            opened.append(handle)
            files.append(("files", (path.name, handle, "image/jpeg")))
        body = request_json(
            client,
            "POST",
            f"/api/events/{event_id}/media/batch-upload",
            files=files,
            timeout=60.0,
        )
    finally:
        for handle in opened:
            handle.close()
    return body["data"]


def poll_job(
    client: httpx.Client,
    job_id: str,
    timeout_seconds: int,
    label: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        body = request_json(client, "GET", f"/api/jobs/{job_id}")
        job = body["data"]
        print(
            f"{label}_POLL={attempt}:status={job['status']}:"
            f"processed={job['processed_files']}:failed={job['failed_files']}:"
            f"needs_review={job['needs_review_count']}",
        )
        if job["status"] in TERMINAL_JOB_STATUSES:
            return job
        attempt += 1
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for job {job_id}.")


def resolve_reviews_and_resume(
    client: httpx.Client,
    event_id: str,
    job_id: str,
    job: dict[str, Any],
    timeout_seconds: int,
) -> tuple[dict[str, Any], int]:
    body = request_json(client, "GET", f"/api/events/{event_id}/review-queue")
    review_items = body["data"]
    review_count = int(body["pagination"]["total"])
    print(f"REVIEW_QUEUE_COUNT={review_count}")

    if review_count == 0:
        print("RESUME_STATUS=not_required")
        return job, review_count

    for item in review_items:
        media_id = item["media_id"]
        request_json(
            client,
            "PATCH",
            f"/api/media/{media_id}/review",
            json={
                "status": "approved",
                "final_primary_folder": item.get("suggested_primary_folder")
                or "Smoke Approved",
                "final_sub_folder": item.get("suggested_sub_folder") or "General",
                "final_tags": item.get("tags") or ["smoke"],
                "include_in_export": True,
                "reviewer_note": "Smoke test approval.",
            },
        )

    request_json(client, "POST", f"/api/jobs/{job_id}/resume")
    resumed_job = poll_job(
        client,
        job_id,
        timeout_seconds=timeout_seconds,
        label="RESUME",
    )
    return resumed_job, review_count


def run_search(client: httpx.Client, event_id: str, mode: str) -> tuple[int, int]:
    query = "event smoke" if mode == "mock" else "photo event"
    body = request_json(
        client,
        "GET",
        f"/api/events/{event_id}/search",
        params={"q": query, "limit": 10},
    )
    result_count = len(body["data"])
    total = int(body["pagination"]["total"])
    if result_count == 0:
        raise RuntimeError("Semantic search returned no results.")
    return result_count, total


def create_and_download_export(
    client: httpx.Client,
    event_id: str,
    artifact_dir: Path,
    timeout_seconds: int,
) -> tuple[dict[str, Any], Path, list[str]]:
    body = request_json(
        client,
        "POST",
        f"/api/events/{event_id}/export",
        json={
            "include_duplicates": True,
            "include_blurry": True,
            "include_pending": False,
        },
    )
    export = body["data"]
    export_id = export["id"]

    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        body = request_json(client, "GET", f"/api/exports/{export_id}")
        export = body["data"]
        print(
            f"EXPORT_POLL={attempt}:status={export['status']}:"
            f"included={export['included_count']}:excluded={export['excluded_count']}",
        )
        if export["status"] in {"completed", "failed"}:
            break
        attempt += 1
        time.sleep(2)

    if export["status"] != "completed":
        raise RuntimeError(f"Export did not complete: {export}")

    response = client.get(f"/api/exports/{export_id}/download", timeout=60.0)
    print(f"GET /api/exports/{export_id}/download -> {response.status_code}")
    response.raise_for_status()

    zip_path = artifact_dir / f"{export_id}.zip"
    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    if "metadata.csv" not in names:
        raise RuntimeError("metadata.csv missing from export ZIP.")
    if "summary.md" not in names:
        raise RuntimeError("summary.md missing from export ZIP.")
    media_entries = [name for name in names if name not in {"metadata.csv", "summary.md"}]
    if not media_entries:
        raise RuntimeError("Export ZIP did not include organized media files.")

    return export, zip_path, names


def publish_public_event(client: httpx.Client, event_id: str, mode: str) -> str:
    public_slug = f"smoke-{mode}-{uuid.uuid4().hex[:8]}"
    body = request_json(
        client,
        "PATCH",
        f"/api/events/{event_id}/public",
        json={"is_public": True, "public_slug": public_slug},
    )
    event = body["data"]
    if not event["is_public"] or event["public_slug"] != public_slug:
        raise RuntimeError(f"Event was not published as expected: {event}")
    return public_slug


def verify_public_event(client: httpx.Client, public_slug: str) -> None:
    public_client = httpx.Client(
        base_url=str(client.base_url).rstrip("/"),
        timeout=30.0,
    )
    try:
        event = request_json(public_client, "GET", f"/api/public/events/{public_slug}")
        if event["data"]["public_slug"] != public_slug:
            raise RuntimeError(f"Unexpected public event response: {event}")

        media = request_json(
            public_client,
            "GET",
            f"/api/public/events/{public_slug}/media",
        )
        if int(media["pagination"]["total"]) < 1 or not media["data"]:
            raise RuntimeError(f"Public media response is empty: {media}")

        thumbnail_url = media["data"][0]["thumbnail_url"]
        response = public_client.get(thumbnail_url, timeout=60.0)
        print(f"GET {thumbnail_url} -> {response.status_code}")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise RuntimeError(f"Unexpected thumbnail content type: {content_type}")
    finally:
        public_client.close()


def verify_private_auth(base_url: str, admin_token: str | None) -> None:
    unauthenticated = httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
    try:
        expect_status(unauthenticated, "GET", "/api/events", 401)
        expect_status(
            unauthenticated,
            "GET",
            "/api/events",
            401,
            headers={"Authorization": "Bearer wrong-token"},
        )
    finally:
        unauthenticated.close()

    if admin_token:
        authorized = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30.0,
        )
        try:
            request_json(authorized, "GET", "/api/events")
        finally:
            authorized.close()


def main() -> None:
    args = parse_args()
    image_count = args.image_count or (3 if args.mode == "mock" else 1)
    artifact_dir = Path(args.artifact_dir or f".tmp/smoke-{args.mode}")
    headers = (
        {"Authorization": f"Bearer {args.admin_token}"}
        if args.admin_token
        else {"X-API-Key": args.api_key}
    )
    client = httpx.Client(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        timeout=30.0,
    )

    print(f"SMOKE_MODE={args.mode}")
    require_ready(client, args.mode)
    verify_private_auth(args.base_url, args.admin_token)

    image_paths = generate_images(artifact_dir, args.mode, image_count)
    print(f"TEST_IMAGE_COUNT={len(image_paths)}")

    event_id = create_event(client, args.mode)
    print(f"EVENT_ID={event_id}")

    upload = upload_images(client, event_id, image_paths)
    print(f"UPLOAD_ACCEPTED={upload['accepted_count']}")
    print(f"UPLOAD_REJECTED={upload['rejected_count']}")
    if upload["accepted_count"] != len(image_paths):
        raise RuntimeError(f"Unexpected upload result: {upload}")

    job_id = upload["job_id"]
    print(f"JOB_ID={job_id}")
    print("MEDIA_IDS=" + ",".join(upload["media_ids"]))

    job = poll_job(
        client,
        job_id,
        timeout_seconds=args.timeout_seconds,
        label="JOB",
    )
    if job["status"] in {"failed", "partial_failed"}:
        raise RuntimeError(f"Batch job failed: {job}")

    job, review_count = resolve_reviews_and_resume(
        client,
        event_id,
        job_id,
        job,
        timeout_seconds=args.timeout_seconds,
    )
    if job["status"] != "completed":
        raise RuntimeError(f"Expected completed job, got {job['status']}.")

    search_result_count, search_total = run_search(client, event_id, args.mode)
    print(f"SEARCH_RESULT_COUNT={search_result_count}")
    print(f"SEARCH_TOTAL={search_total}")

    export, zip_path, zip_entries = create_and_download_export(
        client,
        event_id,
        artifact_dir,
        timeout_seconds=args.timeout_seconds,
    )
    organized_file_count = len(
        [name for name in zip_entries if name not in {"metadata.csv", "summary.md"}],
    )
    print(f"EXPORT_ID={export['id']}")
    print(f"EXPORT_STATUS={export['status']}")
    print(f"EXPORT_INCLUDED={export['included_count']}")
    print(f"ZIP_PATH={zip_path}")
    print(f"ZIP_ENTRY_COUNT={len(zip_entries)}")
    print("ZIP_ENTRIES=" + json.dumps(zip_entries))

    public_slug = publish_public_event(client, event_id, args.mode)
    print(f"PUBLIC_SLUG={public_slug}")
    verify_public_event(client, public_slug)

    print(
        "SMOKE_SUMMARY="
        + json.dumps(
            {
                "mode": args.mode,
                "event_id": event_id,
                "job_id": job_id,
                "test_image_count": len(image_paths),
                "job_status": job["status"],
                "review_queue_count": review_count,
                "search_result_count": search_result_count,
                "search_total": search_total,
                "export_id": export["id"],
                "export_status": export["status"],
                "export_included_count": export["included_count"],
                "public_slug": public_slug,
                "zip_path": str(zip_path),
                "zip_entry_count": len(zip_entries),
                "organized_file_count": organized_file_count,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
