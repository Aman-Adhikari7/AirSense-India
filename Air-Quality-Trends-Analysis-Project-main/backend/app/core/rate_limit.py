"""Lightweight in-memory sliding window rate limiter.

Zero external dependencies (no Redis required).
Protects public read endpoints against denial-of-service and runaway client polling.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Request, Response
from fastapi.responses import JSONResponse

# IP -> list of request timestamps (epoch seconds)
_requests: Dict[str, List[float]] = defaultdict(list)
_last_cleanup = time.time()


def rate_limit_middleware(requests_per_minute: int = 120):
    async def middleware(request: Request, call_next):
        global _last_cleanup
        # Exempt health check endpoints
        if request.url.path in {"/healthz", "/simple", "/docs", "/openapi.json"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Forwarded-For header support for reverse proxies
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        now = time.time()
        window_start = now - 60.0

        # Periodic cleanup of old entries every 5 minutes
        if now - _last_cleanup > 300.0:
            for ip in list(_requests.keys()):
                _requests[ip] = [t for t in _requests[ip] if t > window_start]
                if not _requests[ip]:
                    _requests.pop(ip, None)
            _last_cleanup = now

        # Filter request timestamps in the current 60s window
        timestamps = [t for t in _requests[client_ip] if t > window_start]
        if len(timestamps) >= requests_per_minute:
            retry_after = int(60 - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down.", "retry_after_seconds": max(1, retry_after)},
                headers={"Retry-After": str(max(1, retry_after))},
            )

        timestamps.append(now)
        _requests[client_ip] = timestamps

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, requests_per_minute - len(timestamps)))
        return response

    return middleware
