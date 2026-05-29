import uuid
from pathlib import Path
from typing import Any

from app.agents.mediaops_graph import resume_reviewed_batch, run_mediaops_batch
from app.db.session import SessionLocal
from app.services import (
    analysis_service,
    event_service,
    export_service,
    job_service,
    media_service,
    quality_service,
    review_service,
    search_service,
    storage_factory,
    vision_service,
)


class WorkflowCheckpointError(RuntimeError):
    pass


class WorkflowResumeError(RuntimeError):
    pass


def health_check_task() -> str:
    return "ok"


def process_batch_job(payload: dict[str, Any]) -> str:
    job_id = uuid.UUID(str(payload["job_id"]))

    with SessionLocal() as db:
        job = job_service.get_batch_job(db, job_id)
        if job is None:
            raise ValueError(f"Batch job not found: {job_id}")

        try:
            job_service.mark_job_processing(db, job)

            storage = storage_factory.get_storage_service()
            provider = vision_service.get_vision_provider()
            event = event_service.get_event(db, job.event_id)
            event_context = {
                "event_id": str(job.event_id),
                "name": getattr(event, "name", None),
                "event_type": getattr(event, "event_type", None),
            }
            media_items = media_service.list_batch_media(
                db,
                job.id,
                media_ids=None,
            )
            processed_files = 0
            failed_files = 0
            needs_review_count = 0

            for media in media_items:
                temp_path: Path | None = None
                try:
                    media_service.mark_media_processing(db, media)
                    temp_path = storage.download_to_temp(media.original_object_key)
                    result = provider.analyze_image(
                        str(temp_path),
                        event_context=event_context,
                    )
                    analysis = analysis_service.upsert_ai_analysis(
                        db,
                        media_id=media.id,
                        result=result,
                        model_provider=provider.provider_name,
                        model_name=provider.model_name,
                        raw_response=result.model_dump(),
                        commit=False,
                    )
                    media.ai_analysis = analysis
                    quality_result = quality_service.analyze_image_quality(temp_path)
                    quality_signal = quality_service.upsert_quality_signal(
                        db,
                        media_id=media.id,
                        result=quality_result,
                        commit=False,
                    )
                    media.quality_signal = quality_signal
                    review_reasons = list(result.review_reasons or [])
                    if (
                        quality_result.quality_label == "blurry"
                        and "low_quality_blur" not in review_reasons
                    ):
                        review_reasons.append("low_quality_blur")
                    duplicate_result = quality_service.detect_duplicate_for_media(
                        db,
                        media_id=media.id,
                        event_id=media.event_id,
                        perceptual_hash=quality_result.perceptual_hash,
                        batch_job_id=job.id,
                        commit=False,
                    )
                    if (
                        duplicate_result.is_duplicate
                        and "possible_duplicate" not in review_reasons
                    ):
                        review_reasons.append("possible_duplicate")

                    search_service.upsert_media_embedding(db, media, commit=False)

                    if result.needs_review or review_reasons:
                        review_service.create_pending_review_decision(
                            db,
                            media_id=media.id,
                            review_reasons=review_reasons,
                            commit=False,
                        )
                        media_service.mark_media_needs_review(
                            db,
                            media,
                            reason=", ".join(review_reasons) or "needs_review",
                            commit=False,
                        )
                        db.commit()
                        needs_review_count += 1
                    else:
                        media_service.mark_media_processed(db, media, commit=False)
                        db.commit()
                        processed_files += 1
                except Exception as media_exc:
                    db.rollback()
                    failed_files += 1
                    media_service.mark_media_failed(db, media, str(media_exc))
                finally:
                    if temp_path is not None:
                        try:
                            temp_path.unlink(missing_ok=True)
                        except OSError:
                            pass

            finished_job = job_service.mark_job_finished(
                db,
                job,
                processed_files=processed_files,
                failed_files=failed_files,
                needs_review_count=needs_review_count,
            ) or job
            try:
                run_mediaops_batch(
                    thread_id=finished_job.langgraph_thread_id,
                    job_id=str(finished_job.id),
                    event_id=str(finished_job.event_id),
                    needs_review_count=needs_review_count,
                )
            except Exception as graph_exc:
                job_service.mark_job_workflow_failed(
                    db,
                    finished_job,
                    f"Could not create LangGraph checkpoint: {graph_exc}",
                )
                raise WorkflowCheckpointError(str(graph_exc)) from graph_exc
        except WorkflowCheckpointError:
            raise
        except Exception as exc:
            db.rollback()
            media_service.mark_batch_media_failed(db, job.id, str(exc))
            job_service.mark_job_failed(db, job, str(exc))
            raise

    return str(job_id)


def resume_batch_job(payload: dict[str, Any]) -> str:
    job_id = uuid.UUID(str(payload["job_id"]))
    job = None

    with SessionLocal() as db:
        try:
            job = job_service.get_batch_job(db, job_id)
            if job is None:
                raise ValueError(f"Batch job not found: {job_id}")

            event_id = uuid.UUID(str(payload["event_id"]))
            thread_id = str(payload["thread_id"])

            if payload.get("mode") != "resume":
                raise ValueError("Resume task payload must use mode='resume'.")

            if job.event_id != event_id:
                raise ValueError("Resume task event_id does not match batch job.")
            if job.langgraph_thread_id != thread_id:
                raise ValueError("Resume task thread_id does not match batch job.")
            if job.status != "queued":
                raise ValueError(f"Cannot resume job with status: {job.status}")

            job_service.mark_job_processing(db, job)
            graph_result = resume_reviewed_batch(thread_id=thread_id, job_id=str(job_id))
            if graph_result.status != "finalized":
                raise WorkflowResumeError(
                    f"Expected finalized graph after review resume, got {graph_result.status}."
                )
            if (
                graph_result.thread_id != thread_id
                or graph_result.job_id != str(job_id)
                or graph_result.event_id != str(job.event_id)
            ):
                raise WorkflowResumeError("Resumed graph result does not match batch job.")
            job_service.mark_job_resume_placeholder_done(db, job)
        except Exception as exc:
            db.rollback()
            if job is not None and job.status in {"queued", "processing"}:
                job_service.mark_job_resume_enqueue_failed(db, job)
            raise

    return str(job_id)


def generate_export_job(payload: dict[str, Any]) -> str:
    export_id = uuid.UUID(str(payload["export_id"]))

    if payload.get("mode") != "export":
        raise ValueError("Export task payload must use mode='export'.")

    with SessionLocal() as db:
        export_job = export_service.get_export_job(db, export_id)
        if export_job is None:
            raise ValueError(f"Export job not found: {export_id}")
        if export_job.status not in {"created", "queued"}:
            raise ValueError(f"Cannot generate export with status: {export_job.status}")

        try:
            export_service.mark_export_exporting(db, export_job)
            storage = storage_factory.get_storage_service()
            export_service.generate_export_archive(db, export_job, storage)
        except Exception as exc:
            db.rollback()
            export_service.mark_export_failed(db, export_job, str(exc))
            raise

    return str(export_id)
