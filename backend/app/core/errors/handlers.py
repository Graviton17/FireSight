"""Global exception handlers that render the standard error envelope.

Routes keep raising ``HTTPException`` with the status codes they always used;
these handlers only change the body shape. A ``detail`` that is a dict with
``code`` / ``message`` keys overrides the default code for that status.

Unhandled exceptions become a generic 500 — the traceback goes to the logs,
never to the client.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Mapping, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.telemetries.logger import logger

_CODE_BY_STATUS: Dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}

_INTERNAL_ERROR_MESSAGE = "Something went wrong on our side. Please try again."


def error_code_for_status(status_code: int) -> str:
    """Machine-readable code for an HTTP status (``http_<status>`` if unmapped)."""
    return _CODE_BY_STATUS.get(status_code, f"http_{status_code}")


def error_response(
    status_code: int,
    message: str,
    *,
    code: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
    details: Optional[List[Dict[str, Any]]] = None,
) -> JSONResponse:
    """Build the standard error envelope."""
    body: Dict[str, Any] = {
        "code": code or error_code_for_status(status_code),
        "message": message,
    }
    if details is not None:
        body["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={"error": jsonable_encoder(body)},
        headers=dict(headers or {}),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail: Any = exc.detail
    code: Optional[str] = None
    if isinstance(detail, dict) and "message" in detail:
        code = detail.get("code")
        message = str(detail["message"])
    elif isinstance(detail, str) and detail:
        message = detail
    else:
        message = HTTPStatus(exc.status_code).phrase
    return error_response(exc.status_code, message, code=code, headers=getattr(exc, "headers", None))


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {
            "loc": list(err.get("loc", ())),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    if details:
        first = details[0]
        where = ".".join(str(p) for p in first["loc"])
        message = f"{where}: {first['message']}" if where else first["message"]
    else:
        message = "Invalid request"
    return error_response(422, message, details=details)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    return error_response(500, _INTERNAL_ERROR_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    """Install the handlers on *app*. Call once, right after creating it."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
