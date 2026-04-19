"""
RQ worker entrypoint for Sorty.
Starts workers for enrichment, clustering, and export queues.
"""

import os
from rq import SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from backend.workers.queues import (
    get_clustering_queue,
    get_enrichment_queue,
    get_export_queue,
    get_redis_connection,
)


def main() -> None:
    """Run an RQ worker for all Sorty queues."""
    redis_connection = get_redis_connection()
    queues = [
        get_enrichment_queue(),
        get_clustering_queue(),
        get_export_queue(),
    ]

    if hasattr(os, "fork"):
        worker_cls = Worker
    else:
        class WindowsSimpleWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        worker_cls = WindowsSimpleWorker
    worker = worker_cls([queue.name for queue in queues], connection=redis_connection)
    worker.work()


if __name__ == "__main__":
    main()
