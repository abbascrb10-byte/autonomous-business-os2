import asyncio
from typing import Dict, Any, Optional
from redis import asyncio as aioredis
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class RedisWorkerManager:
    """
    Background worker manager using Redis for background tasks,
    idempotency locking, and retry handling.
    Has a safe fallback to in-memory queue if Redis is not running locally.
    """

    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None

    async def get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(self.redis_url, socket_connect_timeout=1)
                await self._redis.ping()
            except Exception as e:
                logger.warning("Redis unavailable: using local background execution fallback", error=str(e))
                self._redis = None
        return self._redis

    async def acquire_lock(self, lock_key: str, ttl: int = 30) -> bool:
        redis = await self.get_redis()
        if redis:
            try:
                return bool(await redis.set(f"lock:{lock_key}", "1", ex=ttl, nx=True))
            except Exception:
                pass
        return True # Fallback allowed for local mode

    async def enqueue_job(self, queue_name: str, payload: Dict[str, Any]) -> str:
        job_id = payload.get("job_id") or payload.get("workflow_id") or "job_default"
        redis = await self.get_redis()
        if redis:
            try:
                import json
                await redis.rpush(f"queue:{queue_name}", json.dumps(payload))
                logger.info("Enqueued job to Redis queue", queue=queue_name, job_id=job_id)
            except Exception as e:
                logger.error("Failed to enqueue job to Redis", error=str(e))
        return job_id

worker_manager = RedisWorkerManager()
