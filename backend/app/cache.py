"""Redis-backed JSON cache. Fails open: if Redis is unreachable, callers compute fresh."""

import json
import logging
from typing import Any

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            _client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
            _client.ping()
        except redis.RedisError:
            logger.warning("Redis unavailable; caching disabled")
            _client = None
    return _client


def cache_get(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except (redis.RedisError, json.JSONDecodeError):
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl or get_settings().cache_ttl_seconds, json.dumps(value, default=str))
    except redis.RedisError:
        pass


def cache_invalidate(pattern: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        keys = list(client.scan_iter(pattern))
        if keys:
            client.delete(*keys)
    except redis.RedisError:
        pass
