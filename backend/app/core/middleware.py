"""Application middleware: request IDs, structured logging, and security headers."""

import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generates request ID, measures duration, logs request, and injects security headers."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # 1. Request ID
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        # 2. Timing
        start_time = time.perf_counter()

        # 3. Call next middleware / route handler
        response: Response = await call_next(request)

        # 4. Duration
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 5. Response headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # 6. Structured logging
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} in {duration_ms}ms",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
