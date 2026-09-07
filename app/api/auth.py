import hmac
import time
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

# Simple rate limiter memory store
rate_limit_store: Dict[str, list] = {}

async def verify_admin_api_key(request: Request):
    """
    Enforces API key authentication for sensitive operator/admin endpoints.
    """
    auth_header = request.headers.get("Authorization") or request.headers.get("X-API-Key")
    expected_key = settings.ADMIN_API_KEY

    if not auth_header:
        # In development mode without strict key configured, allow request
        if settings.APP_ENV == "development" and not expected_key:
            return True
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API authentication key")

    if not expected_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin API key is not configured")

    token = auth_header.replace("Bearer ", "").strip()
    if not hmac.compare_digest(token, expected_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    return True

async def check_rate_limit(request: Request, max_requests: int = 60, window_seconds: int = 60):
    """
    Simple IP-based rate limiter.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()

    requests = rate_limit_store.get(client_ip, [])
    # Remove timestamps older than window
    requests = [ts for ts in requests if now - ts < window_seconds]

    if len(requests) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: Maximum {max_requests} requests per {window_seconds}s"
        )

    requests.append(now)
    rate_limit_store[client_ip] = requests
