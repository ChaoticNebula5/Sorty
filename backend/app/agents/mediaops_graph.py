def resume_reviewed_batch(thread_id: str, job_id: str) -> None:
    if not thread_id:
        raise ValueError("LangGraph thread id is required.")
    if not job_id:
        raise ValueError("Batch job id is required.")
