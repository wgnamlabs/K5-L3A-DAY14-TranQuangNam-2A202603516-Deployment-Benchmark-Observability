"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis
from app.config import settings

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class LazyRedis:
    def __getattr__(self, name):
        return getattr(get_redis(), name)


r = LazyRedis()


def redis_healthy() -> bool:
    try:
        client = get_redis()
        return bool(client.ping())
    except Exception:
        return False
