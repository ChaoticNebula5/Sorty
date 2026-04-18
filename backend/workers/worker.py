"""
RQ worker entrypoint for Sorty.
Starts workers for enrichment, clustering, and export queues.
"""

from rq import Connection, Worker

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

    with Connection(redis_connection):
        worker = Worker([queue.name for queue in queues])
        worker.work()


if __name__ == "__main__":
    main()
