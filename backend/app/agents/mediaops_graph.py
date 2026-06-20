from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.core.config import get_settings


class MediaOpsState(TypedDict, total=False):
    job_id: str
    event_id: str
    needs_review_count: int
    pending_review_count: int
    reviewed: bool
    phase: str
    completed_phases: list[str]
    failed: bool
    error_message: str | None


@dataclass(frozen=True)
class MediaOpsGraphResult:
    status: Literal["finalized", "interrupted_for_review"]
    thread_id: str
    job_id: str
    event_id: str
    pending_review_count: int


_compiled_graph = None
_checkpointer_context = None


def sqlalchemy_url_to_psycopg_conninfo(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def build_postgres_checkpointer():
    global _checkpointer_context

    settings = get_settings()
    conninfo = sqlalchemy_url_to_psycopg_conninfo(settings.database_url)
    _checkpointer_context = PostgresSaver.from_conn_string(conninfo)
    checkpointer = _checkpointer_context.__enter__()
    if settings.langgraph_auto_setup_checkpointer:
        checkpointer.setup()
    return checkpointer


def _append_phase(state: MediaOpsState, phase: str) -> list[str]:
    return [*state.get("completed_phases", []), phase]


def batch_started(state: MediaOpsState) -> dict[str, Any]:
    return {
        "phase": "batch_started",
        "completed_phases": _append_phase(state, "batch_started"),
    }


def media_processed(state: MediaOpsState) -> dict[str, Any]:
    return {
        "phase": "media_processed",
        "pending_review_count": int(state.get("needs_review_count", 0)),
        "completed_phases": _append_phase(state, "media_processed"),
    }


def review_required(state: MediaOpsState) -> dict[str, Any]:
    pending_review_count = int(state.get("pending_review_count", 0))
    resume_value = interrupt(
        {
            "type": "review_required",
            "job_id": state["job_id"],
            "event_id": state["event_id"],
            "phase": "review_required",
            "pending_review_count": pending_review_count,
        }
    )
    reviewed = bool(resume_value.get("reviewed", True))
    return {
        "reviewed": reviewed,
        "phase": "review_completed",
        "pending_review_count": 0 if reviewed else pending_review_count,
        "completed_phases": _append_phase(state, "review_completed"),
    }


def export_ready(state: MediaOpsState) -> dict[str, Any]:
    return {
        "phase": "export_ready",
        "completed_phases": _append_phase(state, "export_ready"),
    }


def finalize_batch(state: MediaOpsState) -> dict[str, Any]:
    return {
        "phase": "finalized",
        "completed_phases": _append_phase(state, "finalized"),
    }


def failed(state: MediaOpsState) -> dict[str, Any]:
    return {
        "failed": True,
        "phase": "failed",
        "completed_phases": _append_phase(state, "failed"),
    }


def route_after_media_processed(state: MediaOpsState) -> str:
    if state.get("failed"):
        return "failed"
    if int(state.get("pending_review_count", state.get("needs_review_count", 0))) > 0:
        return "review_required"
    return "export_ready"


def build_mediaops_graph(checkpointer=None):
    graph = StateGraph(MediaOpsState)

    graph.add_node("batch_started", batch_started)
    graph.add_node("media_processed", media_processed)
    graph.add_node("review_required", review_required)
    graph.add_node("export_ready", export_ready)
    graph.add_node("finalize_batch", finalize_batch)
    graph.add_node("failed", failed)

    graph.set_entry_point("batch_started")
    graph.add_edge("batch_started", "media_processed")
    graph.add_conditional_edges(
        "media_processed",
        route_after_media_processed,
        {
            "review_required": "review_required",
            "export_ready": "export_ready",
            "failed": "failed",
        },
    )
    graph.add_edge("review_required", "export_ready")
    graph.add_edge("export_ready", "finalize_batch")
    graph.add_edge("finalize_batch", END)
    graph.add_edge("failed", END)

    return graph.compile(checkpointer=checkpointer or build_postgres_checkpointer())


def get_mediaops_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_mediaops_graph()
    return _compiled_graph


def run_mediaops_batch(
    *,
    thread_id: str,
    job_id: str,
    event_id: str,
    needs_review_count: int,
):
    if not thread_id:
        raise ValueError("LangGraph thread id is required.")
    if not job_id:
        raise ValueError("Batch job id is required.")
    if not event_id:
        raise ValueError("Event id is required.")

    graph = get_mediaops_graph()
    result = graph.invoke(
        {
            "job_id": job_id,
            "event_id": event_id,
            "needs_review_count": needs_review_count,
            "pending_review_count": needs_review_count,
            "reviewed": False,
            "phase": "batch_started",
            "completed_phases": [],
            "failed": False,
            "error_message": None,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return graph_result_from_invoke(thread_id=thread_id, result=result)


def resume_reviewed_batch(thread_id: str, job_id: str) -> MediaOpsGraphResult:
    if not thread_id:
        raise ValueError("LangGraph thread id is required.")
    if not job_id:
        raise ValueError("Batch job id is required.")

    graph = get_mediaops_graph()
    result = graph.invoke(
        Command(resume={"reviewed": True, "job_id": job_id}),
        config={"configurable": {"thread_id": thread_id}},
    )
    return graph_result_from_invoke(thread_id=thread_id, result=result)


def graph_result_from_invoke(
    *,
    thread_id: str,
    result: dict[str, Any],
) -> MediaOpsGraphResult:
    interrupt_items = result.get("__interrupt__")
    if interrupt_items:
        payload = interrupt_items[0].value
        return MediaOpsGraphResult(
            status="interrupted_for_review",
            thread_id=thread_id,
            job_id=str(payload["job_id"]),
            event_id=str(payload["event_id"]),
            pending_review_count=int(payload["pending_review_count"]),
        )

    pending_review_count = int(result.get("pending_review_count", 0))
    return MediaOpsGraphResult(
        status="finalized",
        thread_id=thread_id,
        job_id=str(result["job_id"]),
        event_id=str(result["event_id"]),
        pending_review_count=pending_review_count,
    )
