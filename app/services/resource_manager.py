import os
import time
from app.queue.queue_manager import queue_depths
from app.queue.redis_client import redis_client

try:
    import psutil
except ImportError:  # optional until installed
    psutil = None


def worker_snapshot():
    workers = []
    for key in redis_client.keys("worker:*"):
        raw = redis_client.hgetall(key)
        if not raw:
            continue
        workers.append(raw)
    return workers


def resource_snapshot():
    workers = worker_snapshot()
    online = sum(1 for w in workers if w.get("status") in {"ONLINE", "BUSY"})
    busy = sum(1 for w in workers if w.get("status") == "BUSY")
    queues = queue_depths()
    waiting = queues["high"] + queues["medium"] + queues["low"]

    if psutil:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
    else:
        cpu = None
        memory_percent = None

    # v3 control-plane recommendation. It is deliberately advisory: process
    # spawning is environment-specific and is not hidden inside the API.
    desired = max(1, min(32, busy + waiting))
    if online == 0:
        desired = max(1, desired)

    return {
        "host": os.getenv("HOSTNAME", "local"),
        "cpu_percent": cpu,
        "memory_percent": memory_percent,
        "workers_online": online,
        "workers_busy": busy,
        "queue_waiting": waiting,
        "recommended_workers": desired,
        "timestamp": int(time.time()),
    }
