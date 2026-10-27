"""Standard error envelope for every non-2xx response.

``{"error": {"code": "...", "message": "..."}}``
"""

from app.core.errors.handlers import (
    error_code_for_status,
    error_response,
    register_exception_handlers,
)

__all__ = [
    "error_code_for_status",
    "error_response",
    "register_exception_handlers",
]
