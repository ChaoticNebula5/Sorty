from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _normalize_error_detail(detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict):
        code = detail.get("code", "http_error")
        message = detail.get("message", "Request failed.")
        details = detail.get("details", {})

        return {
            "code": code if isinstance(code, str) else "http_error",
            "message": message if isinstance(message, str) else "Request failed.",
            "details": details if isinstance(details, dict) else {},
        }

    return {
        "code": "http_error",
        "message": str(detail),
        "details": {},
    }


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": _normalize_error_detail(exc.detail),
        },
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": {"errors": exc.errors()},
            },
        },
    )
