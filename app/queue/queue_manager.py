from app.queue.redis_client import redis_client

HIGH_QUEUE = "high_priority_queue"
MEDIUM_QUEUE = "medium_priority_queue"
LOW_QUEUE = "low_priority_queue"
QUEUE_NAMES = {
    "HIGH": HIGH_QUEUE,
    "MEDIUM": MEDIUM_QUEUE,
    "LOW": LOW_QUEUE,
}


def normalize_priority(priority: str) -> str:
    value = (priority or "MEDIUM").upper()
    if value not in QUEUE_NAMES:
        raise ValueError(f"Invalid priority: {priority}")
    return value


def enqueue_task(task_id: int, priority: str):
    priority = normalize_priority(priority)
    queue = QUEUE_NAMES[priority]
    try:
        redis_client.rpush(queue, task_id)
        print(f"[QueueManager] Task {task_id} added to {queue}")
    except Exception as e:
        print(f"[QueueManager] Warning: Could not enqueue task {task_id} to Redis: {e}")
    return queue


def queue_depths():
    try:
        return {
            "high": redis_client.llen(HIGH_QUEUE),
            "medium": redis_client.llen(MEDIUM_QUEUE),
            "low": redis_client.llen(LOW_QUEUE),
            "dead_letter": redis_client.llen("dead_letter_queue"),
        }
    except Exception:
        return {"high": 0, "medium": 0, "low": 0, "dead_letter": 0}

