import time
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from redis import asyncio as aioredis
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

# In-memory fallback rate limit store
rate_limit_store: Dict[str, list] = {}

async def verify_admin_api_key(request: Request):
    """
    Enforces API key authentication across all sensitive and administrative endpoints.
    """
    auth_header = request.headers.get("Authorization") or request.headers.get("X-API-Key")
    expected_key = getattr(settings, "ADMIN_API_KEY", None) or settings.SECRET_KEY

    # In development mode, if no header is provided and non-default key isn't set, allow request
    if not auth_header:
        if settings.APP_ENV == "development" and settings.SECRET_KEY.startswith("dev_"):
            return True
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API authentication key")

    token = auth_header.replace("Bearer ", "").strip()
    if token != expected_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    return True

async def check_rate_limit(request: Request, max_requests: int = 60, window_seconds: int = 60):
    """
    Redis-backed rate limiter with in-memory fallback.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Try Redis rate limit first
    try:
        redis = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        key = f"rate_limit:{client_ip}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        await redis.close()

        if current > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: Maximum {max_requests} requests per {window_seconds}s"
            )
        return True
    except HTTPException:
        raise
    except Exception:
        pass

    # In-memory fallback
    now = time.time()
    requests = rate_limit_store.get(client_ip, [])
    requests = [ts for ts in requests if now - ts < window_seconds]

    if len(requests) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: Maximum {max_requests} requests per {window_seconds}s"
        )

    requests.append(now)
    rate_limit_store[client_ip] = requests
    return True
