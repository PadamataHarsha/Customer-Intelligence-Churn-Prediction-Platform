"""Centralized domain exceptions and handlers."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.exceptions")


class AppException(Exception):
    """Base exception for application domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND") -> None:
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT") -> None:
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)


class UnauthorizedException(AppException):
    def __init__(
        self, message: str = "Authentication required", code: str = "UNAUTHORIZED"
    ) -> None:
        super().__init__(code=code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Insufficient permissions", code: str = "FORBIDDEN") -> None:
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)


class ModelNotAvailableException(AppException):
    def __init__(
        self,
        message: str = "Active model not available for prediction",
        code: str = "MODEL_NOT_AVAILABLE",
    ) -> None:
        super().__init__(
            code=code, message=message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


def make_error_payload(code: str, message: str, request_id: str) -> dict[str, Any]:
    """Generates the contract error envelope."""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": request_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Registers exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content=make_error_payload(exc.code, exc.message, req_id),
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException | HTTPException
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "unknown")
        code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = "FORBIDDEN"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"

        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=make_error_payload(code, detail_msg, req_id),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "unknown")
        errors = exc.errors()
        msg = errors[0]["msg"] if errors else "Validation error"
        loc = ".".join(str(p) for p in errors[0]["loc"]) if errors else ""
        full_msg = f"{loc}: {msg}" if loc else msg
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=make_error_payload("VALIDATION_ERROR", full_msg, req_id),
        )

    try:
        from slowapi.errors import RateLimitExceeded

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
            req_id = getattr(request.state, "request_id", "unknown")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=make_error_payload(
                    "RATE_LIMIT_EXCEEDED", f"Rate limit exceeded: {exc.detail}", req_id
                ),
            )
    except ImportError:
        pass

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled server error",
            exc_info=exc,
            extra={"request_id": req_id, "path": str(request.url)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=make_error_payload(
                "INTERNAL_SERVER_ERROR", "An unexpected internal server error occurred", req_id
            ),
        )
