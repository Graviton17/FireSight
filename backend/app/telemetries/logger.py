import logging
import sys

import structlog

from app.static_memory_cache import StaticMemoryCache

_LOGGING_CONFIGURED = False


def setup_logger() -> None:
    """Configure structlog.

    - ``development``: colourful console output via rich.
    - ``production``: JSON lines, ready for log shipping.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    is_development = StaticMemoryCache.get_environment() == "development"

    level_name = StaticMemoryCache.get_config("logging", "log_level") or "INFO"
    log_level = getattr(logging, str(level_name).upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_development:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.rich_traceback,
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy loggers. The ESP32 posts every few seconds, so access logs
    # would drown everything else.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


# Bound logger used across the app
setup_logger()
logger = structlog.get_logger("firesight")
