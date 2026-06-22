import os
import random
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageDraw


def _require_base_url() -> str:
    base_url = os.getenv("SORTY_INTEGRATION_BASE_URL", "").strip()
    if not base_url:
        pytest.skip(
            "Set SORTY_INTEGRATION_BASE_URL to run integration tests, "
            "for example http://localhost:8000."
        )
    return base_url.rstrip("/")


def _integration_auth_headers() -> dict[str, str]:
    admin_token = os.getenv("SORTY_INTEGRATION_ADMIN_TOKEN", "").strip()
    if admin_token:
        return {"Authorization": f"Bearer {admin_token}"}

    api_key = os.getenv("SORTY_INTEGRATION_API_KEY", "").strip()
    if api_key:
        return {"X-API-Key": api_key}

    pytest.skip(
        "Set SORTY_INTEGRATION_ADMIN_TOKEN for bearer auth, or "
        "SORTY_INTEGRATION_API_KEY for explicit local legacy auth."
    )


def _integration_timeout_seconds() -> int:
    raw = os.getenv("SORTY_INTEGRATION_TIMEOUT_SECONDS", "180").strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return 180


@pytest.fixture(scope="session")
def integration_client() -> httpx.Client:
    base_url = _require_base_url()
    headers = _integration_auth_headers()
    timeout = httpx.Timeout(60.0)
    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
        yield client


def _create_test_image(path: Path, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new(
        "RGB",
        (256, 256),
        color=(rng.randrange(0, 256), rng.randrange(0, 256), rng.randrange(0, 256)),
    )
    draw = ImageDraw.Draw(image)
    for _ in range(12):
        x1 = rng.randrange(0, 256)
        y1 = rng.randrange(0, 256)
        x2 = rng.randrange(x1, 256)
        y2 = rng.randrange(y1, 256)
        fill = (rng.randrange(0, 256), rng.randrange(0, 256), rng.randrange(0, 256))
        draw.rectangle([x1, y1, x2, y2], outline=fill, fill=fill)
    image.save(path, format="JPEG", quality=90)


def _create_event(client: httpx.Client, name_prefix: str) -> str:
    event_payload = {
        "name": f"{name_prefix} {uuid.uuid4()}",
        "event_type": "integration",
        "description": "Integration test event",
    }
    event_response = client.post("/api/events", json=event_payload)
    event_response.raise_for_status()
    return event_response.json()["data"]["id"]


def _upload_images(
    client: httpx.Client,
    event_id: str,
    tmp_path: Path,
    seeds: list[int],
) -> dict:
    images: list[Path] = []
    for index, seed in enumerate(seeds, start=1):
        image_path = tmp_path / f"image-{index}.jpg"
        _create_test_image(image_path, seed=seed)
        images.append(image_path)

    file_handles = [path.open("rb") for path in images]
    try:
        files = [
            ("files", (path.name, handle, "image/jpeg"))
            for path, handle in zip(images, file_handles)
        ]
        upload_response = client.post(
            f"/api/events/{event_id}/media/batch-upload",
            files=files,
        )
    finally:
        for handle in file_handles:
            handle.close()

    upload_response.raise_for_status()
    return upload_response.json()["data"]


def _wait_for_job_status(
    client: httpx.Client,
    job_id: str,
    terminal_statuses: set[str],
) -> dict:
    deadline = time.monotonic() + _integration_timeout_seconds()
    last_data: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        last_data = response.json().get("data") or {}
        status = last_data.get("status")
        if status in terminal_statuses:
            return last_data
        time.sleep(2)
    raise AssertionError(
        f"Job {job_id} did not finish in time. Last status: {last_data}"
    )


def _wait_for_job(client: httpx.Client, job_id: str) -> dict:
    return _wait_for_job_status(
        client,
        job_id,
        {"completed", "waiting_for_review", "partial_failed", "failed"},
    )


def _wait_for_export(client: httpx.Client, export_id: str) -> dict:
    deadline = time.monotonic() + _integration_timeout_seconds()
    last_data: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/exports/{export_id}")
        response.raise_for_status()
        last_data = response.json().get("data") or {}
        status = last_data.get("status")
        if status in {"completed", "failed"}:
            return last_data
        time.sleep(2)
    raise AssertionError(
        f"Export {export_id} did not finish in time. Last status: {last_data}"
    )


def _wait_for_media_listing(client: httpx.Client, event_id: str) -> list[dict]:
    deadline = time.monotonic() + _integration_timeout_seconds()
    last_payload: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/events/{event_id}/media")
        response.raise_for_status()
        last_payload = response.json()
        items = last_payload.get("data") or []
        if items:
            return items
        time.sleep(2)
    raise AssertionError(
        f"Media listing for event {event_id} stayed empty. Last payload: {last_payload}"
    )


def _wait_for_review_queue(client: httpx.Client, event_id: str) -> list[dict]:
    deadline = time.monotonic() + _integration_timeout_seconds()
    last_payload: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/events/{event_id}/review-queue")
        response.raise_for_status()
        last_payload = response.json()
        items = last_payload.get("data") or []
        if items:
            return items
        time.sleep(2)
    raise AssertionError(
        f"Review queue for event {event_id} stayed empty. Last payload: {last_payload}"
    )


@pytest.mark.integration
def test_health_endpoints(integration_client: httpx.Client) -> None:
    health = integration_client.get("/api/health")
    health.raise_for_status()
    health_payload = health.json()
    assert health_payload["data"]["status"] == "ok"

    ready = integration_client.get("/api/ready")
    ready.raise_for_status()
    ready_payload = ready.json()
    assert ready_payload["data"]["status"] == "ready"


@pytest.mark.integration
def test_upload_and_export_flow(
    integration_client: httpx.Client,
    tmp_path: Path,
) -> None:
    event_id = _create_event(integration_client, "Integration")
    upload_data = _upload_images(
        integration_client,
        event_id,
        tmp_path,
        seeds=[101, 202],
    )
    job_id = upload_data["job_id"]
    assert upload_data["rejected_count"] == 0
    assert upload_data["accepted_count"] == 2
    assert job_id is not None

    job_data = _wait_for_job(integration_client, str(job_id))
    assert job_data["status"] in {"completed", "waiting_for_review"}
    assert job_data["failed_files"] == 0

    export_payload = {
        "include_duplicates": False,
        "include_blurry": True,
        "include_pending": True,
    }
    export_response = integration_client.post(
        f"/api/events/{event_id}/export",
        json=export_payload,
    )
    export_response.raise_for_status()
    export_data = export_response.json()["data"]
    export_id = export_data["id"]

    export_status = _wait_for_export(integration_client, str(export_id))
    assert export_status["status"] == "completed"

    download_url = export_status.get("download_url") or f"/api/exports/{export_id}/download"
    download_response = integration_client.get(download_url)
    download_response.raise_for_status()

    archive = zipfile.ZipFile(BytesIO(download_response.content))
    names = set(archive.namelist())
    assert "metadata.csv" in names
    assert "summary.md" in names
    archive.close()


@pytest.mark.integration
def test_media_listing_after_upload(
    integration_client: httpx.Client,
    tmp_path: Path,
) -> None:
    event_id = _create_event(integration_client, "Integration Media")
    upload_data = _upload_images(
        integration_client,
        event_id,
        tmp_path,
        seeds=[303],
    )
    job_id = upload_data["job_id"]
    assert upload_data["accepted_count"] == 1
    assert job_id is not None

    job_data = _wait_for_job(integration_client, str(job_id))
    assert job_data["status"] in {"completed", "waiting_for_review"}

    items = _wait_for_media_listing(integration_client, event_id)
    first = items[0]
    assert first.get("event_id") == event_id
    thumbnail_url = first.get("thumbnail_url")
    file_url = first.get("file_url")
    assert isinstance(thumbnail_url, str) and thumbnail_url
    assert isinstance(file_url, str) and file_url


@pytest.mark.integration
def test_resume_job_completes_after_review(
    integration_client: httpx.Client,
    tmp_path: Path,
) -> None:
    event_id = _create_event(integration_client, "Integration Review Resume")
    upload_data = _upload_images(
        integration_client,
        event_id,
        tmp_path,
        seeds=[404, 404],
    )
    job_id = upload_data["job_id"]
    assert upload_data["accepted_count"] == 2
    assert job_id is not None

    job_data = _wait_for_job_status(
        integration_client,
        str(job_id),
        {"waiting_for_review", "completed", "partial_failed", "failed"},
    )
    assert job_data["status"] == "waiting_for_review"

    review_items = _wait_for_review_queue(integration_client, event_id)
    media_id = review_items[0]["media_id"]
    review_payload = {
        "status": "approved",
        "final_primary_folder": "Highlights",
        "final_sub_folder": "General",
        "final_tags": ["integration"],
        "include_in_export": True,
    }
    review_response = integration_client.patch(
        f"/api/media/{media_id}/review",
        json=review_payload,
    )
    review_response.raise_for_status()

    resume_response = integration_client.post(f"/api/jobs/{job_id}/resume")
    resume_response.raise_for_status()

    completed = _wait_for_job_status(
        integration_client,
        str(job_id),
        {"completed", "partial_failed", "failed"},
    )
    assert completed["status"] == "completed"
