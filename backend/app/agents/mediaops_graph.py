from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.core.config import get_settings


class MediaOpsState(TypedDict):
    job_id: str
    event_id: str
    needs_review_count: int
    reviewed: bool
    phase: str


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
    checkpointer.setup()
    return checkpointer


def analyze_batch(state: MediaOpsState) -> dict[str, str]:
    return {"phase": "analyzed"}


def review_checkpoint(state: MediaOpsState) -> dict[str, Any]:
    if state["needs_review_count"] > 0 and not state["reviewed"]:
        resume_value = interrupt(
            {
                "type": "review_required",
                "job_id": state["job_id"],
                "event_id": state["event_id"],
                "pending_review_count": state["needs_review_count"],
            }
        )
        return {
            "reviewed": bool(resume_value.get("reviewed", True)),
            "phase": "reviewed",
        }

    return {"phase": "review_not_required"}


def finalize_batch(state: MediaOpsState) -> dict[str, str]:
    return {"phase": "finalized"}


def build_mediaops_graph(checkpointer=None):
    graph = StateGraph(MediaOpsState)

    graph.add_node("analyze_batch", analyze_batch)
    graph.add_node("review_checkpoint", review_checkpoint)
    graph.add_node("finalize_batch", finalize_batch)

    graph.set_entry_point("analyze_batch")
    graph.add_edge("analyze_batch", "review_checkpoint")
    graph.add_edge("review_checkpoint", "finalize_batch")
    graph.add_edge("finalize_batch", END)

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
    return graph.invoke(
        {
            "job_id": job_id,
            "event_id": event_id,
            "needs_review_count": needs_review_count,
            "reviewed": False,
            "phase": "created",
        },
        config={"configurable": {"thread_id": thread_id}},
    )


def resume_reviewed_batch(thread_id: str, job_id: str) -> None:
    if not thread_id:
        raise ValueError("LangGraph thread id is required.")
    if not job_id:
        raise ValueError("Batch job id is required.")

    graph = get_mediaops_graph()
    graph.invoke(
        Command(resume={"reviewed": True, "job_id": job_id}),
        config={"configurable": {"thread_id": thread_id}},
    )
