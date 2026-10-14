import logging
import time
import uuid

from fastapi import Request

logger = logging.getLogger("airq")


async def log_requests(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:64]
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        dur_ms = (time.perf_counter() - start) * 1000
        status = response.status_code if response is not None else 500
        logger.info("%s %s %s -> %s %.1fms", req_id, request.method, request.url.path, status, dur_ms)
        if response is not None:
            response.headers["X-Request-ID"] = req_id
