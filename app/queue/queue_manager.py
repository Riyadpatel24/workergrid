from app.queue.redis_client import redis_client


HIGH_QUEUE = "high_priority_queue"
MEDIUM_QUEUE = "medium_priority_queue"
LOW_QUEUE = "low_priority_queue"


def enqueue_task(task_id: int, priority: str):

    priority = priority.upper()

    if priority == "HIGH":

        queue = HIGH_QUEUE

    elif priority == "MEDIUM":

        queue = MEDIUM_QUEUE

    elif priority == "LOW":

        queue = LOW_QUEUE

    else:

        raise ValueError(
            f"Invalid priority: {priority}"
        )

    redis_client.rpush(
        queue,
        task_id
    )

    print(
        f"[QueueManager] Task {task_id} "
        f"added to {queue}"
    )