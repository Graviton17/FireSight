import asyncio
import time

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.errors import register_exception_handlers
from app.data_layer.database_manager import DatabaseManager
from app.services.fire_capture_service import FireCaptureService
from app.static_memory_cache import StaticMemoryCache
from app.telemetries.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — runs at startup and shutdown."""
    from app.data_layer.supabase_credentials import resolve_supabase_url

    supabase_url = resolve_supabase_url("database")
    supabase_key, using_service_role = DatabaseManager.resolve_server_supabase_key()

    if not using_service_role:
        logger.warning(
            "No SUPABASE_SERVICE_ROLE_KEY found. "
            "Using anon key — PostgREST RLS may block backend writes."
        )

    await DatabaseManager.initialize(supabase_url=supabase_url, supabase_key=supabase_key)
    logger.info(
        "DatabaseManager initialised",
        mode=StaticMemoryCache.get_environment(),
        base_url=StaticMemoryCache.get_server_base_url(),
    )

    # In the background so an offline phone doesn't hold up startup for the
    # camera timeout. The result shows up in the log a moment later.
    camera_check = asyncio.create_task(FireCaptureService.check_camera())

    yield

    camera_check.cancel()

    try:
        await DatabaseManager.get_instance().shutdown()
    except RuntimeError:
        pass

    logger.info("App is shutting down")


app = FastAPI(
    title="FireSight Backend",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# Every error response uses {"error": {"code", "message"}}.
register_exception_handlers(app)

_cors_origins = StaticMemoryCache.get_config("server", "cors_origins") or ["*"]
if isinstance(_cors_origins, str):
    _cors_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check for monitoring and container probes."""
    if not DatabaseManager.is_initialised():
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "service": "firesight-backend",
                "database": "not_initialised",
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": time.time(),
            "service": "firesight-backend",
            "database": "connected",
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse(
        content={
            "message": "FireSight Backend is running",
            "status": "ok",
            "health_check": "/health",
        }
    )


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=StaticMemoryCache.get_server_port(),
        reload=StaticMemoryCache.get_auto_reload(),
    )
