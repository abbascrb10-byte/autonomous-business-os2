import asyncio
import json
from typing import Dict, Any, Optional, Callable
from redis import asyncio as aioredis
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

class RedisWorkerManager:
    """
    Background worker manager using Redis for background tasks,
    idempotency locking, retry handling, and active background worker consumption.
    Has a safe fallback to in-memory queue if Redis is not running locally.
    """

    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None
        self._is_worker_running = False
        self._local_queues: Dict[str, list[Dict[str, Any]]] = {}

    async def redis_is_ready(self) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        try:
            await redis.ping()
            return True
        except Exception:
            return False

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
        if settings.APP_ENV == "production":
            raise RuntimeError("Redis is required for production job locking")
        return True

    async def enqueue_job(self, queue_name: str, payload: Dict[str, Any], max_retries: int = 3) -> str:
        job_id = payload.get("job_id") or payload.get("workflow_id") or "job_default"
        payload["job_id"] = job_id
        payload["retries"] = payload.get("retries", 0)
        payload["max_retries"] = max_retries

        redis = await self.get_redis()
        if not redis and settings.APP_ENV == "production":
            raise RuntimeError("Redis is required for production job processing")
        if redis:
            try:
                await redis.rpush(f"queue:{queue_name}", json.dumps(payload))
                logger.info("Enqueued job to Redis queue", queue=queue_name, job_id=job_id)
            except Exception as e:
                logger.error("Failed to enqueue job to Redis", error=str(e))
                self._local_queues.setdefault(queue_name, []).append(payload)
        else:
            self._local_queues.setdefault(queue_name, []).append(payload)
            logger.warning("Enqueued job to local fallback queue", queue=queue_name, job_id=job_id)
        return job_id

    async def process_job_payload(self, queue_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes background worker tasks (demand ingestion, intent processing, offer discovery, conversion tracking)
        with error handling and retry logic.
        """
        job_id = payload.get("job_id", "unknown")
        logger.info("Worker processing job", queue=queue_name, job_id=job_id)
        try:
            if queue_name == "demand_ingestion":
                from app.sources.adapters import owned_adapter
                res = owned_adapter.normalize_demand(payload)
                return {"status": "processed", "data": res}
            elif queue_name == "intent_processing":
                from app.services.intent_service import intent_service
                res = await intent_service.analyze_and_extract(payload.get("text", ""))
                return {"status": "processed", "data": res}
            elif queue_name == "offer_discovery":
                from app.merchants.adapters import ebay_adapter
                res = await ebay_adapter.discover_offers(payload)
                return {"status": "processed", "offers": res}
            elif queue_name == "conversion_processing":
                from app.services.tracking_service import tracking_service
                res = tracking_service.process_conversion(
                    payload.get("external_conversion_id", "EXT-1"),
                    payload.get("click_id", "CLK-1"),
                    payload.get("merchant_id", "M-1"),
                    payload.get("amount", 100.0)
                )
                return {"status": "processed", "conversion": res}
        except Exception as e:
            retries = payload.get("retries", 0) + 1
            max_retries = payload.get("max_retries", 3)
            logger.error("Error processing worker job", queue=queue_name, job_id=job_id, retry=retries, error=str(e))
            if retries < max_retries:
                payload["retries"] = retries
                await asyncio.sleep(min(2 ** retries, 30))
                redis = await self.get_redis()
                if redis:
                    await redis.rpush(f"queue:{queue_name}", json.dumps(payload))
                elif settings.APP_ENV != "production":
                    self._local_queues.setdefault(queue_name, []).append(payload)
            else:
                logger.error("Job exceeded max retries, sending to dead-letter queue", queue=queue_name, job_id=job_id)
                redis = await self.get_redis()
                if redis:
                    await redis.rpush(f"dlq:{queue_name}", json.dumps(payload))
                elif settings.APP_ENV != "production":
                    self._local_queues.setdefault(f"dlq:{queue_name}", []).append(payload)
            return {"status": "failed", "error": str(e)}

        return {"status": "completed", "payload": payload}

    async def run_worker_loop(self, queue_name: str, max_jobs: Optional[int] = None):
        """
        Active consumer loop popping and processing jobs from Redis.
        """
        redis = await self.get_redis()
        if not redis:
            if settings.APP_ENV == "production":
                raise RuntimeError("Redis is required for production worker startup")
            logger.info("Redis offline: consuming local fallback queue", queue=queue_name)
            self._is_worker_running = True
            jobs_processed = 0
            while self._is_worker_running:
                queue = self._local_queues.setdefault(queue_name, [])
                if queue:
                    payload = queue.pop(0)
                    await self.process_job_payload(queue_name, payload)
                    jobs_processed += 1
                    if max_jobs and jobs_processed >= max_jobs:
                        break
                elif max_jobs is not None:
                    break
                else:
                    await asyncio.sleep(0.5)
            return

        self._is_worker_running = True
        jobs_processed = 0

        while self._is_worker_running:
            try:
                res = await redis.blpop(f"queue:{queue_name}", timeout=1)
                if res:
                    _, raw_data = res
                    payload = json.loads(raw_data)
                    await self.process_job_payload(queue_name, payload)
                    jobs_processed += 1
                    if max_jobs and jobs_processed >= max_jobs:
                        break
                else:
                    if max_jobs is not None:
                        break
            except Exception as e:
                logger.error("Error in worker loop", queue=queue_name, error=str(e))
                await asyncio.sleep(0.5)

worker_manager = RedisWorkerManager()
