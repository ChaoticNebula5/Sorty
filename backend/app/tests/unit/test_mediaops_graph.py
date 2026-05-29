import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents import mediaops_graph


def test_run_mediaops_batch_finishes_when_no_review_needed() -> None:
    graph = mediaops_graph.build_mediaops_graph(checkpointer=MemorySaver())
    thread_id = f"batch-{uuid.uuid4()}"

    result = graph.invoke(
        {
            "job_id": str(uuid.uuid4()),
            "event_id": str(uuid.uuid4()),
            "needs_review_count": 0,
            "reviewed": False,
            "phase": "created",
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    assert result["phase"] == "finalized"
    assert result["reviewed"] is False


def test_graph_result_from_final_state_returns_finalized_result() -> None:
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())

    result = mediaops_graph.graph_result_from_invoke(
        thread_id="thread-1",
        result={
            "job_id": job_id,
            "event_id": event_id,
            "needs_review_count": 0,
            "reviewed": False,
            "phase": "finalized",
        },
    )

    assert result == mediaops_graph.MediaOpsGraphResult(
        status="finalized",
        thread_id="thread-1",
        job_id=job_id,
        event_id=event_id,
        pending_review_count=0,
    )


def test_mediaops_graph_interrupts_and_resumes_review_checkpoint() -> None:
    graph = mediaops_graph.build_mediaops_graph(checkpointer=MemorySaver())
    thread_id = f"batch-{uuid.uuid4()}"
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    interrupted = graph.invoke(
        {
            "job_id": job_id,
            "event_id": event_id,
            "needs_review_count": 2,
            "reviewed": False,
            "phase": "created",
        },
        config=config,
    )

    assert "__interrupt__" in interrupted
    interrupt_payload = interrupted["__interrupt__"][0].value
    assert interrupt_payload == {
        "type": "review_required",
        "job_id": job_id,
        "event_id": event_id,
        "pending_review_count": 2,
    }
    graph_result = mediaops_graph.graph_result_from_invoke(
        thread_id=thread_id,
        result=interrupted,
    )
    assert graph_result.status == "interrupted_for_review"
    assert graph_result.pending_review_count == 2

    resumed = graph.invoke(Command(resume={"reviewed": True}), config=config)

    assert resumed["phase"] == "finalized"
    assert resumed["reviewed"] is True


def test_resume_reviewed_batch_validates_required_values() -> None:
    try:
        mediaops_graph.resume_reviewed_batch(thread_id="", job_id="job-id")
    except ValueError as exc:
        assert "thread id" in str(exc)
    else:
        raise AssertionError("Expected missing thread_id to fail.")


def test_sqlalchemy_url_to_psycopg_conninfo_removes_sqlalchemy_driver() -> None:
    conninfo = mediaops_graph.sqlalchemy_url_to_psycopg_conninfo(
        "postgresql+psycopg://sorty:sorty@postgres:5432/sorty"
    )

    assert conninfo == "postgresql://sorty:sorty@postgres:5432/sorty"
