import os
import redis

_redis_url = os.getenv("REDIS_URL")

if _redis_url:
    # Cloud providers (Render, Railway, Upstash) supply a full REDIS_URL.
    # redis.Redis.from_url handles rediss:// (TLS) and redis:// equally.
    redis_client = redis.Redis.from_url(
        _redis_url,
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=5.0,
        retry_on_timeout=False,
    )
else:
    # Local development fallback using separate HOST / PORT vars.
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=5.0,
        retry_on_timeout=False,
    )
