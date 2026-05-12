from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exceptions import register_exception_handlers
from app.api.v1 import (
    appointments,
    auth,
    conversations,
    direct_messages,
    inbox,
    meetings,
    portal_me,
    tenants,
    users,
)
from app.infrastructure.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    api_v1_prefix = "/v1"
    app.include_router(auth.router, prefix=api_v1_prefix)
    app.include_router(tenants.router, prefix=api_v1_prefix)
    app.include_router(users.router, prefix=api_v1_prefix)
    app.include_router(meetings.router, prefix=api_v1_prefix)
    app.include_router(conversations.router, prefix=api_v1_prefix)
    app.include_router(appointments.router, prefix=api_v1_prefix)
    app.include_router(direct_messages.router, prefix=api_v1_prefix)
    app.include_router(portal_me.router, prefix=api_v1_prefix)
    app.include_router(inbox.router, prefix=api_v1_prefix)

    return app


app = create_app()
