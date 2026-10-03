"""ASGI application factory for the FireSight backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from firesight_backend.api.router import api_router
from firesight_backend.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
