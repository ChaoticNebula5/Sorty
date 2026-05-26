import redis
from rq import Worker

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    connection = redis.from_url(settings.redis_url)
    worker = Worker([settings.rq_queue_name], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
